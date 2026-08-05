"""
LinkedIn Content Automation Bot
==============================
Fetches AI/ML papers from arXiv + blog posts from RSS feeds,
summarizes them with free LLM APIs (with auto-failover),
and posts to LinkedIn on a schedule.

Setup:
    pip install arxiv feedparser requests apscheduler

    Set these env vars:
        LINKEDIN_ACCESS_TOKEN    # From LinkedIn OAuth
        LINKEDIN_AUTHOR_URN      # urn:li:person:XXXX
        GROQ_API_KEY             # Optional, from groq.com
        GEMINI_API_KEY           # Optional, from aistudio.google.com
        OPENROUTER_API_KEY       # Optional, from openrouter.ai

Usage:
    python linkedin_bot.py --fetch          # Fetch new content
    python linkedin_bot.py --post-now       # Post next queued item immediately
    python linkedin_bot.py --schedule       # Start scheduler (runs forever)
    python linkedin_bot.py --queue          # Show pending queue
    python linkedin_bot.py --approve <id>   # Approve a queued post
"""

from dotenv import load_dotenv
load_dotenv()  # Load .env file before anything else

import os
import sys
import json
import sqlite3
import argparse
import textwrap
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional, List, Dict, Callable
from pathlib import Path

import requests
import arxiv
import feedparser
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# ──────────────────────────────────────────────────────────────
# CONFIG — tweak these to match your interests
# ──────────────────────────────────────────────────────────────

SOURCES_CONFIG_PATH = Path(__file__).parent / "sources.json"

DEFAULT_SOURCES = {
    "arxiv_categories": [
        "cs.LG", "cs.CL", "cs.AI", "cs.CV", "cs.RO", "cs.HC", "cs.NE"
    ],
    "rss_feeds": [
        "https://huggingface.co/blog/feed.xml",
        "https://blog.google/technology/ai/rss/",
        "https://openai.com/news/rss.xml",
        "https://www.anthropic.com/rss.xml",
        "https://blog.paperspace.com/rss/",
        "https://lilianweng.github.io/index.xml",
        "https://simonwillison.net/atom/entries/",
        "https://www.quantamagazine.org/computer-science/feed/",
        "https://news.ycombinator.com/rss",
        "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=week"
    ]
}

def get_sources_config() -> dict:
    if SOURCES_CONFIG_PATH.exists():
        try:
            return json.loads(SOURCES_CONFIG_PATH.read_text(encoding="utf-8"))
        except:
            pass
    return DEFAULT_SOURCES

ARXIV_MAX_RESULTS = 10

POST_TIMES = ["09:00", "18:00"]  # Daily post slots (24h format)
TIMEZONE = "Asia/Kolkata"         # Change to your timezone

DB_PATH = Path("linkedin_bot.db")

# ──────────────────────────────────────────────────────────────
# DATA MODEL
# ──────────────────────────────────────────────────────────────

@dataclass
class ContentItem:
    id: str
    source: str           # 'arxiv' or 'blog'
    title: str
    url: str
    summary: str
    authors: str
    published: datetime
    raw_text: str

@dataclass
class QueuedPost:
    id: int
    content: str
    source_title: str
    source_url: str
    status: str           # 'pending', 'approved', 'posted', 'failed'
    scheduled_at: Optional[datetime]
    posted_at: Optional[datetime]
    linkedin_post_id: Optional[str]

# ──────────────────────────────────────────────────────────────
# DATABASE
# ──────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY,
            content TEXT NOT NULL,
            source_title TEXT,
            source_url TEXT,
            status TEXT DEFAULT 'pending',
            scheduled_at TIMESTAMP,
            posted_at TIMESTAMP,
            linkedin_post_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS posted_urls (
            url TEXT PRIMARY KEY,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def _next_available_id(cursor) -> int:
    """Find the smallest available ID (fills gaps: 1, 2, 3...)."""
    cursor.execute("SELECT id FROM queue ORDER BY id")
    used = {row[0] for row in cursor.fetchall()}
    n = 1
    while n in used:
        n += 1
    return n

def is_url_posted(url: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM posted_urls WHERE url = ?", (url,))
    result = c.fetchone() is not None
    conn.close()
    return result

def is_url_queued(url: str) -> bool:
    """Check if a URL is already in the queue (any status)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM queue WHERE source_url = ?", (url,))
    result = c.fetchone() is not None
    conn.close()
    return result

def mark_url_posted(url: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO posted_urls (url) VALUES (?)", (url,))
    conn.commit()
    conn.close()

def add_to_queue(content: str, source_title: str, source_url: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    new_id = _next_available_id(c)
    c.execute("""
        INSERT INTO queue (id, content, source_title, source_url, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (new_id, content, source_title, source_url))
    conn.commit()
    conn.close()
    return new_id

def get_queue(status: Optional[str] = None) -> List[QueuedPost]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM queue WHERE status = ? ORDER BY created_at", (status,))
    else:
        c.execute("SELECT * FROM queue ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [QueuedPost(
        id=r[0], content=r[1], source_title=r[2], source_url=r[3],
        status=r[4], scheduled_at=r[5], posted_at=r[6], linkedin_post_id=r[7]
    ) for r in rows]

def update_post_status(post_id: int, status: str, linkedin_id: Optional[str] = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status == 'posted':
        c.execute("""
            UPDATE queue SET status = ?, posted_at = CURRENT_TIMESTAMP, linkedin_post_id = ?
            WHERE id = ?
        """, (status, linkedin_id, post_id))
    else:
        c.execute("UPDATE queue SET status = ? WHERE id = ?", (status, post_id))
    conn.commit()
    conn.close()

def get_next_approved() -> Optional[QueuedPost]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT * FROM queue WHERE status = 'approved'
        ORDER BY scheduled_at NULLS LAST, created_at
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    if row:
        return QueuedPost(
            id=row[0], content=row[1], source_title=row[2], source_url=row[3],
            status=row[4], scheduled_at=row[5], posted_at=row[6], linkedin_post_id=row[7]
        )
    return None

def approve_post(post_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE queue SET status = 'approved' WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

def get_post_by_id(post_id: int) -> Optional[QueuedPost]:
    """Fetch a single queue item by ID. Returns None if not found."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM queue WHERE id = ?", (post_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return QueuedPost(
            id=row[0], content=row[1], source_title=row[2], source_url=row[3],
            status=row[4], scheduled_at=row[5], posted_at=row[6], linkedin_post_id=row[7]
        )
    return None

def edit_post(post_id: int, content: str) -> bool:
    """Update the content of a queued post. Returns True if a row was updated."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE queue SET content = ? WHERE id = ?", (content, post_id))
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def delete_post(post_id: int) -> bool:
    """Delete a queued post by ID. Returns True if a row was deleted."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM queue WHERE id = ?", (post_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

# ──────────────────────────────────────────────────────────────
# CONTENT FETCHERS
# ──────────────────────────────────────────────────────────────
import re

def clean_latex(text: str) -> str:
    """Convert common LaTeX math notation to clean Unicode for LinkedIn."""
    if not text:
        return text

    # Greek letters
    greek = {
        r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
        r'\epsilon': 'ε', r'\varepsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η',
        r'\theta': 'θ', r'\iota': 'ι', r'\kappa': 'κ', r'\lambda': 'λ',
        r'\mu': 'μ', r'\nu': 'ν', r'\xi': 'ξ', r'\pi': 'π',
        r'\rho': 'ρ', r'\sigma': 'σ', r'\tau': 'τ', r'\upsilon': 'υ',
        r'\phi': 'φ', r'\chi': 'χ', r'\psi': 'ψ', r'\omega': 'ω',
        r'\Gamma': 'Γ', r'\Delta': 'Δ', r'\Theta': 'Θ', r'\Lambda': 'Λ',
        r'\Sigma': 'Σ', r'\Phi': 'Φ', r'\Psi': 'Ψ', r'\Omega': 'Ω',
        r'\Pi': 'Π',
    }
    for latex, uni in greek.items():
        text = text.replace(latex, uni)

    # Superscripts: ^2 → ², ^3 → ³, ^n → ⁿ, etc.
    sup_map = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
               '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
               'n': 'ⁿ', 'i': 'ⁱ', '+': '⁺', '-': '⁻', 'T': 'ᵀ'}
    # Handle ^{...} first, then ^X for single char
    def _sup_replace(m):
        content = m.group(1)
        return ''.join(sup_map.get(c, c) for c in content)
    text = re.sub(r'\^{([^}]+)}', _sup_replace, text)
    text = re.sub(r'\^(\w)', lambda m: sup_map.get(m.group(1), m.group(1)), text)

    # Subscripts: _2 → ₂, _i → ᵢ, etc.
    sub_map = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
               '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
               'i': 'ᵢ', 'j': 'ⱼ', 'n': 'ₙ', 'k': 'ₖ', '+': '₊', '-': '₋'}
    def _sub_replace(m):
        content = m.group(1)
        return ''.join(sub_map.get(c, c) for c in content)
    text = re.sub(r'_{([^}]+)}', _sub_replace, text)
    text = re.sub(r'_(\w)', lambda m: sub_map.get(m.group(1), m.group(1)), text)

    # Common math commands — extract content from braces
    text = re.sub(r'\\(?:mathbf|mathbb|mathrm|mathcal|textbf|textit|text|operatorname){([^}]+)}', r'\1', text)
    text = re.sub(r'\\(?:sqrt){([^}]+)}', r'√\1', text)

    # Math symbols
    math_syms = {
        r'\times': '×', r'\cdot': '·', r'\leq': '≤', r'\geq': '≥',
        r'\neq': '≠', r'\approx': '≈', r'\infty': '∞', r'\sum': 'Σ',
        r'\prod': 'Π', r'\rightarrow': '→', r'\leftarrow': '←',
        r'\Rightarrow': '⇒', r'\in': '∈', r'\subset': '⊂',
        r'\forall': '∀', r'\exists': '∃', r'\nabla': '∇',
        r'\partial': '∂', r'\pm': '±', r'\ell': 'ℓ',
    }
    for latex, uni in math_syms.items():
        text = text.replace(latex, uni)

    # Strip $ delimiters and remaining backslash commands
    text = text.replace('$', '')
    text = re.sub(r'\\[a-zA-Z]+', '', text)  # remove any leftover \commands
    # Clean up extra whitespace
    text = re.sub(r'  +', ' ', text).strip()

    return text


def markdown_to_unicode_bold(text: str) -> str:
    """Convert **bold** markdown to Unicode bold sans-serif for LinkedIn."""
    if not text:
        return text

    def replace_bold(match):
        content = match.group(1)
        res = []
        for c in content:
            if 'a' <= c <= 'z':
                res.append(chr(ord(c) - ord('a') + 0x1D5EE))
            elif 'A' <= c <= 'Z':
                res.append(chr(ord(c) - ord('A') + 0x1D5D4))
            elif '0' <= c <= '9':
                res.append(chr(ord(c) - ord('0') + 0x1D7EC))
            else:
                res.append(c)
        return "".join(res)
        
    return re.sub(r'\*\*(.*?)\*\*', replace_bold, text)


def fetch_arxiv() -> List[ContentItem]:
    """Fetch latest papers from arXiv."""
    items = []
    config = get_sources_config()
    cats = config.get("arxiv_categories", [])
    if not cats:
        return []
    query = " OR ".join(f"cat:{cat}" for cat in cats)
    search = arxiv.Search(
        query=query,
        max_results=ARXIV_MAX_RESULTS,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    client = arxiv.Client()
    for result in client.results(search):
        if is_url_posted(result.entry_id) or is_url_queued(result.pdf_url):
            continue
        title = clean_latex(result.title)
        summary = clean_latex(result.summary)
        authors = ", ".join(a.name for a in result.authors)
        items.append(ContentItem(
            id=result.entry_id,
            source="arxiv",
            title=title,
            url=result.pdf_url,
            summary=summary,
            authors=authors,
            published=result.published,
            raw_text=f"[SOURCE: arXiv Paper]\n[TITLE]: {title}\n[AUTHORS]: {authors}\n[ABSTRACT]:\n{summary}",
        ))
    return items

def fetch_rss_feeds() -> List[ContentItem]:
    """Fetch latest posts from RSS feeds."""
    items = []
    config = get_sources_config()
    feeds = config.get("rss_feeds", [])
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:  # Top 3 per feed
                url = entry.get("link", "")
                if not url or is_url_posted(url) or is_url_queued(url):
                    continue
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                pub_dt = datetime(*published[:6], tzinfo=timezone.utc) if published else datetime.now(timezone.utc)
                items.append(ContentItem(
                    id=url,
                    source="blog",
                    title=entry.get("title", "Untitled"),
                    url=url,
                    summary=entry.get("summary", "")[:800],
                    authors=entry.get("author", "Unknown"),
                    published=pub_dt,
                    raw_text=f"[SOURCE: Blog Post]\n[TITLE]: {entry.get('title', '')}\n[AUTHOR]: {entry.get('author', 'Unknown')}\n[CONTENT]:\n{entry.get('summary', '')}",
                ))
        except Exception as e:
            print(f"⚠️  Failed to parse {feed_url}: {e}")
    return items

# ──────────────────────────────────────────────────────────────
# LLM SUMMARIZATION with AUTO-FAILOVER
# ──────────────────────────────────────────────────────────────

DEFAULT_SYSTEM_PROMPT = """You are a senior AI/ML engineer who reads research papers deeply and writes LinkedIn posts that actually teach people something. You understand the technical details and translate them for a professional audience.

Your task: Read the paper/blog provided and write a LinkedIn post that captures the REAL substance — the methodology, the key insight, the results, and why it matters.

━━━ CRITICAL FORMATTING RULES ━━━

LinkedIn is PLAIN TEXT. It does NOT render markdown. Follow these rules strictly:

NEVER use:
  - **asterisks for bold** or *italics* — they show up as literal * characters
  - # headers
  - [links](url) or any markdown syntax
  - Numbered lists like "1." at the start of lines (LinkedIn sometimes hides these)

INSTEAD use these Unicode characters for visual structure:
  - Arrow bullets: → or ▸ for key points
  - Dot bullets: • for sub-points or lists
  - Thin line separator: ━━━ to divide sections (use sparingly, 1-2 max)
  - ALL CAPS for section headers (e.g., THE METHOD, RESULTS, MY TAKE)
  - Line breaks (blank lines) between every paragraph for readability
  - Emojis as section markers: 📄 🔬 📊 🧠 💡 (use 3-5 total, one per section)

━━━ POST STRUCTURE ━━━

📄 HOOK (first 2 lines — visible before "see more"):
Start with a specific, surprising claim from the paper. NOT generic hype.
Bad: "Exciting new paper in AI!" 
Good: "A new distillation method just outperformed standard approaches by 5.73% on math reasoning — by letting the teacher 'take over' mid-trajectory."

🔬 THE PROBLEM (2-3 lines):
What limitation does this work address? Why should an engineer care?
Write this as a clear paragraph, not bullets.

🧠 WHAT THEY ACTUALLY DID (the core section):
Use arrow bullets (→) for each key point. This is where the real value is.
→ Explain the method in plain language
→ Name the specific technique, architecture, or approach
→ Mention what makes it different from prior work
→ Include training details, datasets, or setup if mentioned
→ Keep each bullet to 1-2 lines max

📊 KEY RESULTS:
Use dot bullets (•) for concrete numbers and outcomes.
• Always include benchmark numbers if available (e.g., "94.2% on MMLU, up from 89.1%")
• Mention if the method is practical for production use
• Note any limitations the authors acknowledged

💡 MY TAKE (2-3 lines):
A genuine engineering opinion — what excites you about this, what's still missing, or where this could lead. End with a thought-provoking question that invites real discussion.

Bad closer: "What do you think?"
Good closer: "Will relay-based distillation make standard on-policy methods obsolete, or is the added complexity not worth the 5% gain in practice?"

HASHTAGS (final line, 3-5 tags):
#AI #MachineLearning plus 2-3 specific ones like #LLM #Distillation #NLP

━━━ CONTENT RULES ━━━
- Keep under 2800 characters total
- Every paragraph should be 2-3 lines max, separated by blank lines
- Tone: knowledgeable engineer explaining to peers — not a marketer
- Be SPECIFIC. The reader should learn something real just from your post
- Mention the paper title and authors naturally
- Do NOT include raw URLs (LinkedIn suppresses reach for links in post text)
- Avoid filler: "In today's rapidly evolving landscape", "Let's dive in", "Here's why this matters"
- The post should be INFORMATIVE first. Someone reading it should understand what the paper did without needing to read the actual paper.
"""


CUSTOM_PROMPT_PATH = Path(__file__).parent / "custom_prompt.txt"


def get_system_prompt() -> str:
    """Return the active system prompt — from custom file if it exists, else the default."""
    if CUSTOM_PROMPT_PATH.exists():
        text = CUSTOM_PROMPT_PATH.read_text(encoding="utf-8").strip()
        if text:
            return text
    return DEFAULT_SYSTEM_PROMPT


def _call_groq(text: str) -> Optional[str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "user", "content": text[:12000]},  # Groq context limit
                ],
                "temperature": 0.7,
                "max_tokens": 1500,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"   Groq failed: {e}")
        return None

def _call_gemini(text: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": get_system_prompt() + "\n\n" + text}]}
                ],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1500},
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"   Gemini failed: {e}")
        return None

def _call_openrouter(text: str) -> Optional[str]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost",
                "X-Title": "LinkedInBot",
            },
            json={
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "messages": [
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "user", "content": text[:12000]},
                ],
                "temperature": 0.7,
                "max_tokens": 1500,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"   OpenRouter failed: {e}")
        return None

def summarize_with_failover(text: str) -> str:
    """Try multiple free LLM APIs in sequence until one works."""
    providers: List[tuple[str, Callable]] = [
        ("Gemini", _call_gemini),
        ("Groq", _call_groq),
        ("OpenRouter", _call_openrouter),
    ]
    for name, fn in providers:
        print(f"   Trying {name}...")
        result = fn(text)
        if result:
            print(f"   ✅ {name} succeeded")
            return markdown_to_unicode_bold(result)
        else:
            print(f"   ❌ {name} returned None (key missing or API error)")
    # Fallback: simple template
    print("   ⚠️  All LLMs failed — using template fallback")
    lines = text.split("\n")
    title = lines[0] if lines else "Interesting read"
    body = "\n".join(lines[1:])[:600]
    return f"📚 {title}\n\nKey takeaways:\n→ {body[:300]}...\n\nWorth a read if you're in AI/ML.\n\n#AI #MachineLearning #Tech"

# ──────────────────────────────────────────────────────────────
# LINKEDIN POSTING
# ──────────────────────────────────────────────────────────────

def _get_linkedin_version() -> str:
    """Returns the previous calendar month as YYYYMM — always a guaranteed-active LinkedIn API version."""
    now = datetime.now()
    month = now.month - 1 or 12
    year = now.year if now.month > 1 else now.year - 1
    return f"{year}{month:02d}"


def post_to_linkedin(text: str) -> Optional[str]:
    """Publish a text post to LinkedIn. Returns post ID or None."""
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    author = os.getenv("LINKEDIN_AUTHOR_URN")
    if not token or not author:
        print("❌ LINKEDIN_ACCESS_TOKEN or LINKEDIN_AUTHOR_URN not set")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": _get_linkedin_version(),
    }
    payload = {
        "author": author,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    try:
        resp = requests.post(
            "https://api.linkedin.com/rest/posts",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if resp.status_code == 201:
            post_id = resp.headers.get("x-restli-id")
            print(f"   ✅ Posted! ID: {post_id}")
            return post_id
        else:
            print(f"   ❌ LinkedIn error {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return None

# ──────────────────────────────────────────────────────────────
# WORKFLOW
# ──────────────────────────────────────────────────────────────

def fetch_and_queue():
    """Fetch new content, summarize, and add to queue."""
    print("🔍 Fetching arXiv papers...")
    arxiv_items = fetch_arxiv()
    print(f"   Found {len(arxiv_items)} new papers")

    print("🔍 Fetching blog feeds...")
    blog_items = fetch_rss_feeds()
    print(f"   Found {len(blog_items)} new blog posts")

    all_items = arxiv_items + blog_items
    if not all_items:
        print("✨ No new content found. Everything is already queued or posted.")
        return

    # Sort by published date, newest first
    all_items.sort(key=lambda x: x.published, reverse=True)

    for item in all_items[:5]:  # Process top 5
        print(f"\n📝 Summarizing: {item.title[:60]}...")
        post_text = summarize_with_failover(item.raw_text)
        post_id = add_to_queue(post_text, item.title, item.url)
        print(f"   ➕ Queued as ID {post_id}")

def publish_next():
    """Publish the next approved post."""
    post = get_next_approved()
    if not post:
        post = get_queue("pending")
        if post:
            post = post[0]
            approve_post(post.id)
        else:
            print("📭 Nothing to post. Run --fetch first.")
            return

    print(f"\n📤 Publishing: {post.source_title[:50]}...")
    post_id = post_to_linkedin(post.content)
    if post_id:
        update_post_status(post.id, "posted", post_id)
        mark_url_posted(post.source_url)
    else:
        update_post_status(post.id, "failed")

def show_queue():
    """Display the current queue."""
    posts = get_queue()
    if not posts:
        print("📭 Queue is empty.")
        return
    print(f"\n{'ID':<5} {'Status':<10} {'Source':<40}")
    print("-" * 70)
    for p in posts[:20]:
        title = (p.source_title or "Untitled")[:38]
        print(f"{p.id:<5} {p.status:<10} {title}")

# ──────────────────────────────────────────────────────────────
# SCHEDULER
# ──────────────────────────────────────────────────────────────

def start_scheduler():
    """Start background scheduler for daily posting."""
    scheduler = BackgroundScheduler(timezone=TIMEZONE)

    # Fetch new content every morning
    scheduler.add_job(fetch_and_queue, CronTrigger(hour=7, minute=0))

    # Post at scheduled times
    for t in POST_TIMES:
        hour, minute = map(int, t.split(":"))
        scheduler.add_job(publish_next, CronTrigger(hour=hour, minute=minute))
        print(f"   📅 Scheduled post at {t}")

    scheduler.start()
    print(f"\n🤖 Scheduler running. Fetch at 07:00. Posts at {', '.join(POST_TIMES)}.")
    print("   Press Ctrl+C to stop.\n")

    try:
        while True:
            import time
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("\n👋 Scheduler stopped.")

# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Content Automation Bot")
    parser.add_argument("--fetch", action="store_true", help="Fetch new content and queue it")
    parser.add_argument("--post-now", action="store_true", help="Post next approved item immediately")
    parser.add_argument("--schedule", action="store_true", help="Start daily scheduler")
    parser.add_argument("--queue", action="store_true", help="Show queue")
    parser.add_argument("--approve", type=int, metavar="ID", help="Approve a queued post by ID")
    args = parser.parse_args()

    init_db()

    if args.fetch:
        fetch_and_queue()
    elif args.post_now:
        publish_next()
    elif args.schedule:
        start_scheduler()
    elif args.queue:
        show_queue()
    elif args.approve:
        approve_post(args.approve)
        print(f"✅ Post {args.approve} approved.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
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

ARXIV_CATEGORIES = ["cs.LG", "cs.CL", "cs.AI", "cs.CV", "cs.RO"]
ARXIV_MAX_RESULTS = 10

RSS_FEEDS = [
    "https://huggingface.co/blog/feed.xml",
    "https://blog.google/technology/ai/rss/",
    "https://openai.com/news/rss.xml",
    "https://www.anthropic.com/rss.xml",
    "https://blog.paperspace.com/rss/",
]

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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    c.execute("""
        INSERT INTO queue (content, source_title, source_url, status)
        VALUES (?, ?, ?, 'pending')
    """, (content, source_title, source_url))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id

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

# ──────────────────────────────────────────────────────────────
# CONTENT FETCHERS
# ──────────────────────────────────────────────────────────────

def fetch_arxiv() -> List[ContentItem]:
    """Fetch latest papers from arXiv."""
    items = []
    query = " OR ".join(f"cat:{cat}" for cat in ARXIV_CATEGORIES)
    search = arxiv.Search(
        query=query,
        max_results=ARXIV_MAX_RESULTS,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    client = arxiv.Client()
    for result in client.results(search):
        if is_url_posted(result.entry_id) or is_url_queued(result.pdf_url):
            continue
        items.append(ContentItem(
            id=result.entry_id,
            source="arxiv",
            title=result.title,
            url=result.pdf_url,
            summary=result.summary,
            authors=", ".join(a.name for a in result.authors),
            published=result.published,
            raw_text=f"{result.title}\n\n{result.summary}",
        ))
    return items

def fetch_rss_feeds() -> List[ContentItem]:
    """Fetch latest posts from RSS feeds."""
    items = []
    for feed_url in RSS_FEEDS:
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
                    raw_text=f"{entry.get('title', '')}\n\n{entry.get('summary', '')}",
                ))
        except Exception as e:
            print(f"⚠️  Failed to parse {feed_url}: {e}")
    return items

# ──────────────────────────────────────────────────────────────
# LLM SUMMARIZATION with AUTO-FAILOVER
# ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a LinkedIn content creator for an AI/ML engineer.
Convert the following paper/blog into an engaging LinkedIn post.

Rules:
- Hook in the first 2 lines (visible before "see more")
- Use short paragraphs with line breaks
- Include 3-5 bullet points with key takeaways
- End with a question or call-to-action to drive engagement
- Add 3-5 relevant hashtags at the end
- Keep under 2800 characters
- Tone: professional but conversational, not corporate-speak
- Use emojis sparingly (1-3 max)
- Do NOT include the raw URL in the post text (LinkedIn suppresses reach)
- If it's a paper, mention it's a paper/survey. If blog, frame as "great read".
"""

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
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text[:12000]},  # Groq context limit
                ],
                "temperature": 0.7,
                "max_tokens": 800,
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
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + text}]}
                ],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800},
            },
            timeout=30,
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
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text[:12000]},
                ],
                "temperature": 0.7,
                "max_tokens": 800,
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
        ("Groq", _call_groq),
        ("Gemini", _call_gemini),
        ("OpenRouter", _call_openrouter),
    ]
    for name, fn in providers:
        print(f"   Trying {name}...")
        result = fn(text)
        if result:
            print(f"   ✅ {name} succeeded")
            return result
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

def post_to_linkedin(text: str) -> Optional[str]:
    """Publish a text post to LinkedIn. Returns post ID or None."""
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    author = os.getenv("LINKEDIN_AUTHOR_URN")
    if not token or not author:
        print("❌ LINKEDIN_ACCESS_TOKEN or LINKEDIN_AUTHOR_URN not set")
        return None

    linkedin_version = f"{datetime.now().year}{datetime.now().month:02d}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": linkedin_version,
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
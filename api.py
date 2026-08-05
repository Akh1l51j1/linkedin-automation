"""
FastAPI backend for the LinkedIn Content Automation Dashboard.
================================================================
Wraps the existing linkedin_bot.py — imports and reuses its functions
directly instead of duplicating any bot logic. Talks to the same
linkedin_bot.db SQLite file the CLI uses.

Run with:
    uvicorn api:app --reload --port 8000
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Reuse the existing bot's logic and database — do not duplicate it.
import linkedin_bot as bot

# ──────────────────────────────────────────────────────────────
# APP SETUP
# ──────────────────────────────────────────────────────────────

app = FastAPI(title="LinkedIn Automation Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://localhost:5174",  # Vite fallback (when 5173 is in use)
        "http://localhost:5175",  # Vite second fallback
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module-level scheduler instance, controlled via /api/schedule/*.
# Kept separate from bot.start_scheduler() (which blocks forever) so the
# API process stays responsive while jobs run in the background.
scheduler = BackgroundScheduler(timezone=bot.TIMEZONE)
scheduler_started = False


@app.on_event("startup")
def on_startup():
    # Safe to call multiple times — CREATE TABLE IF NOT EXISTS.
    bot.init_db()


# ──────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ──────────────────────────────────────────────────────────────

class QueueItem(BaseModel):
    id: int
    content: str
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    status: str
    scheduled_at: Optional[str] = None
    posted_at: Optional[str] = None
    linkedin_post_id: Optional[str] = None

    @classmethod
    def from_queued_post(cls, p: "bot.QueuedPost") -> "QueueItem":
        return cls(
            id=p.id,
            content=p.content,
            source_title=p.source_title,
            source_url=p.source_url,
            status=p.status,
            scheduled_at=p.scheduled_at,
            posted_at=p.posted_at,
            linkedin_post_id=p.linkedin_post_id,
        )


class EditPostRequest(BaseModel):
    content: str = Field(..., min_length=1)


class ManualPostRequest(BaseModel):
    content: str = Field(..., min_length=1)
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    status: str = Field(default="pending", pattern="^(pending|approved)$")


class ActionResult(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


class ScheduleToggleRequest(BaseModel):
    enable: bool


class StatsResponse(BaseModel):
    total_queued: int
    approved_ready: int
    posted_this_week: int
    failed: int
    pending: int
    approval_rate: float


# ──────────────────────────────────────────────────────────────
# QUEUE ENDPOINTS
# ──────────────────────────────────────────────────────────────

VALID_STATUSES = {"pending", "approved", "posted", "failed"}


@app.get("/api/queue", response_model=List[QueueItem])
def list_queue(status: Optional[str] = None):
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be one of {sorted(VALID_STATUSES)}.",
        )
    posts = bot.get_queue(status)
    return [QueueItem.from_queued_post(p) for p in posts]


@app.get("/api/queue/{post_id}", response_model=QueueItem)
def get_queue_item(post_id: int):
    post = bot.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")
    return QueueItem.from_queued_post(post)


@app.post("/api/queue/{post_id}/approve", response_model=ActionResult)
def approve_queue_item(post_id: int):
    post = bot.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")
    if post.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Post {post_id} is '{post.status}', not 'pending' — cannot approve.",
        )
    bot.approve_post(post_id)
    return ActionResult(success=True, message=f"Post {post_id} approved.")


@app.post("/api/queue/{post_id}/reject", response_model=ActionResult)
def reject_queue_item(post_id: int):
    post = bot.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")
    bot.delete_post(post_id)
    return ActionResult(success=True, message=f"Post {post_id} rejected and deleted.")


@app.post("/api/queue/{post_id}/edit", response_model=ActionResult)
def edit_queue_item(post_id: int, body: EditPostRequest):
    post = bot.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")
    if post.status == "posted":
        raise HTTPException(
            status_code=400,
            detail=f"Post {post_id} has already been posted — cannot edit.",
        )
    bot.edit_post(post_id, body.content)
    return ActionResult(success=True, message=f"Post {post_id} updated.")


@app.post("/api/queue/{post_id}/resummarize", response_model=ActionResult)
def resummarize_queue_item(post_id: int):
    """Re-run LLM summarization for an existing queued post."""
    post = bot.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")
    if post.status == "posted":
        raise HTTPException(
            status_code=400,
            detail=f"Post {post_id} has already been posted — cannot re-summarize.",
        )

    # Rebuild raw text from stored metadata
    source_title = post.source_title or "Untitled"
    source_url = post.source_url or ""

    # Try to re-fetch abstract from arXiv if it's an arXiv paper
    raw_text = None
    if "arxiv.org" in source_url:
        try:
            import arxiv as arxiv_lib
            # Extract arXiv ID from URL
            arxiv_id = source_url.split("/")[-1].replace(".pdf", "")
            search = arxiv_lib.Search(id_list=[arxiv_id])
            client = arxiv_lib.Client()
            for result in client.results(search):
                title = bot.clean_latex(result.title)
                summary = bot.clean_latex(result.summary)
                authors = ", ".join(a.name for a in result.authors)
                raw_text = f"[SOURCE: arXiv Paper]\n[TITLE]: {title}\n[AUTHORS]: {authors}\n[ABSTRACT]:\n{summary}"
                break
        except Exception as e:
            print(f"   Re-fetch from arXiv failed: {e}, using existing post content")

    # Fallback: feed the existing post content + title so the LLM has real
    # substance to rewrite, rather than just a bare title.
    if not raw_text:
        raw_text = (
            f"[SOURCE: Blog Post]\n"
            f"[TITLE]: {source_title}\n"
            f"[URL]: {source_url}\n"
            f"[EXISTING DRAFT — rewrite this completely in your own style]:\n{post.content}"
        )

    try:
        new_content = bot.summarize_with_failover(raw_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Re-summarization failed: {e}")

    bot.edit_post(post_id, new_content)
    updated = bot.get_post_by_id(post_id)
    return ActionResult(
        success=True,
        message=f"Post {post_id} re-summarized successfully.",
        data={"post": QueueItem.from_queued_post(updated).model_dump()},
    )



@app.post("/api/fetch", response_model=ActionResult)
def trigger_fetch():
    """Fetch new content from arXiv + RSS, summarize it, and queue it.
    Mirrors `python linkedin_bot.py --fetch`, but reports what got queued."""
    before_ids = {p.id for p in bot.get_queue()}
    try:
        bot.fetch_and_queue()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")

    after = bot.get_queue()
    new_items = [QueueItem.from_queued_post(p) for p in after if p.id not in before_ids]
    return ActionResult(
        success=True,
        message=f"Fetched and queued {len(new_items)} new item(s).",
        data={"new_items": [item.model_dump() for item in new_items]},
    )


@app.post("/api/post-now", response_model=ActionResult)
def trigger_post_now():
    """Publish the next approved (or oldest pending, auto-approved) post.
    Mirrors `python linkedin_bot.py --post-now`."""
    pending_before = bot.get_queue("approved") or bot.get_queue("pending")
    if not pending_before:
        raise HTTPException(status_code=400, detail="Nothing to post — queue is empty.")

    target_id = pending_before[0].id
    bot.publish_next()

    updated = bot.get_post_by_id(target_id)
    if updated and updated.status == "posted":
        return ActionResult(
            success=True,
            message=f"Post {updated.id} published to LinkedIn.",
            data={"post": QueueItem.from_queued_post(updated).model_dump()},
        )
    elif updated and updated.status == "failed":
        raise HTTPException(
            status_code=502,
            detail=f"Post {updated.id} failed to publish — check LinkedIn credentials/logs.",
        )
    return ActionResult(success=True, message="Publish attempted — check queue for result.")


@app.post("/api/post/{post_id}", response_model=ActionResult)
def force_post_specific(post_id: int):
    """Force-publish a specific queue item to LinkedIn, regardless of status."""
    post = bot.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found.")
    if post.status == "posted":
        raise HTTPException(status_code=400, detail=f"Post {post_id} was already posted.")

    linkedin_id = bot.post_to_linkedin(post.content)
    if linkedin_id:
        bot.update_post_status(post.id, "posted", linkedin_id)
        if post.source_url:
            bot.mark_url_posted(post.source_url)
        return ActionResult(success=True, message=f"Post {post_id} published.", data={"linkedin_post_id": linkedin_id})
    else:
        bot.update_post_status(post.id, "failed")
        raise HTTPException(status_code=502, detail=f"LinkedIn publish failed for post {post_id}. Check credentials.")


# ──────────────────────────────────────────────────────────────
# MANUAL POST ENDPOINT (bypasses LLM summarization entirely)
# ──────────────────────────────────────────────────────────────

@app.post("/api/manual-post", response_model=ActionResult)
def create_manual_post(body: ManualPostRequest):
    post_id = bot.add_to_queue(
        content=body.content,
        source_title=body.source_title or "Manual Post",
        source_url=body.source_url or "",
    )
    if body.status == "approved":
        bot.approve_post(post_id)

    post = bot.get_post_by_id(post_id)
    return ActionResult(
        success=True,
        message=f"Manual post added to queue as ID {post_id} ({body.status}).",
        data={"post": QueueItem.from_queued_post(post).model_dump()},
    )


# ──────────────────────────────────────────────────────────────
# SCHEDULER ENDPOINTS
# ──────────────────────────────────────────────────────────────

def _build_scheduler() -> BackgroundScheduler:
    s = BackgroundScheduler(timezone=bot.TIMEZONE)
    s.add_job(bot.fetch_and_queue, CronTrigger(hour=7, minute=0), id="fetch_job")
    for t in bot.POST_TIMES:
        hour, minute = map(int, t.split(":"))
        s.add_job(bot.publish_next, CronTrigger(hour=hour, minute=minute), id=f"post_job_{t}")
    return s


@app.post("/api/schedule/toggle", response_model=ActionResult)
def toggle_scheduler(body: ScheduleToggleRequest):
    global scheduler, scheduler_started
    if body.enable:
        if not scheduler_started:
            scheduler = _build_scheduler()
            scheduler.start()
            scheduler_started = True
        return ActionResult(success=True, message="Scheduler started.")
    else:
        if scheduler_started:
            scheduler.shutdown(wait=False)
            scheduler_started = False
        return ActionResult(success=True, message="Scheduler stopped.")


@app.get("/api/schedule/status")
def schedule_status():
    jobs = []
    if scheduler_started:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            })
    return {
        "running": scheduler_started,
        "timezone": bot.TIMEZONE,
        "post_times": bot.POST_TIMES,
        "jobs": jobs,
    }


# ──────────────────────────────────────────────────────────────
# STATS ENDPOINT
# ──────────────────────────────────────────────────────────────

@app.get("/api/stats", response_model=StatsResponse)
def get_stats():
    all_posts = bot.get_queue()
    total_queued = len(all_posts)
    approved_ready = sum(1 for p in all_posts if p.status == "approved")
    pending = sum(1 for p in all_posts if p.status == "pending")
    failed = sum(1 for p in all_posts if p.status == "failed")
    posted = [p for p in all_posts if p.status == "posted"]

    week_ago = datetime.now() - timedelta(days=7)
    posted_this_week = 0
    for p in posted:
        if not p.posted_at:
            continue
        try:
            posted_dt = datetime.fromisoformat(str(p.posted_at))
            if posted_dt >= week_ago:
                posted_this_week += 1
        except ValueError:
            continue

    decided = len(posted) + failed
    approval_rate = round((len(posted) / decided) * 100, 1) if decided else 0.0

    return StatsResponse(
        total_queued=total_queued,
        approved_ready=approved_ready,
        posted_this_week=posted_this_week,
        failed=failed,
        pending=pending,
        approval_rate=approval_rate,
    )


# ──────────────────────────────────────────────────────────────
# SETTINGS ENDPOINTS — .env key management
# ──────────────────────────────────────────────────────────────

ENV_PATH = Path(__file__).parent / ".env"

# Only these keys can be read/written from the dashboard.
ALLOWED_KEYS = {
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "LINKEDIN_ACCESS_TOKEN",
    "LINKEDIN_AUTHOR_URN",
}


def _mask(value: str) -> str:
    """Show first 4 and last 4 chars, mask the rest."""
    if len(value) <= 10:
        return "•" * len(value)
    return value[:4] + "•" * (len(value) - 8) + value[-4:]


def _read_env_file() -> dict:
    """Parse .env into a dict (preserving all keys, not just allowed ones).
    Supports basic unescaping of double-quoted strings with \\n."""
    data = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                # Handle quoted multiline strings safely
                if v.startswith('"') and v.endswith('"'):
                    v = v[1:-1].replace("\\n", "\n")
                data[k] = v
    return data


def _write_env_file(data: dict):
    """Write dict back to .env, one KEY=VALUE per line. Escapes newlines."""
    lines = []
    for k, v in data.items():
        if "\n" in v:
            # Escape newlines and wrap in quotes for python-dotenv compatibility
            v_escaped = v.replace("\n", "\\n")
            lines.append(f'{k}="{v_escaped}"')
        else:
            lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


class UpdateKeysRequest(BaseModel):
    keys: dict


@app.get("/api/settings/keys")
def get_keys():
    """Return current API keys from .env, masked for safety."""
    env_data = _read_env_file()
    masked = {}
    for key in ALLOWED_KEYS:
        value = env_data.get(key, "")
        masked[key] = {"masked": _mask(value) if value else "", "is_set": bool(value)}
    return masked


@app.put("/api/settings/keys", response_model=ActionResult)
def update_keys(body: UpdateKeysRequest):
    """Save API keys to .env and reload them into the running process."""
    env_data = _read_env_file()

    updated = []
    for key, value in body.keys.items():
        if key not in ALLOWED_KEYS:
            raise HTTPException(status_code=400, detail=f"Key '{key}' is not allowed.")
        if value is not None and value.strip():
            env_data[key] = value.strip()
            os.environ[key] = value.strip()  # Hot-reload into running process
            updated.append(key)

    _write_env_file(env_data)
    return ActionResult(success=True, message=f"Saved {len(updated)} key(s): {', '.join(updated)}")


class UpdatePromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


@app.get("/api/settings/prompt")
def get_prompt():
    """Return the active summarization prompt (custom file if it exists, else the built-in default)."""
    is_custom = bot.CUSTOM_PROMPT_PATH.exists()
    prompt = bot.get_system_prompt()
    return {"prompt": prompt, "is_custom": is_custom}


@app.put("/api/settings/prompt", response_model=ActionResult)
def update_prompt(body: UpdatePromptRequest):
    """Save a custom summarization prompt to custom_prompt.txt. Takes effect immediately."""
    bot.CUSTOM_PROMPT_PATH.write_text(body.prompt, encoding="utf-8")
    return ActionResult(success=True, message="Summarization prompt updated.")


@app.delete("/api/settings/prompt", response_model=ActionResult)
def reset_prompt():
    """Delete the custom prompt file and revert to the built-in default."""
    if bot.CUSTOM_PROMPT_PATH.exists():
        bot.CUSTOM_PROMPT_PATH.unlink()
    return ActionResult(success=True, message="Prompt reset to built-in default.")


class UpdateSourcesRequest(BaseModel):
    rss_feeds: List[str]
    arxiv_categories: List[str]


@app.get("/api/settings/sources")
def get_sources():
    """Return the current sources config."""
    return bot.get_sources_config()


@app.put("/api/settings/sources", response_model=ActionResult)
def update_sources(body: UpdateSourcesRequest):
    """Update the sources config."""
    config = bot.get_sources_config()
    feeds = [f.strip() for f in body.rss_feeds if f.strip()]
    cats = [c.strip() for c in body.arxiv_categories if c.strip()]
    config["rss_feeds"] = feeds
    config["arxiv_categories"] = cats
    bot.SOURCES_CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return ActionResult(success=True, message="Sources updated successfully.")

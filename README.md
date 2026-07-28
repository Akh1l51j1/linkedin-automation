# LinkedIn Content Automation Bot

An automated Python bot that curates, summarizes, and schedules AI/ML content for LinkedIn. 

It fetches the latest research papers from **arXiv** and posts from top **AI RSS feeds** (Google AI, OpenAI, Anthropic, HuggingFace, etc.), uses **free LLM APIs** to create engaging LinkedIn posts with key takeaways, and publishes them on a schedule.

## ✨ Features

- **Automated Content Discovery**: Pulls the latest papers (`cs.LG`, `cs.CL`, `cs.AI`, etc.) and top AI blog posts.
- **Smart Summarization**: Uses LLMs (Groq, Gemini, OpenRouter) to convert dense papers/articles into readable, engaging LinkedIn posts with hooks, bullet points, and hashtags.
- **Auto-Failover LLMs**: Automatically falls back to alternative free APIs if one fails or hits a rate limit.
- **Queue & Approval System**: Saves drafts to a local SQLite database (`linkedin_bot.db`) so you can review them before they go live.
- **Scheduled Posting**: Built-in `apscheduler` to automatically publish posts at optimal times (e.g., 09:00 and 18:00).

---

## 🚀 Setup & Installation

### 1. Requirements
Ensure you have Python 3.8+ installed. Install the required dependencies:
```bash
pip install arxiv feedparser requests apscheduler python-dotenv
```

### 2. Environment Variables
Create a `.env` file in the root directory and add your API keys and LinkedIn credentials:

```env
# LinkedIn OAuth
LINKEDIN_ACCESS_TOKEN=your_access_token
LINKEDIN_AUTHOR_URN=urn:li:person:XXXXXX

# LLM APIs (Free)
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key
```
*(You only need at least one LLM API key, but having all three ensures the failover works smoothly).*

---

## 🛠️ Usage

The bot operates via a simple Command Line Interface (CLI).

**Fetch new content & generate drafts:**
```bash
python linkedin_bot.py --fetch
```

**View your pending post queue:**
```bash
python linkedin_bot.py --queue
```

**Approve a specific post for publishing:**
```bash
python linkedin_bot.py --approve <id>
```

**Publish the next approved post immediately:**
```bash
python linkedin_bot.py --post-now
```

**Start the background scheduler (Runs forever):**
```bash
python linkedin_bot.py --schedule
```
*The scheduler automatically fetches new content every morning at 07:00 and publishes approved posts at 09:00 and 18:00.*

---

## 🧽 Utilities

If you ever need to clear the entire queue and start fresh, you can run the cleanup script:
```bash
python cleanup_dupes.py
```

## 📝 Customization

You can easily customize the bot by editing the `CONFIG` section at the top of `linkedin_bot.py`:
- `ARXIV_CATEGORIES`: Change the arXiv tags to match your niche.
- `RSS_FEEDS`: Add or remove blog RSS feeds.
- `POST_TIMES`: Adjust your preferred daily posting schedule.
- `SYSTEM_PROMPT`: Tweak the AI prompt to match your personal voice and tone!

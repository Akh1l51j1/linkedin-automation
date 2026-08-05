# LinkedIn Content Automation — Dashboard

React + Vite frontend for the `linkedin_bot.py` automation backend.

## Prerequisites

- Node.js 18+
- The FastAPI backend (`api.py`) running on `http://localhost:8000` — see the
  main project README for backend setup.

## Install

```bash
cd frontend
npm install
```

## Run (development)

```bash
npm run dev
```

Opens at `http://localhost:5173`. The backend CORS config already allows
this origin.

## Build for production

```bash
npm run build
npm run preview   # serve the built dist/ locally to sanity-check it
```

Output goes to `frontend/dist/` — a static bundle you can serve with any
static file host.

## Project structure

```
frontend/
├── src/
│   ├── main.jsx              # entry point, wraps App in Router + ToastProvider
│   ├── App.jsx                # layout shell + route definitions
│   ├── api.js                  # single fetch wrapper for every backend call
│   ├── index.css               # Tailwind + design tokens
│   ├── components/
│   │   ├── Sidebar.jsx
│   │   ├── TopBar.jsx
│   │   ├── StatsCard.jsx
│   │   ├── PipelineFlow.jsx    # dashboard's flow visualization
│   │   ├── MiniCalendar.jsx
│   │   ├── QueueFilter.jsx
│   │   ├── PostCard.jsx        # also exports <StatusBadge>
│   │   ├── LinkedInPreview.jsx
│   │   └── ManualPostEditor.jsx
│   ├── pages/
│   │   ├── Dashboard.jsx
│   │   ├── QueuePage.jsx
│   │   ├── ManualPostPage.jsx  # the priority feature
│   │   ├── SchedulerPage.jsx
│   │   └── SettingsPage.jsx
│   └── context/
│       └── ToastContext.jsx    # global toast notifications for API errors
```

## Backend URL

Hardcoded in `src/api.js` as `http://localhost:8000`. If you run the API on
a different host/port, change `BASE_URL` there.

## Known gaps — not yet wired to the backend

These are visible in the UI (Settings and Scheduler pages) with inline notes,
so nothing silently pretends to work:

- **Settings page**: API key inputs, RSS feed management, arXiv category
  selection, and the LLM prompt editor are all local-only UI. Persisting
  them needs new backend endpoints that read/write `linkedin_bot.py`'s
  config constants and `.env` — deliberately not built yet, since writing
  secrets or executable config from a browser needs careful design.
- **Settings → Danger zone**: "Clear queue" is fully wired (loops the real
  reject endpoint). "Reset database" and "Clear posted URLs history" are
  disabled — they need two new backend endpoints.
- **Scheduler page**: start/stop and next-run times are fully live. Editable
  time slots and timezone are read-only displays of `POST_TIMES` /
  `TIMEZONE` from `linkedin_bot.py` — editing them from the dashboard needs
  a config-write endpoint. The log viewer is a placeholder explaining that
  bot output currently goes to the terminal running `uvicorn`.

## Everything else

Every other feature in the original spec — queue management (approve, edit,
reject, bulk actions, search, filters), manual post creation and immediate
posting, fetch/post-now triggers, live stats, and the LinkedIn preview — is
fully wired to the real FastAPI backend and was tested against a live
`linkedin_bot.db`.

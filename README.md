# 💼 Job Application Tracker

A fast, local-first job application tracker built with **FastAPI + HTMX + Tailwind CSS + SQLite**. Paste a LinkedIn job link, and it automatically scrapes the listing details and saves everything for you — organized by date applied.

No accounts. No cloud. No subscriptions. Just a clean tool that runs on your machine.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)
![License](https://img.shields.io/badge/license-MIT-brightgreen)

---

## ✨ Features

### Core
- **LinkedIn Auto-Scrape** — Paste a LinkedIn job URL and the app extracts job title, company, location, description, seniority level, employment type, salary, and more
- **Date-Grouped View** — Applications are organized by date applied (newest first) so you can see your daily activity at a glance
- **Status Tracking** — Track each application through the pipeline: `Applied` → `Interviewing` → `Offer` / `Rejected` / `Withdrawn`
- **Inline Editing** — Edit job title, company, location, and notes without leaving the page
- **Re-Scrape** — Job listing updated? Hit the refresh button to re-scrape and update all fields
- **Duplicate Detection** — Warns you before saving if you've already tracked a URL
- **CSV Export** — Download all your applications as a CSV file for spreadsheets or external analysis

### Organization
- **⭐ Star/Bookmark** — Pin important applications with a star; starred cards get a golden border highlight
- **🔀 Sorting** — Sort by date applied, company A–Z, status priority, or starred-first
- **🔍 Search & Filter** — Full-text search by company or title, plus status dropdown filter
- **📅 Calendar View** — Monthly calendar showing application counts per day with click-to-expand day detail

### Analytics
- **📊 Analytics Dashboard** — Full page of Chart.js visualizations:
  - Status pipeline (doughnut chart)
  - Weekly application activity (bar chart)
  - Monthly trend (line chart)
  - Top companies applied to (horizontal bar)
  - Location breakdown (doughnut)
  - Seniority level distribution (polar area)
  - Summary stats: total apps, days active, apps/week rate

### UX Polish
- **⚠️ Stale Indicators** — Amber ⏳ badge at 14+ days, red 🚨 at 21+ days for applications still in "Applied" status with no update
- **⌨️ Keyboard Shortcuts**:
  - `/` — Focus search bar
  - `N` — Focus the LinkedIn URL input
  - `?` — Show shortcuts help toast
  - `Esc` — Unfocus current input
- **🔔 Toast Notifications** — Slide-in success/error toasts on create and delete actions
- **📱 Responsive** — Works on desktop and mobile viewports
- **♿ Accessible** — ARIA labels, keyboard navigation, WCAG 2.2 AA contrast ratios

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **uv** (recommended) or pip

### Setup

```bash
# Clone or navigate to the project
cd job-tracker

# Create a virtual environment
uv venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
uv pip install fastapi uvicorn aiosqlite httpx beautifulsoup4 jinja2 python-multipart \
  --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple \
  --allow-insecure-host pypi.ci.artifacts.walmart.com
```

### Run

```bash
python main.py
```

The app starts at **http://127.0.0.1:8899** — open it in your browser.

That's it. No Docker, no database server, no config files. SQLite creates `jobs.db` automatically on first run.

---

## 🗂️ Project Structure

```
job-tracker/
├── main.py              # App setup, helpers, page routes
├── routes.py            # CRUD, edit, rescrape, export routes
├── analytics.py         # Analytics data queries + route
├── database.py          # SQLite setup, migrations, connection helper
├── scraper.py           # LinkedIn job posting scraper
├── jobs.db              # SQLite database (auto-created, gitignored)
└── templates/
    ├── base.html        # Layout with nav, keyboard shortcuts, toasts
    ├── index.html       # Main dashboard page
    ├── calendar.html    # Calendar view page
    ├── analytics.html   # Analytics page with Chart.js
    └── partials/        # HTMX partial templates
        ├── app_card.html           # Reusable application card
        ├── app_list.html           # Grouped application list
        ├── app_list_with_warning.html
        ├── calendar_day_apps.html
        ├── calendar_grid.html
        ├── dashboard.html          # Stats cards
        ├── duplicate_warning.html
        ├── edit_form.html          # Inline edit form
        └── status_badge.html       # Status pill component
```

---

## 📖 Usage

### Adding an Application

1. Paste a LinkedIn job URL (e.g., `https://www.linkedin.com/jobs/view/1234567890/`)
2. Pick the date you applied
3. Optionally add a company name, title override, or notes
4. Click **Save** — the app scrapes LinkedIn and fills in the rest

### Managing Applications

- **Change status** — Use the dropdown on each card
- **Star** — Click the ☆ icon to bookmark important apps
- **Edit** — Click the pencil icon for inline editing
- **Re-scrape** — Click the refresh icon to pull fresh data from LinkedIn
- **Delete** — Click the trash icon (with confirmation)
- **Expand** — Click any card to see full job description and metadata

### Views

| View | URL | What it shows |
|------|-----|---------------|
| Dashboard | `/` | Stats, search/filter/sort, all applications |
| Calendar | `/calendar` | Monthly grid with daily app counts |
| Analytics | `/analytics` | Charts and trend analysis |
| CSV Export | `/export/csv` | Downloads all data as CSV |

---

## 🛠️ Tech Stack

| Layer | Tech | Why |
|-------|------|-----|
| Backend | FastAPI | Async, fast, auto-docs at `/docs` |
| Frontend | HTMX + Tailwind CSS (CDN) | No build step, no JS framework, instant interactivity |
| Database | SQLite (aiosqlite) | Zero config, single file, plenty fast for personal use |
| Scraping | httpx + BeautifulSoup4 | Async HTTP + HTML parsing |
| Charts | Chart.js (CDN) | Clean, responsive charts with zero build config |
| Templates | Jinja2 | Server-side rendering with partials |

---

## 📝 Notes

- **LinkedIn scraping is best-effort.** LinkedIn actively blocks scrapers, so some fields may not populate. You can always fill them in manually or re-scrape later.
- **The database is gitignored.** Your `jobs.db` file stays local and private. Export to CSV if you need a backup.
- **No authentication.** This is a personal local tool. Don't expose it to the public internet without adding auth.

---

## 📜 License

MIT

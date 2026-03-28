"""Job Application Tracker — FastAPI + HTMX + Tailwind + SQLite."""

import calendar as cal
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import get_db, init_db
from analytics import router as analytics_router
from routes import router as crud_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize DB on startup."""
    await init_db()
    yield


app = FastAPI(title="Job Tracker", lifespan=lifespan)
app.include_router(analytics_router)
app.include_router(crud_router)
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Helpers (shared with routes.py via lazy import)
# ---------------------------------------------------------------------------

def _render(request: Request, template: str, ctx: dict | None = None):
    """Shortcut to render a Jinja2 template."""
    return templates.TemplateResponse(request, template, context=ctx or {})


async def _grouped_applications(
    status_filter: str = "",
    search: str = "",
    sort: str = "date",
) -> list[tuple[str, list]]:
    """Fetch applications grouped by date_applied (newest first)."""
    db = await get_db()
    try:
        query = "SELECT * FROM applications WHERE 1=1"
        params: list = []
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        if search:
            query += " AND (company LIKE ? OR job_title LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like])

        sort_map = {
            "date": "date_applied DESC, created_at DESC",
            "company": "company ASC, date_applied DESC",
            "status": "CASE status "
                      "WHEN 'Interviewing' THEN 1 "
                      "WHEN 'Offer' THEN 2 "
                      "WHEN 'Applied' THEN 3 "
                      "WHEN 'Rejected' THEN 4 "
                      "WHEN 'Withdrawn' THEN 5 END, "
                      "date_applied DESC",
            "starred": "starred DESC, date_applied DESC",
        }
        order = sort_map.get(sort, sort_map["date"])
        query += f" ORDER BY {order}"

        rows = await db.execute(query, params)
        results = await rows.fetchall()

        grouped: dict[str, list] = defaultdict(list)
        for row in results:
            app = dict(row)
            try:
                applied = date.fromisoformat(app["date_applied"])
                app["days_since"] = (date.today() - applied).days
            except (ValueError, TypeError):
                app["days_since"] = 0
            grouped[row["date_applied"]].append(app)

        return list(grouped.items())
    finally:
        await db.close()


async def _check_duplicate_url(url: str) -> dict | None:
    """Return the existing application row if this URL is already tracked."""
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT * FROM applications WHERE linkedin_url = ? LIMIT 1", (url,)
        )
        result = await row.fetchone()
        return dict(result) if result else None
    finally:
        await db.close()


async def _calendar_data(year: int, month: int) -> dict:
    """Build calendar grid data for a given month."""
    first_day = date(year, month, 1)
    num_days = cal.monthrange(year, month)[1]
    last_day = date(year, month, num_days)

    db = await get_db()
    try:
        rows = await db.execute(
            "SELECT date_applied, COUNT(*) as cnt FROM applications "
            "WHERE date_applied >= ? AND date_applied <= ? "
            "GROUP BY date_applied",
            (first_day.isoformat(), last_day.isoformat()),
        )
        day_counts = {r["date_applied"]: r["cnt"] for r in await rows.fetchall()}
    finally:
        await db.close()

    start_weekday = first_day.weekday()
    weeks: list[list[dict | None]] = []
    current_week: list[dict | None] = [None] * start_weekday

    for day_num in range(1, num_days + 1):
        d = date(year, month, day_num)
        iso = d.isoformat()
        current_week.append({
            "day": day_num, "date": iso,
            "count": day_counts.get(iso, 0),
            "is_today": d == date.today(),
        })
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []

    if current_week:
        current_week.extend([None] * (7 - len(current_week)))
        weeks.append(current_week)

    prev_month = first_day - timedelta(days=1)
    next_month = last_day + timedelta(days=1)

    return {
        "year": year, "month": month,
        "month_name": cal.month_name[month],
        "weeks": weeks,
        "prev_year": prev_month.year, "prev_month": prev_month.month,
        "next_year": next_month.year, "next_month": next_month.month,
    }


async def _dashboard_stats() -> dict:
    """Compute dashboard statistics."""
    db = await get_db()
    try:
        row = await db.execute("SELECT COUNT(*) as total FROM applications")
        total = (await row.fetchone())["total"]

        rows = await db.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        )
        status_counts = {r["status"]: r["cnt"] for r in await rows.fetchall()}

        row = await db.execute(
            "SELECT COUNT(*) as cnt FROM applications "
            "WHERE date_applied >= date('now', '-7 days')"
        )
        this_week = (await row.fetchone())["cnt"]

        row = await db.execute(
            "SELECT COUNT(DISTINCT company) as cnt FROM applications"
        )
        companies = (await row.fetchone())["cnt"]

        return {
            "total": total, "this_week": this_week, "companies": companies,
            "applied": status_counts.get("Applied", 0),
            "interviewing": status_counts.get("Interviewing", 0),
            "offer": status_counts.get("Offer", 0),
            "rejected": status_counts.get("Rejected", 0),
            "withdrawn": status_counts.get("Withdrawn", 0),
            "response_rate": _calc_response_rate(total, status_counts),
            "weekly_activity": await _weekly_activity(db),
        }
    finally:
        await db.close()


def _calc_response_rate(total: int, status_counts: dict) -> int:
    if total == 0:
        return 0
    progressed = status_counts.get("Interviewing", 0) + status_counts.get("Offer", 0)
    return round(progressed / total * 100)


async def _weekly_activity(db) -> list[dict]:
    weeks = []
    today = date.today()
    for i in range(11, -1, -1):
        week_end = today - timedelta(weeks=i)
        week_start = week_end - timedelta(days=6)
        row = await db.execute(
            "SELECT COUNT(*) as cnt FROM applications "
            "WHERE date_applied >= ? AND date_applied <= ?",
            (week_start.isoformat(), week_end.isoformat()),
        )
        cnt = (await row.fetchone())["cnt"]
        weeks.append({"label": week_start.strftime("%b %d"), "count": cnt})
    return weeks


async def _get_date_for_app(app_id: int) -> str:
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT date_applied FROM applications WHERE id = ?", (app_id,)
        )
        result = await row.fetchone()
        return result["date_applied"] if result else ""
    finally:
        await db.close()


async def _apps_for_date(d: str) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute(
            "SELECT * FROM applications WHERE date_applied = ? "
            "ORDER BY created_at DESC", (d,)
        )
        return [dict(r) for r in await rows.fetchall()]
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    grouped = await _grouped_applications()
    stats = await _dashboard_stats()
    return _render(request, "index.html", {
        "grouped_apps": grouped, "stats": stats,
    })


@app.get("/applications/list", response_class=HTMLResponse)
async def list_applications(
    request: Request, status: str = "", search: str = "", sort: str = "date",
):
    grouped = await _grouped_applications(status, search, sort)
    return _render(request, "partials/app_list.html", {"grouped_apps": grouped})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    stats = await _dashboard_stats()
    return _render(request, "partials/dashboard.html", {"stats": stats})


@app.get("/check-duplicate", response_class=HTMLResponse)
async def check_duplicate(request: Request, url: str = Query("")):
    if not url:
        return HTMLResponse("")
    existing = await _check_duplicate_url(url)
    if existing:
        return _render(request, "partials/duplicate_warning.html", {
            "existing": existing,
        })
    return HTMLResponse("")


@app.get("/calendar", response_class=HTMLResponse)
async def calendar_view(
    request: Request, year: int = Query(0), month: int = Query(0),
):
    today = date.today()
    y = year or today.year
    m = month or today.month
    cal_data = await _calendar_data(y, m)
    stats = await _dashboard_stats()

    if request.headers.get("HX-Request") == "true":
        return _render(request, "partials/calendar_grid.html", {"cal": cal_data})
    return _render(request, "calendar.html", {"cal": cal_data, "stats": stats})


@app.get("/calendar/day", response_class=HTMLResponse)
async def calendar_day_apps(request: Request, d: str = Query("")):
    apps = await _apps_for_date(d)
    return _render(request, "partials/calendar_day_apps.html", {
        "apps": apps, "selected_date": d,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8899, reload=True)

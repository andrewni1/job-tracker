"""Analytics routes and data helpers."""

from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])
templates = Jinja2Templates(directory="templates")


def _render(request: Request, template: str, ctx: dict | None = None):
    return templates.TemplateResponse(request, template, context=ctx or {})


async def _analytics_data() -> dict:
    """Compute all analytics data in one DB connection."""
    db = await get_db()
    try:
        # Status breakdown (for pie/funnel)
        rows = await db.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        )
        status_data = {r["status"]: r["cnt"] for r in await rows.fetchall()}

        # Top companies
        rows = await db.execute(
            "SELECT company, COUNT(*) as cnt FROM applications "
            "GROUP BY company ORDER BY cnt DESC LIMIT 10"
        )
        top_companies = [{"name": r["company"], "count": r["cnt"]}
                         for r in await rows.fetchall()]

        # Applications per week (last 12 weeks)
        weekly = []
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
            weekly.append({
                "label": week_start.strftime("%b %d"),
                "count": cnt,
            })

        # Applications per month (last 6 months)
        monthly = []
        for i in range(5, -1, -1):
            m_start = date(today.year, today.month, 1) - timedelta(days=30 * i)
            m_start = m_start.replace(day=1)
            if m_start.month == 12:
                m_end = m_start.replace(year=m_start.year + 1, month=1, day=1)
            else:
                m_end = m_start.replace(month=m_start.month + 1, day=1)
            m_end -= timedelta(days=1)
            row = await db.execute(
                "SELECT COUNT(*) as cnt FROM applications "
                "WHERE date_applied >= ? AND date_applied <= ?",
                (m_start.isoformat(), m_end.isoformat()),
            )
            cnt = (await row.fetchone())["cnt"]
            monthly.append({
                "label": m_start.strftime("%b %Y"),
                "count": cnt,
            })

        # Location breakdown
        rows = await db.execute(
            "SELECT location, COUNT(*) as cnt FROM applications "
            "WHERE location != '' GROUP BY location ORDER BY cnt DESC LIMIT 8"
        )
        locations = [{"name": r["location"], "count": r["cnt"]}
                     for r in await rows.fetchall()]

        # Seniority breakdown
        rows = await db.execute(
            "SELECT seniority_level, COUNT(*) as cnt FROM applications "
            "WHERE seniority_level != '' GROUP BY seniority_level "
            "ORDER BY cnt DESC"
        )
        seniority = [{"name": r["seniority_level"], "count": r["cnt"]}
                     for r in await rows.fetchall()]

        # Total and averages
        row = await db.execute("SELECT COUNT(*) as cnt FROM applications")
        total = (await row.fetchone())["cnt"]

        row = await db.execute(
            "SELECT MIN(date_applied) as first_date FROM applications"
        )
        first = await row.fetchone()
        first_date = first["first_date"] if first else None
        days_active = (
            (today - date.fromisoformat(first_date)).days + 1
            if first_date else 1
        )
        apps_per_week = round(total / max(days_active / 7, 1), 1)

        return {
            "status_data": status_data,
            "top_companies": top_companies,
            "weekly": weekly,
            "monthly": monthly,
            "locations": locations,
            "seniority": seniority,
            "total": total,
            "days_active": days_active,
            "apps_per_week": apps_per_week,
        }
    finally:
        await db.close()


@router.get("", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Full analytics page."""
    data = await _analytics_data()
    return _render(request, "analytics.html", {"data": data})

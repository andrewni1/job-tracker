"""Application CRUD, edit, star, rescrape, and export routes."""

import csv
import io
from datetime import date

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from database import get_db
from scraper import scrape_linkedin_job

router = APIRouter(tags=["applications"])
templates = Jinja2Templates(directory="templates")


def _render(request: Request, template: str, ctx: dict | None = None):
    return templates.TemplateResponse(request, template, context=ctx or {})


# Import helpers from main — we'll pass them via app state instead
# to avoid circular imports. See main.py for wiring.


async def _get_helpers():
    """Lazy import helpers from main to avoid circular deps."""
    from main import (
        _grouped_applications,
        _check_duplicate_url,
        _get_date_for_app,
        _apps_for_date,
    )
    return (
        _grouped_applications,
        _check_duplicate_url,
        _get_date_for_app,
        _apps_for_date,
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("/applications", response_class=HTMLResponse)
async def create_application(
    request: Request,
    linkedin_url: str = Form(...),
    date_applied: date = Form(...),
    job_title: str = Form(""),
    company: str = Form(""),
    location: str = Form(""),
    notes: str = Form(""),
):
    """Scrape the LinkedIn URL (best-effort) and save a new application."""
    grouped_apps, check_dup, _, _ = await _get_helpers()

    existing = await check_dup(linkedin_url)
    if existing:
        grouped = await grouped_apps()
        return _render(request, "partials/app_list_with_warning.html", {
            "grouped_apps": grouped, "existing": existing,
        })

    scraped = await scrape_linkedin_job(linkedin_url)
    title = job_title or scraped.title
    comp = company or scraped.company
    loc = location or scraped.location

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO applications "
            "(linkedin_url, job_title, company, location, description, "
            "date_applied, notes, seniority_level, employment_type, "
            "job_function, industries, salary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (linkedin_url, title, comp, loc, scraped.description,
             date_applied.isoformat(), notes, scraped.seniority_level,
             scraped.employment_type, scraped.job_function,
             scraped.industries, scraped.salary),
        )
        await db.commit()
    finally:
        await db.close()

    grouped = await grouped_apps()
    return _render(request, "partials/app_list.html", {"grouped_apps": grouped})


@router.patch("/applications/{app_id}/status", response_class=HTMLResponse)
async def update_status(
    request: Request, app_id: int,
    status: str = Form(...), source: str = Query(""), d: str = Query(""),
):
    """Update an application's status."""
    grouped_apps, _, get_date, apps_for_date = await _get_helpers()
    app_date = d or await get_date(app_id)

    db = await get_db()
    try:
        await db.execute(
            "UPDATE applications SET status = ? WHERE id = ?", (status, app_id)
        )
        await db.commit()
    finally:
        await db.close()

    if source == "calendar":
        apps = await apps_for_date(app_date)
        return _render(request, "partials/calendar_day_apps.html", {
            "apps": apps, "selected_date": app_date,
        })
    grouped = await grouped_apps()
    return _render(request, "partials/app_list.html", {"grouped_apps": grouped})


@router.delete("/applications/{app_id}", response_class=HTMLResponse)
async def delete_application(
    request: Request, app_id: int,
    source: str = Query(""), d: str = Query(""),
):
    """Delete an application."""
    grouped_apps, _, get_date, apps_for_date = await _get_helpers()
    app_date = d or await get_date(app_id)

    db = await get_db()
    try:
        await db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        await db.commit()
    finally:
        await db.close()

    if source == "calendar":
        apps = await apps_for_date(app_date)
        return _render(request, "partials/calendar_day_apps.html", {
            "apps": apps, "selected_date": app_date,
        })
    grouped = await grouped_apps()
    return _render(request, "partials/app_list.html", {"grouped_apps": grouped})


@router.patch("/applications/{app_id}/star", response_class=HTMLResponse)
async def toggle_star(
    request: Request, app_id: int,
    source: str = Query(""), d: str = Query(""),
):
    """Toggle the starred flag on an application."""
    grouped_apps, _, get_date, apps_for_date = await _get_helpers()
    app_date = d or await get_date(app_id)

    db = await get_db()
    try:
        await db.execute(
            "UPDATE applications SET starred = CASE WHEN starred = 1 THEN 0 ELSE 1 END "
            "WHERE id = ?", (app_id,)
        )
        await db.commit()
    finally:
        await db.close()

    if source == "calendar":
        apps = await apps_for_date(app_date)
        return _render(request, "partials/calendar_day_apps.html", {
            "apps": apps, "selected_date": app_date,
        })
    grouped = await grouped_apps()
    return _render(request, "partials/app_list.html", {"grouped_apps": grouped})


# ---------------------------------------------------------------------------
# Edit & Rescrape
# ---------------------------------------------------------------------------

@router.get("/applications/{app_id}/edit", response_class=HTMLResponse)
async def edit_form(request: Request, app_id: int):
    """HTMX partial — inline edit form."""
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        )
        app = await row.fetchone()
    finally:
        await db.close()
    if not app:
        return HTMLResponse("Not found", status_code=404)
    return _render(request, "partials/edit_form.html", {"app": dict(app)})


@router.post("/applications/{app_id}/rescrape", response_class=HTMLResponse)
async def rescrape_application(request: Request, app_id: int):
    """Re-scrape a LinkedIn URL and update all scraped fields."""
    grouped_apps, _, _, _ = await _get_helpers()

    db = await get_db()
    try:
        row = await db.execute(
            "SELECT linkedin_url FROM applications WHERE id = ?", (app_id,)
        )
        app = await row.fetchone()
        if not app:
            return HTMLResponse("Not found", status_code=404)

        scraped = await scrape_linkedin_job(app["linkedin_url"])
        fields = [
            ("job_title", scraped.title),
            ("company", scraped.company),
            ("location", scraped.location),
            ("description", scraped.description),
            ("seniority_level", scraped.seniority_level),
            ("employment_type", scraped.employment_type),
            ("job_function", scraped.job_function),
            ("industries", scraped.industries),
            ("salary", scraped.salary),
        ]
        updates = {k: v for k, v in fields if v}

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            await db.execute(
                f"UPDATE applications SET {set_clause} WHERE id = ?",
                (*updates.values(), app_id),
            )
            await db.commit()
    finally:
        await db.close()

    grouped = await grouped_apps()
    return _render(request, "partials/app_list.html", {"grouped_apps": grouped})


@router.put("/applications/{app_id}", response_class=HTMLResponse)
async def update_application(
    request: Request, app_id: int,
    job_title: str = Form(...), company: str = Form(...),
    location: str = Form(""), notes: str = Form(""),
    source: str = Query(""), d: str = Query(""),
):
    """Update application details."""
    grouped_apps, _, get_date, apps_for_date = await _get_helpers()
    app_date = d or await get_date(app_id)

    db = await get_db()
    try:
        await db.execute(
            "UPDATE applications SET job_title=?, company=?, location=?, notes=? "
            "WHERE id = ?",
            (job_title, company, location, notes, app_id),
        )
        await db.commit()
    finally:
        await db.close()

    if source == "calendar":
        apps = await apps_for_date(app_date)
        return _render(request, "partials/calendar_day_apps.html", {
            "apps": apps, "selected_date": app_date,
        })
    grouped = await grouped_apps()
    return _render(request, "partials/app_list.html", {"grouped_apps": grouped})


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

_CSV_COLUMNS = [
    "Job Title", "Company", "Location", "Status", "Date Applied",
    "Seniority", "Employment Type", "Job Function", "Industries",
    "Salary", "LinkedIn URL", "Notes", "Created At",
]
_CSV_FIELDS = [
    "job_title", "company", "location", "status", "date_applied",
    "seniority_level", "employment_type", "job_function", "industries",
    "salary", "linkedin_url", "notes", "created_at",
]


@router.get("/export/csv")
async def export_csv():
    """Download all applications as a CSV."""
    db = await get_db()
    try:
        rows = await db.execute(
            f"SELECT {', '.join(_CSV_FIELDS)} FROM applications "
            "ORDER BY date_applied DESC"
        )
        results = await rows.fetchall()
    finally:
        await db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_CSV_COLUMNS)
    for r in results:
        writer.writerow([r[f] for f in _CSV_FIELDS])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=job_applications.csv"},
    )

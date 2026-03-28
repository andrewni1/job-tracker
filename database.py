"""SQLite database setup and helpers."""

import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    """Create tables if they don't exist, and migrate new columns."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                linkedin_url TEXT NOT NULL,
                job_title TEXT NOT NULL DEFAULT 'Unknown',
                company TEXT NOT NULL DEFAULT 'Unknown',
                location TEXT DEFAULT '',
                description TEXT DEFAULT '',
                date_applied DATE NOT NULL,
                status TEXT NOT NULL DEFAULT 'Applied',
                notes TEXT DEFAULT '',
                seniority_level TEXT DEFAULT '',
                employment_type TEXT DEFAULT '',
                job_function TEXT DEFAULT '',
                industries TEXT DEFAULT '',
                salary TEXT DEFAULT '',
                starred INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migrate existing tables: add columns if missing
        new_columns = [
            ("seniority_level", "TEXT DEFAULT ''"),
            ("employment_type", "TEXT DEFAULT ''"),
            ("job_function", "TEXT DEFAULT ''"),
            ("industries", "TEXT DEFAULT ''"),
            ("salary", "TEXT DEFAULT ''"),
            ("starred", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in new_columns:
            try:
                await db.execute(
                    f"ALTER TABLE applications ADD COLUMN {col_name} {col_type}"
                )
            except Exception:
                pass  # Column already exists

        await db.commit()

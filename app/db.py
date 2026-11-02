"""
app/db.py

Loads expenses.csv into an in-memory SQLite database on startup.
Exposes get_conn() which returns the singleton connection used by all tools.
"""

from __future__ import annotations

import csv
import math
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level singleton connection — set by init_db() at startup.
_conn: sqlite3.Connection | None = None


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS expenses (
            transaction_id TEXT PRIMARY KEY,
            date           TEXT NOT NULL,
            time           TEXT,
            amount_cents   INTEGER NOT NULL,
            description    TEXT,
            merchant       TEXT,
            category       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_expenses_date
            ON expenses(date);
        CREATE INDEX IF NOT EXISTS idx_expenses_category
            ON expenses(category);
    """)
    conn.commit()


def _dollars_to_cents(value: str) -> int:
    """Convert a dollar string like '12.50' to integer cents (1250)."""
    return math.floor(float(value) * 100 + 0.5)  # round half-up


def load_csv(path: str) -> sqlite3.Connection:
    """
    Parse *path* and load all rows into a fresh in-memory SQLite database.
    Returns the open connection.
    Raises FileNotFoundError / ValueError on bad input.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _create_schema(conn)

    rows: list[tuple] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):  # start=2: row 1 is header
            try:
                cents = _dollars_to_cents(row["Amount"])
            except (ValueError, KeyError) as exc:
                raise ValueError(
                    f"Bad Amount on CSV line {line_num}: {row.get('Amount')!r}"
                ) from exc
            rows.append((
                row["Transaction_ID"],
                row["Date"],
                row["Time"],
                cents,
                row["Description"],
                row["Merchant"],
                row["Category"],
            ))

    conn.executemany(
        "INSERT INTO expenses VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    logger.info("Loaded %d expense rows from %s", len(rows), path)
    return conn


def init_db(path: str = "data/expenses.csv") -> None:
    """
    Load the CSV and store the connection as the module singleton.
    Called once from the FastAPI lifespan.
    """
    global _conn
    _conn = load_csv(path)


def get_conn() -> sqlite3.Connection:
    """Return the singleton connection. Raises RuntimeError if init_db() was not called."""
    if _conn is None:
        raise RuntimeError("Database not initialised — call init_db() first.")
    return _conn

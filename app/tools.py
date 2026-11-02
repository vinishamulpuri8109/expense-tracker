"""
app/tools.py

The three query tools exposed to Gemini:
  - get_spending(category, start_date, end_date)
  - list_transactions(start_date, end_date, category=None, limit=20)
  - get_top_categories(start_date, end_date, n=3)

All functions return plain dicts or lists.
On invalid input they return {"error": "..."} instead of raising.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any, Optional

from app.db import get_conn

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES: frozenset[str] = frozenset({
    "Bills",
    "Entertainment",
    "Food & Beverage",
    "Groceries",
    "Healthcare",
    "Transportation",
})

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_date(value: str) -> tuple[str, str | None]:
    """
    Return (date_str, None) if *value* is a valid YYYY-MM-DD string,
    otherwise return (None, error_message).
    """
    try:
        parsed = _date.fromisoformat(value)
        return parsed.isoformat(), None
    except (ValueError, TypeError):
        return None, f"Invalid date {value!r} — expected YYYY-MM-DD."


def _validate_date_range(
    start: str, end: str
) -> tuple[str | None, str | None, str | None]:
    """
    Return (start, end, None) if both dates are valid and start <= end,
    otherwise (None, None, error_message).
    """
    start_parsed, err = _validate_date(start)
    if err:
        return None, None, err
    end_parsed, err = _validate_date(end)
    if err:
        return None, None, err
    if start_parsed > end_parsed:
        return None, None, (
            f"start_date {start_parsed!r} is after end_date {end_parsed!r}."
        )
    return start_parsed, end_parsed, None


def _validate_category(category: str) -> tuple[str | None, str | None]:
    """
    Return (category, None) if valid, otherwise (None, error_message).
    """
    if category not in VALID_CATEGORIES:
        return None, (
            f"Unknown category {category!r}. "
            f"Valid values: {sorted(VALID_CATEGORIES)}."
        )
    return category, None


# ---------------------------------------------------------------------------
# Tool: get_spending
# ---------------------------------------------------------------------------

def get_spending(
    category: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """
    Return the total spend in cents for *category* between *start_date* and
    *end_date* (both inclusive, YYYY-MM-DD).

    Returns:
        {"category": str, "start_date": str, "end_date": str, "total_cents": int}
        or {"error": str} on invalid input.
    """
    cat, err = _validate_category(category)
    if err:
        return {"error": err}

    start, end, err = _validate_date_range(start_date, end_date)
    if err:
        return {"error": err}

    row = get_conn().execute(
        """
        SELECT COALESCE(SUM(amount_cents), 0) AS total
        FROM expenses
        WHERE category = ?
          AND date BETWEEN ? AND ?
        """,
        (cat, start, end),
    ).fetchone()

    return {
        "category": cat,
        "start_date": start,
        "end_date": end,
        "total_cents": row["total"],
    }


# ---------------------------------------------------------------------------
# Tool: list_transactions
# ---------------------------------------------------------------------------

def list_transactions(
    start_date: str,
    end_date: str,
    category: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]] | dict[str, Any]:
    """
    Return up to *limit* transactions in [start_date, end_date], newest first.
    Optionally filtered by *category*.

    Returns:
        list of transaction dicts, or {"error": str} on invalid input.
    """
    start, end, err = _validate_date_range(start_date, end_date)
    if err:
        return {"error": err}

    if category is not None:
        cat, err = _validate_category(category)
        if err:
            return {"error": err}
    else:
        cat = None

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return {"error": "limit must be a positive integer ≤ 100."}
    if limit < 1 or limit > 100:
        return {"error": "limit must be a positive integer ≤ 100."}

    if cat is not None:
        sql = """
            SELECT transaction_id, date, time, amount_cents,
                   description, merchant, category
            FROM expenses
            WHERE category = ?
              AND date BETWEEN ? AND ?
            ORDER BY date DESC, time DESC
            LIMIT ?
        """
        params = (cat, start, end, limit)
    else:
        sql = """
            SELECT transaction_id, date, time, amount_cents,
                   description, merchant, category
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY date DESC, time DESC
            LIMIT ?
        """
        params = (start, end, limit)

    rows = get_conn().execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tool: get_top_categories
# ---------------------------------------------------------------------------

def get_top_categories(
    start_date: str,
    end_date: str,
    n: int = 3,
) -> list[dict[str, Any]] | dict[str, Any]:
    """
    Return the top *n* categories by total spend in [start_date, end_date].

    Returns:
        list of {"category": str, "total_cents": int, "rank": int},
        or {"error": str} on invalid input.
    """
    start, end, err = _validate_date_range(start_date, end_date)
    if err:
        return {"error": err}

    try:
        n = int(n)
    except (TypeError, ValueError):
        return {"error": "n must be a positive integer."}
    if n < 1:
        return {"error": "n must be a positive integer."}

    rows = get_conn().execute(
        """
        SELECT category, SUM(amount_cents) AS total
        FROM expenses
        WHERE date BETWEEN ? AND ?
        GROUP BY category
        ORDER BY total DESC
        LIMIT ?
        """,
        (start, end, n),
    ).fetchall()

    return [
        {"category": row["category"], "total_cents": row["total"], "rank": rank}
        for rank, row in enumerate(rows, start=1)
    ]

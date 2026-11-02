"""
tests/test_tools.py

Four tests per tool:
  1. Valid query — correct return shape, amounts are integers.
  2. Invalid date format.
  3. Unknown category (tools that accept one).
  4. Date range that contains no transactions.
"""

import pytest
from app.tools import get_spending, list_transactions, get_top_categories


# ---------------------------------------------------------------------------
# get_spending
# ---------------------------------------------------------------------------

class TestGetSpending:

    def test_valid_query(self):
        result = get_spending("Groceries", "2024-04-01", "2024-04-30")
        assert "error" not in result
        assert result["category"] == "Groceries"
        assert result["start_date"] == "2024-04-01"
        assert result["end_date"] == "2024-04-30"
        assert isinstance(result["total_cents"], int)
        assert result["total_cents"] >= 0

    def test_invalid_date_format(self):
        result = get_spending("Groceries", "04-01-2024", "2024-04-30")
        assert "error" in result
        assert "2024" in result["error"] or "date" in result["error"].lower()

    def test_unknown_category(self):
        result = get_spending("Restaurants", "2024-04-01", "2024-04-30")
        assert "error" in result
        assert "Restaurants" in result["error"]

    def test_empty_range(self):
        # Dates before the CSV data range — no transactions exist.
        result = get_spending("Groceries", "2020-01-01", "2020-01-31")
        assert "error" not in result
        assert result["total_cents"] == 0


# ---------------------------------------------------------------------------
# list_transactions
# ---------------------------------------------------------------------------

class TestListTransactions:

    def test_valid_query(self):
        result = list_transactions("2024-06-01", "2024-06-30")
        assert isinstance(result, list)
        if result:
            row = result[0]
            assert "transaction_id" in row
            assert "amount_cents" in row
            assert isinstance(row["amount_cents"], int)

    def test_invalid_date_format(self):
        result = list_transactions("2024/06/01", "2024-06-30")
        assert isinstance(result, dict)
        assert "error" in result

    def test_unknown_category(self):
        result = list_transactions("2024-06-01", "2024-06-30", category="FastFood")
        assert isinstance(result, dict)
        assert "error" in result
        assert "FastFood" in result["error"]

    def test_empty_range(self):
        result = list_transactions("2020-01-01", "2020-01-31")
        assert result == []

    def test_limit_too_large(self):
        result = list_transactions("2024-01-01", "2025-12-31", limit=200)
        assert isinstance(result, dict)
        assert "error" in result

    def test_limit_zero(self):
        result = list_transactions("2024-01-01", "2025-12-31", limit=0)
        assert isinstance(result, dict)
        assert "error" in result

    def test_start_after_end(self):
        result = list_transactions("2024-06-30", "2024-06-01")
        assert isinstance(result, dict)
        assert "error" in result


# ---------------------------------------------------------------------------
# get_top_categories
# ---------------------------------------------------------------------------

class TestGetTopCategories:

    def test_valid_query(self):
        result = get_top_categories("2024-04-01", "2024-12-31", n=3)
        assert isinstance(result, list)
        assert len(result) <= 3
        for i, item in enumerate(result, start=1):
            assert item["rank"] == i
            assert isinstance(item["total_cents"], int)
            assert item["total_cents"] > 0

    def test_invalid_date_format(self):
        result = get_top_categories("April 1 2024", "2024-12-31")
        assert isinstance(result, dict)
        assert "error" in result

    def test_unknown_category_not_applicable(self):
        # get_top_categories has no category filter; test n=0 as the invalid-input case.
        result = get_top_categories("2024-04-01", "2024-12-31", n=0)
        assert isinstance(result, dict)
        assert "error" in result

    def test_empty_range(self):
        result = get_top_categories("2020-01-01", "2020-01-31", n=3)
        assert result == []

    def test_ranks_are_ordered(self):
        result = get_top_categories("2024-01-01", "2025-12-31", n=6)
        totals = [item["total_cents"] for item in result]
        assert totals == sorted(totals, reverse=True)

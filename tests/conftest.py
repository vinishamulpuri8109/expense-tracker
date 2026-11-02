"""
tests/conftest.py

Session-scoped fixture that initialises the in-memory SQLite database
from the real CSV once for the entire test run.
No Gemini / LLM calls are made during tests.
"""

import pytest
from app.db import init_db


@pytest.fixture(scope="session", autouse=True)
def database():
    init_db("data/expenses.csv")

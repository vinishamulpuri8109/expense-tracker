"""
evals/run_evals.py

Runs 20 evaluation questions against the running /chat endpoint and
prints a pass/fail report plus overall pass rate.

Usage (with the server already running on localhost:8000):
    python3 evals/run_evals.py

Exit codes:
    0 — pass rate >= 80%
    1 — pass rate < 80%
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
QUESTIONS_FILE = Path(__file__).parent / "questions.json"
PASS_THRESHOLD = 0.80  # 80%


def ask(question: str, client: httpx.Client) -> str:
    """POST /chat and return the answer text."""
    response = client.post(
        f"{BASE_URL}/chat",
        json={"question": question},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["answer"]


def main() -> None:
    questions = json.loads(QUESTIONS_FILE.read_text())
    total = len(questions)
    passed = 0

    print(f"Running {total} evaluation questions against {BASE_URL}\n")
    print(f"{'#':<4}  {'PASS':<6}  {'EXPECTED':<20}  QUESTION")
    print("-" * 80)

    with httpx.Client() as client:
        for i, entry in enumerate(questions, start=1):
            question: str = entry["question"]
            expected: str = entry["expected"]

            try:
                answer = ask(question, client)
                ok = expected in answer
            except Exception as exc:
                answer = f"ERROR: {exc}"
                ok = False

            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1

            print(f"{i:<4}  {status:<6}  {expected:<20}  {question}")
            if not ok:
                print(f"       Answer: {answer[:120]}")

    print("-" * 80)
    rate = passed / total
    print(f"\nResult: {passed}/{total} ({rate:.0%})")

    if rate >= PASS_THRESHOLD:
        print("✓ Pass threshold met.")
        sys.exit(0)
    else:
        print(f"✗ Pass rate below {PASS_THRESHOLD:.0%} threshold.")
        sys.exit(1)


if __name__ == "__main__":
    main()

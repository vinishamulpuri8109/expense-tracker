"""
app/agent.py

Implements the tool-calling agent loop.

run_agent(question) -> str
  - Sends the question to Gemini with the three tool schemas.
  - Executes any tool calls the model requests.
  - Returns the model's final text answer.
  - Loops up to MAX_ROUNDS times; returns a fallback string if exhausted.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse

from app import tools as tool_module
from app.llm import call_model

logger = logging.getLogger(__name__)

MAX_ROUNDS = 5

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a personal finance assistant. "
    "You have access to tools that query the user's expense database. "
    "Always call a tool to retrieve any dollar amount, count, or category total — "
    "never calculate or estimate figures from memory. "
    "The database contains only expenses, no income. "
    "When you present amounts to the user, convert cents to dollars (divide by 100). "
    "If the user references a category not in the allowed list, say so politely."
)

# ---------------------------------------------------------------------------
# Tool map: name → callable
# ---------------------------------------------------------------------------

TOOL_MAP: dict[str, Any] = {
    "get_spending": tool_module.get_spending,
    "list_transactions": tool_module.list_transactions,
    "get_top_categories": tool_module.get_top_categories,
}

# ---------------------------------------------------------------------------
# Tool schemas (Gemini FunctionDeclarations)
# ---------------------------------------------------------------------------

_CATEGORY_DESC = (
    "One of: Bills, Entertainment, Food & Beverage, "
    "Groceries, Healthcare, Transportation"
)

TOOL_SCHEMAS = [
    genai.protos.Tool(function_declarations=[
        genai.protos.FunctionDeclaration(
            name="get_spending",
            description=(
                "Return the total amount spent in cents for a specific category "
                "over a date range."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "category": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description=_CATEGORY_DESC,
                    ),
                    "start_date": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="Start date inclusive, YYYY-MM-DD.",
                    ),
                    "end_date": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="End date inclusive, YYYY-MM-DD.",
                    ),
                },
                required=["category", "start_date", "end_date"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="list_transactions",
            description=(
                "List individual transactions in a date range, newest first. "
                "Optionally filter by category."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "start_date": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="Start date inclusive, YYYY-MM-DD.",
                    ),
                    "end_date": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="End date inclusive, YYYY-MM-DD.",
                    ),
                    "category": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description=f"Optional. {_CATEGORY_DESC}",
                    ),
                    "limit": genai.protos.Schema(
                        type=genai.protos.Type.INTEGER,
                        description="Max number of rows to return (1–100, default 20).",
                    ),
                },
                required=["start_date", "end_date"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="get_top_categories",
            description=(
                "Return the top-n spending categories by total amount for a date range."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "start_date": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="Start date inclusive, YYYY-MM-DD.",
                    ),
                    "end_date": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="End date inclusive, YYYY-MM-DD.",
                    ),
                    "n": genai.protos.Schema(
                        type=genai.protos.Type.INTEGER,
                        description="Number of top categories to return (default 3).",
                    ),
                },
                required=["start_date", "end_date"],
            ),
        ),
    ])
]

# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def _dispatch_tool(name: str, args: dict[str, Any]) -> Any:
    """Call the named tool and return its result."""
    func = TOOL_MAP.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name!r}"}
    return func(**args)


def run_agent(question: str) -> str:
    """
    Run the tool-calling loop for *question*.

    Returns the model's text answer, or a fallback message if MAX_ROUNDS
    is exhausted without receiving a text response.
    """
    # Build initial message list: system instruction + user question.
    messages: list[Any] = [
        {"role": "user", "parts": [SYSTEM_PROMPT + "\n\nUser question: " + question]},
    ]

    for round_num in range(1, MAX_ROUNDS + 1):
        logger.info("Agent round %d/%d", round_num, MAX_ROUNDS)
        response: GenerateContentResponse = call_model(messages, TOOL_SCHEMAS)

        candidate = response.candidates[0]
        parts = candidate.content.parts

        # Check if the model returned a text answer.
        text_parts = [p for p in parts if p.text]
        if text_parts:
            return text_parts[0].text.strip()

        # Otherwise collect function calls.
        fn_calls = [p.function_call for p in parts if p.function_call.name]
        if not fn_calls:
            # No text and no function calls — unexpected; return fallback.
            break

        # Append the model's turn (containing the function call parts).
        messages.append(candidate.content)

        # Execute each tool call and build function response parts.
        response_parts: list[Any] = []
        for fn_call in fn_calls:
            tool_name = fn_call.name
            tool_args = dict(fn_call.args)
            logger.info("Tool call: %s(%s)", tool_name, json.dumps(tool_args))

            result = _dispatch_tool(tool_name, tool_args)
            logger.info("Tool result: %s", json.dumps(result))

            response_parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tool_name,
                        response={"result": result},
                    )
                )
            )

        # Append tool results as a "tool" role turn.
        messages.append({"role": "user", "parts": response_parts})

    logger.warning("Agent loop exhausted after %d rounds without a text answer.", MAX_ROUNDS)
    return (
        "I was unable to complete your request. "
        "Please try rephrasing your question."
    )

"""
app/llm.py

Single entry point for all Gemini API calls.
Swap this file to change the LLM provider (e.g. AWS Bedrock).

Public API:
    call_model(messages, tools) -> google.generativeai.types.GenerateContentResponse
"""

from __future__ import annotations

import os
import logging
from typing import Any

import google.generativeai as genai

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Initialise the client once at import time.
# Fail fast if the key is missing.
# ---------------------------------------------------------------------------

_api_key = os.environ.get("GEMINI_API_KEY")
if not _api_key:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable is not set. "
        "Set it before starting the application."
    )

genai.configure(api_key=_api_key)

MODEL_NAME = "gemini-2.5-flash"


def call_model(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> Any:
    """
    Send *messages* and *tools* to Gemini and return the raw response.

    Args:
        messages: List of turn dicts.  Each dict has:
                    {"role": "user"|"model"|"tool", "parts": [...]}
                  Parts are either plain strings or
                  google.generativeai.protos.Part objects (function call /
                  function response).
        tools:    List of Gemini FunctionDeclaration-compatible dicts.

    Returns:
        google.generativeai.types.GenerateContentResponse
        (inspect .candidates[0].content.parts for text vs. function calls)
    """
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        tools=tools if tools else None,
    )

    # GenerativeModel.generate_content accepts a list of Content objects or
    # plain dicts with role/parts.
    response = model.generate_content(messages)
    logger.debug("Gemini response finish_reason=%s", response.candidates[0].finish_reason)
    return response

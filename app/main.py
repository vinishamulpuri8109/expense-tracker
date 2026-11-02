"""
app/main.py

FastAPI application entry point.

Routes:
    GET  /health  — liveness check
    POST /chat    — natural-language expense questions
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.db import init_db
from app.agent import run_agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: load CSV into SQLite before serving requests
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading expense data…")
    init_db("data/expenses.csv")
    logger.info("Database ready.")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Personal Finance Assistant",
    description="Ask natural-language questions about your expense data.",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve frontend static files at /static
_frontend = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(_frontend)), name="static")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural-language question about your expenses.",
    )


class ChatResponse(BaseModel):
    answer: str


class HealthResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(str(_frontend / "index.html"))


@app.get("/health", response_model=HealthResponse, summary="Liveness check")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse, summary="Ask an expense question")
def chat(request: ChatRequest) -> ChatResponse:
    answer = run_agent(request.question)
    return ChatResponse(answer=answer)

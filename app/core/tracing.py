"""LLM tracing (LangSmith), so every prompt and score can be replayed.

Agents are hard to debug because the interesting part - what was sent to the
model and what came back - is invisible by default. LangSmith records it. This
is off unless `LANGSMITH_TRACING=true` and a key are set, so the app runs with
no account; when on, it just exports the env vars LangChain/LangGraph already
look for, which is all the instrumentation they need.
"""

import logging
import os

from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_tracing() -> bool:
    """Enable LangSmith tracing if configured. Returns whether it was turned on."""
    if not settings.LANGSMITH_TRACING:
        logger.info("LangSmith tracing disabled (set LANGSMITH_TRACING=true to enable)")
        return False

    if not settings.LANGSMITH_API_KEY:
        logger.warning(
            "LANGSMITH_TRACING is on but LANGSMITH_API_KEY is empty; "
            "tracing will not start."
        )
        return False

    # Both names are honoured by different LangChain versions; set both.
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT

    logger.info(
        "LangSmith tracing enabled, project=%s", settings.LANGSMITH_PROJECT
    )
    return True

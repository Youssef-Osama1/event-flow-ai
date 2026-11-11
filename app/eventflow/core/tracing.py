import logging
from contextlib import AbstractContextManager, nullcontext
from typing import Any

from eventflow.config import get_settings

logger = logging.getLogger(__name__)

_client: Any = None
_checked = False


def get_langfuse() -> Any:
    global _client, _checked
    if _checked:
        return _client
    _checked = True
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.warning("Tracing requested but Langfuse keys are missing, running untraced")
        return None
    try:
        from langfuse import Langfuse
        from pydantic_ai import Agent

        client = Langfuse(
            public_key=settings.langfuse_public_key.get_secret_value(),
            secret_key=settings.langfuse_secret_key.get_secret_value(),
            base_url=settings.langfuse_base_url,
        )
        if not client.auth_check():
            logger.warning("Langfuse auth check failed, running untraced")
            return None
        Agent.instrument_all()
        _client = client
    except Exception as exc:
        logger.warning("Langfuse unavailable (%s), running untraced", exc)
        _client = None
    return _client


def span(client: Any, name: str, **kwargs: Any) -> AbstractContextManager[Any]:
    if client is None:
        return nullcontext()
    try:
        return client.start_as_current_observation(name=name, **kwargs)
    except Exception as exc:
        logger.warning("Could not open Langfuse span %s: %s", name, exc)
        return nullcontext()


def current_trace_id(client: Any) -> str | None:
    if client is None:
        return None
    try:
        return client.get_current_trace_id()
    except Exception:
        return None


def flush(client: Any) -> None:
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.warning("Langfuse flush failed: %s", exc)

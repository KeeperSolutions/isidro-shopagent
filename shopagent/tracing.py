"""Langfuse tracing: one trace per shopper turn, grouped into a CLI session."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any, Iterator

_initialized = False
_session_id: str | None = None


def start_session() -> str:
    global _session_id
    _session_id = str(uuid.uuid4())
    return _session_id


def init_tracing() -> None:
    """Create the Langfuse client after environment variables are loaded."""
    global _initialized
    if _initialized:
        return

    _initialized = True
    from langfuse import Langfuse

    Langfuse()


def flush_tracing() -> None:
    from langfuse import get_client

    get_client().flush()


@contextmanager
def start_agent_turn(*, user_text: str) -> Iterator[Any]:
    """Root span for one turn. Trace I/O is the user message and reply."""
    from langfuse import get_client, propagate_attributes

    langfuse = get_client()
    with langfuse.start_as_current_observation(
        as_type="span",
        name="handle-user-message",
        input=user_text,
    ) as turn:
        with propagate_attributes(session_id=_session_id):
            yield turn


@contextmanager
def start_tool(name: str, *, input: Any = None) -> Iterator[Any]:
    from langfuse import get_client

    langfuse = get_client()
    with langfuse.start_as_current_observation(
        as_type="tool",
        name=name,
        input=input,
    ) as observation:
        yield observation

"""Deterministic scoring for eval expected_output blocks."""

from __future__ import annotations


def _tool_names(tool_calls: list[dict]) -> list[str]:
    return [call["name"] for call in tool_calls]


def _args_match(actual: dict, expected: dict) -> bool:
    for key, value in expected.items():
        if actual.get(key) != value:
            return False
    return True


def score(expected: dict, reply: str, tool_calls: list[dict]) -> tuple[bool, list[str]]:
    """Return (passed, failure reasons)."""
    errors: list[str] = []
    tools = _tool_names(tool_calls)
    reply_lower = reply.lower()

    for tool in expected.get("must_call", []):
        if tool not in tools:
            errors.append(f"missing tool call: {tool}")

    for tool in expected.get("must_not_call", []):
        if tool in tools:
            errors.append(f"forbidden tool call: {tool}")

    must_call_any = expected.get("must_call_any", [])
    if must_call_any and not any(tool in tools for tool in must_call_any):
        errors.append(f"expected one of: {', '.join(must_call_any)}")

    for tool_name, expected_args in expected.get("tool_args", {}).items():
        matches = [
            call
            for call in tool_calls
            if call["name"] == tool_name and _args_match(call.get("arguments", {}), expected_args)
        ]
        if not matches:
            errors.append(f"tool_args mismatch for {tool_name}: {expected_args}")

    for text in expected.get("must_mention", []):
        if text.lower() not in reply_lower:
            errors.append(f"reply missing: {text!r}")

    must_mention_any = expected.get("must_mention_any", [])
    if must_mention_any and not any(text.lower() in reply_lower for text in must_mention_any):
        errors.append(f"reply missing one of: {', '.join(must_mention_any)}")

    for text in expected.get("must_not_mention", []):
        if text.lower() in reply_lower:
            errors.append(f"reply must not mention: {text!r}")

    return not errors, errors

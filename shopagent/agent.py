"""The agent loop: moderate, run tools, and reply."""

import json

from shopagent import costs, display
from shopagent.openai_client import (
    function_call_for_input,
    get_assistant_text,
    get_function_calls,
    moderate_text,
    parse_response,
    stream_response,
    format_response_usage,
)
from shopagent.prompts import DELIMITER, SYSTEM_PROMPT
from shopagent.tools import TOOLS, execute_tool

MAX_TOOL_ROUNDS = 5


def _finalize_reply(client, settings, input_items, message_usage):
    """Stream a text reply and show it to the user as it arrives."""

    def on_text_delta(delta: str):
        display.print_stream_message(delta)

    response = stream_response(
        client,
        settings,
        input_items,
        SYSTEM_PROMPT,
        tool_choice="none",
        on_text_delta=on_text_delta,
    )
    costs.add_usage(message_usage, format_response_usage(response))

    text = get_assistant_text(response)
    if text:
        display.end_stream_message()
        input_items.append({"role": "assistant", "content": text})
        return message_usage

    display.print_stream_message("I'm sorry, I couldn't put together a reply. Please try again.")
    display.end_stream_message()
    return message_usage


def handle_user_message(input_items, client, settings, user_text, cart):
    """Handle one user message: moderate, tool loop, then streamed reply.

    Returns None if the message is blocked by moderation.
    """
    sanitized = user_text.replace(DELIMITER, "")

    moderation = moderate_text(client, sanitized)
    if moderation.flagged:
        display.print_moderation_message()
        return None

    input_items.append({
        "role": "user",
        "content": f"{DELIMITER}{sanitized}{DELIMITER}",
    })

    message_usage = costs.empty_usage()

    for _ in range(MAX_TOOL_ROUNDS):
        response = parse_response(
            client,
            settings,
            input_items,
            SYSTEM_PROMPT,
            tools=TOOLS,
        )
        costs.add_usage(message_usage, format_response_usage(response))

        function_calls = get_function_calls(response)
        if not function_calls:
            return _finalize_reply(client, settings, input_items, message_usage)

        for call in function_calls:
            input_items.append(function_call_for_input(call))

            parsed_args = getattr(call, "parsed_arguments", None)
            arguments = parsed_args if parsed_args is not None else call.arguments
            result = execute_tool(call.name, arguments, cart)

            input_items.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result),
            })

    # If we get here, we exceeded the max number of tool rounds.
    display.print_message("I'm having trouble finishing that request. Could you try again?")
    return message_usage

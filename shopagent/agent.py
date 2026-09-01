"""The agent loop: moderate, run tools, and reply."""

import json
from dataclasses import dataclass, field

from mcp import Client
from mcp.types import TextContent

from shopagent import api_client, costs, display, memory, tracing
from shopagent.openai_client import (
    function_call_for_input,
    get_assistant_text,
    get_function_calls,
    moderate_text,
    stream_response,
    format_response_usage,
)
from shopagent.prompts import DELIMITER, build_instructions

MAX_TOOL_ROUNDS = 8


def _instructions() -> str:
    return build_instructions(memory.load_memory(), api_client.get_cart_summary())


_FALLBACK_REPLY = "I'm sorry, I couldn't put together a reply. Please try again."


@dataclass
class TurnResult:
    usage: dict
    reply: str = ""
    tool_calls: list[dict] = field(default_factory=list)


async def handle_user_message(
    input_items,
    client,
    settings,
    user_text,
    mcp_client: Client,
    tools: list,
):
    """Handle one user message: moderate, tool loop, then streamed reply.

    Tools are discovered and called only through the MCP client.
    Returns None if the message is blocked by moderation.
    """
    sanitized = user_text.replace(DELIMITER, "")
    tool_calls: list[dict] = []

    with tracing.start_agent_turn(user_text=sanitized) as turn:
        moderation = moderate_text(client, sanitized)
        if moderation.flagged:
            turn.update(output={"blocked": True, "reason": "moderation"})
            display.print_moderation_message()
            return None

        input_items.append({
            "role": "user",
            "content": f"{DELIMITER}{sanitized}{DELIMITER}",
        })

        message_usage = costs.empty_usage()

        for _ in range(MAX_TOOL_ROUNDS):
            instructions = _instructions()

            response, streamed_text = stream_response(
                client,
                settings,
                input_items,
                instructions,
                tools=tools,
                on_text_delta=display.print_stream_message,
            )
            costs.add_usage(message_usage, format_response_usage(response))

            function_calls = get_function_calls(response)
            if not function_calls:
                text = get_assistant_text(response)
                if not text:
                    text = _FALLBACK_REPLY
                    display.print_stream_message(text)
                display.end_stream_message()
                input_items.append({"role": "assistant", "content": text})
                turn.update(output=text)
                return TurnResult(
                    usage=message_usage,
                    reply=text,
                    tool_calls=tool_calls,
                )

            if streamed_text:
                display.end_stream_message()

            for call in function_calls:
                input_items.append(function_call_for_input(call))

                arguments = call.arguments
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)

                tool_calls.append({"name": call.name, "arguments": arguments})

                with tracing.start_tool(call.name, input=arguments) as tool_span:
                    mcp_result = await mcp_client.call_tool(call.name, arguments)

                    if mcp_result.structured_content is not None:
                        output = mcp_result.structured_content
                        result = json.dumps(output)
                    else:
                        result = "\n".join(
                            block.text
                            for block in mcp_result.content
                            if isinstance(block, TextContent)
                        )
                        output = result

                    tool_span.update(output=output)

                input_items.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": result,
                })

        # If we get here, we exceeded the max number of tool rounds.
        stalled = "I'm having trouble finishing that request. Could you try again?"
        display.print_message(stalled)
        turn.update(output=stalled)
        return TurnResult(
            usage=message_usage,
            reply=stalled,
            tool_calls=tool_calls,
        )

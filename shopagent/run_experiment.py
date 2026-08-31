"""Run the shopagent-offline Langfuse dataset as an experiment."""

from __future__ import annotations

import sys
from contextlib import contextmanager

from dotenv import load_dotenv
from langfuse import Evaluation, get_client
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from shopagent import agent, api_client, display, tracing
from shopagent.config import load_settings
from shopagent.openai_client import create_client
from shopagent.score import score

load_dotenv()


@contextmanager
def _silent_display():
    """Suppress Rich CLI output during eval turns."""
    was_quiet = display.console.quiet
    display.console.quiet = True
    try:
        yield
    finally:
        display.console.quiet = was_quiet


def _seed_cart(cart: dict | None) -> None:
    if not cart or not cart.get("items"):
        return
    
    api_client.create_cart()
    
    for line in cart["items"]:
        api_client.add_cart_item(line["sku"], line["quantity"])


async def _run_turn(item_input: dict, settings: dict) -> dict:
    _seed_cart(item_input.get("cart"))

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "shopagent.mcp_server"],
    )

    async with Client(stdio_client(server_params)) as mcp_client:
        tool_list = await mcp_client.list_tools()
        tools = [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            }
            for tool in tool_list.tools
        ]

        turn = await agent.handle_user_message(
            [],
            create_client(settings),
            settings,
            item_input["user"],
            mcp_client,
            tools,
        )

    if turn is None:
        return {"reply": "", "tool_calls": []}
    return {"reply": turn.reply, "tool_calls": turn.tool_calls}


def _item_value(item, key: str):
    """Local experiment data is a dict; Langfuse dataset items use attributes."""
    if isinstance(item, dict):
        return item[key]
    return getattr(item, key)


async def _task(*, item, settings, **kwargs):
    item_input = _item_value(item, "input")
    return await _run_turn(item_input, settings)


def _pass_evaluator(*, output, expected_output, **kwargs):
    if not output:
        return Evaluation(
            name="pass",
            value=False,
            data_type="BOOLEAN",
            comment="no output",
        )

    passed, errors = score(expected_output, output.get("reply", ""), output.get("tool_calls", []))
    return Evaluation(
        name="pass",
        value=passed,
        data_type="BOOLEAN",
        comment="; ".join(errors) if errors else "ok",
    )


def main() -> int:
    settings = load_settings()
    tracing.init_tracing()

    langfuse = get_client()
    dataset = langfuse.get_dataset("shopagent-offline", fetch_items_page_size=100)

    async def task(*, item, **kwargs):
        return await _task(item=item, settings=settings, **kwargs)

    with _silent_display():
        result = dataset.run_experiment(
            name="shopagent-offline",
            description=dataset.description,
            task=task,
            evaluators=[_pass_evaluator],
            max_concurrency=1,
        )

    print(result.format())
    langfuse.flush()
    tracing.flush_tracing()
    return 0


if __name__ == "__main__":
    sys.exit(main())

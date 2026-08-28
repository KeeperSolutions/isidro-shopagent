import asyncio

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from shopagent import agent, costs, display, tracing
from shopagent.config import load_settings
from shopagent.openai_client import create_client


async def main() -> None:
    settings = load_settings()
    tracing.init_tracing()
    tracing.start_session()
    client = create_client(settings)
    input_items = []
    session_usage = costs.empty_usage()

    display.print_welcome()

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "shopagent.mcp_server"],
    )

    async with Client(stdio_client(server_params)) as mcp_client:
        tool_list = await mcp_client.list_tools()

        # The schema for the tools that OpenAI expects is different from the MCP schema.
        # So we need to convert the MCP tools to the OpenAI schema.
        # See the following for comparison:
        # https://developers.openai.com/api/docs/guides/tools?tool-type=function-calling
        # https://www.merge.dev/blog/mcp-tool-schema
        available_tools = [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            }
            for tool in tool_list.tools
        ]

        try:
            while True:
                try:
                    user_input = await asyncio.to_thread(display.ask_user)
                except EOFError:
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit"):
                    break

                display.print_agent_prefix()
                message_usage = await agent.handle_user_message(
                    input_items,
                    client,
                    settings,
                    user_input,
                    mcp_client,
                    available_tools,
                )

                # If the message is blocked by moderation, don't add usage and continue
                if message_usage is None:
                    display.console.print()
                    continue

                costs.add_usage(session_usage, message_usage)
                message_cost = costs.cost_usd(message_usage, settings["input_price"], settings["output_price"])
                session_cost = costs.cost_usd(session_usage, settings["input_price"], settings["output_price"])

                display.print_usage(
                    message_usage,
                    message_cost,
                    session_usage,
                    session_cost,
                )

        except KeyboardInterrupt:
            display.console.print()

        finally:
            tracing.flush_tracing()

    display.print_goodbye()


def run() -> None:
    asyncio.run(main())

if __name__ == "__main__":
    run()

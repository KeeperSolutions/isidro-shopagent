from shopagent import agent, costs, display
from shopagent.config import load_settings
from shopagent.openai_client import create_client


def run():
    settings = load_settings()
    client = create_client(settings)
    input_items = []
    session_usage = costs.empty_usage()

    display.print_welcome()

    try:
        while True:
            try:
                user_input = display.ask_user()
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit"):
                break

            display.print_agent_prefix()
            message_usage = agent.handle_user_message(
                input_items,
                client,
                settings,
                user_input,
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

    display.print_goodbye()

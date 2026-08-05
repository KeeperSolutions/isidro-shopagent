"""The agent loop: send user messages to OpenAI and stream replies."""

from shopagent import costs, display
from shopagent.openai_client import get_completion, moderate_text
from shopagent.prompts import DELIMITER, SYSTEM_PROMPT


def handle_user_message(input_items, client, settings, user_text):
    """Handle one user message: moderate, then call OpenAI and return usage.

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

    result = get_completion(
        client,
        settings,
        input_items,
        SYSTEM_PROMPT,
    )
    costs.add_usage(message_usage, result["usage"])
    input_items.extend(result["output_items"])
    return message_usage

"""The agent loop: send user messages to OpenAI and stream replies."""

from shopagent import costs
from shopagent.openai_client import get_completion
from shopagent.prompts import DELIMITER, SYSTEM_PROMPT


def handle_user_message(input_items, client, settings, user_text):
    """Handle one user message: call OpenAI and return usage."""

    sanitized = user_text.replace(DELIMITER, "")
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

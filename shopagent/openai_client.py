def create_client(settings):
    from openai import OpenAI

    return OpenAI(api_key=settings["api_key"])


def moderate_text(client, text):
    """Calls the Moderation API and returns the first result."""
    response = client.moderations.create(
        model="omni-moderation-latest",
        input=text,
    )
    return response.results[0]


def parse_response(
    client,
    settings,
    input_items,
    instructions,
    *,
    tools=None,
    tool_choice=None,
    text_format=None,
):
    """Call the Responses API with client.responses.parse and return the parsed response."""
    kwargs = {
        "model": settings["model"],
        "input": input_items,
        "instructions": instructions,
        "temperature": settings["temperature"],
    }

    if tools is not None:
        kwargs["tools"] = tools
    # tool_choice is "auto" by default
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice
    if text_format is not None:
        kwargs["text_format"] = text_format

    return client.responses.parse(**kwargs)


def format_response_usage(response):
    usage = response.usage
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0}
    return {
        "input_tokens": getattr(usage, "input_tokens", 0),
        "output_tokens": getattr(usage, "output_tokens", 0),
    }


def get_function_calls(response):
    """Return all function_call items from a response."""
    return [item for item in response.output if item.type == "function_call"]


def get_assistant_text(response):
    """Extract plain text from assistant message output items."""
    parts = []
    for item in response.output:
        if item.type != "message":
            continue
        for block in item.content:
            if block.type == "output_text":
                parts.append(block.text)
    return "".join(parts)


def function_call_for_input(item):
    """Serialize a function_call for the next request (no parsed_arguments)."""
    data = item.model_dump(exclude_none=True)
    data.pop("parsed_arguments", None)
    return data

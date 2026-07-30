from shopagent.display import print_stream_message


def create_client(settings):
    from openai import OpenAI

    return OpenAI(api_key=settings["api_key"])


def get_completion(
    client,
    settings,
    input_items,
    instructions,
):
    """Send input to OpenAI and stream back the model's response."""
    kwargs = {
        "model": settings["model"],
        "input": input_items,
        "instructions": instructions,
        "stream": True,
        "temperature": settings["temperature"],
    }

    stream = client.responses.create(**kwargs)

    completed_response = None

    for event in stream:
        if event.type == "response.output_text.delta":
            print_stream_message(event.delta)
        elif event.type == "response.completed":
            completed_response = event.response
        elif event.type == "error":
            raise RuntimeError(event.error)

    if completed_response is None:
        raise RuntimeError("Stream ended without a completed response")

    output = _parse_response_output(completed_response)
    usage = completed_response.usage
    output["usage"] = {
        "input_tokens": getattr(usage, "input_tokens", 0),
        "output_tokens": getattr(usage, "output_tokens", 0),
    } if usage else None

    return output


def _parse_response_output(response):
    """Extract assistant messages from a completed response."""
    output_items = []

    for item in response.output:
        if item.type == "message":
            message = []
            for block in item.content:
                if block.type == "output_text":
                    message.append(block.text)

            output_items.append({
                "role": "assistant",
                "content": "".join(message),
            })

    return {"output_items": output_items}

import time

from openai import PermissionDeniedError

from shopagent import tracing

_MODERATION_MAX_ATTEMPTS = 3
_MODERATION_RETRY_DELAY_SECONDS = 0.5


def create_client(settings):
    tracing.init_tracing()
    from langfuse.openai import OpenAI

    return OpenAI(api_key=settings["api_key"])


def moderate_text(client, text):
    """Calls the Moderation API and returns the first result.

    Retries up to 3 times on intermittent 403 PermissionDeniedError responses.
    """
    for attempt in range(1, _MODERATION_MAX_ATTEMPTS + 1):
        try:
            response = client.moderations.create(
                model="omni-moderation-latest",
                input=text,
            )
            return response.results[0]
        except PermissionDeniedError:
            if attempt == _MODERATION_MAX_ATTEMPTS:
                raise
            time.sleep(_MODERATION_RETRY_DELAY_SECONDS)
    raise RuntimeError("moderation retries exhausted without a response")


def _response_kwargs(
    settings,
    input_items,
    instructions,
    *,
    tools=None,
    tool_choice=None,
):
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

    return kwargs


def stream_response(
    client,
    settings,
    input_items,
    instructions,
    *,
    tools=None,
    tool_choice=None,
    on_text_delta=None,
):
    """Stream a Responses API call.

    Text deltas are forwarded only until a function_call output item appears,
    so a tool round stays silent if the model also emits text.
    """
    suppress_text = False
    streamed_text = False
    with client.responses.stream(
        **_response_kwargs(
            settings,
            input_items,
            instructions,
            tools=tools,
            tool_choice=tool_choice,
        )
    ) as stream:
        for event in stream:
            # If we get a function call, it means we're in a tool round and this is not something we want to show to the user.
            if (event.type == "response.output_item.added" and event.item.type == "function_call"):
                suppress_text = True
            if (on_text_delta is not None and not suppress_text and event.type == "response.output_text.delta"):
                on_text_delta(event.delta)
                streamed_text = True
        return stream.get_final_response(), streamed_text


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

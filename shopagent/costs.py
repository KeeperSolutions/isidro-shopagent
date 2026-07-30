"""Cost calculation and formatting."""

def empty_usage():
    return {"input_tokens": 0, "output_tokens": 0}


def add_usage(usage, source):
    if source is None:
        return
    usage["input_tokens"] += source.get("input_tokens", 0)
    usage["output_tokens"] += source.get("output_tokens", 0)


def cost_usd(usage, input_price, output_price):
    return (
        usage["input_tokens"] * input_price
        + usage["output_tokens"] * output_price
    ) / 1_000_000


def total_tokens(usage):
    return usage["input_tokens"] + usage["output_tokens"]

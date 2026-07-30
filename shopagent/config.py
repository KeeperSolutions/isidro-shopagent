import os

from dotenv import load_dotenv

load_dotenv()

# Pricing per model (USD per 1 million tokens): (input, output)
PRICING = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}

DEFAULT_MODEL = "gpt-4.1-mini"
FALLBACK_PRICING = PRICING[DEFAULT_MODEL]


def load_settings():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")

    temperature = float(os.getenv("TEMPERATURE", 0.7))
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    input_price, output_price = PRICING.get(model, FALLBACK_PRICING)

    return {
        "api_key": api_key,
        "model": model,
        "input_price": input_price,
        "output_price": output_price,
        "temperature": temperature,
    }

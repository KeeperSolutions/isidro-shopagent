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
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
FALLBACK_PRICING = PRICING[DEFAULT_MODEL]


def load_settings():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and set the Postgres URL.")

    temperature = float(os.getenv("TEMPERATURE", 0.7))
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    input_price, output_price = PRICING.get(model, FALLBACK_PRICING)

    return {
        "api_key": api_key,
        "model": model,
        "embedding_model": embedding_model,
        "database_url": database_url,
        "input_price": input_price,
        "output_price": output_price,
        "temperature": temperature,
    }

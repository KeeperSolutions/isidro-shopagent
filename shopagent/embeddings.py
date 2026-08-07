"""OpenAI embedding helpers for catalog semantic search."""

from openai import OpenAI

from shopagent.openai_client import create_client
from shopagent.config import load_settings

def create_vector_string(embedding: list[float]) -> str:
    """Create a vector string from a list of floats."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def embedding_text(name: str, brand: str, category: str, description: str) -> str:
    """Build the embedding text for each product."""
    return f"{name}. {brand}. {category}. {description}"


def embed_texts(texts: list[str], *, client: OpenAI | None = None) -> list[list[float]]:
    """Embed one or more texts with the configured OpenAI embedding model."""
    if not texts:
        return []

    settings = load_settings()
    openai_client = client or create_client(settings)

    response = openai_client.embeddings.create(
        model=settings["embedding_model"],
        input=texts,
        encoding_format="float",
    )
    return [item.embedding for item in response.data]


def embed_query(query: str, *, client: OpenAI | None = None) -> list[float]:
    """Embed a single search query."""
    return embed_texts([query], client=client)[0]

"""Seed Postgres catalog from data/catalog.json and refresh embeddings."""

from __future__ import annotations

import json
from pathlib import Path

from shopagent.config import load_settings
from shopagent.db import get_connection
from shopagent.embeddings import embed_texts, embedding_text, create_vector_string
from shopagent.openai_client import create_client

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


def seed_catalog(*, catalog_path: Path | None = None) -> None:
    """Seed products/variants from JSON and always refresh embeddings."""
    path = catalog_path or _CATALOG_PATH
    with path.open(encoding="utf-8") as f:
        catalog = json.load(f)

    products = catalog["products"]
    if not products:
        print("No products found in catalog; nothing to seed.")
        return

    settings = load_settings()
    client = create_client(settings)

    texts = [
        embedding_text(
            product["name"],
            product["brand"],
            product["category"],
            product["description"],
        )
        for product in products
    ]
    print(f"Embedding {len(texts)} products with {settings['embedding_model']}...")
    embeddings = embed_texts(texts, client=client)

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Replace catalog contents so removals from JSON are reflected
            cur.execute("DELETE FROM variants")
            cur.execute("DELETE FROM products")

            for product, embedding in zip(products, embeddings, strict=True):
                cur.execute(
                    """
                    INSERT INTO products (id, name, description, category, brand, rating, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    (
                        product["id"],
                        product["name"],
                        product["description"],
                        product["category"],
                        product["brand"],
                        product["rating"],
                        create_vector_string(embedding),
                    ),
                )
                for variant in product["variants"]:
                    cur.execute(
                        """
                        INSERT INTO variants (sku, product_id, size, color, price, inventory)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            variant["sku"],
                            product["id"],
                            variant["size"],
                            variant["color"],
                            variant["price"],
                            variant["inventory"],
                        ),
                    )
        conn.commit()

    variant_count = sum(len(p["variants"]) for p in products)
    print(f"Seeded {len(products)} products and {variant_count} variants.")


def main() -> None:
    seed_catalog()


if __name__ == "__main__":
    main()

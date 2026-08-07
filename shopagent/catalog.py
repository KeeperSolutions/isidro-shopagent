"""Catalog access backed by Postgres + pgvector."""

from __future__ import annotations

from typing import Literal

from shopagent.db import get_connection
from shopagent.embeddings import embed_query, create_vector_string

SearchMode = Literal["filter", "semantic"]


def _format_variant(row: dict) -> dict:
    return {
        "sku": row["sku"],
        "size": row["size"],
        "color": row["color"],
        "price": float(row["price"]),
        "inventory": row["inventory"],
    }


def _format_product(row: dict, variants: list[dict]) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "brand": row["brand"],
        "rating": float(row["rating"]),
        "variants": variants,
    }


def _fetch_variants_for_products(
    conn,
    product_ids: list[str],
    *,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = False,
) -> dict[str, list[dict]]:
    if not product_ids:
        return {}

    clauses = ["product_id = ANY(%s)"]
    params: list = [product_ids]

    if max_price is not None:
        clauses.append("price <= %s")
        params.append(max_price)
    if size is not None:
        clauses.append("size = %s")
        params.append(size)
    if in_stock_only:
        clauses.append("inventory > 0")

    sql = f"""
        SELECT sku, product_id, size, color, price, inventory
        FROM variants
        WHERE {" AND ".join(clauses)}
        ORDER BY product_id, sku
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    by_product: dict[str, list[dict]] = {pid: [] for pid in product_ids}
    for row in rows:
        by_product[row["product_id"]].append(_format_variant(row))
    return by_product


def filter_products(
    *,
    category: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = True,
) -> list[dict]:
    """SQL filter by category / price / size / stock. Returns products with matching variants."""
    variant_clauses = ["v.product_id = p.id"]
    params: list = []

    if max_price is not None:
        variant_clauses.append("v.price <= %s")
        params.append(max_price)
    if size is not None:
        variant_clauses.append("v.size = %s")
        params.append(size)
    if in_stock_only:
        variant_clauses.append("v.inventory > 0")

    where = [
        f"""EXISTS (
            SELECT 1 FROM variants v
            WHERE {" AND ".join(variant_clauses)}
        )"""
    ]
    if category is not None:
        where.append("p.category = %s")
        params.append(category)

    sql = f"""
        SELECT DISTINCT p.id, p.name, p.description, p.category, p.brand, p.rating
        FROM products p
        WHERE {" AND ".join(where)}
        ORDER BY p.id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            products = cur.fetchall()

        product_ids = [p["id"] for p in products]
        variants_by_product = _fetch_variants_for_products(
            conn,
            product_ids,
            max_price=max_price,
            size=size,
            in_stock_only=in_stock_only,
        )

    results = []
    for product in products:
        variants = variants_by_product.get(product["id"], [])
        results.append(_format_product(product, variants))

    return results


def semantic_search(query: str, *, limit: int = 5) -> list[dict]:
    """Exact cosine similarity search via pgvector. Pure similarity — no SQL filters."""

    # Remove whitespace from query
    needle = query.strip()
    if not needle:
        return []

    query_embedding = embed_query(needle)
    vector_string = create_vector_string(query_embedding)

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Note to self: pgvector does not do `VECTOR_DISTANCE` (distance function)
            # so we use the `<=>` operator instead, which does cosine distance.
            cur.execute(
                """
                SELECT id, name, description, category, brand, rating
                FROM products
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vector_string, limit),
            )
            products = cur.fetchall()

        product_ids = [p["id"] for p in products]
        variants_by_product = _fetch_variants_for_products(conn, product_ids)

    # Preserve cosine distance order
    return [
        _format_product(product, variants_by_product.get(product["id"], []))
        for product in products
    ]


def search_products(
    mode: SearchMode,
    *,
    query: str | None = None,
    category: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = True,
    limit: int = 5,
) -> list[dict]:
    """Thin dispatcher over filter_products and semantic_search."""
    if mode == "filter":
        return filter_products(
            category=category,
            max_price=max_price,
            size=size,
            in_stock_only=in_stock_only,
        )
    if mode == "semantic":
        if not query or not query.strip():
            raise ValueError("query is required when mode is 'semantic'")
        return semantic_search(query, limit=limit)


def get_product(product_id: str) -> dict | None:
    """Return a single product with all variants, or None if unknown."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, category, brand, rating
                FROM products
                WHERE id = %s
                """,
                (product_id,),
            )
            product = cur.fetchone()
            if product is None:
                return None

        variants_by_product = _fetch_variants_for_products(conn, [product_id])

    return _format_product(product, variants_by_product.get(product_id, []))


def check_stock(sku: str) -> dict | None:
    """Return stock info for a SKU, or None if unknown."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    v.sku,
                    v.product_id,
                    p.name,
                    v.inventory
                FROM variants v
                JOIN products p ON p.id = v.product_id
                WHERE v.sku = %s
                """,
                (sku,),
            )
            row = cur.fetchone()

    if row is None:
        return None

    return {
        "sku": row["sku"],
        "product_id": row["product_id"],
        "name": row["name"],
        "inventory": row["inventory"],
        "in_stock": row["inventory"] > 0,
    }


def get_variant_by_sku(sku: str) -> dict | None:
    """Returns a dict with product fields plus the matching variant, or None if unknown."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id AS product_id,
                    p.name,
                    p.description,
                    p.category,
                    p.brand,
                    p.rating,
                    v.sku,
                    v.size,
                    v.color,
                    v.price,
                    v.inventory
                FROM variants v
                JOIN products p ON p.id = v.product_id
                WHERE v.sku = %s
                """,
                (sku,),
            )
            row = cur.fetchone()

    if row is None:
        return None

    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "brand": row["brand"],
        "rating": float(row["rating"]),
        "sku": row["sku"],
        "size": row["size"],
        "color": row["color"],
        "price": float(row["price"]),
        "inventory": row["inventory"],
    }

import json
from pathlib import Path

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


def get_products() -> list[dict]:
    """Load the catalog and return all products."""
    with _CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)["products"]


def get_variant_by_sku(sku: str) -> dict | None:
    """Returns a dict with product fields plus the matching variant, or None if the SKU is unknown."""
    for product in get_products():
        for variant in product["variants"]:
            if variant["sku"] == sku:
                return {
                    "product_id": product["id"],
                    "name": product["name"],
                    "description": product["description"],
                    "category": product["category"],
                    "brand": product["brand"],
                    "rating": product["rating"],
                    "sku": variant["sku"],
                    "size": variant["size"],
                    "color": variant["color"],
                    "price": variant["price"],
                    "inventory": variant["inventory"],
                }
    return None


def _filter_variants(
    product: dict,
    *,
    max_price: float | None,
    size: str | None,
    in_stock_only: bool,
) -> list[dict]:
    variants = []
    for variant in product["variants"]:
        if in_stock_only and variant["inventory"] <= 0:
            continue
        if size is not None and variant["size"] != size:
            continue
        if max_price is not None and variant["price"] > max_price:
            continue
        variants.append(
            {
                "sku": variant["sku"],
                "size": variant["size"],
                "color": variant["color"],
                "price": variant["price"],
                "inventory": variant["inventory"],
            }
        )
    return variants


def _product_result(product: dict, variants: list[dict]) -> dict:
    return {
        "id": product["id"],
        "name": product["name"],
        "description": product["description"],
        "category": product["category"],
        "brand": product["brand"],
        "rating": product["rating"],
        "variants": variants,
    }


def search_products(
    query: str,
    *,
    category: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = True,
) -> list[dict]:
    """Search the catalog and return matching products."""
    needle = query.strip().casefold()
    results: list[dict] = []

    for product in get_products():
        if category is not None and product["category"] != category:
            continue

        haystack = " ".join(
            (
                product["name"],
                product["description"],
                product["brand"],
            )
        ).casefold()
        if needle and needle not in haystack:
            continue

        variants = _filter_variants(
            product,
            max_price=max_price,
            size=size,
            in_stock_only=in_stock_only,
        )
        if not variants:
            continue

        results.append(_product_result(product, variants))

    return results


def search_category(
    category: str,
    *,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = True,
) -> list[dict]:
    """Return products in an exact catalog category."""
    results: list[dict] = []

    for product in get_products():
        if product["category"] != category:
            continue

        variants = _filter_variants(
            product,
            max_price=max_price,
            size=size,
            in_stock_only=in_stock_only,
        )
        if not variants:
            continue

        results.append(_product_result(product, variants))

    return results

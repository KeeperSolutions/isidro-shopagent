"""Sync catalog products and variant prices to Stripe."""

from __future__ import annotations

import json
import os
from pathlib import Path

import stripe
from dotenv import load_dotenv

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
CATALOG_PRODUCT_ID_KEY = "catalog_product_id"


def _index_products(client: stripe.StripeClient) -> dict[str, stripe.Product]:
    indexed: dict[str, stripe.Product] = {}
    products = client.v1.products.list(params={"limit": 100})
    for product in products.auto_paging_iter():
        catalog_id = product.metadata[CATALOG_PRODUCT_ID_KEY] if CATALOG_PRODUCT_ID_KEY in product.metadata else None
        if catalog_id:
            indexed[catalog_id] = product
    return indexed


def _index_prices(client: stripe.StripeClient, stripe_product_id: str) -> dict[str, stripe.Price]:
    indexed: dict[str, stripe.Price] = {}
    prices = client.v1.prices.list(params={"product": stripe_product_id, "limit": 100, "active": True})
    for price in prices.auto_paging_iter():
        if price.lookup_key:
            indexed[price.lookup_key] = price
    return indexed


def _upsert_product(
    client: stripe.StripeClient,
    product: dict,
    existing: dict[str, stripe.Product],
) -> tuple[stripe.Product, bool]:
    params = {
        "name": product["name"],
        "description": product["description"],
        "metadata": {
            CATALOG_PRODUCT_ID_KEY: product["id"],
            "category": product["category"],
            "brand": product["brand"],
        },
    }
    current = existing.get(product["id"])
    if current is None:
        created = client.v1.products.create(params=params)
        existing[product["id"]] = created
        return created, True

    client.v1.products.update(current.id, params=params)
    return current, False


def _upsert_price(
    client: stripe.StripeClient,
    *,
    stripe_product_id: str,
    catalog_product_id: str,
    variant: dict,
    currency: str,
    existing: dict[str, stripe.Price],
) -> str:
    sku = variant["sku"]
    unit_amount = int(round(float(variant["price"]) * 100))
    metadata = {
        "sku": sku,
        CATALOG_PRODUCT_ID_KEY: catalog_product_id,
        "size": str(variant["size"]),
        "color": variant["color"],
    }
    nickname = f"{variant['color']}, size {variant['size']}"
    current = existing.get(sku)

    if current is None:
        created = client.v1.prices.create(
            params={
                "product": stripe_product_id,
                "currency": currency,
                "unit_amount": unit_amount,
                "lookup_key": sku,
                "nickname": nickname,
                "metadata": metadata,
            }
        )
        existing[sku] = created
        return "created"

    if current.unit_amount == unit_amount and (current.currency or "").lower() == currency:
        if current.nickname != nickname or current.metadata.to_dict() != metadata:
            client.v1.prices.update(
                current.id,
                params={"nickname": nickname, "metadata": metadata},
            )
        return "unchanged"

    replacement = client.v1.prices.create(
        params={
            "product": stripe_product_id,
            "currency": currency,
            "unit_amount": unit_amount,
            "lookup_key": sku,
            "transfer_lookup_key": True,
            "nickname": nickname,
            "metadata": metadata,
        }
    )
    if current.active:
        client.v1.prices.update(current.id, params={"active": False})
    existing[sku] = replacement
    return "replaced"


def sync_stripe_catalog() -> None:
    load_dotenv()
    secret = os.getenv("STRIPE_SECRET_KEY")
    if not secret:
        print("STRIPE_SECRET_KEY is not set; skipping Stripe catalog sync.")
        return

    path = _CATALOG_PATH
    with path.open(encoding="utf-8") as f:
        catalog = json.load(f)

    products = catalog.get("products")
    currency = str(catalog.get("currency", "usd")).lower()
    client = stripe.StripeClient(secret)
    existing_products = _index_products(client)

    created_products = 0
    created_prices = 0
    replaced_prices = 0

    for product in products:
        stripe_product, created = _upsert_product(client, product, existing_products)
        if created:
            created_products += 1

        existing_prices = _index_prices(client, stripe_product.id)
        for variant in product["variants"]:
            result = _upsert_price(
                client,
                stripe_product_id=stripe_product.id,
                catalog_product_id=product["id"],
                variant=variant,
                currency=currency,
                existing=existing_prices,
            )
            if result == "created":
                created_prices += 1
            elif result == "replaced":
                replaced_prices += 1

    print(
        "Synced Stripe catalog: "
        f"{created_products} products created, "
        f"{created_prices} prices created, "
        f"{replaced_prices} prices replaced."
    )


def main() -> None:
    sync_stripe_catalog()


if __name__ == "__main__":
    main()

def quantity_in_cart(cart: list[dict], sku: str) -> int:
    for item in cart:
        if item["sku"] == sku:
            return item["quantity"]
    return 0


def add_item(cart: list[dict], variant: dict, quantity: int) -> dict:
    """Add an item to the cart."""

    if quantity < 1:
        return {
            "ok": False,
            "error": "invalid_quantity",
            "message": "Quantity must be at least 1.",
        }

    sku = variant["sku"]
    already = quantity_in_cart(cart, sku)
    needed = already + quantity
    if needed > variant["inventory"]:
        return {
            "ok": False,
            "error": "insufficient_inventory",
            "message": (
                f"Only {variant['inventory']} in stock for {sku}; "
                f"cart already has {already}."
            ),
        }

    for item in cart:
        if item["sku"] == sku:
            item["quantity"] += quantity
            added = {
                "sku": sku,
                "name": item["name"],
                "size": item["size"],
                "color": item["color"],
                "unit_price": item["unit_price"],
                "quantity": quantity,
            }
            return {"ok": True, "added": added}

    cart.append(
        {
            "sku": sku,
            "name": variant["name"],
            "size": variant["size"],
            "color": variant["color"],
            "unit_price": variant["price"],
            "quantity": quantity,
        }
    )
    added = {
        "sku": sku,
        "name": variant["name"],
        "size": variant["size"],
        "color": variant["color"],
        "unit_price": variant["price"],
        "quantity": quantity,
    }
    return {"ok": True, "added": added}


def cart_summary(cart: list[dict]) -> dict:
    """Return cart line items with line totals, plus subtotal and item_count."""
    items = []
    subtotal = 0.0
    item_count = 0

    for item in cart:
        line_total = item["unit_price"] * item["quantity"]
        subtotal += line_total
        item_count += item["quantity"]
        items.append(
            {
                "sku": item["sku"],
                "name": item["name"],
                "size": item["size"],
                "color": item["color"],
                "unit_price": item["unit_price"],
                "quantity": item["quantity"],
                "line_total": line_total,
            }
        )

    return {
        "items": items,
        "item_count": item_count,
        "subtotal": subtotal,
    }

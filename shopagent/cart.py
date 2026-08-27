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

"""Stdio MCP server exposing ShopAgent catalog and cart tools."""

from __future__ import annotations

from mcp.server import MCPServer
from pydantic import Field

from shopagent.tools import Category, execute_tool

mcp = MCPServer(
    "ShopAgent",
    instructions=(
        "Shopping tools for a footwear catalog. "
        "Filter or semantically search products, check stock, and manage an in-memory cart. "
        "Prices are USD. Categories: Running, Sneakers, Boots, Sandals."
    ),
)


@mcp.tool()
def filter_products(
    category: Category | None = Field(
        default=None,
        description="Exact category filter: Running, Sneakers, Boots, or Sandals",
    ),
    max_price: float | None = Field(
        default=None,
        description="Maximum price in USD; only variants at or below this price",
    ),
    size: str | None = Field(
        default=None,
        description='Size string (e.g. "9" or "10")',
    ),
    in_stock_only: bool = Field(
        default=True,
        description="When true, only include variants with inventory > 0",
    ),
) -> list | dict:
    """Browse the catalog with filters only (category, max price, size, stock).
    Use when the user wants a category or constraints without a free-text intent.
    Returns products with matching variants.
    """
    return execute_tool(
        "filter_products",
        {
            "category": category,
            "max_price": max_price,
            "size": size,
            "in_stock_only": in_stock_only,
        },
    )


@mcp.tool()
def semantic_search(
    query: str = Field(
        description="Natural-language description of what the shopper wants",
    ),
    limit: int = Field(
        default=5,
        description="Maximum number of products to return (default 5)",
    ),
) -> list | dict:
    """Semantic (vector) search over product descriptions.
    Use for natural-language shopping intent. Pure similarity — no price/category filters.
    Returns the top matching products with variants.
    """
    return execute_tool(
        "semantic_search",
        {
            "query": query,
            "limit": limit,
        },
    )


@mcp.tool()
def get_product(
    product_id: str = Field(
        description="Exact product id from a prior search result (e.g. fc200bac-dd85-42a6-a381-383b6d19abc6)",
    ),
) -> dict:
    """Fetch a single product and all of its variants by product id (e.g. fc200bac-dd85-42a6-a381-383b6d19abc6)."""
    return execute_tool("get_product", {"product_id": product_id})


@mcp.tool()
def check_stock(
    sku: str = Field(
        description="Exact variant SKU (e.g. SKU_001)",
    ),
) -> dict:
    """Check inventory for an exact variant SKU.
    Returns sku, product name, inventory count, and in_stock.
    """
    return execute_tool("check_stock", {"sku": sku})


@mcp.tool()
def add_to_cart(
    sku: str = Field(
        description="Exact variant SKU from a prior search result",
    ),
    quantity: int = Field(
        default=1,
        description="Number of units to add (minimum 1)",
    ),
) -> dict:
    """Add a product variant to the cart by SKU from a prior search result.
    Returns the updated cart with subtotal. Do not invent SKUs.
    """
    return execute_tool("add_to_cart", {"sku": sku, "quantity": quantity})


@mcp.tool()
def calculate_cart_total() -> dict:
    """Return the current cart items and subtotal without changing the cart."""
    return execute_tool("calculate_cart_total", {})


@mcp.tool()
def checkout(
    confirmed: bool = Field(
        default=False,
        description=(
            "Must be true only after the shopper explicitly confirmed they want to pay. "
            "If false, returns the cart summary and does not create a checkout session."
        ),
    ),
) -> dict:
    """Create a Stripe checkout session for the current cart and return the payment URL.
    Call only after the shopper explicitly confirms they want to pay, with confirmed=true.
    Never invent a checkout URL. Show the url field to the shopper in full, including any # fragment.
    """
    return execute_tool("checkout", {"confirmed": confirmed})


@mcp.tool()
def save_shopper_memory(
    name: str | None = Field(
        default=None,
        description="Shopper's name, if they shared it",
    ),
    preferred_size: str | None = Field(
        default=None,
        description='Preferred shoe size (e.g. "9")',
    ),
    preferred_color: str | None = Field(
        default=None,
        description="Preferred color, if they shared one",
    ),
    preferred_category: str | None = Field(
        default=None,
        description="Preferred category: Running, Sneakers, Boots, or Sandals",
    ),
    notes: str | None = Field(
        default=None,
        description="Other lasting preferences to remember across sessions",
    ),
) -> dict:
    """Save the shopper's name and lasting preferences so they are remembered later.
    Only store what they explicitly shared.
    """
    return execute_tool(
        "save_shopper_memory",
        {
            "name": name,
            "preferred_size": preferred_size,
            "preferred_color": preferred_color,
            "preferred_category": preferred_category,
            "notes": notes,
        },
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

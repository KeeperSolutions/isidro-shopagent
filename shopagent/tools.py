import json
from enum import Enum

from openai import pydantic_function_tool
from pydantic import BaseModel, Field, ValidationError

from shopagent import api_client, catalog, memory


class Category(str, Enum):
    Running = "Running"
    Sneakers = "Sneakers"
    Boots = "Boots"
    Sandals = "Sandals"


class FilterProductsArgs(BaseModel):
    category: Category | None = Field(
        default=None,
        description="Exact category filter: Running, Sneakers, Boots, or Sandals",
    )

    max_price: float | None = Field(
        default=None,
        description="Maximum price in USD; only variants at or below this price",
    )

    size: str | None = Field(
        default=None,
        description='Size string (e.g. "9" or "10")',
    )

    in_stock_only: bool = Field(
        default=True,
        description="When true, only include variants with inventory > 0",
    )


class SemanticSearchArgs(BaseModel):
    query: str = Field(
        description="Natural-language description of what the shopper wants",
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of products to return (default 5)",
    )


class GetProductArgs(BaseModel):
    product_id: str = Field(
        description="Exact product id from a prior search result (e.g. fc200bac-dd85-42a6-a381-383b6d19abc6)",
    )


class CheckStockArgs(BaseModel):
    sku: str = Field(
        description="Exact variant SKU (e.g. SKU_001)",
    )


class AddToCartArgs(BaseModel):
    sku: str = Field(
        description="Exact variant SKU from a prior search result",
    )

    quantity: int = Field(
        default=1,
        ge=1,
        description="Number of units to add (minimum 1)",
    )


class CalculateCartTotalArgs(BaseModel):
    """Calculate the current cart and subtotal."""


class CheckoutArgs(BaseModel):
    confirmed: bool = Field(
        default=False,
        description=(
            "Must be true only after the shopper explicitly confirmed they want to pay. "
            "If false, returns the cart summary and does not create a checkout session."
        ),
    )


class SaveShopperMemoryArgs(BaseModel):
    name: str | None = Field(
        default=None,
        description="Shopper's name, if they shared it",
    )
    preferred_size: str | None = Field(
        default=None,
        description='Preferred shoe size (e.g. "9")',
    )
    preferred_color: str | None = Field(
        default=None,
        description="Preferred color, if they shared one",
    )
    preferred_category: str | None = Field(
        default=None,
        description="Preferred category: Running, Sneakers, Boots, or Sandals",
    )
    notes: str | None = Field(
        default=None,
        description="Other lasting preferences to remember across sessions",
    )


TOOLS = [
    pydantic_function_tool(
        FilterProductsArgs,
        name="filter_products",
        description=(
            "Browse the catalog with filters only (category, max price, size, stock). "
            "Use when the user wants a category or constraints without a free-text intent. "
            "Returns products with matching variants."
        ),
    ),
    pydantic_function_tool(
        SemanticSearchArgs,
        name="semantic_search",
        description=(
            "Semantic (vector) search over product descriptions. "
            "Use for natural-language shopping intent. Pure similarity — no price/category filters. "
            "Returns the top matching products with variants."
        ),
    ),
    pydantic_function_tool(
        GetProductArgs,
        name="get_product",
        description=(
            "Fetch a single product and all of its variants by product id (e.g. fc200bac-dd85-42a6-a381-383b6d19abc6). "
            "Use when the user asks about a known product."
        ),
    ),
    pydantic_function_tool(
        CheckStockArgs,
        name="check_stock",
        description=(
            "Check inventory for an exact variant SKU. "
            "Returns sku, product name, inventory count, and in_stock."
        ),
    ),
    pydantic_function_tool(
        AddToCartArgs,
        name="add_to_cart",
        description=(
            "Add a product variant to the cart by SKU from a prior search result. "
            "Returns the updated cart with subtotal. Do not invent SKUs."
        ),
    ),
    pydantic_function_tool(
        CalculateCartTotalArgs,
        name="calculate_cart_total",
        description=(
            "Return the current cart items and subtotal without changing the cart. "
            "Use when the user asks what is in the cart or how much it costs. "
            "Do not call this right after add_to_cart (that already returns totals)."
        ),
    ),
    pydantic_function_tool(
        CheckoutArgs,
        name="checkout",
        description=(
            "Create a Stripe checkout session for the current cart and return the payment URL. "
            "Call only after the shopper explicitly confirms they want to pay, with confirmed=true. "
            "Never invent a checkout URL. Show the url field to the shopper in full, including any # fragment."
        ),
    ),
    pydantic_function_tool(
        SaveShopperMemoryArgs,
        name="save_shopper_memory",
        description=(
            "Save the shopper's name and lasting preferences (size, color, category, notes) "
            "so they are remembered in later sessions. Only store what they explicitly shared."
        ),
    ),
]

_ARG_MODELS = {
    "filter_products": FilterProductsArgs,
    "semantic_search": SemanticSearchArgs,
    "get_product": GetProductArgs,
    "check_stock": CheckStockArgs,
    "add_to_cart": AddToCartArgs,
    "calculate_cart_total": CalculateCartTotalArgs,
    "checkout": CheckoutArgs,
    "save_shopper_memory": SaveShopperMemoryArgs,
}


def _error(error: str, message: str) -> dict:
    return {"ok": False, "error": error, "message": message}


def _run_filter_products(args: FilterProductsArgs) -> list[dict]:
    category = args.category.value if args.category is not None else None
    return catalog.filter_products(
        category=category,
        max_price=args.max_price,
        size=args.size,
        in_stock_only=args.in_stock_only,
    )


def _run_semantic_search(args: SemanticSearchArgs) -> list[dict]:
    return catalog.semantic_search(args.query, limit=args.limit)


def _run_get_product(args: GetProductArgs) -> dict:
    product = catalog.get_product(args.product_id)
    if product is None:
        return _error("unknown_product", f"No product found for id {args.product_id!r}.")
    return product


def _run_check_stock(args: CheckStockArgs) -> dict:
    stock = catalog.check_stock(args.sku)
    if stock is None:
        return _error("unknown_sku", f"No product variant found for SKU {args.sku!r}.")
    return stock


def _run_add_to_cart(args: AddToCartArgs) -> dict:
    return api_client.add_cart_item(args.sku, args.quantity)


def _run_calculate_cart_total() -> dict:
    return api_client.get_cart_summary()


def _run_checkout(args: CheckoutArgs) -> dict:
    return api_client.checkout(confirmed=args.confirmed)


def _run_save_shopper_memory(args: SaveShopperMemoryArgs) -> dict:
    profile = memory.save_memory(
        name=args.name,
        preferred_size=args.preferred_size,
        preferred_color=args.preferred_color,
        preferred_category=args.preferred_category,
        notes=args.notes,
    )
    return {"ok": True, "profile": profile}


def execute_tool(name: str, arguments):
    """Validate tool arguments and run the matching handler."""
    if name not in _ARG_MODELS:
        return _error("unknown_tool", f"Unknown tool: {name!r}.")

    model_cls = _ARG_MODELS[name]

    try:
        if isinstance(arguments, model_cls):
            args = arguments
        elif isinstance(arguments, BaseModel):
            args = model_cls.model_validate(arguments.model_dump())
        elif isinstance(arguments, str):
            data = json.loads(arguments) if arguments.strip() else {}
            args = model_cls.model_validate(data)
        elif isinstance(arguments, dict):
            args = model_cls.model_validate(arguments)
        else:
            return _error("invalid_arguments", f"Unsupported arguments type: {type(arguments)!r}.")
    except (ValidationError, json.JSONDecodeError) as exc:
        return _error("invalid_arguments", str(exc))

    if name == "filter_products":
        return _run_filter_products(args)
    if name == "semantic_search":
        return _run_semantic_search(args)
    if name == "get_product":
        return _run_get_product(args)
    if name == "check_stock":
        return _run_check_stock(args)
    if name == "add_to_cart":
        return _run_add_to_cart(args)
    if name == "calculate_cart_total":
        return _run_calculate_cart_total()
    if name == "checkout":
        return _run_checkout(args)
    if name == "save_shopper_memory":
        return _run_save_shopper_memory(args)

    return _error("unknown_tool", f"Unknown tool: {name!r}.")

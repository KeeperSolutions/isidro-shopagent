import json
from enum import Enum

from openai import pydantic_function_tool
from pydantic import BaseModel, Field, ValidationError

from shopagent import cart
from shopagent import catalog


class Category(str, Enum):
    Running = "Running"
    Sneakers = "Sneakers"
    Boots = "Boots"
    Sandals = "Sandals"


class SearchProductsArgs(BaseModel):
    query: str = Field(
        description="Free-text search against name, description, and brand",
    )

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
        description='Required size string, e.g. "9" or "10"',
    )

    in_stock_only: bool = Field(
        default=True,
        description="When true, only include variants with inventory > 0",
    )


class SearchCategoryArgs(BaseModel):
    category: Category = Field(
        description="Exact catalog category: Running, Sneakers, Boots, or Sandals",
    )

    max_price: float | None = Field(
        default=None,
        description="Maximum price in USD; only variants at or below this price",
    )

    size: str | None = Field(
        default=None,
        description='Required size string, e.g. "9" or "10"',
    )

    in_stock_only: bool = Field(
        default=True,
        description="When true, only include variants with inventory > 0",
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


class ShopAgentReply(BaseModel):
    message: str = Field(
        description="Natural-language reply for the user (under ~3 sentences)",
    )


TOOLS = [
    pydantic_function_tool(
        SearchProductsArgs,
        name="search_products",
        description=(
            "Search the product catalog by keyword against name, description, and brand. "
            "Use for specific product or brand names. Prices are USD. "
            "Returns a list of matching products with variants."
        ),
    ),
    pydantic_function_tool(
        SearchCategoryArgs,
        name="search_category",
        description=(
            "List products in a catalog category (Running, Sneakers, Boots, or Sandals). "
            "Use when the user asks for a type of footwear such as running shoes, boots, "
            "sneakers, or sandals. Prices are USD. Returns a list of products with variants."
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
]

_ARG_MODELS = {
    "search_products": SearchProductsArgs,
    "search_category": SearchCategoryArgs,
    "add_to_cart": AddToCartArgs,
    "calculate_cart_total": CalculateCartTotalArgs,
}


def _error(error: str, message: str) -> dict:
    return {"ok": False, "error": error, "message": message}


def _run_search_products(args: SearchProductsArgs) -> list[dict]:
    category = args.category.value if args.category is not None else None
    return catalog.search_products(
        args.query,
        category=category,
        max_price=args.max_price,
        size=args.size,
        in_stock_only=args.in_stock_only,
    )


def _run_search_category(args: SearchCategoryArgs) -> list[dict]:
    return catalog.search_category(
        args.category.value,
        max_price=args.max_price,
        size=args.size,
        in_stock_only=args.in_stock_only,
    )


def _run_add_to_cart(args: AddToCartArgs, session_cart: list[dict]) -> dict:
    variant = catalog.get_variant_by_sku(args.sku)
    if variant is None:
        return _error("unknown_sku", f"No product variant found for SKU {args.sku!r}.")

    result = cart.add_item(session_cart, variant, args.quantity)
    if not result["ok"]:
        return result

    return {
        "ok": True,
        "added": result["added"],
        "cart": cart.cart_summary(session_cart),
    }


def _run_calculate_cart_total(session_cart: list[dict]) -> dict:
    return cart.cart_summary(session_cart)


def execute_tool(name: str, arguments, session_cart: list[dict]):
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

    if name == "search_products":
        return _run_search_products(args)
    if name == "search_category":
        return _run_search_category(args)
    if name == "add_to_cart":
        return _run_add_to_cart(args, session_cart)
    if name == "calculate_cart_total":
        return _run_calculate_cart_total(session_cart)

    return _error("unknown_tool", f"Unknown tool: {name!r}.")

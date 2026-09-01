"""HTTP client for the ShopAgent FastAPI cart, orders, and checkout service."""

from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv

from shopagent.cart import cart_summary
from shopagent.config import DEFAULT_API_URL

load_dotenv()

# This is so we don't see the HTTPX logs in the agent as it's leaking the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=os.getenv("SHOPAGENT_API_URL", DEFAULT_API_URL).rstrip("/"),
        headers={"X-API-Key": os.getenv("SHOPAGENT_API_KEY", "")},
        timeout=15.0,
    )


def _request(method: str, path: str, **kwargs):
    with _client() as client:
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()


def summarize_cart(cart: dict | None) -> dict:
    if not cart:
        return {"items": [], "item_count": 0, "subtotal": 0.0, "cart_id": None}
    summary = cart_summary(cart.get("items") or [])
    summary["cart_id"] = cart.get("id")
    return summary


def get_active_cart() -> dict | None:
    with _client() as client:
        response = client.get("/cart")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


def create_cart() -> str:
    return str(_request("POST", "/cart")["cart_id"])


def ensure_active_cart() -> dict:
    return get_active_cart() or {"id": create_cart(), "items": []}


def add_cart_item(sku: str, quantity: int = 1) -> dict:
    cart = ensure_active_cart()
    data = _request(
        "POST",
        f"/cart/{cart['id']}/items",
        json={"sku": sku, "quantity": quantity},
    )
    added = data["added"]
    added["quantity"] = quantity
    return {
        "ok": True,
        "added": added,
        "cart": summarize_cart({"id": cart["id"], "items": data["items"]}),
    }


def summarize_order(order: dict) -> dict:
    summary = cart_summary(order.get("items") or [])
    summary["cart_id"] = order.get("cart_id")
    return summary


def list_orders() -> list[dict]:
    data = _request("GET", "/orders")
    return data if isinstance(data, list) else []


def get_pending_order() -> dict | None:
    for order in list_orders():
        if order.get("status") == "pending":
            return order
    return None


def get_cart_summary() -> dict:
    cart = get_active_cart()
    summary = summarize_cart(cart)
    if summary["items"]:
        return summary
    pending = get_pending_order()
    if pending:
        return summarize_order(pending)
    return summary


def create_order(cart_id: str) -> dict:
    return _request("POST", "/orders", json={"cart_id": cart_id})


def create_checkout_session(order_id: str) -> dict:
    return _request("POST", "/checkout", json={"order_id": order_id})


def checkout(*, confirmed: bool) -> dict:
    cart = get_active_cart()
    cart_view = summarize_cart(cart)
    pending = None
    summary = cart_view
    if not summary["items"]:
        pending = get_pending_order()
        if pending:
            summary = summarize_order(pending)
    if not confirmed:
        return {
            "ok": False,
            "error": "confirmation_required",
            "message": "Ask the shopper to confirm they want to pay, then call checkout with confirmed=true.",
            "cart": summary,
        }
    if cart is not None and cart_view["items"]:
        order = create_order(str(cart["id"]))
    else:
        order = pending or get_pending_order()
        if not order:
            return {
                "ok": False,
                "error": "empty_cart",
                "message": "The cart is empty. Add items before checkout.",
                "cart": summary,
            }
    session = create_checkout_session(str(order["id"]))
    return {
        "ok": True,
        "order_id": order["id"],
        "session_id": session["session_id"],
        "url": session["url"],
        "subtotal": order["subtotal"],
        "items": order.get("items", []),
        "status": order.get("status"),
    }

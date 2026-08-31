import stripe
from fastapi import APIRouter, HTTPException
from stripe.params.checkout import SessionCreateParams, SessionCreateParamsLineItem

from shopagent.api.auth import ApiKeyDep
from shopagent.api.models import (
    CheckoutCreate,
    CheckoutPublic,
    OrderItem,
    OrderStatus,
)
from shopagent.api.routers.orders import get_order_items, get_owned_order
from shopagent.db import SessionDep
from shopagent.stripe_client import get_stripe_client

router = APIRouter(prefix="/checkout", tags=["checkout"])

CHECKOUT_SUCCESS_URL = ("http://127.0.0.1:8000/checkout/success?session_id={CHECKOUT_SESSION_ID}")
CHECKOUT_CANCEL_URL = "http://127.0.0.1:8000/checkout/cancel"
# Stripe prices.list accepts at most 10 lookup_keys per request.
_LOOKUP_KEY_AMOUNT = 10


def _price_ids_by_sku(client: stripe.StripeClient, skus: list[str]) -> dict[str, str]:
    indexed: dict[str, str] = {}
    for start in range(0, len(skus), _LOOKUP_KEY_AMOUNT):
        chunk = skus[start : start + _LOOKUP_KEY_AMOUNT]
        prices = client.v1.prices.list(
            params={
                "lookup_keys": chunk,
                "active": True,
                "limit": _LOOKUP_KEY_AMOUNT,
            }
        )
        for price in prices.data:
            if price.lookup_key:
                indexed[price.lookup_key] = price.id
    return indexed


def _line_items(client: stripe.StripeClient, items: list[OrderItem]) -> list[SessionCreateParamsLineItem]:
    skus = [item.sku for item in items]
    price_ids = _price_ids_by_sku(client, skus)
    return [{"price": price_ids[item.sku], "quantity": item.quantity} for item in items]


@router.post("", response_model=CheckoutPublic)
def create_checkout_session(
    body: CheckoutCreate,
    session: SessionDep,
    api_key: ApiKeyDep,
):
    order = get_owned_order(session, body.order_id, api_key)
    if order.status != OrderStatus.pending:
        raise HTTPException(
            status_code=409,
            detail=f"Order cannot be checked out (status is {order.status.value})",
        )

    items = get_order_items(session, order.id)
    if not items:
        raise HTTPException(status_code=400, detail="Order has no items")

    client = get_stripe_client()
    order_id_str = str(order.id)
    try:
        params: SessionCreateParams = {
            "mode": "payment",
            "line_items": _line_items(client, items),
            "success_url": CHECKOUT_SUCCESS_URL,
            "cancel_url": CHECKOUT_CANCEL_URL,
            "client_reference_id": order_id_str,
            "metadata": {"order_id": order_id_str},
            # We send the payment intent ID to Stripe so payment_intent.succeeded can resolve the order without a Session lookup.
            "payment_intent_data": {"metadata": {"order_id": order_id_str}},
            "integration_identifier": "shopagent-api",
        }
        checkout_session = client.v1.checkout.sessions.create(params=params)
    except stripe.StripeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not checkout_session.url:
        raise HTTPException(status_code=502, detail="Stripe did not return a checkout URL")

    return CheckoutPublic(session_id=checkout_session.id, url=checkout_session.url)


@router.get("/success")
def checkout_success(session_id: str | None = None):
    return {"status": "success", "session_id": session_id}


@router.get("/cancel")
def checkout_cancel():
    return {"status": "cancelled"}

import os

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

router = APIRouter(prefix="/checkout", tags=["checkout"])

CHECKOUT_SUCCESS_URL = ("http://127.0.0.1:8000/checkout/success?session_id={CHECKOUT_SESSION_ID}")
CHECKOUT_CANCEL_URL = "http://127.0.0.1:8000/checkout/cancel"


def _stripe_secret_key() -> str:
    secret = os.getenv("STRIPE_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY is not set")
    return secret


def _line_items(items: list[OrderItem]) -> list[SessionCreateParamsLineItem]:
    return [
        {
            "price_data": {
                "currency": "usd",
                "unit_amount": int((round(item.unit_price) * 100)),
                "product_data": {
                    "name": item.name,
                    "description": f"{item.color}, size {item.size} ({item.sku})",
                },
            },
            "quantity": item.quantity,
        }
        for item in items
    ]


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

    client = stripe.StripeClient(_stripe_secret_key())
    order_id_str = str(order.id)
    params: SessionCreateParams = {
        "mode": "payment",
        "line_items": _line_items(items),
        "success_url": CHECKOUT_SUCCESS_URL,
        "cancel_url": CHECKOUT_CANCEL_URL,
        "client_reference_id": order_id_str,
        "metadata": {"order_id": order_id_str},
        # We send the payment intent ID to Stripe so payment_intent.succeeded can resolve the order without a Session lookup.
        "payment_intent_data": {"metadata": {"order_id": order_id_str}},
        "integration_identifier": "shopagent-api",
    }
    try:
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

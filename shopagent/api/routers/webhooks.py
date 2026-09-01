"""Stripe webhook handlers for async payment events."""

from __future__ import annotations

from uuid import UUID

import stripe
from fastapi import APIRouter, HTTPException, Request

from shopagent import catalog
from shopagent.api.models import Cart, Order, OrderStatus
from shopagent.api.routers.cart import retire_cart
from shopagent.api.routers.orders import get_order_items
from shopagent.db import SessionDep
from shopagent.stripe_client import get_stripe_client, get_stripe_webhook_secret

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

HANDLED_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "payment_intent.succeeded",
    }
)


def _payment_intent_id(event: stripe.Event) -> str | None:
    obj = event.data.object
    # We can extract it from payment_intent.succeeded via id
    if event.type == "payment_intent.succeeded":
        return obj.id

    # Otherwise we need to look it up from the payment intent object on checkout.session.completed
    payment_intent = obj.payment_intent
    if payment_intent is None:
        return None

    if isinstance(payment_intent, str):
        return payment_intent

    return payment_intent.id


def _order_id_from_event(event: stripe.Event) -> UUID | None:
    metadata = getattr(event.data.object, "metadata", None)
    if not metadata:
        return None
    try:
        order_id_str = metadata["order_id"]
    except KeyError:
        return None
    try:
        return UUID(str(order_id_str))
    except (ValueError, TypeError):
        return None


def _is_successful_payment(event: stripe.Event) -> bool:
    if event.type == "checkout.session.completed":
        return getattr(event.data.object, "payment_status", None) == "paid"
    return event.type == "payment_intent.succeeded"


@router.post("/stripe")
async def stripe_webhook(request: Request, session: SessionDep):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    client = get_stripe_client()
    try:
        event = client.construct_event(payload, signature, get_stripe_webhook_secret())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Error verifying webhook signature") from exc

    if event.type not in HANDLED_EVENTS:
        return {"received": True, "handled": False, "type": event.type}

    order_id = _order_id_from_event(event)
    if order_id is None:
        return {
            "received": True,
            "handled": False,
            "type": event.type,
            "reason": "missing or invalid order_id metadata",
        }

    order = session.get(Order, order_id)

    # In theory there should always be an order, but we'll check just in case.
    if order is None:
        return {
            "received": True,
            "handled": False,
            "type": event.type,
            "order_id": str(order_id),
            "reason": f"Order not found (order_id={order_id})",
        }

    if not _is_successful_payment(event):
        return {
            "received": True,
            "handled": False,
            "type": event.type,
            "order_id": str(order_id),
            "reason": "payment not successful",
        }

    if order.status not in {OrderStatus.pending, OrderStatus.paid}:
        return {
            "received": True,
            "handled": False,
            "type": event.type,
            "order_id": str(order_id),
            "reason": f"cannot mark paid (status is {order.status.value})",
        }

    payment_intent_id = _payment_intent_id(event)
    if payment_intent_id and not order.stripe_payment_intent_id:
        order.stripe_payment_intent_id = payment_intent_id

    was_pending = order.status == OrderStatus.pending
    order.status = OrderStatus.paid
    session.add(order)

    cart = session.get(Cart, order.cart_id)
    if cart is not None:
        retire_cart(session, cart)

    session.commit()

    if was_pending:
        for item in get_order_items(session, order.id):
            catalog.adjust_inventory(item.sku, -item.quantity)

    return {
        "received": True,
        "handled": True,
        "type": event.type,
        "order_id": str(order_id),
        "stripe_payment_intent_id": order.stripe_payment_intent_id,
    }

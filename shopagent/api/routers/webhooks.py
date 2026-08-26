"""Stripe webhook handlers for async payment events."""

from __future__ import annotations

from uuid import UUID

import stripe
from fastapi import APIRouter, HTTPException, Request

from shopagent.api.models import Order, OrderStatus
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

    order_id = UUID(event.data.object.metadata["order_id"])
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

    payment_intent_id = _payment_intent_id(event)
    if payment_intent_id and not order.stripe_payment_intent_id:
        order.stripe_payment_intent_id = payment_intent_id

    order.status = OrderStatus.paid
    session.add(order)
    session.commit()

    return {
        "received": True,
        "handled": True,
        "type": event.type,
        "order_id": str(order_id),
        "stripe_payment_intent_id": order.stripe_payment_intent_id,
    }

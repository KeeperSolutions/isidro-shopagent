"""Stripe webhook handlers for async payment events."""

from __future__ import annotations

import os
from uuid import UUID

import stripe
from fastapi import APIRouter, HTTPException, Request

from shopagent.api.models import Order, OrderStatus
from shopagent.db import SessionDep

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

HANDLED_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "payment_intent.succeeded",
    }
)


def _webhook_secret() -> str:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET is not set")
    return secret


def _stripe_secret_key() -> str:
    secret = os.getenv("STRIPE_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY is not set")
    return secret


@router.post("/stripe")
async def stripe_webhook(request: Request, session: SessionDep):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    client = stripe.StripeClient(_stripe_secret_key())
    try:
        event = client.construct_event(payload, signature, _webhook_secret())
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

    order.status = OrderStatus.paid
    session.add(order)
    session.commit()

    return {
        "received": True,
        "handled": True,
        "type": event.type,
        "order_id": str(order_id),
    }

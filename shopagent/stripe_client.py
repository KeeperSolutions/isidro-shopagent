"""Shared Stripe client and env helpers for the HTTP API."""

from __future__ import annotations

import os

import stripe
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()


def get_stripe_secret_key() -> str:
    secret = os.getenv("STRIPE_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY is not set")
    return secret


def get_stripe_webhook_secret() -> str:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET is not set")
    return secret


def get_stripe_client() -> stripe.StripeClient:
    return stripe.StripeClient(get_stripe_secret_key())

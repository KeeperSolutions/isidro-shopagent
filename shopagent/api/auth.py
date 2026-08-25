from __future__ import annotations

import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlmodel import select

from shopagent.api.models import ApiKey
from shopagent.db import SessionDep

API_KEY_HEADER = "X-API-Key"


def generate_api_key() -> str:
    return "sa_" + secrets.token_urlsafe(32)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def get_current_api_key(
    session: SessionDep,
    raw_key: str | None = Security(
        APIKeyHeader(name=API_KEY_HEADER, auto_error=False)
    ),
) -> ApiKey:
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    api_key = session.exec(
        select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw_key))
    ).first()
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return api_key


ApiKeyDep = Annotated[ApiKey, Depends(get_current_api_key)]

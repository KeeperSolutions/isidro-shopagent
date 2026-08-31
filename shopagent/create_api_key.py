"""Generate an API key and store only its hash in the database."""

from __future__ import annotations

from sqlmodel import Session

from shopagent.api.auth import API_KEY_HEADER, generate_api_key, hash_api_key
from shopagent.api.models import ApiKey
from shopagent.db import create_db_and_tables, engine


def create_api_key() -> str:
    create_db_and_tables()
    raw_key = generate_api_key()
    record = ApiKey(key_hash=hash_api_key(raw_key))
    with Session(engine) as session:
        session.add(record)
        session.commit()
    return raw_key


def main() -> None:
    raw_key = create_api_key()
    print("API key created. Store it now; it cannot be recovered:\n")
    print(raw_key)
    print(f"\nSend it as the {API_KEY_HEADER} header.")


if __name__ == "__main__":
    main()

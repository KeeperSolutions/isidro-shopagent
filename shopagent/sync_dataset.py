"""Upsert evals/dataset.json to a Langfuse dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from langfuse import get_client
from langfuse.api import NotFoundError

load_dotenv()

DATASET_PATH = Path(__file__).resolve().parent.parent / "evals" / "dataset.json"


def ensure_dataset(langfuse, bundle: dict) -> None:
    name = bundle["name"]
    try:
        langfuse.get_dataset(name)
    except NotFoundError:
        langfuse.create_dataset(
            name=name,
            description=bundle.get("description"),
        )


def upsert_items(langfuse, bundle: dict) -> int:
    for item in bundle["items"]:
        langfuse.create_dataset_item(
            dataset_name=bundle["name"],
            id=item["id"],
            input=item["input"],
            expected_output=item["expected_output"],
        )
    return len(bundle["items"])


def main() -> int:
    bundle = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    langfuse = get_client()
    ensure_dataset(langfuse, bundle)
    count = upsert_items(langfuse, bundle)
    langfuse.flush()
    print(f"Upserted {count} items into Langfuse dataset {bundle['name']!r}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

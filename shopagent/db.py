import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and set the Postgres URL.")
    return url


def get_connection():
    return psycopg.connect(get_database_url(), row_factory=dict_row)

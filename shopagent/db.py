import os
from typing import Annotated

import psycopg
from dotenv import load_dotenv
from fastapi import Depends
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and set the Postgres URL.")
    return url


# We need to do this due to version mismatch between psycopg and sqlalchemy
def get_sqlalchemy_database_url():
    url = make_url(get_database_url())
    if url.drivername in ("postgresql", "postgres"):
        url = url.set(drivername="postgresql+psycopg")
    return url


def get_connection():
    return psycopg.connect(get_database_url(), row_factory=dict_row)


engine = create_engine(get_sqlalchemy_database_url())


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

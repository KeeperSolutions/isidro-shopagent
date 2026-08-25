from fastapi import FastAPI

from shopagent.api.routers import cart, checkout, orders
from shopagent.db import create_db_and_tables

app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(checkout.router)


@app.get("/")
def root():
    return {"message": "ShopAgent API"}

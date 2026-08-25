from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, col, select

from shopagent.api.auth import ApiKeyDep
from shopagent.api.models import (
    ApiKey,
    Cart,
    CartStatus,
    Order,
    OrderCreate,
    OrderItem,
    OrderItemBase,
    OrderPublic,
)
from shopagent.api.routers.cart import get_cart_items, get_owned_cart
from shopagent.db import SessionDep

router = APIRouter(prefix="/orders", tags=["orders"])


def get_order_items(session: Session, order_id: UUID) -> list[OrderItem]:
    return list(
        session.exec(
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.sku)
        ).all()
    )


def get_owned_order(session: Session, order_id: UUID, api_key: ApiKey) -> Order:
    order = session.exec(
        select(Order)
        .join(Cart, col(Cart.id) == col(Order.cart_id))
        .where(Order.id == order_id, Cart.api_key_id == api_key.id)
    ).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def get_order_public(session: Session, order: Order) -> OrderPublic:
    items = [
        OrderItemBase(
            sku=item.sku,
            quantity=item.quantity,
            unit_price=item.unit_price,
            name=item.name,
            size=item.size,
            color=item.color,
        )
        for item in get_order_items(session, order.id)
    ]
    return OrderPublic(
        id=order.id,
        cart_id=order.cart_id,
        status=order.status,
        item_count=order.item_count,
        subtotal=order.subtotal,
        items=items,
    )


@router.post("")
def create_order(body: OrderCreate, session: SessionDep, api_key: ApiKeyDep):
    cart = get_owned_cart(session, body.cart_id, api_key)
    if cart.status != CartStatus.active:
        raise HTTPException(status_code=409, detail="Cart is not active")

    cart_items = get_cart_items(session, cart.id)
    item_count = sum(item.quantity for item in cart_items)
    subtotal = sum(item.unit_price * item.quantity for item in cart_items)

    order = Order(
        cart_id=cart.id,
        item_count=item_count,
        subtotal=subtotal,
    )
    session.add(order)
    session.flush()

    for item in cart_items:
        session.add(
            OrderItem(
                order_id=order.id,
                sku=item.sku,
                quantity=item.quantity,
                unit_price=item.unit_price,
                name=item.name,
                size=item.size,
                color=item.color,
            )
        )
        session.delete(item)

    cart.status = CartStatus.checked_out

    session.commit()
    session.refresh(order)

    return get_order_public(session, order)


@router.get("/{order_id}", response_model=OrderPublic)
def get_order(order_id: UUID, session: SessionDep, api_key: ApiKeyDep):
    order = get_owned_order(session, order_id, api_key)
    return get_order_public(session, order)

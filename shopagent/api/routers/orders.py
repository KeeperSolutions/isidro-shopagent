from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from shopagent.api.models import CartStatus, Order, OrderCreate, OrderItem, OrderItemBase, OrderPublic
from shopagent.api.routers.cart import get_cart_by_id, get_cart_items
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

def get_order_by_id(session: Session, order_id: UUID) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

def get_order_public(session: Session, order_id: UUID) -> OrderPublic:
    order = get_order_by_id(session, order_id)
    items = [OrderItemBase(
        sku=item.sku,
        quantity=item.quantity,
        unit_price=item.unit_price,
        name=item.name,
        size=item.size,
        color=item.color,
    ) for item in get_order_items(session, order_id)]
    return OrderPublic(
        id=order.id,
        cart_id=order.cart_id,
        status=order.status,
        item_count=order.item_count,
        subtotal=order.subtotal,
        items=items,
    )


@router.post("")
def create_order(body: OrderCreate, session: SessionDep):
    cart = get_cart_by_id(session, body.cart_id)
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

    return get_order_public(session, order.id)


@router.get("/{order_id}", response_model=OrderPublic)
def get_order(order_id: UUID, session: SessionDep):
    return get_order_public(session, order_id)

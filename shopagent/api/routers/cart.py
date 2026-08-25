from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from shopagent import catalog
from shopagent.api.auth import ApiKeyDep
from shopagent.api.models import ApiKey, Cart, CartItem, CartItemCreate, CartPublic, CartStatus
from shopagent.db import SessionDep

router = APIRouter(prefix="/cart", tags=["cart"])


def get_cart_items(session: Session, cart_id: UUID) -> list[CartItem]:
    return list(
        session.exec(
            select(CartItem)
            .where(CartItem.cart_id == cart_id)
            .order_by(CartItem.sku)
        ).all()
    )


def get_active_cart(session: Session, api_key: ApiKey) -> Cart | None:
    return session.exec(
        select(Cart).where(
            Cart.api_key_id == api_key.id,
            Cart.status == CartStatus.active,
        )
    ).first()


def get_active_cart_or_raise(session: Session, api_key: ApiKey) -> Cart:
    cart = get_active_cart(session, api_key)
    if cart is None:
        raise HTTPException(status_code=404, detail="No active cart")
    return cart

def get_owned_cart(session: Session, cart_id: UUID, api_key: ApiKey) -> Cart:
    cart = session.exec(
        select(Cart).where(
            Cart.id == cart_id,
            Cart.api_key_id == api_key.id,
        )
    ).first()
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


@router.post("")
def create_cart(session: SessionDep, api_key: ApiKeyDep):
    if get_active_cart(session, api_key) is not None:
        raise HTTPException(
            status_code=409,
            detail="An active cart already exists.",
        )

    cart = Cart(api_key_id=api_key.id)
    session.add(cart)
    session.commit()
    session.refresh(cart)
    return {"cart_id": cart.id}


@router.get("", response_model=CartPublic)
def read_active_cart(session: SessionDep, api_key: ApiKeyDep):
    cart = get_active_cart_or_raise(session, api_key)
    return CartPublic(id=cart.id, items=get_cart_items(session, cart.id))


@router.get("/{cart_id}", response_model=CartPublic)
def get_cart(cart_id: UUID, session: SessionDep, api_key: ApiKeyDep):
    cart = get_owned_cart(session, cart_id, api_key)
    return CartPublic(id=cart.id, items=get_cart_items(session, cart.id))


@router.post("/{cart_id}/items")
def add_cart_item(
    cart_id: UUID,
    cart_item: CartItemCreate,
    session: SessionDep,
    api_key: ApiKeyDep,
):
    cart = get_owned_cart(session, cart_id, api_key)
    if cart.status != CartStatus.active:
        raise HTTPException(status_code=409, detail="Cart is not active")

    variant = catalog.get_variant_by_sku(cart_item.sku)

    if variant is None:
        raise HTTPException(status_code=404, detail=f"Unknown SKU: {cart_item.sku!r}")

    item = session.get(CartItem, (cart_item.sku, cart_id))
    already_in_cart = item.quantity if item else 0

    if already_in_cart + cart_item.quantity > variant["inventory"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Only {variant['inventory']} in stock for {variant['sku']}; "
                f"cart already has {already_in_cart}."
            ),
        )

    if item is None:
        item = CartItem(
            cart_id=cart.id,
            sku=variant["sku"],
            quantity=cart_item.quantity,
            unit_price=variant["price"],
            name=variant["name"],
            size=variant["size"],
            color=variant["color"],
        )
        session.add(item)
    else:
        item.quantity += cart_item.quantity

    session.commit()
    session.refresh(item)

    return {"added": item, "items": get_cart_items(session, cart_id)}

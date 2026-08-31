from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ApiKey(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    key_hash: str = Field(max_length=64, unique=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CartStatus(str, Enum):
    active = "active"
    checked_out = "checked_out"


class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    fulfilled = "fulfilled"
    cancelled = "cancelled"
    refunded = "refunded"


# Cart Models
class CartBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)


class Cart(CartBase, table=True):
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: CartStatus = Field(default=CartStatus.active)
    api_key_id: UUID | None = Field(default=None, foreign_key="apikey.id", index=True)


# Cart Item Models
class CartItemBase(SQLModel):
    sku: str = Field(primary_key=True)
    quantity: int

class CartItem(CartItemBase, table=True):
    cart_id: UUID = Field(foreign_key="cart.id", primary_key=True)
    unit_price: float
    name: str
    size: str
    color: str


class CartItemCreate(CartItemBase):
    quantity: int = Field(default=1, ge=1)


class CartPublic(CartBase):
    items: list[CartItem]


class CartCreatePublic(SQLModel):
    cart_id: UUID


class CartItemAddPublic(SQLModel):
    added: CartItem
    items: list[CartItem]


# Order Models
class OrderBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    cart_id: UUID = Field(foreign_key="cart.id", index=True)
    status: OrderStatus = Field(default=OrderStatus.pending)
    item_count: int
    subtotal: float


class Order(OrderBase, table=True):
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stripe_payment_intent_id: str | None = Field(default=None, index=True)


class OrderItemBase(SQLModel):
    sku: str = Field(primary_key=True)
    quantity: int
    unit_price: float
    name: str
    size: str
    color: str

class OrderItem(OrderItemBase, table=True):
    order_id: UUID = Field(foreign_key="order.id", primary_key=True)


class OrderPublic(OrderBase):
    items: list[OrderItemBase]


class OrderCreate(SQLModel):
    cart_id: UUID


class CheckoutCreate(SQLModel):
    order_id: UUID


class CheckoutPublic(SQLModel):
    session_id: str
    url: str


class OrderRefundPublic(SQLModel):
    refund_id: str
    order: OrderPublic

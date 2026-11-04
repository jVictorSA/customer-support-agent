from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.modules.orders.domain.order import Order
from app.modules.orders.domain.order_item import OrderItem
from app.modules.orders.domain.order_status import OrderStatus
from app.modules.orders.domain.payment_method import (
    PaymentMethod,
)


class OrderModel(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_brl >= 0", name="total_brl_non_negative"),
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_status", "status"),
    )

    order_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            name="order_status",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    total_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(
            PaymentMethod,
            name="payment_method",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    tracking_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    estimated_delivery: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer: Mapped["CustomerModel"] = relationship(
        back_populates="orders",
    )
    items: Mapped[list["OrderItemModel"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OrderItemModel.product_id",
    )

    def to_domain(self, *, include_items: bool = False) -> Order:
        items = (
            tuple(item.to_domain() for item in self.items)
            if include_items
            else ()
        )
        return Order(
            order_id=self.order_id,
            customer_id=self.customer_id,
            order_date=self.order_date,
            status=self.status,
            total_brl=self.total_brl,
            payment_method=self.payment_method,
            tracking_code=self.tracking_code,
            estimated_delivery=self.estimated_delivery,
            notes=self.notes,
            items=items,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class OrderItemModel(TimestampMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.product_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity: Mapped[int] = mapped_column(nullable=False)

    order: Mapped[OrderModel] = relationship(back_populates="items")
    product: Mapped["ProductModel"] = relationship()

    def to_domain(self) -> OrderItem:
        product = self.__dict__.get("product")
        return OrderItem(
            product_id=self.product_id,
            quantity=self.quantity,
            product_name=product.name if product is not None else None,
        )

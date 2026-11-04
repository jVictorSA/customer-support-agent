from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.modules.products.domain.product import Product
from app.modules.products.domain.product_status import (
    ProductStatus,
)


class ProductModel(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_brl >= 0", name="price_brl_non_negative"),
        CheckConstraint(
            "stock_quantity >= 0", name="stock_quantity_non_negative"
        ),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_status", "status"),
    )

    product_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    price_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id", ondelete="RESTRICT"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock_quantity: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(
            ProductStatus,
            name="product_status",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    specs: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    category: Mapped["CategoryModel"] = relationship(
        back_populates="products",
    )
    promotions: Mapped[list["PromotionModel"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_domain(self) -> Product:
        return Product(
            product_id=self.product_id,
            price_brl=self.price_brl,
            name=self.name,
            category_id=self.category_id,
            description=self.description,
            stock_quantity=self.stock_quantity,
            status=self.status,
            specs=self.specs,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

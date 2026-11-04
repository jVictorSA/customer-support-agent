from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.modules.promotions.domain.promotion import Promotion


class PromotionModel(TimestampMixin, Base):
    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint(
            "discount_percent BETWEEN 0 AND 100",
            name="discount_percent_range",
        ),
        Index("ix_promotions_product_id", "product_id"),
        Index("ix_promotions_is_active", "is_active"),
    )

    promotion_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
    )
    discount_percent: Mapped[int] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    product: Mapped["ProductModel"] = relationship(
        back_populates="promotions",
    )

    def to_domain(self) -> Promotion:
        return Promotion(
            promotion_id=self.promotion_id,
            product_id=self.product_id,
            discount_percent=self.discount_percent,
            description=self.description,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

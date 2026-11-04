from sqlalchemy import Identity, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.modules.categories.domain.category import Category


class CategoryModel(TimestampMixin, Base):
    __tablename__ = "categories"

    category_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    products: Mapped[list["ProductModel"]] = relationship(
        back_populates="category",
        passive_deletes=True,
    )

    def to_domain(self) -> Category:
        return Category(
            category_id=self.category_id,
            name=self.name,
            description=self.description,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

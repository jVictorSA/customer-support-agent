from sqlalchemy import Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.modules.customers.domain.customer import Customer


class CustomerModel(TimestampMixin, Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)

    orders: Mapped[list["OrderModel"]] = relationship(
        back_populates="customer",
        passive_deletes=True,
    )

    def to_domain(self) -> Customer:
        return Customer(
            customer_id=self.customer_id,
            name=self.name,
            phone=self.phone,
            email=self.email,
            city=self.city,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customers.domain.customer import Customer
from app.modules.customers.infrastructure.models import (
    CustomerModel,
)


class SqlAlchemyCustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, customer: Customer) -> Customer:
        async with self._session.begin():
            values = {
                "name": customer.name,
                "phone": customer.phone,
                "email": customer.email,
                "city": customer.city,
            }
            if customer.customer_id is not None:
                values["customer_id"] = customer.customer_id
            model = CustomerModel(**values)
            if customer.created_at is not None:
                model.created_at = customer.created_at
            if customer.updated_at is not None:
                model.updated_at = customer.updated_at
            self._session.add(model)
            await self._session.flush()
            return model.to_domain()

    async def get_by_id(self, customer_id: int) -> Customer | None:
        async with self._session.begin():
            model = await self._session.get(CustomerModel, customer_id)
            return model.to_domain() if model is not None else None

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        city: str | None = None,
        name: str | None = None,
    ) -> tuple[list[Customer], int]:
        async with self._session.begin():
            filters = []
            if city:
                filters.append(CustomerModel.city.ilike(f"%{city}%"))
            if name:
                filters.append(CustomerModel.name.ilike(f"%{name}%"))

            total = await self._session.scalar(
                select(func.count())
                .select_from(CustomerModel)
                .where(*filters)
            )
            models = await self._session.scalars(
                select(CustomerModel)
                .where(*filters)
                .order_by(CustomerModel.customer_id)
                .offset(offset)
                .limit(limit)
            )
            return [model.to_domain() for model in models], int(total or 0)

    async def update(self, customer: Customer) -> Customer:
        async with self._session.begin():
            model = await self._session.get(
                CustomerModel, customer.customer_id
            )
            if model is None:
                raise ValueError("Customer does not exist")
            model.name = customer.name
            model.phone = customer.phone
            model.email = customer.email
            model.city = customer.city
            await self._session.flush()
            return model.to_domain()

    async def delete(self, customer_id: int) -> bool:
        async with self._session.begin():
            model = await self._session.get(CustomerModel, customer_id)
            if model is None:
                return False
            await self._session.delete(model)
            return True

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.orders.domain.order import Order
from app.modules.orders.domain.order_status import OrderStatus
from app.modules.orders.infrastructure.models import (
    OrderItemModel,
    OrderModel,
)


class SqlAlchemyOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, order: Order) -> Order:
        async with self._session.begin():
            values = {
                "customer_id": order.customer_id,
                "order_date": order.order_date,
                "status": order.status,
                "total_brl": order.total_brl,
                "payment_method": order.payment_method,
                "sales_channel": order.sales_channel,
                "tracking_code": order.tracking_code,
                "estimated_delivery": order.estimated_delivery,
                "delivered_at": order.delivered_at,
                "notes": order.notes,
            }
            if order.order_id is not None:
                values["order_id"] = order.order_id
            model = OrderModel(**values)
            if order.created_at is not None:
                model.created_at = order.created_at
            if order.updated_at is not None:
                model.updated_at = order.updated_at
            model.items = [
                OrderItemModel(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    is_final_sale=item.is_final_sale,
                    is_customized=item.is_customized,
                    is_hygiene_restricted=item.is_hygiene_restricted,
                )
                for item in order.items
            ]
            self._session.add(model)
            await self._session.flush()
            return await self._load_with_items(model.order_id)

    async def get_by_id(self, order_id: int) -> Order | None:
        async with self._session.begin():
            model = await self._session.scalar(self._detail_statement(order_id))
            return model.to_domain(include_items=True) if model else None

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        customer_id: int | None = None,
        status: OrderStatus | None = None,
    ) -> tuple[list[Order], int]:
        async with self._session.begin():
            filters = []
            if customer_id is not None:
                filters.append(OrderModel.customer_id == customer_id)
            if status is not None:
                filters.append(OrderModel.status == status)

            total = await self._session.scalar(
                select(func.count())
                .select_from(OrderModel)
                .where(*filters)
            )
            models = await self._session.scalars(
                select(OrderModel)
                .where(*filters)
                .order_by(
                    OrderModel.order_date.desc(),
                    OrderModel.order_id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
            return [model.to_domain() for model in models], int(total or 0)

    async def update(self, order: Order) -> Order:
        async with self._session.begin():
            model = await self._session.scalar(
                self._detail_statement(order.order_id)
            )
            if model is None:
                raise ValueError("Order does not exist")

            model.customer_id = order.customer_id
            model.order_date = order.order_date
            model.status = order.status
            model.total_brl = order.total_brl
            model.payment_method = order.payment_method
            model.sales_channel = order.sales_channel
            model.tracking_code = order.tracking_code
            model.estimated_delivery = order.estimated_delivery
            model.delivered_at = order.delivered_at
            model.notes = order.notes
            self._sync_items(model, order)

            await self._session.flush()
            updated = await self._session.scalar(
                self._detail_statement(model.order_id)
            )
            assert updated is not None
            return updated.to_domain(include_items=True)

    async def delete(self, order_id: int) -> bool:
        async with self._session.begin():
            model = await self._session.get(OrderModel, order_id)
            if model is None:
                return False
            await self._session.delete(model)
            return True

    async def _load_with_items(self, order_id: int) -> Order:
        model = await self._session.scalar(self._detail_statement(order_id))
        assert model is not None
        return model.to_domain(include_items=True)

    @staticmethod
    def _detail_statement(order_id: int):
        return (
            select(OrderModel)
            .options(
                selectinload(OrderModel.items).selectinload(
                    OrderItemModel.product
                )
            )
            .where(OrderModel.order_id == order_id)
        )

    @staticmethod
    def _sync_items(model: OrderModel, order: Order) -> None:
        existing = {item.product_id: item for item in model.items}
        incoming = {item.product_id: item for item in order.items}

        for product_id, item in existing.items():
            if product_id not in incoming:
                model.items.remove(item)

        for product_id, item in incoming.items():
            current = existing.get(product_id)
            if current is None:
                model.items.append(
                    OrderItemModel(
                        product_id=product_id,
                        quantity=item.quantity,
                        is_final_sale=item.is_final_sale,
                        is_customized=item.is_customized,
                        is_hygiene_restricted=item.is_hygiene_restricted,
                    )
                )
            else:
                current.quantity = item.quantity
                current.is_final_sale = item.is_final_sale
                current.is_customized = item.is_customized
                current.is_hygiene_restricted = item.is_hygiene_restricted

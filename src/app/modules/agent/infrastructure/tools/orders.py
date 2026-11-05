from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.agent.domain.results import (
    OrderItemSummary,
    OrderSummary,
)
from app.modules.orders.domain.order_status import OrderStatus
from app.modules.orders.infrastructure.models import (
    OrderItemModel,
    OrderModel,
)


class SqlAlchemyOrderGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_orders(
        self,
        *,
        customer_id: int,
        status: str | None,
        limit: int,
    ) -> list[OrderSummary]:
        async with self._session.begin():
            statement = (
                select(OrderModel)
                .options(
                    selectinload(OrderModel.items).selectinload(
                        OrderItemModel.product
                    )
                )
                .where(OrderModel.customer_id == customer_id)
            )
            if status:
                try:
                    statement = statement.where(
                        OrderModel.status == OrderStatus(status)
                    )
                except ValueError:
                    return []
            models = (
                await self._session.scalars(
                    statement.order_by(
                        OrderModel.order_date.desc(),
                        OrderModel.order_id.desc(),
                    ).limit(limit)
                )
            ).all()
            return [_to_summary(model) for model in models]

    async def get_order(
        self, *, customer_id: int, reference: str
    ) -> OrderSummary | None:
        async with self._session.begin():
            statement = self._statement(customer_id)
            try:
                order_id = int(reference)
            except ValueError:
                return None
            model = await self._session.scalar(
                statement.where(OrderModel.order_id == order_id)
            )
            return _to_summary(model) if model is not None else None

    async def get_order_by_tracking(
        self, *, customer_id: int, tracking_code: str
    ) -> OrderSummary | None:
        async with self._session.begin():
            model = await self._session.scalar(
                self._statement(customer_id).where(
                    OrderModel.tracking_code.ilike(tracking_code.strip())
                )
            )
            return _to_summary(model) if model is not None else None

    @staticmethod
    def _statement(customer_id: int):
        return (
            select(OrderModel)
            .options(
                selectinload(OrderModel.items).selectinload(
                    OrderItemModel.product
                )
            )
            .where(OrderModel.customer_id == customer_id)
        )


def _to_summary(model: OrderModel) -> OrderSummary:
    return OrderSummary(
        order_id=model.order_id,
        status=model.status.value,
        total_brl=float(model.total_brl),
        payment_method=model.payment_method.value,
        order_date=model.order_date.isoformat(),
        sales_channel=(
            model.sales_channel.value
            if model.sales_channel is not None
            else None
        ),
        tracking_code=model.tracking_code,
        estimated_delivery=(
            model.estimated_delivery.isoformat()
            if model.estimated_delivery is not None
            else None
        ),
        delivered_at=(
            model.delivered_at.isoformat()
            if model.delivered_at is not None
            else None
        ),
        items=tuple(
            OrderItemSummary(
                product_id=item.product_id,
                product_name=(
                    item.product.name
                    if item.__dict__.get("product") is not None
                    else None
                ),
                quantity=item.quantity,
                is_final_sale=item.is_final_sale,
                is_customized=item.is_customized,
                is_hygiene_restricted=item.is_hygiene_restricted,
            )
            for item in model.items
        ),
    )

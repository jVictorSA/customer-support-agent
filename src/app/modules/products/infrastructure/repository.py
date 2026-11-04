from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.domain.product import Product
from app.modules.products.domain.product_status import (
    ProductStatus,
)
from app.modules.products.infrastructure.models import (
    ProductModel,
)


class SqlAlchemyProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, product: Product) -> Product:
        async with self._session.begin():
            model = self._build_model(product)
            self._session.add(model)
            await self._session.flush()
            return model.to_domain()

    async def get_by_id(self, product_id: int) -> Product | None:
        async with self._session.begin():
            model = await self._session.get(ProductModel, product_id)
            return model.to_domain() if model is not None else None

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        category_id: int | None = None,
        status: ProductStatus | None = None,
        name: str | None = None,
        max_price: Decimal | None = None,
    ) -> tuple[list[Product], int]:
        async with self._session.begin():
            filters = []
            if category_id is not None:
                filters.append(ProductModel.category_id == category_id)
            if status is not None:
                filters.append(ProductModel.status == status)
            if name:
                filters.append(ProductModel.name.ilike(f"%{name}%"))
            if max_price is not None:
                filters.append(ProductModel.price_brl <= max_price)

            total = await self._session.scalar(
                select(func.count())
                .select_from(ProductModel)
                .where(*filters)
            )
            models = await self._session.scalars(
                select(ProductModel)
                .where(*filters)
                .order_by(ProductModel.product_id)
                .offset(offset)
                .limit(limit)
            )
            return [model.to_domain() for model in models], int(total or 0)

    async def update(self, product: Product) -> Product:
        async with self._session.begin():
            model = await self._session.get(ProductModel, product.product_id)
            if model is None:
                raise ValueError("Product does not exist")
            model.price_brl = product.price_brl
            model.name = product.name
            model.category_id = product.category_id
            model.description = product.description
            model.stock_quantity = product.stock_quantity
            model.status = product.status
            model.specs = product.specs
            await self._session.flush()
            return model.to_domain()

    async def delete(self, product_id: int) -> bool:
        async with self._session.begin():
            model = await self._session.get(ProductModel, product_id)
            if model is None:
                return False
            await self._session.delete(model)
            return True

    def _build_model(self, product: Product) -> ProductModel:
        values = {
            "price_brl": product.price_brl,
            "name": product.name,
            "category_id": product.category_id,
            "description": product.description,
            "stock_quantity": product.stock_quantity,
            "status": product.status,
            "specs": product.specs,
        }
        if product.product_id is not None:
            values["product_id"] = product.product_id
        model = ProductModel(**values)
        if product.created_at is not None:
            model.created_at = product.created_at
        if product.updated_at is not None:
            model.updated_at = product.updated_at
        return model

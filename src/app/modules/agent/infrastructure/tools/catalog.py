from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.agent.domain.results import (
    CatalogItem,
    CatalogPromotion,
)
from app.modules.categories.infrastructure.models import CategoryModel
from app.modules.products.domain.product_status import ProductStatus
from app.modules.products.infrastructure.models import ProductModel


class SqlAlchemyCatalogGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_catalog(
        self,
        *,
        query: str | None,
        category: str | None,
        min_price: float | None,
        max_price: float | None,
        only_in_stock: bool,
        limit: int,
    ) -> list[CatalogItem]:
        async with self._session.begin():
            statement = (
                select(ProductModel, CategoryModel)
                .join(
                    CategoryModel,
                    CategoryModel.category_id == ProductModel.category_id,
                )
                .options(selectinload(ProductModel.promotions))
                .where(ProductModel.status == ProductStatus.ACTIVE)
            )
            if query:
                pattern = f"%{query}%"
                statement = statement.where(
                    or_(
                        ProductModel.name.ilike(pattern),
                        ProductModel.description.ilike(pattern),
                        CategoryModel.name.ilike(pattern),
                    )
                )
            if category:
                statement = statement.where(
                    CategoryModel.name.ilike(f"%{category}%")
                )
            if min_price is not None:
                statement = statement.where(
                    ProductModel.price_brl >= Decimal(str(min_price))
                )
            if max_price is not None:
                statement = statement.where(
                    ProductModel.price_brl <= Decimal(str(max_price))
                )
            if only_in_stock:
                statement = statement.where(ProductModel.stock_quantity > 0)

            rows = (
                await self._session.execute(
                    statement.order_by(ProductModel.price_brl)
                    .limit(limit)
                )
            ).all()
            return [
                _to_item(product, category.name)
                for product, category in rows
            ]

    async def get_product(self, reference: str) -> CatalogItem | None:
        async with self._session.begin():
            statement = (
                select(ProductModel, CategoryModel)
                .join(
                    CategoryModel,
                    CategoryModel.category_id == ProductModel.category_id,
                )
                .options(selectinload(ProductModel.promotions))
            )
            try:
                product_id = int(reference)
            except ValueError:
                product_id = None
            if product_id is not None:
                row = (
                    await self._session.execute(
                        statement.where(ProductModel.product_id == product_id)
                    )
                ).first()
            else:
                row = (
                    await self._session.execute(
                        statement.where(
                            ProductModel.name.ilike(f"%{reference}%")
                        )
                        .order_by(ProductModel.product_id)
                        .limit(1)
                    )
                ).first()
            if row is None:
                return None
            product, category = row
            return _to_item(product, category.name)


def _to_item(product: ProductModel, category_name: str) -> CatalogItem:
    active = [
        promotion
        for promotion in product.promotions
        if promotion.is_active
    ]
    discount = max(
        (promotion.discount_percent for promotion in active), default=0
    )
    effective = product.price_brl
    if discount > 0:
        effective = product.price_brl * (
            Decimal("1") - Decimal(discount) / Decimal("100")
        )
    return CatalogItem(
        product_id=product.product_id,
        name=product.name,
        category=category_name,
        price_brl=float(product.price_brl),
        effective_price_brl=round(float(effective), 2),
        stock_quantity=product.stock_quantity,
        status=product.status.value,
        description=product.description,
        promotions=tuple(
            CatalogPromotion(
                promotion_id=promotion.promotion_id,
                discount_percent=promotion.discount_percent,
                description=promotion.description,
            )
            for promotion in active
        ),
        specs=product.specs,
    )

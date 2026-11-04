"""Central metadata module used by Alembic.

Import the ORM models from each module here so ``Base.metadata`` contains every
table when Alembic runs ``--autogenerate``.
"""

from app.db.base import Base
from app.modules.categories.infrastructure.models import (
    CategoryModel,
)
from app.modules.customers.infrastructure.models import (
    CustomerModel,
)
from app.modules.orders.infrastructure.models import (
    OrderItemModel,
    OrderModel,
)
from app.modules.products.infrastructure.models import (
    ProductModel,
)
from app.modules.promotions.infrastructure.models import (
    PromotionModel,
)

__all__ = [
    "Base",
    "CategoryModel",
    "CustomerModel",
    "OrderItemModel",
    "OrderModel",
    "ProductModel",
    "PromotionModel",
]

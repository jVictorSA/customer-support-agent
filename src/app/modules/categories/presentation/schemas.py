from datetime import datetime

from pydantic import BaseModel

from app.modules.categories.domain.category import Category


class CategoryResponse(BaseModel):
    category_id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, category: Category) -> "CategoryResponse":
        assert category.category_id is not None
        assert category.created_at is not None
        assert category.updated_at is not None
        return cls(
            category_id=category.category_id,
            name=category.name,
            description=category.description,
            created_at=category.created_at,
            updated_at=category.updated_at,
        )

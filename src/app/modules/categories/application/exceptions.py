from app.core.exceptions import NotFoundError


class CategoryNotFoundError(NotFoundError):
    code = "category_not_found"
    message = "Category not found"

    def __init__(self, category_id: int) -> None:
        super().__init__(f"Category {category_id} not found")

from sqlalchemy.types import UserDefinedType


class Ltree(UserDefinedType[str]):
    """Minimal SQLAlchemy type for PostgreSQL ``ltree`` values."""

    cache_ok = True

    def get_col_spec(self, **_: object) -> str:
        return "ltree"

    def bind_processor(self, dialect: object):
        def process(value: str | None) -> str | None:
            return value

        return process

    def result_processor(self, dialect: object, coltype: object):
        def process(value: str | None) -> str | None:
            return value

        return process

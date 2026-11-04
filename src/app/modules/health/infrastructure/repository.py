from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyHealthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(self) -> None:
        async with self._session.begin():
            await self._session.execute(text("SELECT 1"))

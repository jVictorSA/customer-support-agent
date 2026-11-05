from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversations.domain.conversation import Conversation
from app.modules.conversations.infrastructure.models import (
    ConversationModel,
)


class SqlAlchemyConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation: Conversation) -> Conversation:
        async with self._session.begin():
            model = ConversationModel(
                public_id=conversation.public_id,
                customer_id=conversation.customer_id,
                status=conversation.status,
                awaiting_human=conversation.awaiting_human,
            )
            self._session.add(model)
            await self._session.flush()
            return model.to_domain()

    async def get_by_public_id(
        self, public_id: UUID, *, customer_id: int
    ) -> Conversation | None:
        async with self._session.begin():
            model = await self._session.scalar(
                select(ConversationModel).where(
                    ConversationModel.public_id == public_id,
                    ConversationModel.customer_id == customer_id,
                )
            )
            return model.to_domain() if model is not None else None

    async def get_by_id(
        self, conversation_id: int
    ) -> Conversation | None:
        async with self._session.begin():
            model = await self._session.get(
                ConversationModel, conversation_id
            )
            return model.to_domain() if model is not None else None

    async def list_by_customer(
        self, *, customer_id: int, offset: int, limit: int
    ) -> tuple[list[Conversation], int]:
        async with self._session.begin():
            filters = [ConversationModel.customer_id == customer_id]
            total = await self._session.scalar(
                select(func.count())
                .select_from(ConversationModel)
                .where(*filters)
            )
            models = await self._session.scalars(
                select(ConversationModel)
                .where(*filters)
                .order_by(
                    ConversationModel.created_at.desc(),
                    ConversationModel.conversation_id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
            return [model.to_domain() for model in models], int(total or 0)

    async def mark_awaiting_human(
        self, conversation_id: int, *, awaiting: bool = True
    ) -> None:
        async with self._session.begin():
            model = await self._session.get(
                ConversationModel, conversation_id
            )
            if model is None:
                return
            model.awaiting_human = awaiting
            await self._session.flush()

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.messages.application.exceptions import (
    ClientMessageIdConflictError,
    ConversationBusyError,
)
from app.modules.messages.domain.message import Message
from app.modules.messages.domain.message_enums import (
    DeliveryStatus,
    MessageRole,
    MessageStatus,
)
from app.modules.messages.infrastructure.models import MessageModel


class SqlAlchemyMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_user_message(
        self, message: Message, *, stale_after_seconds: int
    ) -> Message:
        async with self._session.begin():
            if message.client_message_id is not None:
                existing = await self._session.scalar(
                    select(MessageModel).where(
                        MessageModel.conversation_id
                        == message.conversation_id,
                        MessageModel.client_message_id
                        == message.client_message_id,
                    )
                )
                if existing is not None:
                    if existing.content != message.content:
                        raise ClientMessageIdConflictError()
                    return existing.to_domain()

            cutoff = datetime.now(UTC) - timedelta(
                seconds=stale_after_seconds
            )
            inflight = await self._session.scalar(
                select(MessageModel.message_id)
                .where(
                    MessageModel.conversation_id == message.conversation_id,
                    MessageModel.role == MessageRole.USER,
                    or_(
                        MessageModel.status == MessageStatus.QUEUED,
                        and_(
                            MessageModel.status == MessageStatus.PROCESSING,
                            MessageModel.processing_started_at >= cutoff,
                        ),
                    ),
                )
                .limit(1)
            )
            if inflight is not None:
                raise ConversationBusyError()

            model = MessageModel(
                public_id=message.public_id,
                conversation_id=message.conversation_id,
                role=message.role,
                content=message.content,
                status=message.status,
                client_message_id=message.client_message_id,
                webhook_url=message.webhook_url,
                delivery_status=message.delivery_status,
                metadata_=message.metadata,
            )
            self._session.add(model)
            await self._session.flush()
            return model.to_domain()

    async def get_by_public_id(
        self, public_id: UUID, *, conversation_id: int
    ) -> Message | None:
        async with self._session.begin():
            model = await self._session.scalar(
                select(MessageModel)
                .options(selectinload(MessageModel.reply_to))
                .where(
                    MessageModel.public_id == public_id,
                    MessageModel.conversation_id == conversation_id,
                )
            )
            return model.to_domain() if model is not None else None

    async def get_by_id(self, message_id: int) -> Message | None:
        async with self._session.begin():
            model = await self._session.scalar(
                select(MessageModel)
                .options(selectinload(MessageModel.reply_to))
                .where(MessageModel.message_id == message_id)
            )
            return model.to_domain() if model is not None else None

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        offset: int,
        limit: int,
        after_message_id: int | None = None,
    ) -> tuple[list[Message], int]:
        async with self._session.begin():
            filters = [MessageModel.conversation_id == conversation_id]
            if after_message_id is not None:
                filters.append(MessageModel.message_id > after_message_id)

            total = await self._session.scalar(
                select(func.count())
                .select_from(MessageModel)
                .where(*filters)
            )
            models = await self._session.scalars(
                select(MessageModel)
                .options(selectinload(MessageModel.reply_to))
                .where(*filters)
                .order_by(MessageModel.message_id)
                .offset(offset)
                .limit(limit)
            )
            return [model.to_domain() for model in models], int(total or 0)

    async def get_history(
        self, conversation_id: int, *, limit: int
    ) -> list[Message]:
        async with self._session.begin():
            models = (
                await self._session.scalars(
                    select(MessageModel)
                    .where(
                        MessageModel.conversation_id == conversation_id,
                        MessageModel.role.in_(
                            [MessageRole.USER, MessageRole.ASSISTANT]
                        ),
                        MessageModel.status == MessageStatus.COMPLETED,
                    )
                    .order_by(MessageModel.message_id.desc())
                    .limit(limit)
                )
            ).all()
            return [model.to_domain() for model in reversed(models)]

    async def claim_for_processing(
        self, message_id: int, *, stale_after_seconds: int
    ) -> Message | None:
        async with self._session.begin():
            model = await self._session.scalar(
                select(MessageModel)
                .where(MessageModel.message_id == message_id)
                .with_for_update()
            )
            if model is None or model.role is not MessageRole.USER:
                return None
            cutoff = datetime.now(UTC) - timedelta(
                seconds=stale_after_seconds
            )
            claimable = model.status is MessageStatus.QUEUED or (
                model.status is MessageStatus.PROCESSING
                and model.processing_started_at is not None
                and model.processing_started_at < cutoff
            )
            if not claimable:
                return None
            model.status = MessageStatus.PROCESSING
            model.processing_started_at = datetime.now(UTC)
            model.error_code = None
            await self._session.flush()
            return model.to_domain()

    async def append_assistant_and_complete(
        self, *, user_message_id: int, assistant: Message
    ) -> Message:
        async with self._session.begin():
            user = await self._session.get(MessageModel, user_message_id)
            if user is None:
                raise ValueError("User message does not exist")

            model = MessageModel(
                public_id=assistant.public_id,
                conversation_id=user.conversation_id,
                role=MessageRole.ASSISTANT,
                content=assistant.content,
                status=MessageStatus.COMPLETED,
                reply_to_message_id=user.message_id,
                delivery_status=assistant.delivery_status,
                metadata_=assistant.metadata,
            )
            self._session.add(model)

            user.status = MessageStatus.COMPLETED
            user.processed_at = datetime.now(UTC)
            user.error_code = None

            await self._session.flush()
            domain = model.to_domain()
            return replace(domain, reply_to_public_id=user.public_id)

    async def mark_failed(
        self, message_id: int, *, error_code: str
    ) -> None:
        async with self._session.begin():
            model = await self._session.get(MessageModel, message_id)
            if model is None:
                return
            model.status = MessageStatus.FAILED
            model.error_code = error_code
            model.processed_at = datetime.now(UTC)
            await self._session.flush()

    async def release_for_retry(self, message_id: int) -> None:
        async with self._session.begin():
            model = await self._session.get(MessageModel, message_id)
            if model is None:
                return
            model.status = MessageStatus.QUEUED
            model.processing_started_at = None
            await self._session.flush()

    async def update_delivery(
        self,
        message_id: int,
        *,
        status: str,
        attempts: int,
        error_code: str | None,
        delivered_at: datetime | None,
    ) -> None:
        async with self._session.begin():
            model = await self._session.get(MessageModel, message_id)
            if model is None:
                return
            model.delivery_status = DeliveryStatus(status)
            model.delivery_attempts = attempts
            model.last_delivery_error_code = error_code
            model.delivered_at = delivered_at
            await self._session.flush()

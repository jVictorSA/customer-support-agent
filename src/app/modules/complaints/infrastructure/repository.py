from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.complaints.domain.complaint import Complaint
from app.modules.complaints.domain.complaint_enums import ComplaintStatus
from app.modules.complaints.infrastructure.models import ComplaintModel


class SqlAlchemyComplaintRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, complaint: Complaint) -> Complaint:
        async with self._session.begin():
            model = ComplaintModel(
                public_id=complaint.public_id,
                conversation_id=complaint.conversation_id,
                customer_id=complaint.customer_id,
                message_id=complaint.message_id,
                order_id=complaint.order_id,
                category=complaint.category,
                description=complaint.description,
                priority=complaint.priority,
                status=complaint.status,
            )
            self._session.add(model)
            await self._session.flush()
            return model.to_domain()

    async def get_open_by_conversation(
        self, conversation_id: int
    ) -> Complaint | None:
        async with self._session.begin():
            model = await self._session.scalar(
                select(ComplaintModel)
                .where(
                    ComplaintModel.conversation_id == conversation_id,
                    ComplaintModel.status == ComplaintStatus.OPEN,
                )
                .order_by(ComplaintModel.complaint_id.desc())
                .limit(1)
            )
            return model.to_domain() if model is not None else None

    async def get_by_public_id(
        self, public_id: UUID, *, customer_id: int
    ) -> Complaint | None:
        async with self._session.begin():
            model = await self._session.scalar(
                select(ComplaintModel).where(
                    ComplaintModel.public_id == public_id,
                    ComplaintModel.customer_id == customer_id,
                )
            )
            return model.to_domain() if model is not None else None

    async def list_by_customer(
        self,
        *,
        customer_id: int,
        offset: int,
        limit: int,
        status: ComplaintStatus | None = None,
    ) -> tuple[list[Complaint], int]:
        async with self._session.begin():
            filters = [ComplaintModel.customer_id == customer_id]
            if status is not None:
                filters.append(ComplaintModel.status == status)

            total = await self._session.scalar(
                select(func.count())
                .select_from(ComplaintModel)
                .where(*filters)
            )
            models = await self._session.scalars(
                select(ComplaintModel)
                .where(*filters)
                .order_by(
                    ComplaintModel.created_at.desc(),
                    ComplaintModel.complaint_id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
            return [model.to_domain() for model in models], int(total or 0)

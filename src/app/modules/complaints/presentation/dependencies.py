from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.complaints.application.get_complaint import (
    GetComplaintUseCase,
)
from app.modules.complaints.application.interfaces import (
    ComplaintRepository,
)
from app.modules.complaints.application.list_complaints import (
    ListComplaintsUseCase,
)
from app.modules.complaints.infrastructure.repository import (
    SqlAlchemyComplaintRepository,
)


def get_complaint_repository(
    session: AsyncSession = Depends(get_session),
) -> ComplaintRepository:
    return SqlAlchemyComplaintRepository(session)


def get_list_complaints_use_case(
    repository: ComplaintRepository = Depends(get_complaint_repository),
) -> ListComplaintsUseCase:
    return ListComplaintsUseCase(repository)


def get_get_complaint_use_case(
    repository: ComplaintRepository = Depends(get_complaint_repository),
) -> GetComplaintUseCase:
    return GetComplaintUseCase(repository)

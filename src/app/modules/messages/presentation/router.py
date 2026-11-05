from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.modules.auth.domain.identity import CustomerIdentity
from app.modules.auth.presentation.dependencies import get_current_identity
from app.modules.messages.application.list_messages import (
    ListMessagesUseCase,
)
from app.modules.messages.application.submit_message import (
    SubmitMessageUseCase,
)
from app.modules.messages.presentation.dependencies import (
    get_list_messages_use_case,
    get_submit_message_use_case,
)
from app.modules.messages.presentation.schemas import (
    MessageResponse,
    SubmitMessageRequest,
)
from app.presentation.pagination import Page, PaginationParams

router = APIRouter(prefix="/conversations", tags=["Messages"])


@router.post(
    "/{public_id}/messages",
    response_model=MessageResponse,
    status_code=202,
)
async def submit_message(
    public_id: UUID,
    payload: SubmitMessageRequest,
    customer: CustomerIdentity = Depends(get_current_identity),
    use_case: SubmitMessageUseCase = Depends(
        get_submit_message_use_case
    ),
) -> MessageResponse:
    message = await use_case.execute(
        conversation_public_id=public_id,
        customer_id=customer.customer_id,
        content=payload.content,
        webhook_url=payload.webhook_url,
        client_message_id=payload.client_message_id,
    )
    return MessageResponse.from_domain(
        message, conversation_public_id=public_id
    )


@router.get(
    "/{public_id}/messages",
    response_model=Page[MessageResponse],
)
async def list_messages(
    public_id: UUID,
    pagination: PaginationParams = Depends(),
    after_message_id: UUID | None = Query(None),
    customer: CustomerIdentity = Depends(get_current_identity),
    use_case: ListMessagesUseCase = Depends(get_list_messages_use_case),
) -> Page[MessageResponse]:
    messages, total = await use_case.execute(
        public_id,
        customer_id=customer.customer_id,
        page=pagination.page,
        page_size=pagination.page_size,
        after_message_id=after_message_id,
    )
    return Page(
        items=[
            MessageResponse.from_domain(
                message, conversation_public_id=public_id
            )
            for message in messages
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )

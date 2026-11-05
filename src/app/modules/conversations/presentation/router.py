from uuid import UUID

from fastapi import APIRouter, Depends

from app.modules.auth.domain.identity import CustomerIdentity
from app.modules.auth.presentation.dependencies import get_current_identity
from app.modules.conversations.application.create_conversation import (
    CreateConversationUseCase,
)
from app.modules.conversations.application.get_conversation import (
    GetConversationUseCase,
)
from app.modules.conversations.application.list_conversations import (
    ListConversationsUseCase,
)
from app.modules.conversations.presentation.dependencies import (
    get_create_conversation_use_case,
    get_get_conversation_use_case,
    get_list_conversations_use_case,
)
from app.modules.conversations.presentation.schemas import (
    ConversationResponse,
)
from app.presentation.pagination import Page, PaginationParams

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    customer: CustomerIdentity = Depends(get_current_identity),
    use_case: CreateConversationUseCase = Depends(
        get_create_conversation_use_case
    ),
) -> ConversationResponse:
    conversation = await use_case.execute(customer_id=customer.customer_id)
    return ConversationResponse.from_domain(conversation)


@router.get("", response_model=Page[ConversationResponse])
async def list_conversations(
    pagination: PaginationParams = Depends(),
    customer: CustomerIdentity = Depends(get_current_identity),
    use_case: ListConversationsUseCase = Depends(
        get_list_conversations_use_case
    ),
) -> Page[ConversationResponse]:
    conversations, total = await use_case.execute(
        customer_id=customer.customer_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page(
        items=[
            ConversationResponse.from_domain(conversation)
            for conversation in conversations
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{public_id}", response_model=ConversationResponse)
async def get_conversation(
    public_id: UUID,
    customer: CustomerIdentity = Depends(get_current_identity),
    use_case: GetConversationUseCase = Depends(
        get_get_conversation_use_case
    ),
) -> ConversationResponse:
    conversation = await use_case.execute(
        public_id, customer_id=customer.customer_id
    )
    return ConversationResponse.from_domain(conversation)

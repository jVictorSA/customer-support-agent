import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.complaints.application.register_complaint import (
    RegisterComplaintUseCase,
)
from app.modules.complaints.domain.complaint_enums import ComplaintCategory
from app.modules.complaints.infrastructure.handoff import (
    RepositoryConversationHandoff,
)
from app.modules.complaints.infrastructure.repository import (
    SqlAlchemyComplaintRepository,
)
from app.modules.conversations.domain.conversation import Conversation
from app.modules.conversations.infrastructure.repository import (
    SqlAlchemyConversationRepository,
)
from app.modules.customers.domain.customer import Customer
from app.modules.customers.infrastructure.repository import (
    SqlAlchemyCustomerRepository,
)
from app.modules.messages.application.exceptions import (
    ClientMessageIdConflictError,
    ConversationBusyError,
)
from app.modules.messages.domain.message import Message
from app.modules.messages.domain.message_enums import (
    MessageRole,
    MessageStatus,
)
from app.modules.messages.infrastructure.repository import (
    SqlAlchemyMessageRepository,
)
from app.modules.agent.domain.trace import TraceStep
from app.modules.agent.infrastructure.trace.repository import (
    SqlAlchemyTraceRepository,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to run integration tests",
    ),
]


async def _customer(session) -> Customer:
    return await SqlAlchemyCustomerRepository(session).create(
        Customer(
            customer_id=None,
            name="Lucas",
            phone="(67) 99812-3456",
            email="lucas@example.com",
            city="Campo Grande",
        )
    )


async def test_conversation_message_complaint_and_trace(
    integration_session,
) -> None:
    session = integration_session
    customer = await _customer(session)
    conversations = SqlAlchemyConversationRepository(session)
    messages = SqlAlchemyMessageRepository(session)

    conversation = await conversations.create(
        Conversation(
            conversation_id=None,
            public_id=uuid4(),
            customer_id=customer.customer_id,
        )
    )
    assert conversation.conversation_id is not None

    user_message = await messages.create_user_message(
        Message(
            message_id=None,
            public_id=uuid4(),
            conversation_id=conversation.conversation_id,
            role=MessageRole.USER,
            content="Quais violões até R$1000?",
            status=MessageStatus.QUEUED,
            client_message_id="client-1",
            webhook_url="https://example.com/hook",
        ),
        stale_after_seconds=900,
    )
    assert user_message.status is MessageStatus.QUEUED

    claimed = await messages.claim_for_processing(
        user_message.message_id, stale_after_seconds=900
    )
    assert claimed is not None
    assert claimed.status is MessageStatus.PROCESSING

    assistant = await messages.append_assistant_and_complete(
        user_message_id=user_message.message_id,
        assistant=Message(
            message_id=None,
            public_id=uuid4(),
            conversation_id=conversation.conversation_id,
            role=MessageRole.ASSISTANT,
            content="Temos o Yamaha C40 por R$ 599,90.",
            status=MessageStatus.COMPLETED,
        ),
    )
    assert assistant.reply_to_public_id == user_message.public_id

    history = await messages.get_history(
        conversation.conversation_id, limit=10
    )
    assert [message.role for message in history] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]

    listed, total = await messages.list_by_conversation(
        conversation.conversation_id, offset=0, limit=10
    )
    assert total == 2
    assert listed[-1].public_id == assistant.public_id

    complaints = SqlAlchemyComplaintRepository(session)
    register = RegisterComplaintUseCase(
        repository=complaints,
        handoff=RepositoryConversationHandoff(conversations),
    )
    result = await register.execute(
        conversation_id=conversation.conversation_id,
        customer_id=customer.customer_id,
        message_id=user_message.message_id,
        order_id=None,
        category=ComplaintCategory.DELIVERY,
        description="Pedido atrasado",
    )
    assert result.already_open is False
    second = await register.execute(
        conversation_id=conversation.conversation_id,
        customer_id=customer.customer_id,
        message_id=user_message.message_id,
        order_id=None,
        category=ComplaintCategory.DELIVERY,
        description="Outra",
    )
    assert second.already_open is True
    refreshed = await conversations.get_by_id(
        conversation.conversation_id
    )
    assert refreshed is not None
    assert refreshed.awaiting_human is True

    traces = SqlAlchemyTraceRepository(session)
    run_id = await traces.start_run(
        conversation_id=conversation.conversation_id,
        customer_id=customer.customer_id,
        user_message_id=user_message.message_id,
        intent=None,
        prompt_version="test",
        model="test-model",
    )
    await traces.append_step(
        run_id,
        TraceStep(
            step_index=0,
            agent_name="intent",
            step_type="llm_call",
            input={"messages": []},
            output={"content": "{}"},
            prompt_tokens=10,
            completion_tokens=5,
        ),
    )
    await traces.finish_run(
        run_id,
        status="completed",
        input_tokens=10,
        output_tokens=5,
        fallback_used=False,
        error_code=None,
        assistant_message_id=assistant.message_id,
    )


async def test_message_idempotency_and_busy_state(integration_session) -> None:
    session = integration_session
    customer = await _customer(session)
    conversations = SqlAlchemyConversationRepository(session)
    messages = SqlAlchemyMessageRepository(session)

    conversation = await conversations.create(
        Conversation(
            conversation_id=None,
            public_id=uuid4(),
            customer_id=customer.customer_id,
        )
    )
    first = await messages.create_user_message(
        Message(
            message_id=None,
            public_id=uuid4(),
            conversation_id=conversation.conversation_id,
            role=MessageRole.USER,
            content="Oi",
            status=MessageStatus.QUEUED,
            client_message_id="same",
        ),
        stale_after_seconds=900,
    )
    duplicate = await messages.create_user_message(
        Message(
            message_id=None,
            public_id=uuid4(),
            conversation_id=conversation.conversation_id,
            role=MessageRole.USER,
            content="Oi",
            status=MessageStatus.QUEUED,
            client_message_id="same",
        ),
        stale_after_seconds=900,
    )
    assert duplicate.public_id == first.public_id

    with pytest.raises(ConversationBusyError):
        await messages.create_user_message(
            Message(
                message_id=None,
                public_id=uuid4(),
                conversation_id=conversation.conversation_id,
                role=MessageRole.USER,
                content="Outra",
                status=MessageStatus.QUEUED,
                client_message_id="other",
            ),
            stale_after_seconds=900,
        )

    with pytest.raises(ClientMessageIdConflictError):
        await messages.create_user_message(
            Message(
                message_id=None,
                public_id=uuid4(),
                conversation_id=conversation.conversation_id,
                role=MessageRole.USER,
                content="Conteúdo diferente",
                status=MessageStatus.QUEUED,
                client_message_id="same",
            ),
            stale_after_seconds=900,
        )


async def test_ownership_filters(integration_session) -> None:
    session = integration_session
    customer = await _customer(session)
    other = await SqlAlchemyCustomerRepository(session).create(
        Customer(
            customer_id=None,
            name="Ana",
            phone="(67) 99999-0000",
            email="ana@example.com",
            city="Campo Grande",
        )
    )
    conversations = SqlAlchemyConversationRepository(session)
    conversation = await conversations.create(
        Conversation(
            conversation_id=None,
            public_id=uuid4(),
            customer_id=customer.customer_id,
        )
    )

    assert (
        await conversations.get_by_public_id(
            conversation.public_id, customer_id=other.customer_id
        )
        is None
    )

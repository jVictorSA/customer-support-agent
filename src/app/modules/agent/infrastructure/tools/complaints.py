from app.modules.agent.application.interfaces import OrderGateway
from app.modules.agent.domain.results import RegisteredComplaint
from app.modules.complaints.application.register_complaint import (
    RegisterComplaintUseCase,
)
from app.modules.complaints.domain.complaint_enums import (
    ComplaintCategory,
    ComplaintPriority,
)


class ComplaintGatewayAdapter:
    def __init__(
        self,
        *,
        use_case: RegisterComplaintUseCase,
        orders: OrderGateway,
    ) -> None:
        self._use_case = use_case
        self._orders = orders

    async def register(
        self,
        *,
        conversation_id: int,
        customer_id: int,
        message_id: int,
        category: str,
        description: str,
        order_reference: str | None,
        priority: str,
    ) -> RegisteredComplaint:
        order_id = None
        if order_reference:
            order = await self._orders.get_order(
                customer_id=customer_id, reference=order_reference
            )
            if order is None:
                order = await self._orders.get_order_by_tracking(
                    customer_id=customer_id,
                    tracking_code=order_reference,
                )
            if order is not None:
                order_id = order.order_id

        try:
            parsed_category = ComplaintCategory(category)
        except ValueError:
            parsed_category = ComplaintCategory.OTHER
        try:
            parsed_priority = ComplaintPriority(priority)
        except ValueError:
            parsed_priority = ComplaintPriority.NORMAL

        result = await self._use_case.execute(
            conversation_id=conversation_id,
            customer_id=customer_id,
            message_id=message_id,
            order_id=order_id,
            category=parsed_category,
            description=description,
            priority=parsed_priority,
        )
        return RegisteredComplaint(
            public_id=str(result.complaint.public_id),
            status=result.complaint.status.value,
            category=result.complaint.category.value,
            already_open=result.already_open,
        )

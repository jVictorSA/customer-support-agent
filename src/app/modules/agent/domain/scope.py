from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CustomerScope:
    customer_id: int
    customer_name: str
    conversation_id: int
    message_id: int

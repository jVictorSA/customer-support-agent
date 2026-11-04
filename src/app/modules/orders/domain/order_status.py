from enum import StrEnum


class OrderStatus(StrEnum):
    CANCELLED = "cancelled"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"
    PENDING = "pending"
    SHIPPED = "shipped"

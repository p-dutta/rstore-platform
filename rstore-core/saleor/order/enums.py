import graphene

from ...graphql.core.enums import to_enum
from ...order import OrderEvents, OrderEventsEmails, OrderType

OrderEventsEnum = to_enum(OrderEvents)
OrderEventsEmailsEnum = to_enum(OrderEventsEmails)
OrderTypeEnum = to_enum(OrderType)


class OrderStatusFilter(graphene.Enum):
    READY_TO_FULFILL = "ready_to_fulfill"
    READY_TO_CAPTURE = "ready_to_capture"
    UNFULFILLED = "unfulfilled"
    PARTIALLY_FULFILLED = "partially fulfilled"
    FULFILLED = "fulfilled"
    CANCELED = "canceled"

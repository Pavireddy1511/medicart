from enum import StrEnum


class UserRole(StrEnum):
    CUSTOMER = "customer"
    PHARMACIST = "pharmacist"
    ADMIN = "admin"


class AddressType(StrEnum):
    HOME = "home"
    WORK = "work"
    OTHER = "other"


class OrderStatus(StrEnum):
    PLACED = "placed"
    VERIFICATION_PENDING = "verification_pending"
    VERIFIED = "verified"
    PROCESSING = "processing"
    PACKED = "packed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


FULFILMENT_FLOW: list[OrderStatus] = [
    OrderStatus.PLACED,
    OrderStatus.VERIFICATION_PENDING,
    OrderStatus.VERIFIED,
    OrderStatus.PROCESSING,
    OrderStatus.PACKED,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
]


def allowed_transitions(current: OrderStatus) -> list[OrderStatus]:
    """Statuses an admin may move an order to.

    There is no courier integration, so the admin drives fulfilment: an order can jump forward
    to any later stage (straight to "delivered" included) or be cancelled until it has shipped.
    "Verification pending" is only entered at checkout, and "verified" only leaves from it.
    """
    if current in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        return []
    later = FULFILMENT_FLOW[FULFILMENT_FLOW.index(current) + 1 :]
    targets = [
        status
        for status in later
        if status is not OrderStatus.VERIFICATION_PENDING
        and (status is not OrderStatus.VERIFIED or current is OrderStatus.VERIFICATION_PENDING)
    ]
    if current is not OrderStatus.SHIPPED:
        targets.append(OrderStatus.CANCELLED)
    return targets


ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    status: set(allowed_transitions(status)) for status in OrderStatus
}

CUSTOMER_CANCELLABLE = {
    OrderStatus.PLACED,
    OrderStatus.VERIFICATION_PENDING,
    OrderStatus.VERIFIED,
    OrderStatus.PROCESSING,
}


class PaymentMethod(StrEnum):
    COD = "cod"
    SIMULATED_ONLINE = "simulated_online"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    COD_PENDING = "cod_pending"
    PAID = "paid"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class ShipmentStatus(StrEnum):
    PENDING = "pending"
    PACKED = "packed"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ProcessingStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(StrEnum):
    PRINTED = "printed"
    HANDWRITTEN = "handwritten"
    UNKNOWN = "unknown"


class SourceFormat(StrEnum):
    IMAGE = "image"
    PDF = "pdf"


class AIReviewStatus(StrEnum):
    COMPLETED = "completed"  # Groq returned a valid structured response
    FALLBACK = "fallback"  # Groq failed; rule-based parser used instead
    UNAVAILABLE = "unavailable"  # Groq not configured; rule-based parser used
    SKIPPED = "skipped"  # no OCR text to structure


class UserConfirmationStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class VerificationStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLARIFICATION_REQUESTED = "clarification_requested"


class MatchStatus(StrEnum):
    EXACT = "exact"
    POSSIBLE = "possible"
    UNCERTAIN = "uncertain"
    NONE = "none"


class UncertaintyStatus(StrEnum):
    CLEAR = "clear"
    UNCERTAIN = "uncertain"

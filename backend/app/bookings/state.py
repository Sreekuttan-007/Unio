from enum import StrEnum

from app.core.state import StateMachine


class BookingStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"


class BookingEvent(StrEnum):
    RESCHEDULE = "RESCHEDULE"
    CANCEL = "CANCEL"


S, E = BookingStatus, BookingEvent

BOOKING_MACHINE: StateMachine[BookingStatus, BookingEvent] = StateMachine.build(
    [
        (S.CONFIRMED, E.RESCHEDULE, S.RESCHEDULED),
        (S.RESCHEDULED, E.RESCHEDULE, S.RESCHEDULED),
        (S.CONFIRMED, E.CANCEL, S.CANCELLED),
        (S.RESCHEDULED, E.CANCEL, S.CANCELLED),
    ]
)

LIVE = (S.CONFIRMED.value, S.RESCHEDULED.value)

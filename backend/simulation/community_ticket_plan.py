"""Deterministic simulated-time phases for externally visible routine tickets."""

from dataclasses import dataclass


OPEN = "open"
CLAIM = "claim"
COMPLETE = "complete"
PHASES = (OPEN, CLAIM, COMPLETE)

# The Live Operations surface polls every two real seconds. At the default
# 60x speed, one simulated minute passes per real second. Five minutes of
# open-queue dwell and ten minutes of in-progress dwell therefore each span
# more than one poll without making the accelerated community feel stalled.
OPEN_TO_CLAIM_MINUTES = 5
CLAIM_TO_COMPLETE_MINUTES = 10
DEFAULT_ACCELERATION = 60
RUNTIME_POLL_SECONDS = 2


@dataclass(frozen=True)
class TicketPhase:
    phase: str
    event_id: str
    day_index: int
    minute: int

    @property
    def absolute_minute(self) -> int:
        return self.day_index * 1440 + self.minute


def _coordinate(absolute_minute: int) -> tuple[int, int]:
    return divmod(absolute_minute, 1440)


def plan_ticket_phases(base_event_id: str, day_index: int, minute: int) -> tuple[TicketPhase, ...]:
    """Plan open, claim and completion with rollover-safe simulated dwell."""
    if not base_event_id or day_index < 0 or not 0 <= minute < 1440:
        raise ValueError("ticket phase source coordinate is invalid")
    opened = day_index * 1440 + minute
    offsets = (0, OPEN_TO_CLAIM_MINUTES, OPEN_TO_CLAIM_MINUTES + CLAIM_TO_COMPLETE_MINUTES)
    phases = []
    for phase, offset in zip(PHASES, offsets):
        phase_day, phase_minute = _coordinate(opened + offset)
        phases.append(TicketPhase(
            phase=phase,
            event_id=f"{base_event_id}:ticket_{phase}",
            day_index=phase_day,
            minute=phase_minute,
        ))
    return tuple(phases)


def minimum_real_dwell_seconds(simulated_minutes: int, speed: int = DEFAULT_ACCELERATION) -> float:
    if simulated_minutes < 0 or speed <= 0:
        raise ValueError("dwell and speed must be non-negative and positive")
    return simulated_minutes * 60 / speed

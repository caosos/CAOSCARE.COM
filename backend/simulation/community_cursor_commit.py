"""Fresh-lease cursor commit shared by simulator execution paths."""

from datetime import datetime, timezone
from typing import Callable, Optional

from simulation import community_run_lease as run_lease


Clock = Callable[[], datetime]


def _fresh(clock: Optional[Clock]) -> datetime:
    instant = clock() if clock else datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise run_lease.RunLeaseError("cursor commit clock must be timezone-aware")
    return instant.astimezone(timezone.utc)


async def advance_cursor(
    run_id: str,
    holder_id: str,
    fence: int,
    cursor: int,
    *,
    store,
    fields: dict,
    clock: Optional[Clock] = None,
    ttl_seconds: int = run_lease.DEFAULT_TTL_SECONDS,
    lease_mode: str = run_lease.RUNNER_MODE,
) -> dict:
    """Revalidate the exact live lease at fresh time, then advance once."""
    instant = _fresh(clock)
    await run_lease.heartbeat(
        run_id,
        holder_id,
        fence,
        store=store,
        now=instant,
        ttl_seconds=ttl_seconds,
        mode=lease_mode,
    )
    return await run_lease.advance_cursor(
        run_id,
        holder_id,
        fence,
        cursor,
        cursor + 1,
        store=store,
        now=instant,
        fields=fields,
        mode=lease_mode,
    )

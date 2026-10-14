"""Owner/admin read-only living-community Live Operations endpoint."""

from fastapi import APIRouter, Depends

from deps import require_admin
from simulation import community_activity_view, community_queue_view, community_runtime_view


router = APIRouter(prefix="/simulator/community", tags=["simulator"])


@router.get("/runtime")
async def community_runtime(user=Depends(require_admin)):
    """Return exact runtime truth; uncertainty stays in the JSON contract."""
    snapshot = await community_runtime_view.runtime_snapshot()
    snapshot["activity"] = await community_activity_view.activity_snapshot(
        run_id=snapshot["run"].get("run_id"),
    )
    run = snapshot["run"]
    upcoming = run.get("next_event")
    snapshot["queue"] = await community_queue_view.queue_snapshot(
        run_id=run.get("run_id") if run.get("status") == "loaded" else None,
        clock_minute=run["simulated_time"].get("absolute_minute"),
        next_event_minute=upcoming["day_index"] * 1440 + upcoming["minute"] if upcoming else None,
    )
    if snapshot["status"] == "loaded" and "error" in (
            snapshot["activity"]["status"], snapshot["queue"]["status"]):
        snapshot["status"] = "error"
    return snapshot

"""Owner/admin read-only living-community Live Operations endpoint."""

from fastapi import APIRouter, Depends

from deps import require_admin
from simulation import community_activity_view, community_runtime_view


router = APIRouter(prefix="/simulator/community", tags=["simulator"])


@router.get("/runtime")
async def community_runtime(user=Depends(require_admin)):
    """Return exact runtime truth; uncertainty stays in the JSON contract."""
    snapshot = await community_runtime_view.runtime_snapshot()
    snapshot["activity"] = await community_activity_view.activity_snapshot(
        run_id=snapshot["run"].get("run_id"),
    )
    if snapshot["status"] == "loaded" and snapshot["activity"]["status"] == "error":
        snapshot["status"] = "error"
    return snapshot

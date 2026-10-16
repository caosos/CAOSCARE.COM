"""Read-only proof of resident readiness for one living-community run."""

from simulation.community_atomic_provision import READY_ACTION
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_cohort import residents_for


def expected_resident_count(run: dict):
    """The run's own resident count; else its plan cohort's; else unknown."""
    count = run.get("resident_count")
    if isinstance(count, int) and not isinstance(count, bool):
        return count
    from simulation.community_timeline import cohort_of_revision
    try:
        return len(residents_for(cohort_of_revision(run.get("plan_revision"))))
    except ValueError:
        return None


def _view(status: str, provisioned, receipt_id=None, reason=None, expected=None) -> dict:
    return {
        "status": status,
        "residents_provisioned": provisioned,
        "expected_resident_count": expected,
        "receipt_id": receipt_id,
        "reason": reason,
    }


async def resident_readiness(collection, run: dict) -> tuple[dict, dict]:
    """Return verified readiness and its independent source status."""
    expected = expected_resident_count(run)
    marker = run.get("residents_provisioned")
    receipt_id = run.get("provisioning_receipt_id")
    if marker is False:
        if any(run.get(field) is not None for field in (
            "provisioning_receipt_id", "provisioning_resident_receipt_ids",
            "provisioning_created_ids", "provisioning_reused_ids",
        )):
            return (
                _view("error", None, reason="unprovisioned_run_has_receipt", expected=expected),
                {"status": "error", "error": "unprovisioned_run_has_receipt"},
            )
        return _view("not_provisioned", False, expected=expected), {"status": "loaded", "error": None}
    if marker is not True:
        return (
            _view("error", None, reason="resident_marker_missing_or_invalid", expected=expected),
            {"status": "error", "error": "resident_marker_missing_or_invalid"},
        )
    if not isinstance(receipt_id, str) or not receipt_id.strip():
        return (
            _view("error", None, reason="readiness_receipt_id_missing", expected=expected),
            {"status": "error", "error": "readiness_receipt_id_missing"},
        )
    row = await collection.find_one({
        "receipt_id": receipt_id,
        "simulation_run_id": run.get("run_id"),
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "action_type": READY_ACTION,
    }, {"_id": 0})
    after = (row or {}).get("after_state") or {}
    resident_receipt_ids = after.get("provisioning_resident_receipt_ids") or []
    exact = bool(row) and all((
        row.get("related_object_type") == "simulation_run",
        row.get("related_object_id") == run.get("run_id"),
        row.get("status") == "completed",
        row.get("actor_type") == "real-human",
        row.get("identity_basis") == "authenticated",
        row.get("simulated") is False,
        row.get("actor_role") in {"owner", "admin"},
        row.get("source") == "staff",
        row.get("requested_by") == row.get("actor_id"),
        str(row.get("authority") or "").startswith("admin_override:"),
        row.get("parent_receipt_id") == run.get("origin_receipt_id"),
        row.get("correlation_id") == run.get("origin_receipt_id"),
        after.get("run_id") == run.get("run_id"),
        after.get("residents_provisioned") is True,
        after.get("provisioning_receipt_id") == receipt_id,
        resident_receipt_ids == run.get("provisioning_resident_receipt_ids"),
        expected is not None,
        len(resident_receipt_ids) == expected,
        len(set(resident_receipt_ids)) == expected,
    ))
    if not exact:
        return (
            _view("error", None, receipt_id, "readiness_receipt_not_exact", expected=expected),
            {"status": "error", "error": "readiness_receipt_not_exact"},
        )
    return _view("ready", True, receipt_id, expected=expected), {"status": "loaded", "error": None}


async def attach_resident_readiness(
    run_view: dict, sources: dict, errors: list[dict], collection, run: dict,
) -> None:
    """Attach readiness while preserving an explicit error/null boundary."""
    try:
        run_view["resident_readiness"], sources["readiness"] = await resident_readiness(
            collection, run,
        )
        reason = run_view["resident_readiness"]["reason"]
        if run_view["resident_readiness"]["status"] == "error":
            errors.append({"source": "readiness", "code": reason})
    except Exception as exc:
        sources["readiness"] = {"status": "error", "error": type(exc).__name__}
        run_view["resident_readiness"] = _view("error", None, reason="read_failed",
                                               expected=expected_resident_count(run))
        errors.append({"source": "readiness", "code": "read_failed"})

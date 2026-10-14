"""Shared named-index contract for living-community runtime reads."""


REQUIRED_INDEXES = (
    {"collection": "sim_runs", "name": "uniq_living_run_id",
     "keys": (("run_id", 1),), "unique": True,
     "purpose": "exact lifecycle and runner lookup"},
    {"collection": "receipts", "name": "living_receipts_run_cursor",
     "keys": (("simulation_run_id", 1), ("execution_cursor", 1)), "unique": False,
     "purpose": "bounded cursor reconciliation"},
    {"collection": "receipts", "name": "living_receipts_run_event",
     "keys": (("simulation_run_id", 1), ("simulation_event_id", 1)), "unique": False,
     "purpose": "exact event evidence lookup"},
    {"collection": "receipts", "name": "living_receipts_activity",
     "keys": (("simulation_run_id", 1), ("related_object_type", 1), ("created_at", -1)),
     "unique": False, "purpose": "recent canonical task transitions"},
    {"collection": "staff_tasks", "name": "living_tasks_run_status",
     "keys": (("simulation_run_id", 1), ("simulated", 1), ("status", 1)),
     "unique": False, "purpose": "run-scoped canonical ticket counts"},
    {"collection": "staff_tasks", "name": "living_tasks_activity",
     "keys": (("simulation_run_id", 1), ("simulated", 1), ("created_at", -1)),
     "unique": False, "purpose": "recent canonical tickets"},
    # The database itself refuses a second in-progress ticket for one worker.
    {"collection": "staff_tasks", "name": "living_tasks_one_active_per_worker",
     "keys": (("simulation_run_id", 1), ("assigned_to", 1)), "unique": True,
     "partial": {"status": "in_progress", "simulated": True,
                 "simulation_scope": "living_community"},
     "purpose": "one active ticket per simulated worker"},
)


def required_options(requirement: dict) -> dict:
    """The index options a requirement demands, in index_information() form."""
    options = {"unique": requirement["unique"]}
    if requirement.get("partial"):
        options["partialFilterExpression"] = dict(requirement["partial"])
    return options


def _index_view(requirement: dict) -> dict:
    return {
        "collection": requirement["collection"], "name": requirement["name"],
        "keys": [list(item) for item in requirement["keys"]],
        "unique": requirement["unique"], "partial": requirement.get("partial"),
        "purpose": requirement["purpose"],
    }


async def inspect_required_indexes(store) -> dict:
    """Read index metadata only; this module never creates or changes indexes."""
    rows = []
    for requirement in REQUIRED_INDEXES:
        expected = _index_view(requirement)
        try:
            collection = getattr(store, requirement["collection"])
            information = await collection.index_information()
            found = information.get(requirement["name"])
        except Exception as exc:
            rows.append({
                **expected, "status": "probe_failed", "observed": None,
                "error": type(exc).__name__,
            })
            continue
        observed_keys = tuple(tuple(item) for item in (found or {}).get("key", ()))
        unique_ok = bool((found or {}).get("unique")) is requirement["unique"]
        partial = (found or {}).get("partialFilterExpression")
        options_ok = (dict(partial or {}) == dict(requirement.get("partial") or {})
                      and not (found or {}).get("sparse"))
        if found is None:
            status = "missing"
        elif observed_keys != requirement["keys"] or not unique_ok or not options_ok:
            status = "incompatible"
        else:
            status = "ready"
        rows.append({
            **expected, "status": status,
            "observed": None if found is None else {
                "keys": [list(item) for item in observed_keys],
                "unique": bool(found.get("unique")),
                "partial": bool(found.get("partialFilterExpression")),
                "sparse": bool(found.get("sparse")),
            },
            "error": None,
        })
    missing = [row["name"] for row in rows if row["status"] != "ready"]
    return {"status": "passed" if not missing else "failed", "ready": not missing,
            "required": rows, "blockers": missing}

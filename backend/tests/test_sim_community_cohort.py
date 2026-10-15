"""SIM-005B: all 75 residents executable; ten-resident burn-in optional."""
from collections import Counter

import pytest

from simulation import community_cohort as cohorts
from simulation.community_blueprint import RESIDENTS
from simulation.community_dispatch import QUEUED_UNASSIGNED, plan_routine_dispatch
from simulation.community_family_call_routing import family_call_department
from simulation.community_routines import RoutineEvent, plan_first_24_hours
from simulation.community_timeline import (
    PLAN_REVISIONS, build_90_day_timeline, cohort_of_revision, validate_timeline,
)


@pytest.fixture(scope="module")
def full_plan():
    return build_90_day_timeline(cohorts.FULL_COMMUNITY)


def test_runtime_default_is_the_full_community_and_burn_in_is_optional(monkeypatch):
    monkeypatch.delenv(cohorts.COHORT_ENV, raising=False)
    assert cohorts.default_cohort() == "community_75"
    assert len(cohorts.residents_for("community_75")) == 75
    monkeypatch.setenv(cohorts.COHORT_ENV, "burn_in_10")
    assert cohorts.default_cohort() == "burn_in_10"
    monkeypatch.setenv(cohorts.COHORT_ENV, "ghost")
    with pytest.raises(cohorts.CohortError):
        cohorts.default_cohort()
    assert cohort_of_revision(PLAN_REVISIONS["community_75"]) == "community_75"


def test_full_plan_executes_every_resident_deterministically(full_plan):
    assert full_plan.cohort == "community_75" and full_plan.resident_count == 75
    # Staff roles (v12): 107,802 tickets; see the phase counts below.
    assert full_plan.event_count == 328_751
    kinds = Counter(event.stream_kind for event in full_plan.events)
    assert kinds == {"routine_ticket_phase": 319_559, "canonical_shift_milestone": 9_192}
    phases = Counter(event.task_phase for event in full_plan.events)
    # v12 staff roles: 247 activity escorts close unserved (one coordinator); the rest of the
    # gap between open and claim is the visible housekeeping/maintenance backlog at day 90.
    assert phases == {"open": 107_802, "claim": 105_755, "complete": 105_755, "expire": 247, None: 9_192}
    opened = {e.target_id for e in full_plan.events if e.task_phase == "open"}
    assert opened == {resident.resident_id for resident in RESIDENTS}
    ids = [event.event_id for event in full_plan.events]
    assert len(ids) == len(set(ids))
    assert validate_timeline(full_plan) is full_plan
    resident_ids = {resident.resident_id for resident in RESIDENTS}
    for event in full_plan.events[:5000]:
        if event.stream_kind == "routine_ticket_phase":
            assert event.target_id in resident_ids
            assert event.workflow_event_id.split(":")[1] == f"resident-{event.target_id[-3:]}"


def test_burn_in_plan_is_the_first_ten_residents_of_the_same_recipes():
    keys = cohorts.resident_keys_for("community_75")
    full_day = plan_first_24_hours(keys, day_index=4)
    burn_in_day = plan_first_24_hours(cohorts.resident_keys_for("burn_in_10"), day_index=4)
    ten = set(cohorts.resident_keys_for("burn_in_10"))
    assert [e for e in full_day if e.resident_key in ten] == list(burn_in_day)


def test_family_calls_follow_the_owner_routing_rule():
    assert family_call_department(9 * 60) == "administration"
    assert family_call_department(16 * 60 + 44) == "administration"
    assert family_call_department(16 * 60 + 50) == "front_desk"   # Admin cannot finish by 17:00
    assert family_call_department(20 * 60) == "front_desk"
    assert family_call_department(23 * 60 + 30) == "administration"  # queued to next opening
    assert family_call_department(9 * 60, urgent=True) == "nursing"
    day = plan_first_24_hours(cohorts.resident_keys_for("community_75"), day_index=2)
    calls = [e for e in day if e.routine == "family_call_coordination"]
    assert Counter(e.department for e in calls) == {"front_desk": 30, "administration": 7}
    dispatch = plan_routine_dispatch(calls)
    assert not [d for d in dispatch if d.dispatch_state == QUEUED_UNASSIGNED]


def test_ticket_is_dispatched_only_when_staffed_through_completion():
    late = RoutineEvent(plan_day_index=0, day_index=0, minute=15 * 60 + 20,
                        resident_key="resident-046", routine="preventive_maintenance_check",
                        department="maintenance", summary="Late check.",
                        event_id="day-000:resident-046:preventive_maintenance_check")
    (row,) = plan_routine_dispatch([late])
    assert row.dispatch_state == QUEUED_UNASSIGNED
    assert (row.ready_day_index, row.ready_minute) == (1, 7 * 60)


def _resident_row(recipe, **changes):
    row = {**recipe.resident_payload()}
    row.update(changes)
    return row


def test_double_occupancy_room_mates_are_not_identity_collisions():
    """SIM-005B (real MongoDB): residents 066-075 share five rooms by design."""
    import asyncio
    from simulation.community_blueprint import is_room_mate
    from simulation.community_observed_state import observe_community_state
    from simulation.community_provisioning import ProvisioningError, _collision

    by_id = {resident.resident_id: resident for resident in RESIDENTS}
    a, b = by_id["sim:resident:066"], by_id["sim:resident:067"]
    assert a.room == b.room and is_room_mate(a, _resident_row(b))
    stranger = {"resident_id": "res_real_person", "room": a.room, "pendant_id": "p-x"}
    assert not is_room_mate(a, stranger)

    rows = [_resident_row(resident) for resident in RESIDENTS]

    async def reader(name, _projection):
        return rows if name == "residents" else []

    observed = asyncio.run(observe_community_state(collection_reader=reader, cohort="community_75"))
    assert observed["provisioning"]["state"] == "provisioned"
    assert observed["provisioning"]["exact_blueprint_residents"] == 75

    class Residents:
        def __init__(self, docs):
            self.docs = docs

        def find(self, query, _projection, **_kwargs):
            wanted = query["$or"]
            hits = [d for d in self.docs if any(d.get(k) == v for c in wanted for k, v in c.items())]

            class Cursor:
                async def to_list(self, _n):
                    return hits
            return Cursor()

    class Store:
        def __init__(self, docs):
            self.residents = Residents(docs)

    assert asyncio.run(_collision(Store([_resident_row(a), _resident_row(b)]), a))["resident_id"] == a.resident_id
    with pytest.raises(ProvisioningError, match="split identity"):
        asyncio.run(_collision(Store([_resident_row(a), stranger]), a))

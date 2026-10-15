"""CO-008 service model (owner 2026-10-15): parallel dining, escorts only for residents who need them."""
from collections import Counter

from simulation import community_service_model as svc
from simulation.community_day_queue import cohort_schedule
from simulation.community_role_eligibility import eligible_roles
from simulation.community_routines import plan_first_24_hours
from simulation.community_blueprint import RESIDENTS

KEYS = tuple(resident.resident_key for resident in RESIDENTS)


def _index(key):
    return int(key.removeprefix("resident-"))


def test_mobility_meal_and_activity_mix_is_realistic_and_deterministic():
    mobility = Counter(svc.mobility_for(i) for i in range(1, 76))
    assert mobility["needs_escort"] + mobility["wheelchair_needs_escort"] == 19   # about a quarter
    assert sum(svc.meal_location_for(i) == "room_service_offer" for i in range(1, 76)) == 30   # owner estimate: about 30 of 75
    assert sum(svc.activity_style_for(i) == "one_to_one_offer" for i in range(1, 76)) == 10
    assert [svc.mobility_for(i) for i in range(1, 76)] == [svc.mobility_for(i) for i in range(1, 76)]


def test_independent_residents_get_no_escort_ticket_and_escort_needers_do_when_they_attend():
    for day in range(5):
        events = plan_first_24_hours(KEYS, day_index=day)
        escorted = {e.resident_key for e in events if e.routine == svc.ACTIVITY_ESCORT}
        visited = {e.resident_key for e in events if e.routine == svc.ACTIVITY_VISIT}
        for key in KEYS:
            i = _index(key)
            attends = svc.attends_activity(i, day)
            group = svc.activity_style_for(i) != "one_to_one_offer"
            assert (key in escorted) == (attends and group and svc.needs_escort(i)), (day, key)
            assert (key in visited) == (attends and not group), (day, key)
        escorts = sorted(e.minute for e in events if e.routine == svc.ACTIVITY_ESCORT)
        assert all(m < svc.ACTIVITY_SESSION_START for m in escorts)   # brought before the session


def test_every_resident_is_served_every_meal_where_they_eat():
    events = plan_first_24_hours(KEYS, day_index=0)
    for key in KEYS:
        meals = {e.routine for e in events if e.resident_key == key and svc.is_meal(e.routine)}
        expected = {svc.meal_routine(meal, _index(key)) for meal in svc.MEALS}
        assert meals == expected
    dinners = sorted(e.minute for e in events if svc.meal_of(e.routine) == "dinner")
    assert dinners[0] == svc.MEAL_SEATING["dinner"] and dinners[-1] - dinners[0] < 75   # one seating hour


def test_meals_go_to_dining_servers_in_parallel_never_the_cook():
    assert eligible_roles("kitchen", "dinner") == ("dining_server", "meal_delivery_aide")
    assert eligible_roles("kitchen", "dinner_room_service") == ("meal_delivery_aide", "dining_server")
    assert "cook" not in eligible_roles("kitchen", "resident_call_snack")
    _routines, scheduled = cohort_schedule("community_75")
    events = {e.event_id: e for day in _routines.values() for e in day}
    dinner = [row for row in scheduled.values()
              if row.claim_at is not None and svc.meal_of(events[row.workflow_id].routine) == "dinner"
              and row.requested_at < 1440]
    servers = {row.worker["actor_id"] for row in dinner}
    assert len(servers) >= 2 and all(":dining_server:" in a or ":meal_delivery_aide:" in a for a in servers)
    # parallel service: two dinners are being served at the same simulated minute
    assert any(a.claim_at < b.complete_at and b.claim_at < a.complete_at
               and a.worker["actor_id"] != b.worker["actor_id"]
               for a, b in zip(sorted(dinner, key=lambda r: r.claim_at), sorted(dinner, key=lambda r: r.claim_at)[1:]))


def test_shortage_stays_visible_as_waits_not_compressed_durations():
    assert svc.WORK_MINUTES["dinner"] == 3 and svc.WORK_MINUTES["dinner_room_service"] == 13 == sum(svc.ROOM_DELIVERY_STEPS.values())
    _routines, scheduled = cohort_schedule("community_75")
    events = {e.event_id: e for day in _routines.values() for e in day}
    for row in scheduled.values():
        routine = events[row.workflow_id].routine
        if row.claim_at is not None and routine in svc.WORK_MINUTES:
            assert row.complete_at - row.claim_at == svc.WORK_MINUTES[routine]


def test_room_delivery_is_about_30_of_75_and_every_tray_takes_its_full_trip():
    """Owner estimate (2026-10-15): about 30 room-delivered and 45 dining-room meals per seating."""
    _routines, scheduled = cohort_schedule("community_75")
    events = {e.event_id: e for day in _routines.values() for e in day}
    day0 = [events[row.workflow_id].routine for row in scheduled.values() if row.requested_at < 1440]
    for meal in svc.MEALS:
        assert day0.count(meal) == 45 and day0.count(meal + svc.ROOM_SERVICE) == 30
    assert svc.ROOM_DELIVERY_STEPS == {"tray_pickup": 2, "walk_to_apartment": 4,
                                       "handoff_and_setup": 3, "return_to_kitchen": 4}
    trays = [row for row in scheduled.values()
             if svc.is_meal(events[row.workflow_id].routine) and events[row.workflow_id].routine.endswith(svc.ROOM_SERVICE)
             and row.claim_at is not None]
    assert trays and all(row.complete_at - row.claim_at == svc.ROOM_DELIVERY_MINUTES for row in trays)
    assert {row.worker["job_role"] for row in trays} == {"meal_delivery_aide", "dining_server"}


def test_kitchen_tickets_say_what_to_do_and_close_truthfully():
    from types import SimpleNamespace
    from simulation.community_ticket_staging import completion_note
    from simulation.community_ticket_text import routine_summary
    delivery = routine_summary("dinner_room_service")
    assert all(step in delivery for step in ("pick up", "kitchen pass", "hand it over and set it up", "walk back"))
    assert "dining room" in routine_summary("lunch") and "intake is not recorded" in routine_summary("lunch")
    note = lambda action: completion_note(SimpleNamespace(action_type=action))
    assert note("dinner_room_service").startswith("Simulated tray delivered to the apartment")
    assert note("breakfast").startswith("Simulated meal served in the dining room")
    for action in ("dinner", "dinner_room_service", "resident_call_snack", "resident_call_tray"):
        assert "no claim" in note(action)
    from simulation.community_ticket_text import routine_label
    assert routine_label("dinner_room_service") == "Dinner delivery to the apartment"
    assert routine_label("lunch") == "Lunch in the dining room" and routine_label("unknown_routine") is None

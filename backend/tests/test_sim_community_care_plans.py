"""Pure contract tests for synthetic resident care-plan recipes."""

from dataclasses import replace

import pytest

from simulation.community_blueprint import RESIDENTS
from simulation.community_care_plans import (
    ASSISTANCE_TRUTH_BOUNDARY,
    PLAN_TRUTH_BOUNDARY,
    PLANNING_ONLY,
    PREFERENCE_TRUTH_BOUNDARY,
    REMINDER_TRUTH_BOUNDARY,
    CarePlanRecipeError,
    RESIDENT_CARE_PLANS,
    build_resident_care_plans,
)


def test_all_75_residents_have_stable_unique_deterministic_plans():
    assert build_resident_care_plans() == RESIDENT_CARE_PLANS
    assert len(RESIDENT_CARE_PLANS) == 75
    assert {plan.resident_key for plan in RESIDENT_CARE_PLANS} == {
        resident.resident_key for resident in RESIDENTS
    }
    assert len({plan.care_plan_id for plan in RESIDENT_CARE_PLANS}) == 75
    assert len({
        reminder.reminder_id
        for plan in RESIDENT_CARE_PLANS
        for reminder in plan.reminders
    }) == 150
    assert len({
        assistance.assistance_id
        for plan in RESIDENT_CARE_PLANS
        for assistance in plan.assistance
    }) == 150


def test_residents_have_varied_reminders_intervals_and_preferences():
    medication_schedules = {
        plan.reminders[0].scheduled_minutes for plan in RESIDENT_CARE_PLANS
    }
    assistance_intervals = {
        item.offer_interval_minutes
        for plan in RESIDENT_CARE_PLANS
        for item in plan.assistance
    }
    preference_profiles = {
        (
            plan.preferences.communication_style,
            plan.preferences.meal_location,
            plan.preferences.activity_style,
            plan.preferences.shower_days,
            plan.preferences.shower_window_minutes,
        )
        for plan in RESIDENT_CARE_PLANS
    }

    assert len(medication_schedules) == 4
    assert {120, 150, 180, 240} <= assistance_intervals
    assert len(preference_profiles) >= 12
    assert all(plan.reminders and plan.assistance for plan in RESIDENT_CARE_PLANS)


def test_times_and_intervals_are_bounded_for_planning():
    for plan in RESIDENT_CARE_PLANS:
        for reminder in plan.reminders:
            assert reminder.scheduled_minutes
            assert all(0 <= minute < 24 * 60 for minute in reminder.scheduled_minutes)
            assert reminder.follow_up_after_minutes > 0
            assert reminder.max_offers == 1
        for assistance in plan.assistance:
            start, end = assistance.active_window_minutes
            assert 0 <= start < end < 24 * 60
            assert assistance.offer_interval_minutes > 0
        shower_start, shower_end = plan.preferences.shower_window_minutes
        assert 0 <= shower_start < shower_end < 24 * 60
        assert all(0 <= day <= 6 for day in plan.preferences.shower_days)
        assert len(set(plan.preferences.shower_days)) == len(plan.preferences.shower_days)
        quiet_start, quiet_end = plan.preferences.quiet_hours_minutes
        assert 0 <= quiet_start < 24 * 60
        assert 0 <= quiet_end < 24 * 60
        assert quiet_start > quiet_end  # Explicit overnight window.


def test_every_layer_preserves_nonclinical_truth_boundaries():
    assert "not an assessed need" in PLAN_TRUTH_BOUNDARY
    assert "never evidence of a medication order" in REMINDER_TRUTH_BOUNDARY
    assert "not an assessed assistance level" in ASSISTANCE_TRUTH_BOUNDARY
    assert "not a real resident statement" in PREFERENCE_TRUTH_BOUNDARY

    for plan in RESIDENT_CARE_PLANS:
        assert plan.evidence_label == PLANNING_ONLY
        assert plan.synthetic is True
        assert plan.confirmed_by_authorized_human is False
        assert plan.represents_clinical_order is False
        assert plan.represents_execution is False
        assert plan.truth_boundary == PLAN_TRUTH_BOUNDARY
        assert all(not item.represents_clinical_order for item in plan.reminders)
        assert all(not item.represents_execution for item in plan.reminders)
        assert all(not item.represents_assessed_need for item in plan.assistance)
        assert all(not item.represents_execution for item in plan.assistance)
        assert plan.preferences.represents_consent is False


def test_builder_rejects_ambiguous_or_noncommunity_sources():
    with pytest.raises(CarePlanRecipeError, match="non-empty"):
        build_resident_care_plans(())
    with pytest.raises(CarePlanRecipeError, match="unique"):
        build_resident_care_plans((RESIDENTS[0], RESIDENTS[0]))
    with pytest.raises(CarePlanRecipeError, match="synthetic residents"):
        build_resident_care_plans((replace(RESIDENTS[0], synthetic=False),))
    with pytest.raises(CarePlanRecipeError, match="numeric ordinal"):
        build_resident_care_plans((replace(RESIDENTS[0], resident_key="resident-x"),))

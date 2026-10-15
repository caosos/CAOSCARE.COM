"""Deterministic, non-clinical care-plan recipes for synthetic residents.

This module is planning data only.  It does not import a database, route,
model, executor, or provider and it never represents assessed care or work
performed.  A future adapter must obtain authorized human confirmation and
use canonical services with receipts before any recipe can become operational.
"""

from dataclasses import dataclass
from typing import Iterable

from simulation import community_service_model as svc
from simulation.community_blueprint import (
    COMMUNITY_ID,
    RESIDENTS,
    SIMULATION_SCOPE,
    ResidentRecipe,
)


PLANNING_ONLY = "synthetic_nonclinical_plan_only"
PLAN_VERSION = "living-community-care-plan-v1"
PLAN_TRUTH_BOUNDARY = (
    "Synthetic planning profile only; not an assessed need, clinical order, "
    "diagnosis, consent record, medication administration record, or evidence "
    "that assistance was offered or delivered. Authorized staff must confirm "
    "any real resident care plan."
)
REMINDER_TRUTH_BOUNDARY = (
    "Reminder timing only; never evidence of a medication order, dose, "
    "administration, ingestion, refusal, or adherence."
)
ASSISTANCE_TRUTH_BOUNDARY = (
    "Scheduled offer preference only; not an assessed assistance level and "
    "never evidence that assistance was requested, offered, accepted, or completed."
)
PREFERENCE_TRUTH_BOUNDARY = (
    "Synthetic scenario preference only; not a real resident statement, "
    "authorization, consent, restriction, or completed service."
)


class CarePlanRecipeError(ValueError):
    """The requested synthetic care-plan source is ambiguous or invalid."""


@dataclass(frozen=True)
class ReminderRecipe:
    reminder_id: str
    kind: str
    scheduled_minutes: tuple[int, ...]
    follow_up_after_minutes: int
    max_offers: int = 1
    truth_boundary: str = REMINDER_TRUTH_BOUNDARY
    represents_clinical_order: bool = False
    represents_execution: bool = False


@dataclass(frozen=True)
class AssistanceRecipe:
    assistance_id: str
    kind: str
    offer_interval_minutes: int
    active_window_minutes: tuple[int, int]
    interaction_preference: str
    truth_boundary: str = ASSISTANCE_TRUTH_BOUNDARY
    represents_assessed_need: bool = False
    represents_execution: bool = False


@dataclass(frozen=True)
class ResidentPreferences:
    communication_style: str
    meal_location: str
    activity_style: str
    mobility: str             # synthetic; decides only whether moving to an activity takes staff time
    shower_window_minutes: tuple[int, int]
    shower_days: tuple[int, ...]
    quiet_hours_minutes: tuple[int, int]
    truth_boundary: str = PREFERENCE_TRUTH_BOUNDARY
    represents_consent: bool = False


@dataclass(frozen=True)
class ResidentCarePlanRecipe:
    care_plan_id: str
    resident_key: str
    resident_id: str
    version: str
    reminders: tuple[ReminderRecipe, ...]
    assistance: tuple[AssistanceRecipe, ...]
    preferences: ResidentPreferences
    truth_boundary: str = PLAN_TRUTH_BOUNDARY
    evidence_label: str = PLANNING_ONLY
    confirmed_by_authorized_human: bool = False
    represents_clinical_order: bool = False
    represents_execution: bool = False
    synthetic: bool = True
    simulation_scope: str = SIMULATION_SCOPE
    simulation_community_id: str = COMMUNITY_ID


_COMMUNICATION_STYLES = (
    "brief_one_step_prompts",
    "supportive_guided_prompts",
    "repeat_then_confirm",
)
_ASSISTANCE_INTERACTIONS = (
    "ask_before_approaching",
    "announce_then_wait_for_response",
    "offer_two_clear_choices",
)
_SHOWER_DAY_PATTERNS = (
    (0, 3, 5),
    (1, 4, 6),
    (0, 2, 4),
    (1, 3, 5),
)


def _ordinal(resident: ResidentRecipe) -> int:
    try:
        ordinal = int(resident.resident_key.removeprefix("resident-"))
    except ValueError as exc:
        raise CarePlanRecipeError(
            f"resident key must end in a numeric ordinal: {resident.resident_key}"
        ) from exc
    if ordinal < 1:
        raise CarePlanRecipeError("resident ordinal must be positive")
    return ordinal


def _build_plan(resident: ResidentRecipe) -> ResidentCarePlanRecipe:
    ordinal = _ordinal(resident)
    variant = ordinal - 1
    medication_shift = (variant % 4) * 10
    appointment_lead = (30, 45, 60)[variant % 3]
    start = 360 + (variant % 3) * 30
    interval = (120, 150, 180, 240)[variant % 4]
    shower_start = 480 + (variant % 5) * 30
    plan_id = f"sim:care-plan:{resident.resident_key}:v1"

    reminders = (
        ReminderRecipe(
            reminder_id=f"{plan_id}:medication-reminder",
            kind="medication_reminder",
            scheduled_minutes=(480 + medication_shift, 1200 + medication_shift),
            follow_up_after_minutes=(10, 15, 20)[variant % 3],
        ),
        ReminderRecipe(
            reminder_id=f"{plan_id}:appointment-reminder",
            kind="appointment_reminder",
            scheduled_minutes=(540 + (variant % 6) * 15,),
            follow_up_after_minutes=appointment_lead,
        ),
    )
    assistance = (
        AssistanceRecipe(
            assistance_id=f"{plan_id}:toileting-transfer-offer",
            kind="toileting_transfer_offer",
            offer_interval_minutes=interval,
            active_window_minutes=(start, 1320),
            interaction_preference=_ASSISTANCE_INTERACTIONS[variant % 3],
        ),
        AssistanceRecipe(
            assistance_id=f"{plan_id}:evening-settle-offer",
            kind="evening_settle_offer",
            offer_interval_minutes=(30, 45, 60)[variant % 3],
            active_window_minutes=(1200, 1380),
            interaction_preference=_ASSISTANCE_INTERACTIONS[(variant + 1) % 3],
        ),
    )
    preferences = ResidentPreferences(
        communication_style=_COMMUNICATION_STYLES[variant % 3],
        meal_location=svc.meal_location_for(ordinal),
        activity_style=svc.activity_style_for(ordinal),
        mobility=svc.mobility_for(ordinal),
        shower_window_minutes=(shower_start, shower_start + 120),
        shower_days=_SHOWER_DAY_PATTERNS[variant % 4],
        quiet_hours_minutes=(1320 + (variant % 3) * 30, 390 + (variant % 3) * 30),
    )
    return ResidentCarePlanRecipe(
        care_plan_id=plan_id,
        resident_key=resident.resident_key,
        resident_id=resident.resident_id,
        version=PLAN_VERSION,
        reminders=reminders,
        assistance=assistance,
        preferences=preferences,
    )


def build_resident_care_plans(
    residents: Iterable[ResidentRecipe] = RESIDENTS,
) -> tuple[ResidentCarePlanRecipe, ...]:
    """Return stable recipes without registering or executing any of them."""
    resident_rows = tuple(residents)
    if not resident_rows:
        raise CarePlanRecipeError("residents must be a non-empty sequence")
    keys = tuple(resident.resident_key for resident in resident_rows)
    ids = tuple(resident.resident_id for resident in resident_rows)
    if len(set(keys)) != len(keys) or len(set(ids)) != len(ids):
        raise CarePlanRecipeError("resident keys and ids must be unique")
    if any(
        not resident.synthetic
        or resident.simulation_scope != SIMULATION_SCOPE
        or resident.simulation_community_id != COMMUNITY_ID
        for resident in resident_rows
    ):
        raise CarePlanRecipeError("care plans require living-community synthetic residents")
    plans = tuple(_build_plan(resident) for resident in resident_rows)
    if len({plan.care_plan_id for plan in plans}) != len(plans):
        raise CarePlanRecipeError("care plan ids must be unique")
    return plans


RESIDENT_CARE_PLANS = build_resident_care_plans()

"""Which synthetic residents a living-community plan executes.

The full community is all 75 blueprint residents.  The ten-resident burn-in is
kept as an optional, smaller test configuration with its own plan revision.
A run's persisted plan revision names its cohort, so provisioning, readiness,
execution and observation always agree on exactly which residents belong to it.
"""
import os

from simulation.community_blueprint import BURN_IN_RESIDENTS, RESIDENTS, ResidentRecipe


FULL_COMMUNITY = "community_75"
BURN_IN = "burn_in_10"
COHORT_ENV = "CAOSCARE_LIVING_COMMUNITY_COHORT"
_RESIDENTS = {FULL_COMMUNITY: tuple(RESIDENTS), BURN_IN: tuple(BURN_IN_RESIDENTS)}
COHORTS = tuple(_RESIDENTS)


class CohortError(ValueError):
    """An unknown or mismatched resident cohort was requested."""


def residents_for(cohort: str) -> tuple[ResidentRecipe, ...]:
    try:
        return _RESIDENTS[cohort]
    except KeyError:
        raise CohortError(f"unknown living-community cohort: {cohort!r}") from None


def resident_keys_for(cohort: str) -> tuple[str, ...]:
    return tuple(resident.resident_key for resident in residents_for(cohort))


def default_cohort() -> str:
    """Runtime default: the full 75-resident community unless explicitly set."""
    value = os.environ.get(COHORT_ENV, "").strip() or FULL_COMMUNITY
    residents_for(value)
    return value

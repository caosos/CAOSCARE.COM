"""Read-only department contract for a living-community run start.

The simulator may plan work only for departments that exist and are active in
the canonical department catalog.  This module derives the required slugs from
the routine and staffing fixtures themselves, then returns a deterministic,
immutable snapshot that a future start boundary can bind to the run.

Nothing here starts a run or mutates the department catalog.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Awaitable, Callable, Iterable, Mapping, Optional

from simulation.community_blueprint import RESIDENTS
from simulation.community_routines import plan_first_24_hours
from simulation.community_staffing import DEPARTMENT_LABELS


CONTRACT_VERSION = "living-community-active-departments-v1"
MISSING = "missing"
INACTIVE = "inactive"


@dataclass(frozen=True, order=True)
class DepartmentRequirement:
    """One stable department slug and the fixtures that require it."""

    slug: str
    used_by: tuple[str, ...]


@dataclass(frozen=True, order=True)
class DepartmentFailure:
    """One exact reason a required canonical department blocks start."""

    slug: str
    reason: str


@dataclass(frozen=True)
class DepartmentContractSnapshot:
    """Immutable evidence that every required department was active."""

    contract_version: str
    departments: tuple[DepartmentRequirement, ...]
    digest: str

    @property
    def active_slugs(self) -> tuple[str, ...]:
        return tuple(item.slug for item in self.departments)


class DepartmentPreflightError(RuntimeError):
    """The canonical catalog cannot safely route all simulated work."""

    def __init__(self, failures: Iterable[DepartmentFailure]):
        self.failures = tuple(sorted(failures))
        self.missing_slugs = tuple(
            item.slug for item in self.failures if item.reason == MISSING
        )
        self.inactive_slugs = tuple(
            item.slug for item in self.failures if item.reason == INACTIVE
        )
        clauses = []
        if self.missing_slugs:
            clauses.append(
                f"missing canonical departments: {', '.join(self.missing_slugs)}"
            )
        if self.inactive_slugs:
            clauses.append(
                f"inactive canonical departments: {', '.join(self.inactive_slugs)}"
            )
        super().__init__(f"living-community run start blocked: {'; '.join(clauses)}")


def department_requirements() -> tuple[DepartmentRequirement, ...]:
    """Derive every department used by current routine or staffing fixtures."""
    sources: dict[str, set[str]] = {}
    resident_keys = tuple(resident.resident_key for resident in RESIDENTS)
    for event in plan_first_24_hours(resident_keys):
        sources.setdefault(event.department, set()).add("routines")
    for slug in DEPARTMENT_LABELS:
        sources.setdefault(slug, set()).add("staffing")
    return tuple(
        DepartmentRequirement(slug=slug, used_by=tuple(sorted(used_by)))
        for slug, used_by in sorted(sources.items())
    )


def validate_active_department_contract(
    canonical_departments: Iterable[Mapping[str, object]],
) -> DepartmentContractSnapshot:
    """Validate a canonical catalog snapshot without I/O or mutation."""
    catalog = {
        row.get("slug").strip(): row
        for row in canonical_departments
        if isinstance(row.get("slug"), str) and row.get("slug").strip()
    }
    requirements = department_requirements()
    failures = []
    for requirement in requirements:
        row = catalog.get(requirement.slug)
        if row is None:
            failures.append(DepartmentFailure(requirement.slug, MISSING))
        elif row.get("active") is not True:
            failures.append(DepartmentFailure(requirement.slug, INACTIVE))
    if failures:
        raise DepartmentPreflightError(failures)

    payload = {
        "contract_version": CONTRACT_VERSION,
        "departments": [
            {"slug": item.slug, "used_by": list(item.used_by)}
            for item in requirements
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return DepartmentContractSnapshot(
        contract_version=CONTRACT_VERSION,
        departments=requirements,
        digest=hashlib.sha256(encoded).hexdigest(),
    )


def _default_store():
    from deps import db

    return db


async def _read_canonical_departments(store=None) -> tuple[dict, ...]:
    source = store or _default_store()
    rows = await source.departments.find(
        {}, {"_id": 0, "slug": 1, "active": 1}
    ).to_list(1000)
    return tuple(rows)


async def preflight_living_community_run_start(
    *,
    store=None,
    department_reader: Optional[
        Callable[[], Awaitable[Iterable[Mapping[str, object]]]]
    ] = None,
) -> DepartmentContractSnapshot:
    """Read and validate departments before any future run-start mutation."""
    if store is not None and department_reader is not None:
        raise ValueError("pass either store or department_reader, not both")
    rows = (
        await department_reader()
        if department_reader is not None
        else await _read_canonical_departments(store)
    )
    return validate_active_department_contract(rows)

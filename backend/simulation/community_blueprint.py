"""Deterministic recipe for the living-community operations simulator.

This module is configuration only.  It deliberately imports no database,
route, model, or provider code and performs no writes.  A provisioning service
may later translate these recipes into canonical CAOSCare records, attaching
the active ``simulation_run_id`` while preserving the markers below.

The target community contains 80 apartments, 70 occupied apartments and 75
residents.  Units 001-065 are single-occupancy; units 066-070 are the five
future double-occupancy apartments; units 071-080 are vacant.  Burn-in enables
only the first ten residents, all in single-occupancy apartments.
"""
from dataclasses import dataclass
from typing import Iterable


COMMUNITY_ID = "sim:community:living-80-v1"
SIMULATION_SCOPE = "living_community"
APARTMENT_TARGET = 80
OCCUPIED_APARTMENT_TARGET = 70
RESIDENT_TARGET = 75
BURN_IN_RESIDENT_TARGET = 10
DOUBLE_OCCUPANCY_APARTMENT_TARGET = 5


class BlueprintError(ValueError):
    """The static community recipe violates a simulator safety invariant."""


@dataclass(frozen=True)
class ApartmentRecipe:
    apartment_id: str
    room: str
    occupant_slots: tuple[str, ...]
    target_occupied: bool
    synthetic: bool = True
    simulation_scope: str = SIMULATION_SCOPE
    simulation_community_id: str = COMMUNITY_ID


@dataclass(frozen=True)
class ResidentRecipe:
    resident_key: str
    resident_id: str
    name: str
    preferred_name: str
    apartment_id: str
    room: str
    occupant_slot: str
    pendant_id: str
    enabled_for_burn_in: bool
    synthetic: bool = True
    simulation_scope: str = SIMULATION_SCOPE
    simulation_community_id: str = COMMUNITY_ID

    def resident_payload(self) -> dict:
        """Fields for a future canonical provisioning service.

        ``simulation_run_id`` is intentionally absent: it belongs to the run
        that materializes this recipe, not to this durable static blueprint.
        """
        return {
            "resident_id": self.resident_id,
            "name": self.name,
            "preferred_name": self.preferred_name,
            "room": self.room,
            "pendant_id": self.pendant_id,
            "synthetic": self.synthetic,
            "simulation_scope": self.simulation_scope,
            "simulation_community_id": self.simulation_community_id,
        }


def build_apartments() -> tuple[ApartmentRecipe, ...]:
    """Build the stable 80-apartment target inventory."""
    return tuple(
        ApartmentRecipe(
            apartment_id=f"sim:apartment:{number:03d}",
            room=f"SIM-{number:03d}",
            occupant_slots=("A", "B") if 66 <= number <= 70 else ("A",),
            target_occupied=number <= OCCUPIED_APARTMENT_TARGET,
        )
        for number in range(1, APARTMENT_TARGET + 1)
    )


def build_residents(
    apartments: Iterable[ApartmentRecipe] | None = None,
) -> tuple[ResidentRecipe, ...]:
    """Build 75 stable identities against the supplied apartment recipe."""
    apartment_rows = build_apartments() if apartments is None else tuple(apartments)
    apartment_by_number = {
        int(apartment.room.removeprefix("SIM-")): apartment
        for apartment in apartment_rows
    }
    assignments: list[tuple[int, str]] = [
        (number, "A") for number in range(1, 66)
    ]
    assignments.extend(
        (number, slot)
        for number in range(66, 71)
        for slot in ("A", "B")
    )
    residents = []
    for ordinal, (apartment_number, slot) in enumerate(assignments, start=1):
        apartment = apartment_by_number[apartment_number]
        residents.append(
            ResidentRecipe(
                resident_key=f"resident-{ordinal:03d}",
                resident_id=f"sim:resident:{ordinal:03d}",
                name=f"SIM Resident {ordinal:03d}",
                preferred_name=f"Resident {ordinal:03d}",
                apartment_id=apartment.apartment_id,
                room=apartment.room,
                occupant_slot=slot,
                pendant_id=f"sim:pendant:{ordinal:03d}",
                enabled_for_burn_in=ordinal <= BURN_IN_RESIDENT_TARGET,
            )
        )
    return tuple(residents)


def _require_unique(values: Iterable[str], label: str) -> None:
    rows = tuple(values)
    if len(rows) != len(set(rows)):
        raise BlueprintError(f"duplicate {label}")


def validate_blueprint(
    apartments: Iterable[ApartmentRecipe], residents: Iterable[ResidentRecipe]
) -> dict:
    """Validate counts, identities, occupancy and synthetic provenance."""
    apartment_rows, resident_rows = tuple(apartments), tuple(residents)
    if len(apartment_rows) != APARTMENT_TARGET:
        raise BlueprintError(f"expected {APARTMENT_TARGET} apartments")
    if len(resident_rows) != RESIDENT_TARGET:
        raise BlueprintError(f"expected {RESIDENT_TARGET} residents")

    _require_unique((a.apartment_id for a in apartment_rows), "apartment id")
    _require_unique((a.room for a in apartment_rows), "room")
    _require_unique((r.resident_key for r in resident_rows), "resident key")
    _require_unique((r.resident_id for r in resident_rows), "resident id")
    _require_unique((r.pendant_id for r in resident_rows), "pendant id")
    _require_unique(
        (f"{r.apartment_id}:{r.occupant_slot}" for r in resident_rows),
        "apartment occupant slot",
    )

    apartment_by_id = {a.apartment_id: a for a in apartment_rows}
    occupancy = {a.apartment_id: [] for a in apartment_rows}
    for resident in resident_rows:
        apartment = apartment_by_id.get(resident.apartment_id)
        if not apartment:
            raise BlueprintError(f"unknown apartment for {resident.resident_id}")
        if resident.room != apartment.room:
            raise BlueprintError(f"room mismatch for {resident.resident_id}")
        if resident.occupant_slot not in apartment.occupant_slots:
            raise BlueprintError(f"invalid occupant slot for {resident.resident_id}")
        occupancy[resident.apartment_id].append(resident)

    occupied = [a for a in apartment_rows if occupancy[a.apartment_id]]
    if len(occupied) != OCCUPIED_APARTMENT_TARGET:
        raise BlueprintError(
            f"expected {OCCUPIED_APARTMENT_TARGET} occupied apartments"
        )
    for apartment in apartment_rows:
        actually_occupied = bool(occupancy[apartment.apartment_id])
        if actually_occupied != apartment.target_occupied:
            raise BlueprintError(f"target occupancy mismatch for {apartment.room}")
        if len(occupancy[apartment.apartment_id]) > len(apartment.occupant_slots):
            raise BlueprintError(f"apartment capacity exceeded for {apartment.room}")

    doubles = [a for a in occupied if len(occupancy[a.apartment_id]) == 2]
    if len(doubles) != DOUBLE_OCCUPANCY_APARTMENT_TARGET:
        raise BlueprintError(
            f"expected {DOUBLE_OCCUPANCY_APARTMENT_TARGET} double-occupancy apartments"
        )

    burn_in = [r for r in resident_rows if r.enabled_for_burn_in]
    if len(burn_in) != BURN_IN_RESIDENT_TARGET:
        raise BlueprintError(f"expected {BURN_IN_RESIDENT_TARGET} burn-in residents")
    if any(len(occupancy[r.apartment_id]) != 1 for r in burn_in):
        raise BlueprintError("burn-in residents must be single-occupancy")

    all_rows = (*apartment_rows, *resident_rows)
    if any(
        not row.synthetic
        or row.simulation_scope != SIMULATION_SCOPE
        or row.simulation_community_id != COMMUNITY_ID
        for row in all_rows
    ):
        raise BlueprintError("every blueprint row must carry synthetic provenance")

    return {
        "community_id": COMMUNITY_ID,
        "apartments": len(apartment_rows),
        "occupied_apartments": len(occupied),
        "residents": len(resident_rows),
        "burn_in_residents": len(burn_in),
        "double_occupancy_apartments": len(doubles),
        "vacant_apartments": len(apartment_rows) - len(occupied),
    }


APARTMENTS = build_apartments()
RESIDENTS = build_residents(APARTMENTS)
BURN_IN_RESIDENTS = tuple(r for r in RESIDENTS if r.enabled_for_burn_in)
SUMMARY = validate_blueprint(APARTMENTS, RESIDENTS)

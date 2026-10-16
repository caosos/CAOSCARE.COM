"""Living-community blueprint: deterministic, synthetic and internally safe."""
from dataclasses import replace

import pytest

from simulation.community_blueprint import (
    APARTMENTS,
    BURN_IN_RESIDENTS,
    COMMUNITY_ID,
    RESIDENTS,
    SIMULATION_SCOPE,
    SUMMARY,
    BlueprintError,
    build_apartments,
    build_residents,
    validate_blueprint,
)


def test_target_counts_and_occupancy_shape():
    assert SUMMARY == {
        "community_id": COMMUNITY_ID,
        "apartments": 80,
        "occupied_apartments": 70,
        "residents": 75,
        "burn_in_residents": 10,
        "double_occupancy_apartments": 5,
        "vacant_apartments": 10,
    }
    counts = {a.apartment_id: 0 for a in APARTMENTS}
    for resident in RESIDENTS:
        counts[resident.apartment_id] += 1
    assert sorted(counts.values()).count(0) == 10
    assert sorted(counts.values()).count(1) == 65
    assert sorted(counts.values()).count(2) == 5


def test_burn_in_is_ten_deterministic_single_occupancy_residents():
    assert [r.resident_id for r in BURN_IN_RESIDENTS] == [
        f"sim:resident:{number:03d}" for number in range(1, 11)
    ]
    full_counts = {
        apartment.apartment_id: sum(
            resident.apartment_id == apartment.apartment_id for resident in RESIDENTS
        )
        for apartment in APARTMENTS
    }
    assert all(full_counts[r.apartment_id] == 1 for r in BURN_IN_RESIDENTS)
    assert all(r.room == f"SIM-{number:03d}" for number, r in enumerate(BURN_IN_RESIDENTS, 1))


def test_stable_ids_are_unique_and_rebuild_is_deterministic():
    assert build_apartments() == APARTMENTS
    assert build_residents(build_apartments()) == RESIDENTS
    assert len({a.apartment_id for a in APARTMENTS}) == 80
    assert len({a.room for a in APARTMENTS}) == 80
    assert len({r.resident_key for r in RESIDENTS}) == 75
    assert len({r.resident_id for r in RESIDENTS}) == 75
    assert len({r.pendant_id for r in RESIDENTS}) == 75
    assert len({(r.apartment_id, r.occupant_slot) for r in RESIDENTS}) == 75


def test_every_row_is_explicitly_synthetic():
    for row in (*APARTMENTS, *RESIDENTS):
        assert row.synthetic is True
        assert row.simulation_scope == SIMULATION_SCOPE
        assert row.simulation_community_id == COMMUNITY_ID
    assert all(r.name.startswith("SIM Resident ") for r in RESIDENTS)


def test_validation_rejects_provenance_and_occupancy_drift():
    unsafe = (replace(RESIDENTS[0], synthetic=False), *RESIDENTS[1:])
    with pytest.raises(BlueprintError, match="synthetic provenance"):
        validate_blueprint(APARTMENTS, unsafe)

    duplicate_slot = (
        RESIDENTS[0],
        replace(
            RESIDENTS[1],
            apartment_id=RESIDENTS[0].apartment_id,
            room=RESIDENTS[0].room,
            occupant_slot=RESIDENTS[0].occupant_slot,
        ),
        *RESIDENTS[2:],
    )
    with pytest.raises(BlueprintError, match="apartment occupant slot"):
        validate_blueprint(APARTMENTS, duplicate_slot)

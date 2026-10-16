"""Pure safety contract for future canonical resident provisioning."""

from simulation.community_blueprint import (
    BURN_IN_RESIDENTS,
    COMMUNITY_ID,
    SIMULATION_SCOPE,
)


def test_resident_payload_preserves_server_set_synthetic_scope():
    """A provisioner must not lose the markers that make reset/isolation safe."""
    payload = BURN_IN_RESIDENTS[0].resident_payload()

    assert payload["synthetic"] is True
    assert payload["simulation_scope"] == SIMULATION_SCOPE
    assert payload["simulation_community_id"] == COMMUNITY_ID
    assert "simulation_run_id" not in payload

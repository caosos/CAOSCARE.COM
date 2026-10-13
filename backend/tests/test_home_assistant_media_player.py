"""State-reporting TV volume contract for Home Assistant media_player."""

from device_adapters import _read_media_player_state, _verifies


def test_media_player_volume_is_normalized_to_percent():
    assert _read_media_player_state(
        {"volume_level": 0.42, "is_volume_muted": False}, "playing"
    ) == {"power": "on", "volume": 42, "muted": False}


def test_media_player_off_has_power_off_but_retains_reported_volume():
    assert _read_media_player_state({"volume_level": 0.2}, "off") == {
        "power": "off", "volume": 20,
    }


def test_media_player_volume_requires_matching_readback():
    after = {"state": "playing", "attributes": {"volume_level": 0.25}}
    assert _verifies("volume", 25, after, "media_player") is True
    assert _verifies("volume", 40, after, "media_player") is False


def test_media_player_power_on_accepts_playing_or_idle_state():
    assert _verifies("power", "on", {"state": "playing", "attributes": {}}, "media_player") is True
    assert _verifies("power", "on", {"state": "idle", "attributes": {}}, "media_player") is True
    assert _verifies("power", "on", {"state": "off", "attributes": {}}, "media_player") is False

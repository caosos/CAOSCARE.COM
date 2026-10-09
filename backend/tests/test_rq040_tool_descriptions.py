"""RQ-040: device tools tell the model to ask on ambiguity (and take a
`device` argument); end_call is restricted to explicit endings. Schema
assertions only - no backend, no network."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.realtime_device_tools import _build_device_tools

AMBIGUOUS_TOOLS = ["toggle_light", "toggle_tv", "set_tv_input", "adjust_tv_volume",
                   "set_tv_channel", "adjust_room_temperature", "set_blinds"]


def _by_name():
    return {t["name"]: t for t in _build_device_tools()}


def test_every_targeted_device_tool_asks_instead_of_retrying():
    tools = _by_name()
    for name in AMBIGUOUS_TOOLS:
        t = tools[name]
        assert "ambiguous" in t["description"], name
        assert "ASK the resident" in t["description"], name
        assert "Never repeat the same call" in t["description"], name
        assert "device" in t["parameters"]["properties"], name
        assert t["parameters"]["additionalProperties"] is False


def _end_call():
    # _build_tools() reads the DB, so check the schema text in the source.
    import inspect
    from routes import realtime_tools
    src = inspect.getsource(realtime_tools)
    i = src.index('"name": "end_call"')
    return {"description": src[i:src.index('"parameters"', i)].replace('"\n                "', "")}


def test_end_call_description_is_restricted():
    d = _end_call()["description"]
    assert "ONLY when the resident has just said goodbye" in d
    assert "NEVER call it for a statement about the test, the wake word" in d
    assert "thanks alone" in d
    assert "do NOT call it again until the resident has answered" in d


def test_rq041_end_call_forbids_unprompted_farewell():
    d = _end_call()["description"]
    assert "NEVER say goodbye or goodnight" in d
    assert "same turn" in d
    from routes.realtime_companion_prompt import _build_companion_instructions  # noqa: F401
    import inspect, routes.realtime_companion_prompt as m
    src = inspect.getsource(m).replace('"\n        "', "")  # join adjacent string literals
    assert "same turn as `end_call`" in src

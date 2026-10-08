"""RQ-031: Aria cannot see, admin asks route to front desk, failed staff
tools never imply arrival. Text assertions over the tool schemas, the
persona prompt and the self-knowledge text. No backend, no network."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.realtime_tools_operations import _build_operations_tools
from routes.realtime_self_knowledge import _system_self_knowledge


def _tool(name):
    from routes import realtime_tools
    import inspect
    src = inspect.getsource(realtime_tools)
    assert name in src
    return src


def test_request_staff_help_covers_no_sight_and_admin_asks():
    desc = next(t for t in _build_operations_tools(["nursing", "front_desk"])
                if t["name"] == "request_staff_help")["description"]
    assert "NO camera" in desc and "never describe what you 'see'" in desc
    assert "executive director" in desc and "front_desk" in desc
    assert "Do NOT say a call is being connected" in desc


def test_request_live_staff_failure_never_implies_arrival():
    src = _tool("request_live_staff")
    assert "NEVER say someone is coming" in src


def test_persona_states_no_sight_and_routing():
    import asyncio
    from routes.realtime_companion_prompt import _build_companion_instructions
    text = asyncio.get_event_loop().run_until_complete(_build_companion_instructions(None))
    assert "You cannot see." in text
    assert "no camera" in text
    assert "category front_desk" in text
    assert "never that someone is aware or on the way" in text


def test_self_knowledge_does_not_imply_sight():
    text = _system_self_knowledge()
    assert "no camera" in text

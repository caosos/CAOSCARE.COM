"""RQ-059: 2026-10-09 session rt_3ctpadu5 - Aria said 'I'll end the call now. Take care' and then
end_call was refused, so the resident was told the call was ending when it was not."""
from routes.realtime_companion_prompt import _build_companion_instructions  # noqa: F401
from routes.realtime_tools import _build_tools
import asyncio, inspect, routes.realtime_companion_prompt as p


def test_end_call_tool_forbids_announcing_before_the_result():
    desc = next(t for t in asyncio.run(_build_tools()) if t.get("name") == "end_call")["description"]
    assert "Say NOTHING before calling it" in desc and "only after a successful" in desc


def test_persona_says_end_call_first_and_goodbye_only_after_success():
    src = inspect.getsource(p)
    assert "FIRST, with no words before it" in src
    assert "until the tool result says it succeeded" in src

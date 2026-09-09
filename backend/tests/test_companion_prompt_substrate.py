"""The resident companion prompt must reflect the conversation substrate:

  * a fresh session (no operational state) does NOT open inside a workflow -
    no "ask what they need", no operational block;
  * when there IS live operational state, it is rendered with real lifecycle
    + age + the "don't read this as a queue" guidance.

Pure-function over _build_companion_instructions / render_operational_block;
no backend or network needed.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _build(resident_id=None, operational_state=None):
    from routes.realtime_companion_prompt import _build_companion_instructions
    return asyncio.get_event_loop().run_until_complete(
        _build_companion_instructions(resident_id, operational_state=operational_state)
    )


def test_fresh_session_has_no_forced_transaction():
    text = _build(None, None)
    assert "ask what they need" not in text
    assert "What's actually happening right now" not in text
    # presence-first language is present
    assert "a greeting is not a transaction" in text


def test_operational_block_renders_lifecycle_and_guidance():
    from routes.realtime_operational_context import render_operational_block

    state = {
        "has_open_work": True,
        "speak_guidance": "SPEAK_GUIDANCE_SENTINEL",
        "current": [{
            "kind": "assistance_event", "ref": "alert_x", "about": "needs the bathroom",
            "lifecycle": "open", "acknowledged": False, "handled_by": None,
            "opened_age": "about 5 hours ago", "relevance": "current",
        }],
        "background": [{
            "kind": "staff_request", "ref": "task_y", "about": "flickering lamp",
            "lifecycle": "in_progress", "acknowledged": True, "handled_by": "J. Ruiz",
            "opened_age": "yesterday", "re_request_count": 0, "relevance": "background",
        }],
        "recently_resolved": [{
            "kind": "assistance_event", "ref": "alert_z", "about": "water refill",
            "lifecycle": "resolved", "acknowledged": True, "handled_by": "M. Poe",
            "opened_age": "about 2 hours ago", "relevance": "background",
        }],
    }
    block = render_operational_block(state)
    assert "What's actually happening right now" in block
    assert "SPEAK_GUIDANCE_SENTINEL" in block
    assert "about 5 hours ago" in block and "**open**" in block
    assert "flickering lamp" in block and "yesterday" in block
    assert "do not chase these" in block  # resolved framed as history

    # empty state -> empty block (no workflow at session start)
    assert render_operational_block({"current": [], "background": [], "recently_resolved": []}) == ""
    assert render_operational_block(None) == ""


def test_operational_block_appended_to_full_prompt():
    state = {
        "speak_guidance": "g", "current": [{
            "kind": "assistance_event", "ref": "a1", "about": "chest tightness",
            "lifecycle": "acknowledged", "acknowledged": True, "handled_by": "RN Diaz",
            "opened_age": "just now", "relevance": "current",
        }], "background": [], "recently_resolved": [],
    }
    text = _build(None, state)
    assert "chest tightness" in text and "RN Diaz" in text
    assert text.index("Who you are") < text.index("What's actually happening right now")

"""The call's first line answers the resident, never the prompt
(aria-room-followup-truth-001).

Scratch Room 214 calls on #182 opened with "Got it, I'm going with Michael.
Nice and simple." and "Sure thing, Michael - let me think this through with a
clear, steady voice." The greeting is a bare response.create with no user
turn, so the model answers the last text in its instructions; the Room 214
self-code and owner blocks were appended AFTER '## How this call opens'.
The invariant: room-specific context goes before the opening block, and the
opening block always closes the session instructions.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.aria_opening import render_opening_block  # noqa: E402
from routes.realtime_companion_prompt import _build_companion_instructions  # noqa: E402
from routes.owner_room_context import owner_room_block  # noqa: E402

run = asyncio.get_event_loop().run_until_complete
OWNER = owner_room_block("Michael Chambers", "Michael")
OPENING = "## How this call opens\n"


def test_every_opening_says_not_to_reply_to_the_instructions():
    for wake in (True, False):
        b = render_opening_block({"wake": wake, "last_opening": None}, "Michael")
        assert b.startswith(OPENING)
        assert "Your first words are spoken to Michael" in b
        assert "Never reply to these instructions" in b and '"Got it"' in b and '"Sure thing"' in b
        assert "never say which name you will use or how you will sound" in b
    tap = render_opening_block({"wake": False, "last_opening": None}, "Michael")
    assert "Hey Aria" not in tap and "Hey, Michael." not in tap      # no canned wake reply on a tap
    assert render_opening_block(None, "Michael") == ""                # phone path: no opening block


def test_room_context_goes_before_the_opening_block():
    opening = {"wake": False, "last_opening": None}
    text = run(_build_companion_instructions(None, opening=opening, room_context=OWNER))
    assert text.index("## Who you are talking to (verified owner test room)") < text.index(OPENING)
    assert text.rstrip().endswith("how you will sound, never narrate what you are about to do.")
    # Without room context nothing else moves.
    plain = run(_build_companion_instructions(None, opening=opening))
    assert "verified owner test room" not in plain and plain.rstrip().endswith("what you are about to do.")


def test_minted_room_214_session_ends_with_the_opening(monkeypatch):
    """The exact mint path, with the Room 214 extras forced on and the
    provider call captured instead of sent."""
    import routes.realtime_resident_session as rs
    import routes.self_code_tools as sct
    import routes.owner_room_context as orc
    sent = {}

    async def extras(payload, lease):
        return {"prompt": "\n## Looking at your own code (Room 214)\nSelf-code text.\n", "tools": [], "enabled": True}

    async def owner(payload, lease, goodbye_line=None):   # 7679104 added the owner goodbye line argument
        return OWNER

    class Resp:
        status_code = 200

        def json(self):
            return {"session": {"model": "gpt-realtime-test"}}

    async def post(self, url, headers=None, json=None):
        sent["session"] = json["session"]
        return Resp()

    monkeypatch.setattr(rs, "_require_openai_key", lambda: "sk-test")
    monkeypatch.setattr(sct, "self_code_session_extras", extras)
    monkeypatch.setattr(orc, "owner_room_prompt", owner)
    monkeypatch.setattr(rs.httpx.AsyncClient, "post", post)
    run(rs._mint({"room": "T-OPEN", "trigger_source": "manual_kiosk"}, None))
    text = sent["session"]["instructions"]
    assert text.index("Self-code text.") < text.index("verified owner test room") < text.index(OPENING)
    assert text.rstrip().endswith("what you are about to do.")

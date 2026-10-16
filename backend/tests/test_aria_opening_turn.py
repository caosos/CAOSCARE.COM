"""The call's opening is its own turn (aria-room-opening-context-regression-003).

Room 214, 2026-10-16: the call opened with a bare response.create and no user
turn, so the model answered the end of the ~35k-character session prompt.
rt_tq43w3sw opened "Hey, Michael. Just checking in! If you meant to ask
something specific, I'm all ears."; that line was then quoted in the next
call's opening block and rt_rx28k7x9 opened with a 30-second capability tour
("Gotcha, you're asking about calls, texts, and tickets ..."). The page now
sends greeting_response() as the first response: one chosen line, its own
short instructions, no tools, nothing from earlier calls.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.aria_opening import WAKE_OPENINGS, TAP_OPENINGS, greeting_response, render_opening_block  # noqa: E402

run = asyncio.get_event_loop().run_until_complete
CHECKIN = "Hey, Michael. Just checking in! If you meant to ask something specific, I'm all ears."
TOUR = ("Gotcha, you're asking about calls, texts, and tickets. I can talk with you and be here while you wait. "
        "I can page a nurse if something feels wrong, or send a staff request for non-emergency needs.")


def _opening(wake, recent):
    return {"wake": wake, "recent_openings": recent, "last_opening": (recent or [None])[0],
            "name": "Michael", "part_of_day": "afternoon"}


def test_greeting_is_one_chosen_line_with_no_tools_and_no_history():
    for wake in (True, False):
        g = greeting_response(_opening(wake, [CHECKIN, TOUR, "Hi, Michael."]))
        assert g["tool_choice"] == "none"
        ins = g["instructions"]
        line = ins.split('"')[1]
        pool = {o.format(n="Michael") for o in (WAKE_OPENINGS if wake else TAP_OPENINGS)} | {"Good afternoon, Michael."}
        assert line in pool and not line.startswith(("Hey, Michael", "Hi, Michael")), line   # rotates past recent leads
        assert "Just checking in" not in ins and "tickets" not in ins and "nurse" not in ins
        assert ("called your name" in ins) == wake and len(ins) < 300


def test_greeting_needs_an_opening_and_falls_back_to_a_plain_line():
    assert greeting_response(None) is None
    g = greeting_response({"wake": True, "recent_openings": [], "name": None})
    assert '"Hey, there."' in g["instructions"]


def test_bad_prior_openings_never_reach_the_session_prompt_tail():
    b = render_opening_block(_opening(True, [CHECKIN, TOUR]), "Michael", "afternoon")
    assert "Just checking in" not in b and "tickets" not in b and "most recent calls opened" not in b


def test_minted_session_carries_the_greeting_for_the_page(monkeypatch):
    """The exact mint path, provider call captured instead of sent: _caos.greeting is what
    realtimeConnection.js sends as the first response.create."""
    import routes.realtime_resident_session as rs
    sent = {}

    class Resp:
        status_code = 200

        def json(self):
            return {"session": {"model": "gpt-realtime-test"}}

    async def post(self, url, headers=None, json=None):
        sent["session"] = json["session"]
        return Resp()

    monkeypatch.setattr(rs, "_require_openai_key", lambda: "sk-test")
    monkeypatch.setattr(rs.httpx.AsyncClient, "post", post)
    for trigger, wake in (("wake_word", True), ("manual_kiosk", False)):
        out = json.loads(run(rs._mint({"room": "T-OPEN", "trigger_source": trigger}, None)).body)
        g = out["_caos"]["greeting"]
        assert g["tool_choice"] == "none" and ("called your name" in g["instructions"]) == wake
        assert g["instructions"] not in sent["session"]["instructions"]

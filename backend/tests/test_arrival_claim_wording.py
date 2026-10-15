"""Which sentences count as "help is coming" (arrival_claim_guard.ARRIVAL).

Voice PE 2026-10-15: "your words are coming through" and "the sound is
coming from the EliteDesk" were treated as arrival claims, stripped, and
replaced with "Your request is recorded..." on a turn with no request.
"""
import pytest

from routes.arrival_claim_guard import ARRIVAL

CLAIMS = [
    "I've sent that to maintenance. It's on its way!",
    "Help is on the way.",
    "Someone is coming to help you.",
    "A staff member will be right there.",
    "The nurse is coming over now.",
    "They'll be right with you.",
    "Maintenance will stop by soon.",
    "Help is en route.",
    "She's headed your way.",
]
NOT_CLAIMS = [
    "I can hear you, Michael, your words are coming through just fine on my end.",
    "So, the speaker sound is coming from the Elite desk unit instead of where you'd expect it.",
    "I can send a request and tell them the sound is coming from the Elite Desk.",
    "I'll be right here if you need me.",
    "By the way, it is coming up on noon.",
    "The weather is coming in cooler tomorrow.",
]


@pytest.mark.parametrize("text", CLAIMS)
def test_arrival_claims_are_caught(text):
    assert ARRIVAL.search(text)


@pytest.mark.parametrize("text", NOT_CLAIMS)
def test_ordinary_coming_is_not_a_claim(text):
    assert not ARRIVAL.search(text)

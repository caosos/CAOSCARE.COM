"""A durable room setting accepts only an unambiguous whole-turn yes."""

import pytest

from routes.kiosks import _AFFIRMATIVE


@pytest.mark.parametrize("text", ["yes", "Yes.", "correct", "that's right", "Yes, that's right", "please do"])
def test_whole_turn_affirmatives_are_accepted(text):
    assert _AFFIRMATIVE.fullmatch(text)


@pytest.mark.parametrize("text", ["yes, but leave it on", "I said yes yesterday", "maybe", "no", "yes and no"])
def test_qualified_or_ambiguous_answers_are_rejected(text):
    assert not _AFFIRMATIVE.fullmatch(text)

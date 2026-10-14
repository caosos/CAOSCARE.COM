"""Does what the resident said support a room-device change?

Server-side form of the room page's guards (frontend/src/lib/powerDirection.js,
realtimeDeviceTools.js tvPowerRequestIsGrounded, realtimeRoomControls.js).
The model picks tool arguments; these checks require the resident's own
words for the same turn to agree before anything is sent:
- light on/off must not contradict the sentence, nor be invented from a
  sentence that asks for no power change (Room 214, 2026-10-10/10-12);
- TV power needs the TV named with an explicit power verb in that direction;
- volume and channel need a volume cue or the channel number said aloud
  (2026-08-30 "Hello Lab" -> volume 11).
A turn with no transcript at all is not blocked for lights (no evidence
either way), matching the room page.
"""
import re
from typing import Optional

_ON = re.compile(r"\bon\b", re.I)
_OFF = re.compile(r"\b(off|shut|darken|dark)\b|\blights? out\b", re.I)
_NEGATED = re.compile(r"\b(don'?t|do not|never|not)\b", re.I)
_POWER_WORDS = re.compile(r"\b(turn|switch|shut|put|light|lights|lamp|on|off|bright|dim|dark|darken)\b", re.I)
_CONFIRM = re.compile(r"\b(yes|yeah|yep|sure|okay|ok|please|do it|go ahead|pick one)\b", re.I)


def heard_power_direction(text: Optional[str]) -> Optional[str]:
    t = text or ""
    if _NEGATED.search(t):
        return None
    on, off = bool(_ON.search(t)), bool(_OFF.search(t))
    return None if on == off else ("on" if on else "off")


def power_direction_mismatch(state: Optional[str], text: Optional[str], label: str = "light",
                             answering: bool = False) -> Optional[str]:
    """A short refusal for the model, or None when the action may run.
    answering = the turn replies to Aria's own "which one?" question."""
    if state not in ("on", "off"):
        return None
    words = (text or "").strip()
    if not words:
        return None
    heard = heard_power_direction(words)
    contradicts = heard is not None and heard != state
    unasked = not answering and heard is None and not _POWER_WORDS.search(words) and not _CONFIRM.search(words)
    if not contradicts and not unasked:
        return None
    return f"I want to be sure I heard you right - did you want the {label} on or off? (Nothing was changed.)"


_TV = r"(?:the\s+)?(?:tv|television)"
_TV_POWER = {
    "on": [re.compile(rf"\b(?:turn|switch|power|put)\s+{_TV}\s+(?:back\s+)?on\b", re.I),
           re.compile(rf"\b(?:turn|switch|power|put)\s+(?:back\s+)?on\s+{_TV}\b", re.I)],
    "off": [re.compile(rf"\b(?:turn|switch|power|shut)\s+{_TV}\s+off\b", re.I),
            re.compile(rf"\b(?:turn|switch|power|shut)\s+off\s+{_TV}\b", re.I)],
}
_TV_NEGATION = re.compile(r"\b(?:don'?t|do\s+not|not|never|no)\b", re.I)


def tv_power_grounded(text: Optional[str], state: Optional[str]) -> bool:
    heard = (text or "").strip()
    if state not in _TV_POWER or _TV_NEGATION.search(heard):
        return False
    return any(p.search(heard) for p in _TV_POWER[state])


VOLUME_PHRASES = re.compile(
    r"\b(volume|loud(er|ness)?|quiet(er)?|turn\s*(it|the\s*(tv|sound))?\s*(up|down)|mute|unmute)\b", re.I)
CHANNEL_WORD = re.compile(r"\bchannel\b", re.I)

_ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}


def numbers_in(text: Optional[str]) -> set:
    """Numbers said as digits ("channel 11") or words ("twenty one")."""
    lower = (text or "").lower()
    out = {int(m) for m in re.findall(r"\d+", lower)}
    words = [w for w in re.split(r"[^a-z]+", lower) if w]
    for i, w in enumerate(words):
        if w in _TENS:
            nxt = _ONES.get(words[i + 1]) if i + 1 < len(words) else None
            out.add(_TENS[w] + (nxt if nxt and 0 < nxt < 10 else 0))
        elif w in _ONES:
            out.add(_ONES[w])
    return out

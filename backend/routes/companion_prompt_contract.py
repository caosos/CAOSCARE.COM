"""What every resident-companion prompt must (and must not) contain.

One definition used by the regression tests and by
scripts/measure_voice_prompt.py, so "required section present", "duplicated
instruction" and "unsupported tool claim" mean the same thing in both.
"""
import re

from routes.companion_tool_guidance import CAPABILITY

# Mandatory blocks: each must appear exactly once.
REQUIRED_SECTIONS = (
    "## About yourself", "## Who you are", "## What never to say", "## What to do",
    "## Truth discipline", "## Memory is reference", "## Attribution discipline",
    "## When you make a mistake", "## What you can do", "## Safety", "## Right now",
)

# Mandatory instructions: each must be stated in exactly one place.
RULES = {
    "emergency": r"chest pain",
    "name_not_negotiable": r"negotiable",
    "never_overpromise": r"NEVER say you can do something and then fail",
    "rest_or_quiet": r"rest or be quiet|'let me rest'",
    "session_ending_phrases": r"that'll be all for now",
    "attribution_source": r"never claim 'you told me'",
    "no_unbacked_action": r"unless you have actually invoked the tool",
    "name_correction_tool": r"`update_preferred_name`",
}

# Text that is only true on the kiosk (screen) channel.
KIOSK_ONLY = ("## What's on the kiosk screen", "The kiosk will hang up",
              "OpenAI Realtime API (WebRTC)")
LIVE_WEB_CLAIM = "look things up on the live web"
_TOOL_REF = re.compile(r"`([a-z][a-z0-9_]+)`")


def referenced_tools(text: str, universe) -> set:
    return {n for n in _TOOL_REF.findall(text) if n in universe}


def unsupported_tool_claims(text: str, provided, universe) -> list:
    """Tools named to the model that this call does not provide."""
    return sorted(referenced_tools(text, universe) - set(provided))


def unsupported_capability_claims(text: str, provided, channel: str) -> list:
    out = [f"capability:{t}" for t, phrase in CAPABILITY.items()
           if t not in provided and phrase in text]
    if LIVE_WEB_CLAIM in text and "research_topic" not in provided:
        out.append("capability:live_web")
    if channel == "voice":
        out += [f"channel:{p}" for p in KIOSK_ONLY if p in text]
    return out


def rule_counts(text: str) -> dict:
    return {k: len(re.findall(p, text)) for k, p in RULES.items()}


def duplicated_instructions(text: str) -> list:
    dup = [k for k, n in rule_counts(text).items() if n > 1]
    dup += [h for h in REQUIRED_SECTIONS if text.count(h) > 1]
    return dup


def missing_sections(text: str) -> list:
    return [h for h in REQUIRED_SECTIONS if h not in text]

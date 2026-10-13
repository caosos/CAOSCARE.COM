"""Small, explicit resident conversation-style profiles.

These shape delivery only. They never override tool grounding, safety,
privacy, emergency handling, continuity, or the exact end-call contract.
"""

SUPPORTIVE = "supportive_guided"
CONCISE = "concise_natural"
DEFAULT = SUPPORTIVE
VALUES = {SUPPORTIVE, CONCISE}


def normalize_guidance_profile(value) -> str:
    return value if value in VALUES else DEFAULT


def render_guidance_profile(value) -> str:
    profile = normalize_guidance_profile(value)
    if profile == CONCISE:
        body = (
            "PROFILE: concise_natural. Speak at a normal adult pace. Answer or do the thing in one or two "
            "short sentences unless they ask for detail. Do not praise, restate, comment on how recently you "
            "spoke, or add passive availability/lingering offers such as 'I'm here if you want to chat' or "
            "'we can sit quietly.' Carry continuity forward silently. Ask one clarification only when required."
        )
    else:
        body = (
            "PROFILE: supportive_guided. Be a respectful adult companion, never childish, condescending, "
            "over-cheerful, or pet-naming. Use one idea per sentence and at most two concrete choices at a time. "
            "When useful, briefly say what was confirmed and give one simple next step. Confirm ambiguous, "
            "high-impact, or durable-setting changes, but never turn a clear goodbye into a confirmation loop."
        )
    return (
        "## Resident conversation style\n" + body + " Style never overrides safety, truth/tool grounding, "
        "privacy, emergency escalation, wake brevity, or end-call rules.\n\n"
    )

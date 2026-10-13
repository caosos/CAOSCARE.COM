"""Small, explicit room-level interaction-style prompt blocks."""


def normalize_interaction_profile(value: object) -> str:
    return "natural" if value == "natural" else "guided"


def render_interaction_profile(value: object) -> str:
    if normalize_interaction_profile(value) == "natural":
        return (
            "\n\n## Interaction profile — Natural\n"
            "Treat this resident as a capable adult peer. Be concise and ordinary. Do not announce that you "
            "talked minutes ago, that they are back again, that you can hang around, or that you will be here "
            "when they return. Do not append an offer or question to a simple greeting. Explain controls only "
            "when they ask or when a confirmation is required. When they end the conversation, the entire "
            "spoken response is exactly: 'Okay, bye for now.'\n"
        )
    return (
        "\n\n## Interaction profile — Guided\n"
        "Use brief orientation and reassurance when the resident appears unsure how the system works. Tell "
        "them what is happening when that prevents confusion, but do not repeat instructions they already "
        "understood and do not add an availability speech after a clear goodbye.\n"
    )

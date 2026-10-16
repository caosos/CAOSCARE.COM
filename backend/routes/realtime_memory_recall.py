"""'What do I usually ask you about?' - answered from the record.

Owner review 2026-10-16 (aria-room-runtime-fixes-001): Room 214 Aria gave
generic filler to "what do I usually ask you for", although every finished
conversation is already summarized into db.memories (aria_life_memory.py).
This counts topics across those summaries with a fixed keyword table, so the
answer is a tally of real past conversations, never a guess. Only topics that
came up in at least MIN_COUNT conversations are listed.
"""
import re

MIN_COUNT = 2
MAX_TOPICS = 6

# (label, pattern). A summary counts once per topic.
TOPICS = (
    ("turning the lights or lamps on, off, or dimmer", r"\b(lights?|lamps?|dim)\b"),
    ("the TV - power, volume, sound", r"\b(tv|television)\b"),
    ("news and current events", r"\b(news|elections?|current events)\b"),
    ("the time or the date", r"\b(what time|the time|the date)\b"),
    ("the weather", r"\bweather\b"),
    ("meals and the menu", r"\b(supper|dinner|lunch|breakfast|menu|meal)s?\b"),
    ("how you work and what you can do", r"\b(capabilit\w*|her code|own code|how she|remembers?|limitations?)\b"),
    ("their health", r"\b(health|doctor|swelling|pain|medic\w*)\b"),
    ("requests to staff", r"\b(request|maintenance|nurse|staff|administration)\b"),
    ("testing the wake word and the system", r"\b(wake word|testing|tested|tests?)\b"),
)
_COMPILED = tuple((label, re.compile(p, re.I)) for label, p in TOPICS)


def usual_asks(summaries: list) -> list:
    """[(label, count)] most-frequent first, from conversation summary texts."""
    counts = {}
    for text in summaries:
        for label, rx in _COMPILED:
            if rx.search(text or ""):
                counts[label] = counts.get(label, 0) + 1
    ranked = sorted((c, -i, label) for i, (label, _) in enumerate(TOPICS) if (c := counts.get(label, 0)) >= MIN_COUNT)
    return [(label, c) for c, _, label in reversed(ranked)][:MAX_TOPICS]


def render_usual_asks(name: str, summaries: list) -> str:
    asks = usual_asks(summaries)
    if not asks:
        return ""
    lines = "\n".join(f"- {label} (came up in {c} of your last {len(summaries)} conversations)" for label, c in asks)
    return (f"\n\n## What {name} usually asks you for  (counted from your saved conversation summaries)\n"
            f"{lines}\n")

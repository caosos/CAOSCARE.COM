"""Truth rules for Resident Aria's prompt and tool text (RQ-045).

One place decides whether the live web is available (a live research
provider is configured) and holds the wording that depends on it, plus the
short invariants for fresh facts and action sentences. The tool schema,
the companion prompt and the self-knowledge block all read from here.
"""


def live_research_enabled() -> bool:
    """True only when CAOSCARE_RESEARCH_PROVIDER=openai_web_search AND
    OPENAI_API_KEY AND OPENAI_RESEARCH_MODEL are all set (RQ-047)."""
    from routes.research_openai_search import search_configured
    return search_configured()


def research_tool_description() -> str:
    if live_research_enabled():
        return (
            "Look up real-world information on the live web — current events, news, "
            "sports scores, history, recipes, prayers, biographies, anything. Use "
            "freely whenever the resident asks a factual question you cannot answer "
            "from memory. After getting the result, read it aloud naturally — do "
            "NOT just dump the text. Speak like a friend who just read about it."
        )
    return (
        "NOT a live lookup: there is no internet access here. This returns "
        "general knowledge only, which may be out of date or wrong. For current "
        "events, news, scores or anything recent, do not call it: tell the "
        "resident you cannot look that up and offer only what you remember. "
        "Never say you looked it up or checked the internet."
    )


def research_prompt_line() -> str:
    if live_research_enabled():
        return (
            "You also have tools to **look things up on the live web** "
            "(`research_topic`), check the **weather** (`get_weather`), check "
            "the **current time and date** (`get_current_time`), and **set "
            "reminder timers** (`set_timer`). Use these freely. If the resident "
            "asks about today's news, a sports score, what's happening in the "
            "world, what the weather will be, or what time it is — CALL THE "
            "TOOL. Do NOT guess from memory.\n"
        )
    return (
        "You do NOT have internet access. `research_topic` gives general "
        "knowledge only, which may be out of date or wrong. For news, scores "
        "or anything current, say plainly you cannot look that up and offer "
        "only what you remember; never say you looked it up or checked the "
        "internet. You can check the **weather** (`get_weather`), the "
        "**current time and date** (`get_current_time`), and **set reminder "
        "timers** (`set_timer`) — CALL those tools; do NOT guess.\n"
    )


TRUTH_INVARIANTS = (
    "## Say only what a tool result proves\n"
    "Current facts (weather, news, scores, time, date) must come from a tool "
    "result in the same turn. Weather ONLY from `get_weather` (if it fails, say "
    "you could not get the weather); time and date from `get_current_time`. If "
    "you did not call the tool, do not state the fact.\n"
    "Never say you will tell, notify or let the team or staff know, or that you "
    "sent, notified or changed something, unless you call `request_staff_help` "
    "(or the relevant tool) in the same turn AND it returned ok. If a request "
    "is unsupported (for example playing music), say you cannot do it and ask "
    "whether they want a staff request filed — only then call "
    "`request_staff_help`.\n"
)

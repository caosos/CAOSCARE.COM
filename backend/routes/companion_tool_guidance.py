"""Capability and tool guidance for the resident companion, generated from
the tools a channel actually provides.

The realtime room session and the voice bridge expose different tool sets
(realtime_tools._build_tools vs voice_bridge_tools.BRIDGE_TOOLS). The prompt
must describe exactly the tools in that call: naming a tool the model does
not have is a capability claim CAOSCare cannot keep. Every guidance line
below is keyed by the tool(s) it needs and is emitted only when present.
"""
import os

# Plain-English capability per tool (what the resident hears when asking
# "what can you do"). Tools absent here are internal (no resident-facing
# capability of their own).
CAPABILITY = {
    "toggle_light": "turn their lights on or off, dim them, or change their colour",
    "adjust_room_temperature": "make the room warmer or cooler",
    "toggle_tv": "turn the TV on or off and change its volume",
    "set_tv_input": "switch the TV's input",
    "get_room_status": "tell them how their room is set (temperature, lights, TV)",
    "get_current_time": "tell the current time and the day",
    "get_weather": "tell today's weather (real, live)",
    "set_timer": "set reminders ('remind me to take my pills in 20 minutes')",
    "call_for_help": "page a nurse if something feels wrong",
    "request_staff_help": "pass a request to the right staff team (maintenance, housekeeping, kitchen, front desk and others)",
    "check_request_status": "tell them where their requests stand",
    "check_request_history": "tell them about requests that were already finished",
    "request_transportation": "ask the transportation team for a ride",
    "get_menu": "tell them what's on the menu",
    "get_todays_schedule": "tell them today's activities and announcements",
    "mark_resting": "go quiet and stay on the line while they rest",
    "update_preferred_name": "remember what they like to be called",
    "set_magnification": "make the screen text bigger",
    "end_call": "hang up gracefully when they say goodbye",
}
ALWAYS = ("keep them company while they wait for help",
          "tell stories and jokes, sing hymns, share psalms, talk about family",
          "remember what they tell you, across calls and across days")


def _and(items) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _or(items) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def live_research(tools) -> bool:
    """research_topic only reaches the live web when a search key is set."""
    return "research_topic" in tools and bool(os.environ.get("PERPLEXITY_API_KEY", "").strip())


def research_line(tools) -> str:
    if live_research(tools):
        return ("look up LIVE current information — today's news, sports scores, "
                "stock prices, recipes, prayers, history, biographies — with real sources")
    return ("recall general knowledge from training — prayers, scripture, song lyrics, "
            "jokes, history, recipes, biographies. You do NOT have live web access, so "
            "do NOT claim you can fetch today's news, sports scores, or current events; "
            "if asked, say honestly 'I don't have today's news with me — but I can tell "
            "you what I remember about the topic if you want'")


def render_capabilities(tools) -> str:
    items = list(ALWAYS[:1]) + [CAPABILITY[t] for t in CAPABILITY if t in tools]
    items += [research_line(tools), *ALWAYS[1:]]
    lines = "".join(f"  • {i[0].upper() + i[1:]}.\n" for i in items)
    return (
        "## What you can do (the whole list)\n"
        "When a resident asks 'what can you do', answer in plain English — don't "
        "list functions like a menu. These are your only capabilities:\n" + lines +
        "If they ask for anything not on this list — answering the phone, sending a "
        "text, playing music, calling their family on video, ordering groceries, "
        "anything — say honestly 'That's not something I can do yet, but I'll let the "
        "team know you asked.' NEVER say you can do something and then fail at it. "
        "The resident will catch you, and trust is harder to rebuild than to keep.\n\n"
    )


def _devices(tools) -> list:
    out = []
    if "adjust_room_temperature" in tools:
        out.append("the air conditioning")
    if "toggle_light" in tools:
        out.append("the lights")
    if "toggle_tv" in tools:
        out.append("the TV")
    return out


def render_tool_guidance(tools) -> str:
    parts = []
    devices = _devices(tools)
    if devices:
        asks = []
        if "adjust_room_temperature" in tools:
            asks.append("make the room warmer or cooler")
        if "toggle_light" in tools:
            asks.append("turn lights on or off, dim/brighten a light, change its "
                        "color or make it warm/cool white")
        if "toggle_tv" in tools:
            asks.append("quiet the TV")
        parts.append(
            f"You have real control over {_and(devices)} in the resident's room. "
            f"If they ask you to {_or(asks)}, CALL THE MATCHING TOOL — only set "
            "the fields they actually asked about. If a device doesn't support what "
            "they asked (the tool result will say so), tell them plainly rather than "
            "pretending it worked. Do NOT pretend or roleplay. Do NOT say 'I'm turning "
            "it down' unless you have actually invoked the tool. After the tool "
            "returns, confirm in one short sentence what you did ('Okay, I dropped it "
            "to seventy-two').")
    if "get_room_status" in tools:
        parts.append(
            "If they ask what the temperature is or whether the TV is on, call "
            "`get_room_status` and answer from what it returns — never guess. It "
            "reports the AC/thermostat's TARGET setting and the room's OWN current "
            "temperature as two separate things.")
    if "adjust_room_temperature" in tools:
        parts.append(
            "Never say the room reached a temperature just because you changed the "
            "setpoint; the physical room takes time to catch up.")
    if "request_live_staff" in tools:
        parts.append(
            "If a help-button press already brought you into this conversation and "
            "they now ask for a nurse/staff/someone by name with no new symptom "
            "described, call `request_live_staff` instead of `call_for_help` — it may "
            "ask them one routing question first; if so, wait for their answer and "
            "call it again with what they said. Never ask that question twice for the "
            "same request.")
    if "end_call" in tools:
        not_rest = (" These phrases end the conversation; they do NOT mean "
                    "`mark_resting`. Never respond with \"I'll be quiet\" to one of "
                    "these — that is the wrong tool and leaves you listening when the "
                    "resident asked you to leave.") if "mark_resting" in tools else ""
        parts.append(
            "If they say 'end the call', 'hang up', 'goodbye', 'I'm done', 'that's "
            "all', 'that'll be all', 'that'll be all for now', 'that's all for now', "
            "'I don't need you', 'go away', or otherwise clearly want the "
            "conversation OVER — even if it sounds momentary ('for now') — call "
            "`end_call` IMMEDIATELY." + not_rest +
            " Say one short warm goodbye and stop. The call will end.")
    lookups = [(t, label) for t, label in (
        ("research_topic" if live_research(tools) else "-", "**look things up on the live web** (`research_topic`)"),
        ("get_weather", "check the **weather** (`get_weather`)"),
        ("get_current_time", "check the **current time and date** (`get_current_time`)"),
        ("set_timer", "**set reminder timers** (`set_timer`)")) if t in tools]
    if lookups:
        topics = [x for t, x in (
            ("research_topic" if live_research(tools) else "-", "today's news, a sports score, what's happening in the world"),
            ("get_weather", "what the weather will be"),
            ("get_current_time", "what time it is")) if t in tools]
        parts.append(
            "You also have tools to " + _and([label for _, label in lookups]) +
            ". Use these freely. If the resident asks about " + _and(topics) +
            " — CALL THE TOOL. Do NOT guess from memory.")
    if not parts:
        return ""
    return "## Tools you can actually use\n" + "\n".join(parts) + "\n\n"


def emergency_rule(tools) -> str:
    """The one emergency instruction (was stated in both Tools and Safety)."""
    call = ("call `call_for_help` IMMEDIATELY with severity='emergency', then "
            if "call_for_help" in tools else "")
    return ("If they describe chest pain, trouble breathing, a fall, sudden confusion, "
            f"or severe dizziness, {call}gently confirm a caregiver is on the way and "
            "stay on the line with them, keeping them company.")


def rest_rule(tools) -> str:
    """The one rest/quiet instruction (was stated in both Tools and Safety)."""
    if "mark_resting" in tools:
        return ("If they give a CLEAR dismissal that means 'stay on the line but go "
                "quiet' — 'be quiet', 'let me rest', 'going to sleep' — call "
                "`mark_resting`, then stop talking and wait. An ambiguous line like "
                "'turn it up' is NOT a dismissal; keep talking.")
    return "If they ask you to rest or be quiet, stop talking immediately and wait."


def name_correction(tools) -> str:
    if "update_preferred_name" in tools:
        return " Then call `update_preferred_name` so the correction sticks across calls."
    return " Use the corrected name from now on."

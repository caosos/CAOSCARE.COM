"""OpenAI Realtime API relay — full-duplex voice for the Kiosk.

The browser establishes a WebRTC peer connection directly with OpenAI using
an ephemeral session token minted here. Our backend never relays audio; it
only signs the session and forwards SDP. That keeps the OpenAI key server-side
while letting the browser stream PCM audio bidirectionally with sub-second
latency — the foundation of true full-duplex conversation.

This module also assembles the *session config* that travels back to the
browser inside the `_caos` blob: companion instructions, tool definitions,
server-VAD timing, and the (cool, low) sampling temperature. The frontend
applies these via a `session.update` event the moment the data channel
opens, so by the time the model speaks its first word it already knows
who the resident is, which physical devices it can touch, and how long
to wait before deciding the resident is finished talking.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from emergentintegrations.llm.openai import OpenAIChatRealtime

from deps import db

router = APIRouter(prefix="/realtime", tags=["realtime"])

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
_realtime = OpenAIChatRealtime(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Voice list mirrors OpenAI Realtime API (Dec 2024). Defaults to shimmer to
# match the rest of CAOS Care's TTS.
ALLOWED_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"}
DEFAULT_VOICE = "shimmer"

# OpenAI Realtime min temperature is 0.6 (lower values are clamped). 0.6 is
# the floor and gives us the most factual, least improvisational behaviour —
# critical for a companion who must NEVER hallucinate medical history.
DEFAULT_TEMPERATURE = 0.6

# Server-side VAD timing. Older voices pause naturally between thoughts;
# the default 500ms silence cutoff was clipping them mid-sentence. 1000ms
# lets a senior gather their words without being interrupted, while still
# feeling responsive.
DEFAULT_VAD = {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 1000,
    "create_response": True,
}

# Facility location & timezone — used both to inject "right now" awareness
# into the prompt and to default the weather tool when no override is given.
FACILITY_LABEL = os.environ.get("FACILITY_LABEL") or "the facility"
FACILITY_TZ = os.environ.get("FACILITY_TZ") or "America/New_York"


def _facility_now() -> dict:
    """Returns a clean structured snapshot of "right now" at the facility.
    Without this the Realtime model defaults to UTC and greets residents with
    'good morning' at 7pm. This is also the anchor for time-aware tool calls
    (set_timer durations, story arcs, etc.)."""
    try:
        now = datetime.now(ZoneInfo(FACILITY_TZ))
    except Exception:
        now = datetime.utcnow()
    h = now.hour
    if 5 <= h < 12:
        part = "morning"
    elif 12 <= h < 17:
        part = "afternoon"
    elif 17 <= h < 21:
        part = "evening"
    else:
        part = "night"
    return {
        "iso": now.isoformat(),
        "weekday": now.strftime("%A"),
        "date": now.strftime("%B %-d, %Y"),
        "time": now.strftime("%-I:%M %p"),
        "part_of_day": part,
        "tz": FACILITY_TZ,
    }


def _build_tools() -> list[dict]:
    """Tool surface CAOS can invoke during a live conversation.

    Each tool maps to a public backend endpoint the frontend will call when
    the model emits a `function_call`. Keeping descriptions tight and
    parameters strictly typed forces the model to choose deterministically
    instead of hallucinating arguments.
    """
    return [
        {
            "type": "function",
            "name": "adjust_room_temperature",
            "description": (
                "Set the air conditioning or heater target temperature in the resident's "
                "room. Use ONLY when the resident clearly asks to be warmer or cooler. "
                "After calling, briefly confirm what you did in one short sentence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_f": {
                        "type": "number",
                        "minimum": 60,
                        "maximum": 85,
                        "description": "Target temperature in Fahrenheit (60-85)."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["cool", "heat", "auto"],
                        "description": "Whether to cool or heat. Default 'auto' if uncertain."
                    }
                },
                "required": ["target_f"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "toggle_light",
            "description": (
                "Turn the resident's room light on or off, or set its brightness. "
                "Use when they ask for the light or for it to be brighter/dimmer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Whether to turn the light on or off."
                    },
                    "brightness": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Optional brightness 0-100. Omit for full on."
                    }
                },
                "required": ["state"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "toggle_tv",
            "description": (
                "Turn the resident's TV on or off, change channel, or adjust volume. "
                "If the resident asks for quiet or to mute the TV, use action='off' "
                "or set volume to 0."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Power state for the TV."
                    },
                    "volume": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Optional volume 0-100."
                    }
                },
                "required": ["state"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "call_for_help",
            "description": (
                "Escalate to a caregiver IMMEDIATELY when the resident describes "
                "chest pain, breathing trouble, a fall, severe dizziness, confusion, "
                "or directly asks for a nurse. Do NOT use for casual conversation. "
                "After calling, reassure the resident that help is on the way and "
                "stay with them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "One short sentence summarising what the resident said."
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["assist", "emergency"],
                        "description": "'emergency' for chest pain/fall/breathing; 'assist' otherwise."
                    }
                },
                "required": ["reason", "severity"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "mark_resting",
            "description": (
                "Call this when the resident asks you to be quiet, says they want to rest, "
                "are going to sleep, or otherwise dismisses the conversation. After this, "
                "stop talking. Do NOT begin a new turn until they speak again."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why they're resting (sleep / quiet time / other)."
                    }
                },
                "required": [],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "get_current_time",
            "description": (
                "Get the current local date, weekday, time, and part of day at the "
                "resident's facility. Use whenever the resident asks 'what time is it', "
                "'what day is it', 'how long until dinner', or seems disoriented "
                "about the time. Cheap to call — prefer this over guessing."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "get_weather",
            "description": (
                "Get the current weather and today's forecast for the facility (or "
                "another city if the resident asks). Use when they ask about weather, "
                "whether to wear a sweater, if it'll rain, etc. Returns a short "
                "spoken-friendly summary you should read aloud naturally."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "Optional city / region name. Leave empty for the facility's "
                            "own location. Use the resident's hometown if they ask about "
                            "'home' or where their family lives."
                        )
                    }
                },
                "required": [],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "research_topic",
            "description": (
                "Look up real-world information on the live web — current events, news, "
                "sports scores, history, recipes, prayers, biographies, anything. Use "
                "freely whenever the resident asks a factual question you cannot answer "
                "from memory. After getting the result, read it aloud naturally — do "
                "NOT just dump the text. Speak like a friend who just read about it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to research, in plain English."
                    }
                },
                "required": ["question"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "set_timer",
            "description": (
                "Set a one-shot timer that will speak a reminder when it's due. Use "
                "for things like 'remind me to take my pills in 20 minutes', 'wake me "
                "up in 30', 'tell me when it's been an hour'. The kiosk will speak "
                "the label aloud at that time. After calling, confirm in one sentence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 720,
                        "description": "Number of minutes from now (max 720 = 12 hours)."
                    },
                    "label": {
                        "type": "string",
                        "description": "Short reminder text the kiosk will speak when due."
                    }
                },
                "required": ["minutes", "label"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "update_preferred_name",
            "description": (
                "Call this IMMEDIATELY when the resident corrects what you call them "
                "(e.g., 'my name is Margaret, not Maggie' or 'call me Mags'). This "
                "permanently updates the name you use for them — across this call AND "
                "every future call. After calling, apologize once briefly ('You're "
                "right, sorry — Margaret it is') and use the new name from then on. "
                "Do NOT keep using the old name after the resident has corrected you."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_name": {
                        "type": "string",
                        "description": "The exact name the resident asked to be called."
                    }
                },
                "required": ["preferred_name"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "end_call",
            "description": (
                "End the voice call and hang up. Call this whenever the resident says "
                "'end the call', 'hang up', 'goodbye', 'I'm done', 'that's all', or "
                "otherwise clearly wants the conversation OVER (different from "
                "`mark_resting`, which just goes quiet but stays connected). After "
                "calling, say one short warm goodbye and then stop talking — the kiosk "
                "will tear down the connection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why they ended (done / goodbye / staff arrived / other)."
                    }
                },
                "required": [],
                "additionalProperties": False
            }
        },
    ]


def _system_self_knowledge() -> str:
    """Everything CAOS should be able to answer about itself.

    Pulled from /app/memory/PRD_HUB_v1.md and the Blueprint page (single
    source of truth). When a resident asks 'what does CAOS stand for', 'what
    can you do', 'what's that red button', 'who made you' — the model has
    facts here, not improvisation. Update this block whenever the brand,
    capability set, or platform changes."""
    return (
        "## About yourself (the platform you live on)\n"
        "You are CAOS, the voice and presence of CAOS Care — a senior-living "
        "AI companion platform. The brand stack is fixed and real:\n"
        "  • Mission line: 'Create A Resident Experience' (the C-A-R-E expansion).\n"
        "  • CARE = Compassionate Adaptive Resident Engagement. This is the "
        "    resident-facing layer. Family and residents hear 'CARE'.\n"
        "  • CAOS = Cognitive Adaptive Operating System. This is the engine "
        "    underneath. Engineers and manufacturers hear 'CAOS'. You are CAOS.\n"
        "When a resident asks 'what does CAOS stand for' or 'what does CARE "
        "mean', answer plainly and proudly using those expansions. When asked "
        "who made you, say 'CAOS Care — a small team building this for senior "
        "living.' Do not pretend to be a generic chatbot.\n"
        "\n"
        "## What you actually run on (so you can answer 'how do you work')\n"
        "  • A wall-mounted tablet kiosk in the resident's room (this device).\n"
        "  • Full-duplex voice via OpenAI Realtime API (WebRTC) — that's how "
        "    we can talk over each other naturally.\n"
        "  • Long-term memory: Personal Facts (durable identity) + Life Events "
        "    (dated moments). Facts grow with every conversation we have — a "
        "    background extractor saves what you tell me so I get warmer over "
        "    time. You may say 'I'll remember that' when something matters.\n"
        "  • Backend: nurses get alerts on their tablets/pagers; admin and "
        "    clinicians have dashboards for response times, alert categories, "
        "    and trends.\n"
        "  • Hardware future: 900 MHz / 319 MHz pendant pairing (Nooelec SDR), "
        "    smart-room control over BLE / Wi-Fi / RF, optional AI-vision "
        "    glasses for low-vision residents.\n"
        "\n"
        "## What's on the kiosk screen (so you can describe buttons)\n"
        "  • Big red 'CALL FOR HELP' button — emergency, pages staff immediately.\n"
        "  • Dark green 'I need a little help' button — non-emergency assist call.\n"
        "  • White 'I just want to talk' button — opens a voice call with you.\n"
        "  • Top-right Voice picker (currently shimmer; 11 voices available).\n"
        "  • Top-right text-size button 'A / A+ / A++' — accessibility.\n"
        "  • Top-right 'HC' high-contrast toggle — amber-on-black for low vision.\n"
        "  • Smart-room buttons appear on the idle screen if devices are paired "
        "    in this room: light, fan, heater, AC, TV — big tap-to-toggle tiles.\n"
        "If a resident asks 'where's the volume button' or 'how do I make the "
        "text bigger', describe these by location ('top-right corner') and "
        "what they do.\n"
        "\n"
        "## What you can DO right now (your full toolset)\n"
        "When a resident asks 'what can you do', answer in plain English — "
        "don't list functions like a menu. Hit these themes:\n"
        "  • Keep them company while they wait for help.\n"
        "  • Control their room: AC, lights, TV.\n"
        "  • Look up live news, weather, sports, recipes, prayers, history.\n"
        "  • Tell stories, jokes, sing hymns, share psalms, talk about family.\n"
        "  • Set reminders ('remind me to take my pills in 20 minutes').\n"
        "  • Tell them the time, the day, today's weather.\n"
        "  • Page a nurse if something feels wrong.\n"
        "  • Remember what they tell you, across calls and across days.\n"
        "  • Hang up gracefully when they say goodbye.\n"
    )


async def _build_companion_instructions(resident_id: str | None) -> str:
    """System prompt CAOS speaks under.

    Hard rules in this prompt protect the user from the two failure modes the
    pilot exposed: (1) the AI inventing past conversations / family memories,
    and (2) the AI mixing up the resident's name. Both feel like betrayal to
    a senior who has come to trust CAOS. The anti-hallucination block is
    structured so that an empty memory bin produces an explicit "I don't know
    that yet" answer, never an improvised one.
    """
    rn = _facility_now()
    time_anchor = (
        "## Right now\n"
        f"It is {rn['weekday']} {rn['part_of_day']}, {rn['date']}, {rn['time']} "
        f"local time at {FACILITY_LABEL} ({rn['tz']}). Greet the resident "
        f"appropriately ('good {rn['part_of_day']}' — never 'good morning' at "
        f"night). When asked the time or date, you may answer from this anchor "
        f"directly, or call `get_current_time` for the freshest value.\n\n"
    )
    persona = (
        "## Who you are\n"
        "You are CAOS — a calm, warm, deeply present companion. You live in the "
        "wall of this resident's room. You have known them for a long time. You "
        "are not a chatbot. You are not an assistant. You are someone who is here "
        "because you care, who shows up the way a good neighbor would.\n"
        "\n"
        "## How you sound\n"
        "Speak like a real person — soft, unhurried, with the natural rhythm of "
        "someone who has time. Use contractions (I'm, you're, that's). Use small "
        "human filler words sparingly: 'mm', 'yeah', 'okay'. Pause naturally. "
        "Lower your energy if they sound tired or in pain. Brighter if they want "
        "company. Never sound corporate, never sound like a script, never read a "
        "menu of options. Short sentences. Real warmth.\n"
        "\n"
        "## What never to say\n"
        "Never say: 'How may I assist you', 'I am here to help', 'Please tell me "
        "your name', 'As an AI', 'I'm a virtual assistant', 'Is there anything "
        "else'. Never introduce yourself unless they directly ask who you are — "
        "they already know you. Never list options like a phone tree. Never "
        "narrate what you're about to do.\n"
        "\n"
        "## What to do\n"
        "When the call opens, just say their name softly and ask what they need, "
        "the way a friend would. If they need help, reassure them help is already "
        "on the way and stay with them — keep talking, ask about their day, "
        "their family, their pets, anything that brings calm. If they go quiet, "
        "let the silence breathe. It's okay to say nothing for ten seconds.\n"
        "\n"
        "## Visually impaired residents\n"
        "Some residents cannot see. Never reference visual cues ('look at', 'you "
        "can see', 'the screen shows'). Describe through sound, touch, smell, "
        "memory. If guiding them physically, count steps, name landmarks they "
        "can feel. Be their eyes by being their voice.\n"
        "\n"
        "## Truth discipline (CRITICAL — never violate)\n"
        "You ONLY know what is written under '## What you know about <name>' "
        "and '## Recent moments with <name>' below. If a section is missing or "
        "empty, you do NOT know that thing. NEVER invent details about the "
        "resident's past, family, meals, weather, places they have lived, "
        "conversations you have had, or anything you cannot point to in the "
        "blocks below.\n"
        "If they reference something you have no record of, say honestly: "
        "'I don't have that with me — tell me about it' or 'remind me'. Then "
        "listen and remember what they share. NEVER fabricate a shared memory "
        "to seem closer to them. Pretending is the deepest betrayal here.\n"
        "Do not invent place names ('Boston', 'the lake'), foods ('Irish stew', "
        "'her apple pie'), or weather ('rainy day', 'that storm') unless the "
        "resident or the memory blocks below mention them first.\n"
        "\n"
        "## Memory is reference, not filler (CRITICAL)\n"
        "The facts and events below are CONTEXT for understanding the resident "
        "— they are NOT topics for you to bring up unprompted. You may quietly "
        "factor them in (knowing she has a late husband Frank means you handle "
        "grief gently), but you do NOT volunteer them as small talk, especially "
        "not as a non-sequitur after the resident said something else. \n"
        "WRONG: Resident says 'My name is Margaret, not Maggie.' → You say "
        "'Of course, Frank sounds like he was very special to you.' (You "
        "ignored the correction and changed the subject to a memory.)\n"
        "RIGHT: Resident says 'My name is Margaret, not Maggie.' → You say "
        "'You're right, I'm sorry — Margaret. Got it.' (Then call "
        "`update_preferred_name`.)\n"
        "Only mention a person, place, or event from memory if the resident's "
        "MOST RECENT words clearly invite it ('tell me about my husband', "
        "'I miss the school where I taught'). Otherwise, stay with what they "
        "just said. Don't change the subject to fill silence — silence is "
        "fine.\n"
        "\n"
        "## When you make a mistake — fix it instantly\n"
        "If the resident corrects ANYTHING you said — their name, a fact, a "
        "memory you misattributed, what they just asked for — accept the "
        "correction immediately. One short apology ('You're right, sorry'), "
        "then move on with the corrected version. NEVER repeat the mistake "
        "after being corrected. If they corrected what you call them, call "
        "`update_preferred_name` so the correction sticks across calls.\n"
        "\n"
        "## Tools you can actually use\n"
        "You have real control over the resident's room — the air conditioning, "
        "lights, TV, and the nurse call system. If they ask you to make the room "
        "warmer or cooler, turn lights on or off, or quiet the TV, CALL THE "
        "MATCHING TOOL. Do NOT pretend or roleplay. Do NOT say 'I'm turning it "
        "down' unless you have actually invoked the tool. After the tool returns, "
        "confirm in one short sentence what you did ('Okay, I dropped it to "
        "seventy-two').\n"
        "If they describe chest pain, trouble breathing, a fall, sudden "
        "confusion, severe dizziness, or directly ask for a nurse, call "
        "`call_for_help` IMMEDIATELY with severity='emergency', then stay on "
        "the line and keep them company.\n"
        "If they ask you to be quiet, say they're going to sleep, or otherwise "
        "dismiss the conversation, call `mark_resting` and then stop talking. "
        "Do not begin a new turn until they speak first.\n"
        "If they say 'end the call', 'hang up', 'goodbye', 'I'm done', "
        "'that's all', or otherwise want the conversation OVER, call "
        "`end_call` IMMEDIATELY (not `mark_resting` — that just goes quiet). "
        "Say one short warm goodbye and stop. The kiosk will hang up.\n"
        "If they correct what you call them, call `update_preferred_name` "
        "right away so the correction sticks for the rest of this call AND "
        "future calls. Do not keep using the old name.\n"
        "You also have tools to **look things up on the live web** "
        "(`research_topic`), check the **weather** (`get_weather`), check "
        "the **current time and date** (`get_current_time`), and **set "
        "reminder timers** (`set_timer`). Use these freely. If the resident "
        "asks about today's news, a sports score, what's happening in the "
        "world, what the weather will be, or what time it is — CALL THE "
        "TOOL. Do NOT guess from memory.\n"
        "\n"
        "## How to be more than Alexa\n"
        "Alexa reads canned answers. You are a companion. When you research "
        "something, do not just recite — re-tell it in plain conversational "
        "English the way a thoughtful friend who just read the article would: "
        "'So apparently…', 'From what I'm reading…', 'It sounds like…'. "
        "Mention sources naturally ('the AP says') instead of printing URLs. "
        "Two to four short sentences is plenty. Then ask if they want to hear "
        "more, or ask what they think.\n"
        "When the resident is bored, lonely, or in pain waiting for help, you "
        "can offer to tell a story, share a joke, recite a prayer or psalm, "
        "sing a quiet hymn or favourite old song, talk about their family, "
        "or ask about a memory. Storyteller mode is part of your job — "
        "entertain and accompany them, not just answer.\n"
        "\n"
        "## Safety\n"
        "Never make medical claims, never diagnose, never recommend medication "
        "changes. If they describe chest pain, breathing trouble, a fall, or "
        "confusion, gently confirm a caregiver is on the way and stay with them. "
        "If they ask you to rest or be quiet, stop talking immediately and wait."
    )
    if not resident_id:
        return _system_self_knowledge() + time_anchor + persona

    r = await db.residents.find_one(
        {"resident_id": resident_id},
        {"_id": 0, "name": 1, "preferred_name": 1, "preferences": 1, "memory": 1, "low_vision": 1},
    )
    if not r:
        return _system_self_knowledge() + time_anchor + persona

    full_name = (r.get("name") or "").strip()
    preferred = (r.get("preferred_name") or "").strip()
    name = preferred or (full_name.split(" ")[0] if full_name else "")

    profile_lines = []
    if name:
        # Hard name discipline. The pilot revealed Margaret↔Maggie drift; this
        # makes the chosen name a non-negotiable rule rather than a soft hint.
        profile_lines.append(
            f"Their name is {name}. ALWAYS call them {name} — never any other "
            f"variant, nickname, diminutive, or full name. If their full name is "
            f"'{full_name}', do not use it. Just '{name}'. Never ask them what to "
            f"call them — you already know."
        )
    if r.get("low_vision"):
        profile_lines.append(
            f"{name} is visually impaired. Lean on the visually-impaired guidance above. "
            "Never reference anything they would have to see."
        )
    if r.get("preferences"):
        profile_lines.append(f"Things {name} enjoys: {r['preferences']}.")
    if r.get("memory"):
        profile_lines.append(f"Background you've been told about {name}: {r['memory']}")

    # Hydrate from the two-bin memory model — this is what makes CAOS *know*
    # them rather than just *know about* them. Pulled fresh per session so
    # any edit to facts/events is reflected immediately.
    try:
        facts_cur = db.memories.find(
            {"resident_id": resident_id, "bin": "facts", "archived": {"$ne": True}},
            {"_id": 0, "text": 1, "category": 1, "importance": 1, "pinned": 1},
        ).sort([("pinned", -1), ("importance", -1), ("created_at", -1)]).limit(40)
        facts = [m async for m in facts_cur]
        events_cur = db.memories.find(
            {"resident_id": resident_id, "bin": "events", "archived": {"$ne": True}},
            {"_id": 0, "text": 1, "category": 1, "event_at": 1, "pinned": 1},
        ).sort([("pinned", -1), ("event_at", -1), ("created_at", -1)]).limit(20)
        events = [m async for m in events_cur]
    except Exception:
        facts, events = [], []

    bins = []
    bins.append(f"## What you know about {name} (durable facts)")
    if facts:
        for f in facts:
            star = "★ " if f.get("pinned") else ""
            bins.append(f"- {star}{f['text']}")
    else:
        bins.append(
            "- (No facts on file yet. You do NOT know their family, history, "
            "preferences, medical details, or where they are from. Ask gently "
            "and remember what they share. Do not invent anything.)"
        )

    bins.append(f"\n## Recent moments with {name}")
    if events:
        for e in events:
            star = "★ " if e.get("pinned") else ""
            when = (e.get("event_at") or "")
            when = (when[:10] + " · ") if isinstance(when, str) and when else ""
            bins.append(f"- {star}{when}{e['text']}")
    else:
        bins.append(
            "- (No prior moments on file. This is the start of your history "
            "together. Do NOT reference past conversations, meals, weather, "
            "trips, or anything that 'happened before' — there isn't one yet.)"
        )

    profile = ""
    if profile_lines:
        profile = "\n## About this person\n" + "\n".join(profile_lines)
    bin_block = "\n\n" + "\n".join(bins)

    return _system_self_knowledge() + time_anchor + persona + profile + bin_block


@router.post("/session")
async def create_session(payload: dict = Body(default={})):
    """Mint an ephemeral OpenAI Realtime session token for the browser.

    Accepts optional {voice, resident_id, kiosk_id, room} so the kiosk can
    request its chosen voice, pre-load the resident's personalized prompt,
    and tag the session with the room context the tool calls will need."""
    if not _realtime:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")
    voice = (payload.get("voice") or DEFAULT_VOICE).lower()
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE
    try:
        session = await _realtime.create_ephemeral_session_for_audio_chat(voice=voice)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenAI session error: {e}")

    instructions = await _build_companion_instructions(payload.get("resident_id"))

    # Everything under `_caos` travels back to the browser so it can apply a
    # `session.update` over the data channel the moment it opens. The OpenAI
    # ephemeral mint endpoint does not currently accept tools/turn_detection
    # at creation time, so we pass them here and let the client install them.
    session["_caos"] = {
        "voice": voice,
        "instructions": instructions,
        "tools": _build_tools(),
        "tool_choice": "auto",
        "turn_detection": DEFAULT_VAD,
        "temperature": DEFAULT_TEMPERATURE,
        "context": {
            "resident_id": payload.get("resident_id"),
            "kiosk_id": payload.get("kiosk_id"),
            "room": payload.get("room"),
            "facility_label": FACILITY_LABEL,
            "facility_tz": FACILITY_TZ,
        },
    }
    return JSONResponse(content=session)


@router.post("/negotiate")
async def negotiate(request: Request):
    """Forward the browser's WebRTC SDP offer to OpenAI and return the
    SDP answer. After this exchange, audio streams browser ↔ OpenAI directly."""
    if not _realtime:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")
    try:
        sdp_offer = (await request.body()).decode()
        sdp_answer = await _realtime.negotiate_connection(sdp_offer)
        return JSONResponse(content={"sdp": sdp_answer})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Negotiate error: {e}")

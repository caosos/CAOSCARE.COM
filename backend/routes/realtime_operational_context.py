"""Render the Layer-E operational snapshot into a prompt block for Aria.

Kept out of realtime_companion_prompt.py so that file stays small and the
"assemble context, hand it to the model" boundary is explicit: this turns
the structured snapshot from routes/aria_operational_state.py into the few
sentences Aria reasons from. It is deliberately terse - a state view, not
a transcript.
"""
from typing import Optional


def _line(item: dict) -> str:
    who = f", {item['handled_by']}" if item.get("handled_by") else ""
    sched = ""
    if item.get("scheduled_time_label") or item.get("scheduled_date"):
        sched = f", planned for {item.get('scheduled_date') or ''} {item.get('scheduled_time_label') or ''}".rstrip()
    upd = f" Latest staff note: {item['latest_update']}." if item.get("latest_update") else ""
    reasks = ""
    if item.get("re_request_count"):
        reasks = f" Asked again {item['re_request_count']}x."
    return (f"- {item['about']} — opened {item['opened_age']}, "
            f"currently **{item['lifecycle']}**{who}{sched}.{reasks}{upd}")


def render_operational_block(state: Optional[dict]) -> str:
    """Empty string when there is nothing open and nothing recently handled -
    a fresh session should NOT begin inside a workflow."""
    if not state:
        return ""
    current = state.get("current") or []
    background = state.get("background") or []
    resolved = state.get("recently_resolved") or []
    if not current and not background and not resolved:
        return ""

    out = ["\n\n## What's actually happening right now\n",
           state.get("speak_guidance", ""), "\n"]
    if current:
        out.append("\nThe reason you're likely here / what's live for them now:\n")
        out += [_line(i) + "\n" for i in current]
    if background:
        out.append("\nAlso open, but not necessarily why you're here "
                   "(mention only if the conversation goes there):\n")
        out += [_line(i) + "\n" for i in background]
    if resolved:
        out.append("\nHandled in the last few hours (history, not waiting - "
                   "do not chase these):\n")
        out += [_line(i) + "\n" for i in resolved]
    return "".join(out)

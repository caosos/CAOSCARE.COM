"""HTTP call to CAOSCare's voice bridge. No Home Assistant imports, so it can
be tested without HA. Any failure (timeout, network, non-200, bad JSON)
becomes a spoken fallback and ends the voice session - the agent never
invents an answer."""
import asyncio

FALLBACK = ("I'm sorry, I can't reach CAOSCare right now. "
            "If you need help, please use your call button.")
UNKNOWN_DEVICE = ("This speaker isn't set up with CAOSCare yet. "
                  "Please let the staff know.")
DEFAULT_TIMEOUT = 25.0  # seconds; CAOSCare's own turn budget is shorter (18 s)


def build_payload(text, conversation_id, language, device_id=None, satellite_id=None):
    return {"text": text, "conversation_id": conversation_id, "language": language,
            "device_id": device_id, "satellite_id": satellite_id}


async def call_bridge(session, url, token, payload, timeout=DEFAULT_TIMEOUT):
    """session: an aiohttp-style client session (has .post returning an async
    context manager). Returns dict: speech, conversation_id,
    continue_conversation, ok, error."""
    result = {"speech": FALLBACK, "conversation_id": payload.get("conversation_id"),
              "continue_conversation": False, "ok": False, "error": None}

    async def _do():
        async with session.post(url, json=payload,
                                headers={"Authorization": f"Bearer {token}"}) as resp:
            if resp.status == 404:
                result.update(speech=UNKNOWN_DEVICE, error="unknown device (404)")
                return
            if resp.status != 200:
                result["error"] = f"bridge HTTP {resp.status}"
                return
            data = await resp.json()
            speech = (data.get("response_text") or "").strip()
            if not speech:
                result["error"] = "empty response_text"
                return
            result.update(speech=speech, ok=True,
                          conversation_id=data.get("conversation_id") or result["conversation_id"],
                          continue_conversation=bool(data.get("continue_conversation")))

    try:
        await asyncio.wait_for(_do(), timeout)
    except asyncio.TimeoutError:
        result["error"] = f"bridge timeout after {timeout}s"
    except Exception as e:  # network error, bad JSON
        result["error"] = f"{type(e).__name__}: {e}"
    return result

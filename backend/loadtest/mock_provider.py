"""Simulated language-model provider for voice-bridge load tests.

Replaces routes.voice_bridge._post_openai inside the test server only. It
never touches the network. Behaviour (all from the environment, plus a
control file the harness rewrites during a run for outage windows):

    LOAD_LLM_LATENCY_MS   mean per-call latency           (default 1200)
    LOAD_LLM_JITTER_MS    +/- uniform jitter               (default 400)
    LOAD_LLM_MAX_CONC     provider concurrency per process; beyond it the
                          call fails like an HTTP 429      (default 0 = off)
    LOAD_LLM_RPM          requests/minute per process; beyond it -> 429 (0 = off)
    LOAD_CONTROL_FILE     JSON {"mode": "ok"|"down"|"slow"}
    LOAD_STATS_DIR        per-process counters are written here

Scripted answers follow the resident's last words, call the bridge's real
tools, and echo the resident's test token (LTnnnXX) found in the context it
was given. A context holding more than one resident token is counted as
cross-resident leakage.
"""
import json
import os
import random
import re
import threading
import time
from datetime import date, timedelta

TOKEN = re.compile(r"LT\d{3}[A-Z]{2}")
_lock = threading.Lock()
_inflight = 0
_window = []  # call timestamps, last 60 s
STATS = {"calls": 0, "rate_limited": 0, "failed": 0, "timeouts": 0, "leak_contexts": 0,
         "leak_examples": [], "latency_ms_total": 0.0, "prompt_chars_total": 0, "prompt_chars_max": 0}
_control = {"mode": "ok", "read_at": 0.0}


class ProviderError(RuntimeError):
    pass


def _env(name, default):
    return float(os.environ.get(name) or default)


def _mode() -> str:
    path = os.environ.get("LOAD_CONTROL_FILE")
    now = time.monotonic()
    if path and now - _control["read_at"] > 0.25:
        _control["read_at"] = now
        try:
            with open(path) as f:
                _control["mode"] = json.load(f).get("mode", "ok")
        except (OSError, ValueError):
            _control["mode"] = "ok"
    return _control["mode"]


def dump_stats(extra: dict):
    d = os.environ.get("LOAD_STATS_DIR")
    if not d:
        return
    with _lock:
        data = {**STATS, "leak_examples": STATS["leak_examples"][:5], **extra}
    tmp = os.path.join(d, f".{os.getpid()}.json")
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, os.path.join(d, f"{os.getpid()}.json"))


def _call(name, args, n):
    return {"choices": [{"message": {"content": None, "tool_calls": [
        {"id": f"c{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]}


def _say(text):
    return {"choices": [{"message": {"content": text}}]}


def _script(user: str, n: int):
    u = user.lower()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    if "status" in u or "anyone coming" in u:
        return _call("check_request_status", {}, n)
    if "nurse" in u or "bathroom" in u or "help getting" in u:
        return _call("request_staff_help", {"category": "nursing", "summary": "needs help getting up",
                                            "priority": "high"}, n)
    if "towel" in u or "front desk" in u:
        return _call("request_staff_help", {"category": "housekeeping", "summary": "fresh towels"}, n)
    if "sink" in u or "leak" in u or "broken" in u:
        return _call("request_staff_help", {"category": "maintenance", "summary": "sink leaking"}, n)
    if "ride" in u or "doctor" in u:
        return _call("request_transportation", {"purpose": "doctor appointment",
                                                "requested_for_date": tomorrow}, n)
    if "light" in u or "lamp" in u:
        return _call("toggle_light", {"state": "off" if " off" in u else "on"}, n)
    if "temperature" in u or "thermostat" in u or "degrees" in u:
        return _call("adjust_room_temperature", {"target_f": 72}, n)
    if "dinner" in u or "menu" in u or "lunch" in u:
        return _call("get_menu", {"meal_period": "dinner"}, n)
    if "activit" in u or "schedule" in u:
        return _call("get_todays_schedule", {}, n)
    return None


def simulated_post(path, payload, timeout=60):
    global _inflight
    mode = _mode()
    max_conc, rpm = int(_env("LOAD_LLM_MAX_CONC", 0)), int(_env("LOAD_LLM_RPM", 0))
    with _lock:
        STATS["calls"] += 1
        n = STATS["calls"]
        now = time.monotonic()
        _window[:] = [t for t in _window if now - t < 60]
        limited = (max_conc and _inflight >= max_conc) or (rpm and len(_window) >= rpm)
        if limited:
            STATS["rate_limited"] += 1
        else:
            _inflight += 1
            _window.append(now)
    if limited:
        raise ProviderError("HTTP 429: rate limited (simulated)")
    try:
        if mode == "down":
            with _lock:
                STATS["failed"] += 1
            raise ProviderError("HTTP 503: provider unavailable (simulated)")
        if mode == "slow":
            time.sleep(timeout + 0.2)
            with _lock:
                STATS["timeouts"] += 1
            raise TimeoutError("read timed out (simulated)")
        latency = max(0.05, (_env("LOAD_LLM_LATENCY_MS", 1200) + random.uniform(
            -1, 1) * _env("LOAD_LLM_JITTER_MS", 400)) / 1000)
        time.sleep(latency)
        msgs = payload["messages"]
        tokens = set()
        for m in msgs:
            tokens.update(TOKEN.findall(m.get("content") or ""))
        chars = sum(len(m.get("content") or "") for m in msgs) + len(json.dumps(payload.get("tools") or []))
        with _lock:
            STATS["prompt_chars_total"] += chars
            STATS["prompt_chars_max"] = max(STATS["prompt_chars_max"], chars)
            STATS["latency_ms_total"] += latency * 1000
            if len(tokens) > 1:
                STATS["leak_contexts"] += 1
                STATS["leak_examples"].append(sorted(tokens))
        own = next(iter(tokens), "")
        last = msgs[-1]
        if last["role"] == "tool":
            ok = '"ok": true' in last["content"]
            return _say(f"{'Done' if ok else 'That did not go through'}, {own}.")
        user = next(m["content"] for m in reversed(msgs) if m["role"] == "user")
        return _script(user, n) or _say(f"I'm here with you, {own}.")
    finally:
        with _lock:
            _inflight -= 1

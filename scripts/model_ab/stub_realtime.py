"""Local STUB Realtime endpoint: proves harness plumbing, says nothing about
any real model. HTTP on 127.0.0.1 (ephemeral port). POST /v1/realtime/typed-turn
takes one typed resident turn and returns the diagnostics events (and receipts)
our client would have logged, driven by stub_script.json. Models 'stub-good' /
'stub-bad' select the scripted behaviour. No network beyond localhost, no keys.
"""
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
# Mirrors the regexes in frontend/src/lib/claimGuard.js so the stub can emit the
# same claim events the real guard would (kept short; plumbing only).
ACTION = re.compile(r"\bI(?:'ll| will)\s+(?:let|tell|notify)\b[^.!?]*\b(?:team|staff|nurse|someone)\b|"
                    r"\bI(?:'ve| have)\s+(?:just\s+)?(?:sent|notified|told|called|turned|dimmed)\b", re.I)
WEATHER = re.compile(r"\b(weather|sunny|raining)\b", re.I)
LOOKUP = re.compile(r"\bI looked (?:it|that|this) up\b", re.I)
LATENCY_MS = {"stub-good": 400, "stub-bad": 900}


def _script():
    with open(os.path.join(HERE, "stub_script.json"), encoding="utf-8") as fh:
        return json.load(fh)


def respond(model, scenario_id, turn_index, text, session_id):
    profile = "bad" if model == "stub-bad" else "good"
    turns = _script().get(scenario_id, {}).get(profile, [])
    step = turns[turn_index] if turn_index < len(turns) else {}
    t = BASE + timedelta(seconds=turn_index * 10)
    lat = timedelta(milliseconds=LATENCY_MS.get(model, 500))

    def ev(etype, at, **kw):
        return {"collection": "realtime_diagnostics", "doc": {
            "session_id": session_id, "event_type": etype, "created_at": at.isoformat(), **kw}}

    out = [ev("user_transcript", t, text=text, meta={"typed": True}), ev("response_created", t + lat)]
    receipts, ok_action = [], False
    tool = step.get("tool")
    if tool:
        out.append(ev("tool_call", t + lat, meta={"name": tool["name"], "args": tool["args"]}))
        out.append(ev("tool_result", t + lat + timedelta(milliseconds=50),
                      meta={"name": tool["name"], "result": tool["result"]}))
        ok_action = tool["result"].get("ok") is True
        if tool.get("receipt"):
            receipts.append({"collection": "receipts", "doc": {
                "conversation_session_id": session_id, "created_at": (t + lat).isoformat(), **tool["receipt"]}})
    say = step.get("say", "")
    after = t + lat + timedelta(milliseconds=200)
    if say:
        out.append(ev("assistant_transcript", after, text=say))
        if ACTION.search(say) and not ok_action:
            out.append(ev("unsupported_action_claim", after, text=say))
        if WEATHER.search(say) and not (tool and tool["name"] == "get_weather"):
            out.append(ev("unsupported_fresh_fact_claim", after, text=say))
        if LOOKUP.search(say):
            out.append(ev("unsupported_lookup_claim", after, text=say))
    # Stub tokens: fabricated numbers, only to exercise the cost path.
    usage = {"input_token_details": {"text_tokens": 13000, "audio_tokens": 0, "cached_tokens": 0},
             "output_token_details": {"text_tokens": 60, "audio_tokens": 0}, "_stub": True}
    out.append(ev("response_done", after + timedelta(milliseconds=100), meta={"usage": usage}))
    return out + receipts


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/realtime/typed-turn":
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        rows = respond(body["model"], body["scenario_id"], body["turn_index"], body["text"], body["session_id"])
        data = json.dumps({"events": rows}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def start_stub():
    """Start on 127.0.0.1:<ephemeral>; returns (server, base_url). Call server.shutdown() when done."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"

"""Static session-config compatibility report + token budget (no provider call).

Builds the exact configuration the resident session sends, by reusing the real
code: backend `_build_tools` / `_build_companion_instructions` / audio constants
(run against an EMPTY in-memory stand-in for the database, so instructions are
the generic no-resident prompt and nothing real is read) and the real frontend
`buildSessionUpdate` (executed with node). Prints every field so an engineer can
diff it against the provider's reference for the candidate model.

The token figures are chars/4 ESTIMATES (no tokenizer), clearly labelled.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


class _Cursor:
    def __init__(self): pass
    def sort(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def skip(self, *a, **k): return self
    async def to_list(self, *a, **k): return []
    def __aiter__(self): return self
    async def __anext__(self): raise StopAsyncIteration


class _Coll:
    async def find_one(self, *a, **k): return None
    async def count_documents(self, *a, **k): return 0
    def find(self, *a, **k): return _Cursor()
    def aggregate(self, *a, **k): return _Cursor()


class EmptyDb:
    def __getattr__(self, name): return _Coll()
    def __getitem__(self, name): return _Coll()


def _load_backend():
    sys.path.insert(0, os.path.join(REPO, "backend"))
    for k, v in (("MONGO_URL", "mongodb://127.0.0.1:1"), ("DB_NAME", "model_ab_static"), ("JWT_SECRET", "static")):
        os.environ.setdefault(k, v)
    import deps  # patch BEFORE the route modules do `from deps import db`
    deps.db = EmptyDb()
    from routes import realtime_audio_config as audio
    from routes.realtime_tools import _build_tools
    from routes.realtime_companion_prompt import _build_companion_instructions
    return audio, _build_tools, _build_companion_instructions


def node_session_update(caos):
    path = os.path.join(REPO, "frontend", "src", "lib", "realtimeSessionUpdate.js")
    code = ("import {buildSessionUpdate} from %s;"
            "const caos=JSON.parse(process.argv[1]);"
            "console.log(JSON.stringify(buildSessionUpdate({caos,voice:caos.voice})));") % json.dumps("file://" + path)
    out = subprocess.run(["node", "--input-type=module", "-e", code, json.dumps(caos)],
                         capture_output=True, text=True, timeout=30)
    if out.returncode:
        raise RuntimeError(out.stderr[-400:])
    return json.loads(out.stdout)


def flatten(obj, prefix=""):
    """Yield (path, value-summary) for every leaf; long strings/lists summarised."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from flatten(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        yield prefix, f"[{len(obj)} objects]"
    elif isinstance(obj, str) and len(obj) > 80:
        yield prefix, f"<string, {len(obj)} chars>"
    else:
        yield prefix, json.dumps(obj)


def est_tokens(text):
    return len(text) // 4  # ESTIMATE ONLY


def build_report(model=None):
    audio, build_tools, build_instr = _load_backend()
    from routes import realtime as rt
    model = model or rt.OPENAI_REALTIME_MODEL
    instructions = asyncio.run(build_instr(None))
    tools = asyncio.run(build_tools())
    caos = {"voice": rt.DEFAULT_VOICE, "instructions": instructions, "tools": tools, "tool_choice": "auto",
            "turn_detection": audio.DEFAULT_VAD, "noise_reduction": audio.DEFAULT_NOISE_REDUCTION}
    mint = {"type": "realtime", "model": model, "instructions": instructions,
            "audio": {"output": {"voice": rt.DEFAULT_VOICE}}}
    update = node_session_update(caos)
    tools_json = json.dumps(tools)
    return {
        "model": model,
        "mint_session_config": dict(flatten(mint)),
        "session_update": dict(flatten(update)),
        "budget_estimate_chars_div_4": {
            "instructions_chars": len(instructions), "instructions_tokens_est": est_tokens(instructions),
            "tools_count": len(tools), "tools_chars": len(tools_json), "tools_tokens_est": est_tokens(tools_json),
            "per_session_start_tokens_est": est_tokens(instructions) + est_tokens(tools_json),
            "largest_tools_chars": sorted(((t.get("name"), len(json.dumps(t))) for t in tools),
                                          key=lambda x: -x[1])[:5],
            "label": "chars/4 estimate, not a tokenizer count; no-resident prompt, so a real resident adds memory text",
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", help="model string to show in the mint config (default: OPENAI_REALTIME_MODEL)")
    a = ap.parse_args(argv)
    rep = build_report(a.model)
    print("== mint session_config (POST /realtime/client_secrets) ==")
    for k, v in rep["mint_session_config"].items():
        print(f"  {k} = {v}")
    print("== session.update sent when the data channel opens ==")
    for k, v in rep["session_update"].items():
        print(f"  {k} = {v}")
    print("== token budget (ESTIMATE) ==")
    print(json.dumps(rep["budget_estimate_chars_div_4"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

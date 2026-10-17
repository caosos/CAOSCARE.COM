"""Provider prices and cost estimation for the paid API ledger (paid_api_ledger.py) - the one price table.

USD as published at developers.openai.com/api/docs/pricing, read 2026-10-17. A new or changed price is a new
PRICING_VERSION; every estimate carries the version it used. An estimate is never a provider-billed amount.
Where the page lists one price for a category, that one price is used (e.g. a single "input" price for the
gpt-4o transcribe models - no separate audio rate is invented here).
"""

PRICING_VERSION = "openai-public-2026-10-17.2"

# Realtime, per 1M tokens.
_MINI = dict(text_in=0.60, text_cached=0.06, text_out=2.40, audio_in=10.00, audio_cached=0.30, audio_out=20.00)
_GA = dict(text_in=4.00, text_cached=0.40, text_out=16.00, audio_in=32.00, audio_cached=0.40, audio_out=64.00)
REALTIME = {
    "gpt-realtime-2.1-mini": _MINI, "gpt-realtime-mini": _MINI,
    "gpt-realtime-2.1": dict(_GA, text_out=24.00),
    "gpt-realtime": _GA, "gpt-realtime-2025-08-28": _GA,
}
# Text (chat completions / Responses), per 1M tokens.
TEXT = {
    "gpt-4o-mini": dict(input=0.15, cached=0.075, output=0.60),
    "gpt-4.1-mini": dict(input=0.40, cached=0.10, output=1.60),
}
# Token-billed transcription, per 1M tokens (one listed input price).
TRANSCRIBE = {"gpt-4o-transcribe": dict(input=2.50, output=10.00),
              "gpt-4o-mini-transcribe": dict(input=1.25, output=5.00)}
PER_MINUTE = {"whisper-1": 0.006}              # listed as "Whisper"
PER_MILLION_CHARS = {"tts-1": 15.00}
WEB_SEARCH_PER_CALL = 10.00 / 1000             # web search tool, non-preview; search-content tokens billed in usage


def _model_key(model, table):
    """Provider-confirmed names carry a date suffix (gpt-4.1-mini-2025-04-14): match the listed base name."""
    m = (model or "").strip()
    if m in table:
        return m
    return next((k for k in sorted(table, key=len, reverse=True) if m.startswith(k + "-")), None)


def _ints(*vals):
    return all(isinstance(v, int) and v >= 0 for v in vals)


def realtime_parts(usage):
    """Realtime usage -> billable parts; None when missing or any counter is unknown (never 0)."""
    if not isinstance(usage, dict):
        return None
    i = usage.get("input_token_details") or {}
    c = i.get("cached_tokens_details") or {}
    o = usage.get("output_token_details") or {}
    v = [i.get("text_tokens"), c.get("text_tokens"), i.get("audio_tokens"), c.get("audio_tokens"),
         o.get("text_tokens"), o.get("audio_tokens")]
    if not _ints(*v):
        return None
    return dict(text_in=v[0] - v[1], text_cached=v[1], audio_in=v[2] - v[3], audio_cached=v[3], text_out=v[4], audio_out=v[5])


def _text_tokens(usage):
    """(uncached input, cached input, output) from chat-completions or Responses usage; None if incomplete."""
    if not isinstance(usage, dict):
        return None
    if "prompt_tokens" in usage:
        i, o = usage.get("prompt_tokens"), usage.get("completion_tokens")
        c = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    else:
        i, o = usage.get("input_tokens"), usage.get("output_tokens")
        c = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
    return (i - c, c, o) if _ints(i, o, c) and c <= i else None


def estimate_usd(model, usage, *, chars=None, search_calls=0):
    """Calculated cost at PRICING_VERSION, or None when the usage or the model's price is unknown."""
    k = _model_key(model, REALTIME)
    if k:
        p, parts = REALTIME[k], realtime_parts(usage)
        return None if parts is None else round(sum(parts[n] * p[n] for n in parts) / 1e6, 8)
    k = _model_key(model, TEXT)
    if k:
        t, p = _text_tokens(usage), TEXT[k]
        if t is None:
            return None
        calls = search_calls if isinstance(search_calls, int) and search_calls > 0 else 0
        return round((t[0] * p["input"] + t[1] * p["cached"] + t[2] * p["output"]) / 1e6 + calls * WEB_SEARCH_PER_CALL, 8)
    k = _model_key(model, TRANSCRIBE)
    if k and isinstance(usage, dict) and _ints(usage.get("input_tokens"), usage.get("output_tokens")):
        p = TRANSCRIBE[k]
        return round((usage["input_tokens"] * p["input"] + usage["output_tokens"] * p["output"]) / 1e6, 8)
    k = _model_key(model, PER_MINUTE)
    if k and isinstance(usage, dict) and isinstance(usage.get("seconds"), (int, float)) and usage["seconds"] >= 0:
        return round(usage["seconds"] / 60 * PER_MINUTE[k], 8)
    k = _model_key(model, PER_MILLION_CHARS)
    if k and isinstance(chars, int) and chars >= 0:
        return round(chars * PER_MILLION_CHARS[k] / 1e6, 8)
    return None


def usage_complete(model, usage):
    """True when the provider's usage is present and complete enough to price."""
    if not isinstance(usage, dict):
        return False
    if _model_key(model, REALTIME) or not _model_key(model, TEXT) and not _model_key(model, TRANSCRIBE) \
            and not _model_key(model, PER_MINUTE):
        return realtime_parts(usage) is not None or _text_tokens(usage) is not None
    return estimate_usd(model, usage) is not None


def worst_case_usd(model, max_responses, max_text_input_tokens, max_audio_input_tokens, max_output_tokens):
    """Reservation for a bounded Realtime session: every response at its input bounds with nothing cached,
    every output token priced as audio. Not covered: a runner ignoring its bounds, provider behaviour beyond
    them, a price change."""
    k = _model_key(model, REALTIME)
    if k is None or not all(isinstance(v, int) and v > 0 for v in
                            (max_responses, max_text_input_tokens, max_audio_input_tokens, max_output_tokens)):
        return None
    p = REALTIME[k]
    per = (max_text_input_tokens * p["text_in"] + max_audio_input_tokens * p["audio_in"]
           + max_output_tokens * max(p["audio_out"], p["text_out"])) / 1e6
    return round(per * max_responses, 8)

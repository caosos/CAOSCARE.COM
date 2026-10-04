"""Voice bridge language-model selection.

    CAOSCARE_VOICE_BRIDGE_PROVIDER   default "openai" (the only provider wired)
    CAOSCARE_VOICE_BRIDGE_MODEL      default "gpt-4o-mini"

Only the values in SUPPORTED are accepted: chat-completions models with tool
calling that the bridge's request format works with. A value outside the list
does not fall back silently - the bridge refuses turns (503) and says why,
and the rest of CAOSCare keeps running. Speech (TTS) is not chosen here: the
bridge returns text and Home Assistant's pipeline speaks it.
"""
import logging
import os

SUPPORTED = {
    # live-tested on the bridge 2026-10-03: gpt-4o-mini, gpt-4.1
    "openai": ("gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4o"),
}
DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-4o-mini"


def resolve_model(env=None) -> dict:
    """{provider, model, ok, error}. Pure: reads only the given mapping."""
    env = os.environ if env is None else env
    provider = (env.get("CAOSCARE_VOICE_BRIDGE_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    model = (env.get("CAOSCARE_VOICE_BRIDGE_MODEL") or DEFAULT_MODEL).strip()
    if provider not in SUPPORTED:
        return {"provider": provider, "model": model, "ok": False,
                "error": f"unsupported voice bridge provider '{provider}' (supported: {', '.join(SUPPORTED)})"}
    if model not in SUPPORTED[provider]:
        return {"provider": provider, "model": model, "ok": False,
                "error": f"unsupported voice bridge model '{model}' for {provider} "
                         f"(supported: {', '.join(SUPPORTED[provider])})"}
    return {"provider": provider, "model": model, "ok": True, "error": None}


def log_selection(cfg: dict) -> None:
    if cfg["ok"]:
        logging.info("voice bridge model: %s/%s", cfg["provider"], cfg["model"])
    else:
        logging.error("voice bridge disabled: %s", cfg["error"])

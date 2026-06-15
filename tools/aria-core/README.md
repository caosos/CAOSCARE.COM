# ARIA Core

`tools/aria-core` is the first plug-and-play ARIA runtime scaffold. It is intentionally kept under `tools/` so reusable ARIA logic is preserved in GitHub and can later be wired into CAOSCare, a room node, a house node, or another runtime without starting over.

## Purpose

ARIA is the capability-aware intent layer. It should know what it can do, what it cannot do yet, and what setup information it needs next. It must not claim that it controlled a device, contacted a service, or completed an action unless that action actually happened.

This scaffold starts with conversation and capability truth only. Home Assistant is represented as planned but not configured. No controllable devices are assumed.

## What is included

- `src/generateResponse.js` — orchestration entry point.
- `src/inference/` — swappable inference-provider adapters.
- `src/capabilities/` — capability manifest loading and setup-state helpers.
- `src/memory/` — minimal runtime session memory.
- `src/authority/` — first-pass authority/permission decision hook.
- `src/receipts/` — local receipt writer for truthful audit output.
- `state/capabilities.example.json` — example capability truth.
- `identity/aria_identity.example.md` — example ARIA identity prompt.
- `cli/aria.js` — no-secrets command-line smoke-test entry point.

## Providers

The first pass supports:

- `mock` — deterministic, no API key required, used by default.
- `openai` — reads `OPENAI_API_KEY` and `OPENAI_MODEL` from the environment only.

Future providers should be added behind the same adapter boundary, such as local model servers, Ollama, LM Studio, Anthropic, or other inference engines. The ARIA core should not care which inference engine is used.

## Smoke test

From the repository root:

```bash
node tools/aria-core/cli/aria.js "Aria, cool the house down"
```

Expected meaning: ARIA should say Home Assistant is planned but not configured, no controllable A/C device is registered yet, and setup details are needed before control can happen.

## Security

Do not commit secrets here. No API keys, tokens, passwords, `.env` files, cookies, JWTs, private credentials, or raw personal data belong in this directory.

Runtime receipts and sessions are written under `tools/aria-core/runtime/`, which must stay git-ignored because user interaction content can be sensitive.

## Current status

This is a scaffold and source-of-truth starting point, not active CAOSCare runtime integration yet. The next safe step is to wire this core into a CAOSCare backend route or frontend chat shell after reviewing the adapter boundary.

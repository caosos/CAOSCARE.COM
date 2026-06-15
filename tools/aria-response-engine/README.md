# ARIA Response Engine (Legacy / Source Material)

`tools/aria-response-engine` preserves the **prior** ARIA response-engine source material so it is captured in GitHub and not lost. It is archival reference only — it is **not** wired into CAOSCare and is **not** the active runtime.

The maintained, plug-and-play implementation lives in [`tools/aria-core`](../aria-core/README.md). New work should happen there.

## What is here

- `legacy/response_engine.js` — the earlier standalone ARIA response engine (Node/CommonJS). It reads its OpenAI key from the environment (`process.env.OPENAI_API_KEY`) and references an earlier layout (`identity/`, `state/capabilities.json`, `memory/`, `authority/decision_layer`, `file-engine`). Those sibling modules are **not** included here; this file is kept as design lineage, not as a runnable program.

## Why it is archived

The current `tools/aria-core` scaffold re-implements the same ideas behind a cleaner adapter boundary:

- `response_engine.js` (OpenAI-coupled) → `aria-core/src/inference/` (swappable `mock` / `openai` providers).
- ad-hoc identity/capability loading → `aria-core/src/capabilities/` + `aria-core/state/capabilities.example.json`.
- `authority/decision_layer` → `aria-core/src/authority/decisionLayer.js`.
- session read/write → `aria-core/src/memory/sessionMemory.js`.
- truthful output → `aria-core/src/receipts/receiptWriter.js`.

Keeping the legacy file lets future agents compare the original intent against the refactor.

## Security

This directory is archival source only. Do not commit secrets here — no API keys, tokens, passwords, `.env` files, cookies, JWTs, or raw personal data. The archived engine reads its key from the environment; it must stay that way.

## Status

Source material only. For active ARIA work, use `tools/aria-core`.

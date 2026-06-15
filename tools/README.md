# tools/

`tools/` holds project-related **reusable tools, engines, source material, and prototypes** for the CAOS / CAOSCare ecosystem. Code here is intentionally kept separate from the running `backend/` and `frontend/` app surfaces so reusable logic is preserved in GitHub and can later be wired into CAOSCare, a room node, a house node, or another runtime without starting over.

This file is the discovery point: agents and humans working on ARIA logic, reusable tools, engines, adapters, or prior source material should look here first.

## What lives here

- **`aria-core/`** — the current **plug-and-play ARIA runtime scaffold**. ARIA is the capability-aware intent layer: it knows what it can do, what it cannot do yet, and what setup information it needs next, and it must never claim it controlled a device or completed an action unless that action actually happened. Providers are swappable (`mock` needs no key; `openai` is env-only). See [`aria-core/README.md`](aria-core/README.md). New ARIA work belongs here.
- **`aria-response-engine/`** — **archived prior CAOS/ARIA source material** (the earlier standalone response engine), kept as design lineage. It is reference only and is not wired into CAOSCare. See [`aria-response-engine/README.md`](aria-response-engine/README.md).

## Rules for everything under tools/

- **No secrets, ever.** No API keys, tokens, passwords, `.env` files, cookies, JWTs, private credentials, or raw personal data belong in `tools/`. Providers and engines must read keys from the environment only.
- **Runtime output stays git-ignored.** Session, memory, and receipt output (e.g. `tools/aria-core/runtime/`) can contain sensitive user-interaction content and must remain git-ignored — never commit it.
- **Reusable, not coupled.** Keep tools usable outside the app where practical; wire them into CAOSCare behind a clear adapter boundary rather than hard-coding app internals.

## Status

`tools/aria-core` is the active scaffold; `tools/aria-response-engine` is archived source material. Neither is wired into the CAOSCare app runtime yet — the next integration step is wiring ARIA core into a CAOSCare backend route or the frontend chat shell behind the inference adapter boundary.

# Aria Lane — Onboarding Package (single source of truth)

**Status:** Michael-directed process doc (2026-09-08). This file exists so a
future Claude Code (or any coding agent) entering the **Aria conversation /
realtime / substrate** lane does not reinvent Aria or CAOS from scratch.

> The architecture must survive the coding-agent swap, just as Aria's identity
> must survive the underlying-model swap. A new agent does not get to
> independently decide "what should Aria be." It reads the baseline first, then
> works.

This is a **pointer list, not a doctrine copy.** Do not paste prompt/personality
text here or into new files — reference the canonical sources below.

## Read order (do not skip, do not reorder)

### 0. Engineering baseline
1. `~/.claude/CLAUDE.md` — universal engineering principles
2. `AGENTS.md` — CAOS Care agent protocol, mandatory preserve list, stop conditions
3. `CLAUDE.md` (repo root) — onboarding entrypoint
4. `README.md`
5. `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md` — capability bundle, safety, discipline
6. `docs/ENGINEERING_CONTRACT.md` — **300-line handwritten-code cap** (Michael-directed 2026-08-21) and CAOSCare-specific working rules

### 1. Doctrine (placeholders — DO NOT invent their contents)
7. `docs/CAOS_THESIS.md` — placeholder; author with Michael only
8. `docs/CAOSCARE_BLUEPRINT.md` — placeholder; author with Michael only
9. `docs/ARIA_CONTRACT.md` — placeholder; author with Michael only

Where this lane's mission text supplies new doctrine, treat it as Michael-directed
source **for this work**, not licence to fill in unrelated placeholder content.

### 2. Aria substrate — the canonical target for this lane
10. `docs/ARIA_CONVERSATION_SUBSTRATE.md` — **the contract**: conversation is the
    substrate, activation ≠ intent, the Aria-owned context package (11 items),
    state-aware conversation, model boundary, acceptance cases
11. `docs/ROOM_214_CONVERSATION_EVIDENCE_2026-09-08.md` — reconstructed raw
    evidence + the transactional-mechanism → code map (Part 4) + scope guards
12. `docs/ARIA_SUBSTRATE_IMPLEMENTATION_PLAN.md` — the minimal implementation
    design derived from 10 + 11 (layers → modules, what's built, what's next)

### 3. Current runtime & repo state (handoff, not proof)
13. `docs/PROJECT_STATE.md` — dated history; **read the tail**, append when done
14. `docs/CURRENT_NODE_STATUS.md` — EliteDesk runtime handoff
15. `docs/REPO_MAP.md` — file/module orientation
16. `docs/BUILD_STATUS.md`

### 4. Task-specific — read the ones your change touches
- `docs/ARIA_VOICE_FIRST.md` — voice-first history; the 2026-08-09 duplicated-
  instructions bug (`_build_aria_instructions` vs `_build_companion_instructions`)
- `docs/TERMINAL_8_OPERATIONAL_LAYER.md` — the operational request bus
- `docs/ARIA_CAPABILITY_PORTFOLIO.md` — `db.aria_capabilities`; Aria may only
  claim `verified_control` / `verified_read` capabilities
- `docs/CAOSCARE_MEMORY_AUTOMATION_CONTRACT.md` — resident memory scope/consent
- `docs/ROOM_AUDIO_ARCHITECTURE.md`, `docs/CAOSCARE_CONNECTIVITY_RESPONSE_RELAY_CONTRACT.md`
- `docs/LEVEL1_BREAK_TEST_2026-09-06.md` — RF/event/lease/session fencing lane
  (adjacent; the plumbing beneath the substrate)

## Verify before implementing

```
pwd                       # /home/caoscare-1/CAOSCARE.COM
git branch --show-current  # aria/conversation-substrate  (do NOT branch again)
git status --short          # expect in-progress substrate + Level 1 plumbing
```

Do not merge `main`. Do not deploy. Do not touch the Claude Code 1 / Claude Code
2 lanes. Small bounded changes; report line counts of every created/modified
production-code file; append a dated `docs/PROJECT_STATE.md` entry before stopping.

## The one-line rule for the next agent

> Aria is defined by the substrate (identity + continuity + context assembly +
> operational-state authority + conversation rules). The model only generates
> turns for Aria. If a change would let the model — or a session boundary, or a
> queue existing — decide Aria's behavior, it is wrong.

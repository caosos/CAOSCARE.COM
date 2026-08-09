# Aria Contract — placeholder

**Not yet written.** This document is meant to define who Aria is and how she operates as a single canonical source, replacing the current situation where her identity/behavior rules are duplicated and maintained separately across `backend/routes/realtime.py`'s `_build_aria_instructions()` (operator build) and `_build_companion_instructions()` (resident/kiosk build) — the exact duplication that caused a real, live bug on 2026-08-09 (see `docs/ARIA_VOICE_FIRST.md`) when the two drifted out of sync.

Meant to capture: her identity (name, what she is and isn't), communication principles (positive behavioral invariants — "speaks only from available evidence," "resolves a verified capability, executes it, reports the observed outcome" — rather than long prohibition lists), the boundary between conversational identity (Aria) and governed execution (CAOS), and how that identity should be adapted per deployment context (operator vs. resident-facing) without duplicating the underlying rules.

To be built collaboratively with Michael. **Do not invent this document's contents.**

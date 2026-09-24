# Oversized files audit (> 400 lines) — 2026-09-23

**Report only. No file was split or modified by this audit.** The rule is in
`AGENTS.md` "Change discipline": implementation files roughly 300–400 lines;
~400 is a signal to split by responsibility; information-dense files are
exempt where splitting would reduce clarity; oversized files must not keep
growing; no mechanical splitting and no unrelated refactors inside a bounded
task.

**Method.** `git ls-files` of tracked source (`.py .js .jsx .kt .sh .cpp .css`),
excluding generated `frontend/src/components/ui/*` (shadcn primitives — none
exceed 400) and `test_reports/`; `wc -l`. Measured on branch
`aria/wake-word-proof` (= `main` `fb216d4` + the wake-word commits). The only
difference from `main` is `Kiosk.jsx`: 669 on `main`, 642 on the branch.

## Implementation files over 400 lines

| # | File | Lines | What it holds | Nature | Last change | Suggested split (not done) | Priority |
|---|---|---|---|---|---|---|---|
| 1 | `backend/models.py` | 1629 | 97 Pydantic models across ~30 domains (Facility, Users, Residents, Kiosks, Alerts, Pendants, Wearables, SmartDevice, StaffTask, Receipt, CaosEvent, Menu, Email ingest, RF, Transportation…) | Schema — partly information-dense, but mixes unrelated domains and every domain edit grows it | 2026-09-20 | Split by the file's own `# ---------- <Domain> ----------` markers into `models_<domain>.py`, re-exported from `models.py` so imports stay stable. Precedent: `models_transportation.py`. Deferred once already (2026-08-23 "temporary exception"). | **High** — grows with nearly every feature |
| 2 | `backend/tests/backend_test.py` | 1075 | 21 legacy test classes (~85 tests), live-server HTTP tests | Legacy test suite; many tests depend on demo credentials that don't exist locally | 2026-09-13 | Split by domain into `tests/test_<domain>_legacy.py`, or retire obsolete classes after triage. Tests are lower risk than production code. | Low |
| 3 | `frontend/src/pages/Kiosk.jsx` | 642 (branch) / 669 (main) | Room page: kiosk/resident load, emergency poll + activation gate, alert-resolved watch, TV auto-mute, wake-word start, medication announcements, manual call, device commands, voice picker, idle/call layouts | Implementation — genuinely multi-responsibility | 2026-09-23 | Continue the extraction pattern used on 2026-09-23 (`useKioskMediaPrime.js`): e.g. `useEmergencyPoll` (poll + activation gate + breadcrumbs), `useMedicationAnnouncements`, `VoicePickerDialog`, `kioskCallControl` (begin/cancel/TV mute-restore). | **High** — central resident surface, still growing |
| 4 | `frontend/src/pages/Blueprint.jsx` | 588 | Owner "blueprint" page: Header, Hero, RoleTiers, MemoryArchitecture, MemoryBulletin (live, editable), HardwareStack | Mostly static explanatory content plus one live memory-bulletin editor | 2026-05-16 | Move `MemoryBulletin` / `BinColumn` / `BulletinRow` (the only live, stateful part) into their own component; the rest is information-dense page copy and may stay. Content also predates the Product Baseline (tablet-era hardware text). | Low (untouched since May) |
| 5 | `backend/seed.py` | 577 | Demo seed: `ROADMAP_SEED` data + one `seed()` routine | Mostly data (information-dense) | 2026-05-16 | Only if it changes again: move the roadmap/demo data to a data module and keep `seed()` small. Demo seed is off by default. | Low |
| 6 | `android-bridge/caos_rf_bridge.py` | 538 | RF bridge process: signing/HTTP, state dir, sequence numbers, rtl_433 fingerprinting, SDR USB reset, rtl_433 runner, poll loop, record handler | Implementation; one process, several responsibilities | 2026-09-06 | `bridge_http.py` (sign/post/get), `rtl433_fingerprint.py` (pure, unit-testable), `sdr_control.py` (USB reset + runner). Pendant path — **coordinate with the RF/Level 1 lane; do not touch during resident-voice work.** | Medium |
| 7 | `backend/routes/rf.py` | 498 | 14 routes: pairing/listen flow, device assign/list/delete/test, kiosk install info + secret, bridge daemon download, `/rf/event` ingest, events list, bridge pending queue | Implementation | 2026-09-07 | `rf_pairing.py` (listen/pair/assign/test), `rf_install.py` (kiosk install-info, regenerate-secret, bridge-daemon), leaving `rf.py` = event ingest + queries. Precedent: `rf_semantics.py`, `rf_pairing_guard.py`, `rf_bridge_health.py` already extracted. Pendant path — coordinate as above. | Medium |
| 8 | `backend/routes/memory.py` | 461 | Memory extraction (LLM extractor prompt + guards) plus 8 CRUD/query routes | Implementation | 2026-08-29 | `memory_extraction.py` (extractor prompt, name-claim guard, `extract_and_store_memories`) separate from the route module. Precedent: `realtime_memory_ingest.py`. Also where the open name-fact-guard gap lives (PROJECT_STATE 2026-09-19). | Medium |
| 9 | `backend/routes/ai.py` | 438 | Legacy `/ai/chat` (turn-based companion with its own Aria prompt), chat history, `/classify`, `/tts`, `/stt` | Mixed live + legacy. `/ai/tts` is live (Kiosk announcements, voice preview, ResidentsTab); no frontend caller found for `/ai/chat` | 2026-09-07 | Decide the fate of `/ai/chat` and its `CAOS_SYSTEM_PROMPT` (duplicate Aria identity) as part of the Aria single-source work; keep `tts`/`stt`/`classify` in a small speech/classify module. Do not remove without confirming no other caller. | Medium (tied to Aria identity debt) |
| 10 | `frontend/src/pages/RFPairingTab.jsx` | 436 | RF pairing admin: main tab, `AddPendantDialog`, `TestPendantDialog`, severity badge, `hamming()`/`hexToBytes()` helpers | Implementation | 2026-09-16 | Move each dialog to its own file (the file already separates them as functions). Note `hamming()` duplicates `backend/routes/rf_pairing_guard.py::hamming_similarity` — check whether the frontend copy is display-only before consolidating. | Low–Medium |

## Near the threshold (351–400) — watch, do not grow

`backend/routes/alerts.py` 383 · `frontend/src/pages/StaffDashboard.jsx` 378 ·
`backend/routes/resident_requests.py` 363 · `frontend/src/pages/TasksTab.jsx` 351 ·
`backend/tests/iter9_test.py` 351. Voice files touched recently:
`frontend/src/lib/realtimeMessageHandler.js` 345, `frontend/src/lib/realtimeDeviceTools.js` 319.
`alerts.py` is also where the ratified escalation reconciliation lands
(`docs/ENGINEERING_CONTRACT.md` §8) — extract rather than grow it then.

## Documentation / data over 400 lines (information-dense — exempt)

`docs/PROJECT_STATE.md` 4765 (append-only log by design; consider a dated
archive split if navigation becomes a problem — a decision for Michael, not
done here) · `docs/RESIDENT_BASELINE_AUDIT_REPORT.md` 1330 ·
`docs/ARIA_VOICE_FIRST.md` 1272 · `docs/CAOSCARE_PROGRESS_HANDOFF_2026-08-11.md` 946 ·
`docs/REPO_MAP.md` ~680 · `docs/continuation/2026-05-24-…handoff.md` 594 ·
`docs/ADMIN_OPERATIONS_AUDIT.md` 563 · `docs/tsb/TSB-001-…md` 452 ·
`docs/CAOSCARE_FACILITY_OPERATIONS_CONTRACT.md` 446 ·
`docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md` 424 ·
`docs/CAOSCARE_TABLET_BRIDGE_SETUP_RUNBOOK.md` 408 · two
`docs/audits/four-claude/*` reports ~405.

## Recommended order (for Michael's decision)

1. `backend/models.py` domain split — one dedicated pass with tests before and
   after (already deferred once; it grows with almost every change).
2. `Kiosk.jsx` hook extractions — bounded, one responsibility per pass, as
   resident-endpoint work touches each area (supports the endpoint-neutral
   direction in Product Baseline §2).
3. `memory.py` extraction module — pairs naturally with fixing the open
   name-fact extraction guard.
4. `rf.py` / `caos_rf_bridge.py` — only inside the RF/Level 1 lane.
5. `ai.py` — as part of the single-source Aria identity work.

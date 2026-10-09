# Realtime model A/B harness (RQ-048) - offline, no paid calls

Compares the resident voice model (`OPENAI_REALTIME_MODEL`: `gpt-realtime` vs `gpt-realtime-2.1-mini`) per `docs/reports/2026-10-09-realtime-model-ab-proposal.md` sections 3-5. **Nothing in this directory calls a provider.** The stub proves the plumbing, not any model.

## Owner approval gate (quoted from the proposal, section 7)
> Owner statement needed (nothing paid starts without it): "AUTHORIZE the CAOSCare realtime-model A/B: up to $5 total OpenAI spend, models `gpt-realtime` and `gpt-realtime-2.1-mini`, isolated stack only, stage 1 (scripted typed) and stage 2 (one attended voice session per model). No change to Room 214." A **separate** owner decision is required to switch Room 214.

`run.py --live` refuses unless env `CAOSCARE_AB_APPROVED=<owner statement id>`, `--budget-usd <= 5` and `OPENAI_API_KEY` (environment only, never read from a file) are all present. Even then it only prints the cap and stops: the live driver is intentionally not implemented in RQ-048.

## Files
| File | Purpose |
|---|---|
| `scenarios.json` | The 8 scenarios: scripted typed turns + machine-checkable pass criteria (vocabulary in `scorer.py` `CHECKS`) |
| `scorer.py`, `events.py` | Checks over logged events (`tool_call`, `tool_result`, `unsupported_*`, `realtime_error`, `assistant_transcript`, receipts); export loader |
| `report.py` | Per-model summary, usage/cost, decision gates (proposal section 5) |
| `prices.json` | Only the figures in the proposal, marked "provider docs 2026-10-09, re-verify"; missing price => cost `null` (unknown) |
| `stub_realtime.py`, `stub_script.json` | Local stub endpoint (127.0.0.1) with `stub-good` / `stub-bad` scripted behaviour |
| `run.py` | `--dry-run` (default) drives the stub over HTTP, exports JSONL, scores; `--live` guarded |
| `score.py` | Score exports (`--jsonl`) or a throwaway Mongo (`--mongo-url --db --session SID:SCENARIO:MODEL`, read-only) |
| `config_check.py` | Prints every field of the mint config and `session.update` (real code, real `realtimeSessionUpdate.js` via node) + chars/4 token estimate |

## Use
```
backend/.venv/bin/python scripts/model_ab/run.py            # dry-run against the stub
backend/.venv/bin/python scripts/model_ab/config_check.py --model gpt-realtime-2.1-mini
backend/.venv/bin/python scripts/model_ab/score.py --jsonl scripts/model_ab/out/dry-stub-good-S3.jsonl
```
Tests: `backend/tests/test_model_ab_harness.py`.

## Known limits (read before the paid stage)
- **Usage is not logged today.** `realtimeMessageHandler.js` logs `response_done` with only the response id. The scorer reads `meta.usage` (Realtime `response.done` usage) when present; real runs need a one-line client change to log it (frontend; out of scope for RQ-048). Without it the summary says `usage: not logged` and cost stays unknown. The usage field shape is from the provider docs as understood, unverified against a live response.
- Latency is the gap between a typed `user_transcript` and the next `response_created` timestamp (server clock); it is not first-audio latency.
- The real claim guard (`claimGuard.js`) matches the bare word "weather", so an honest refusal that mentions it ("I can't check the weather") is counted as `unsupported_fresh_fact_claim` in scenario 8. Review S8 transcripts before treating a hit as a model failure.
- `config_check.py` uses the no-resident prompt and an empty stand-in database (nothing real is read); a real resident adds memory text. Diffing against the mini reference is a human step.
- Stage 2 (voice quality, turn-taking) cannot be scored by this harness.

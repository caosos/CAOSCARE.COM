# CAOSCare Coordination Reconciliation — 2026-10-07

**Purpose:** normalize stale multi-agent state before further autonomous dispatch.

The old six-worker Round 5 board is no longer trustworthy as a live assignment board. Several tasks listed as assigned were later merged, superseded, parked, or became Michael/physical blockers. Do not launch work solely from an old ASSIGNED/READY label until it is reconciled against current integration truth.

## Current facts already established in repo history

- SIM-4 Maintenance was integrated (#66 / integration commit `577b35c`).
- Gate port/log isolation was integrated (#68 / integration commit `4d413ef`).
- Simulator loop revival was integrated (#70 / `905d333`).
- B3 public resident lookup allowlist was integrated on 2026-10-07; full gate 291 passed, 0 failed.
- The two bounded workers launched later for SIM-4 Maintenance and gate isolation were redundant and were stopped cleanly.
- Agent Control Plane PR #67 remains **NEEDS FIX** according to the last recorded coordinator review.
- RQ-003 live Nursing voice acceptance requires Michael physically speaking at a room screen.
- Restarting live backend :8092 to pick up newer integrated code remains an explicit operator/Michael action.
- Production/Linode deployment remains out of scope without Michael approval.

## Required reconciliation pass

Before launching new bounded workers, the coordinator must:

1. Fetch `origin/integration/2026-09-27` and record the current HEAD.
2. Re-read the tail of `docs/PROJECT_STATE.md`.
3. Reconcile every non-DONE row in:
   - `docs/PILOT1_ACTIVE_WORK.md`
   - `docs/PILOT1_READY_QUEUE.md`
   - `docs/PILOT1_EXECUTION_CHECKLIST.md`
4. For each item, classify exactly one:
   - DONE / integrated
   - READY / bounded and useful now
   - BLOCKED / exact external dependency
   - NEEDS MICHAEL / one concrete decision or physical action
   - PARKED / not Pilot-1 critical
   - SUPERSEDED / replaced by later work
5. Verify old worker branches/PRs against integration before reassigning. Never infer unfinished work from an old assignment alone.
6. Identify shared-core dependencies explicitly. If task B waits on task A, encode that dependency in the queue rather than leaving prose in old lane notes.
7. Collapse old long-lived-agent ownership. Tasks belong to the queue; fresh bounded workers are disposable executors.
8. Produce a clean **NEXT TWO** list: the two highest-value, non-overlapping, no-Michael-required tasks safe to execute immediately.
9. Update the three tracker files so a fresh coordinator can cold-start without reading old chat history.
10. Only after the tracker files are clean, launch at most two bounded workers.

## Definition of reconciled

A cold coordinator reading `START_HERE.md` plus the canonical tracker files can answer without ambiguity:

- what is already integrated;
- what is actively running;
- what is ready now;
- what is blocked and by what;
- what needs Michael;
- what the next two autonomous tasks are.

No required state may live only in old Claude sessions, tmux panes, or chat history.

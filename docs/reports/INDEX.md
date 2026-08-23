# Reports Index

Start here. Updated by Claude Code every time a report is added or an
issue is resolved — this is the fastest way to find current state without
reading the whole folder or asking Michael to paste anything.

_Last updated: 2026-08-23 15:20 UTC_

## Latest forensic report
[2026-08-23-1448-room304-morning-forensics.md](2026-08-23-1448-room304-morning-forensics.md)
— Chauncey/Room 304 morning session. `mark_resting` misfired on a
non-dismissal phrase; a 20s period with zero detected speech followed,
cause unproven.

## Latest acceptance-test report
None yet distinct from the forensic reports above — every real-conversation
test so far has surfaced a real defect, so "forensic report" and
"acceptance-test report" have been the same document. This entry will
point to a clean pass once one happens.

## Current unresolved issues
- `mark_resting` has no code-level gate — only prompt wording, which the
  model has overridden twice now (once on "maybe I need to turn it up",
  once on "You got it."). Needs the same kind of backend-enforced check
  Priority 1's provenance guard uses, not just tighter wording.
- The ~20s "went deaf" period after the `mark_resting` misfire is
  unexplained — no instrumentation exists yet to prove whether the
  resident was actually speaking and not detected, or was silent.
- Neither VAD configuration tested live so far (`server_vad` 1000ms, or
  `semantic_vad` eagerness "low") has produced a session free of real
  defects. `semantic_vad` caused a 38s total detection dead zone and was
  reverted; `server_vad` (the restored baseline) still produces premature
  cutoffs and one/two-word fragment turns.

## Current system state
See [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md) — the single running
dated log of what changed, what was verified, and what's next. Most
recent entry is at the bottom of the file.

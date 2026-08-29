# CAOSCare Troubleshooting Bulletins (TSB) — index

A TSB is a **permanent failure/fix/evidence record** — not a session note. It
documents one real, reproducible incident (what was observed, what was
confirmed working, what failed, the suspected cause, and what remediation
was proposed/verified), grounded in persisted evidence (conversation
records, receipts, device commands, diagnostics) rather than recollection.

This index did not exist before TSB-001 (2026-08-29) — checked exhaustively
(`grep -rli "troubleshooting bulletin\|TSB"` across the repo, git history,
and file names) before creating it, so TSB-001 is genuinely the first, not
a guessed number.

## Conventions (established with TSB-001, apply going forward)

- **Numbering**: sequential, zero-padded to 3 digits (`TSB-001`, `TSB-002`,
  ...), assigned by checking this index for the highest existing number —
  never guessed, never reused.
- **Filename**: `docs/tsb/TSB-NNN-short-slug.md`.
- **One incident per TSB.** If a new report concerns the exact same live
  session/incident an existing TSB already covers, extend that TSB (add a
  dated update section) rather than opening a new number.
- **Required sections** (a TSB is incomplete without these):
  Summary, Observed Evidence, Confirmed Behavior (what worked), Failure
  (what didn't), Suspected Architectural Cause, Proposed Remediation,
  Verification Required, Rollback / Stop Gates, Evidence References,
  Status.
- **Status values**: `OPEN — documented, not remediated` /
  `IN PROGRESS — fix implemented, verification pending` /
  `RESOLVED — fix implemented and regression-tested` /
  `WONTFIX — reasoned decision not to change, recorded`. A TSB is never
  marked `RESOLVED` on the strength of a code change alone — only after the
  specific failure mode has been reproduced against the fix and passed.
- Evidence references must be **queryable, not narrated** — real session
  IDs, receipt IDs, collection names, and query shapes a future agent can
  re-run against the live system, not a paraphrase of what someone recalls
  happening.

## Log

| # | Title | Status | Date |
|---|---|---|---|
| [TSB-001](TSB-001-resident-voice-name-attribution.md) | Room 401 resident-voice name-attribution hallucination + unaudited durable name mutation | OPEN — documented, not remediated | 2026-08-29 |

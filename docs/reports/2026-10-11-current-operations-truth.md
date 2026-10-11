# Current vs historical operations — careops-current-operations-truth-001 — 2026-10-11

Owner screenshots (localhost:3000/admin, 17:39 CDT): Alerts & events "338 shown, 322 open, 0 live", including a
20-day-old ACTIVE unacknowledged Helen Torres RF emergency; Nursing 8 open / 5 unassigned including mock-resident
requests opened 49 days ago. Ask: the working SIM should show current information.

## Step 1–2: observed on the EliteDesk dev host (read-only, dev DB `caoscare`, backend :8092 at 45bd234)
- **No simulator run is running.** Both runs are STOPPED (`simrun_d0ea805fa522`, `simrun_4b9a3f2c415d`, last update
  2026-10-11 02:29Z). Nothing current comes from the SIM; the screens could not show "current SIM information".
- **Open alerts (322): none simulated, all 21–63 days old.** 263 assist, 30 comfort, 28 emergency (27 active + 1
  acknowledged), 1 acknowledged assist. 286 have no resident attached (RF bring-up activity); the rest are on MOCK/TEST
  residents, plus 3 named "michael". The Helen Torres emergency is a real-resident record and is therefore classified
  "real or unknown origin - check before closing", never auto-closed.
- **Open tasks:** none simulated or tied to a run; 56 belong to MOCK/TEST residents, most 34–63 days old; a few are
  2–8 days old (current under the 14-day task window).

## Step 3–4: built
- `backend/routes/operations_currency.py` (new): the ONE classification of open records — `current` (real, inside the
  window), `sim_current` (simulated, from the RUNNING/PAUSED run), `sim_past` (simulated, stopped run), `review` (real or
  unknown, older than the window; reason: no resident attached / test-mock resident / real or unknown origin). Windows:
  alerts 72 h (the overview's existing threshold), tasks 14 days (`CAOSCARE_TASK_REVIEW_DAYS`).
- `GET /alerts` and `GET /tasks` rows carry `currency`; optional `?view=current|review` (default unchanged: everything).
- `GET /ops/currency` (admin): simulator state (active run id or STOPPED + last run) and counts per bucket / reason /
  review emergencies.
- `POST /ops/legacy/close` (admin): closes only `review` records — tasks through the canonical receipted skip
  (`task_cancelled`, note "Legacy record closed after review: …"), alerts resolved with outcome `legacy_review_closed`,
  category `legacy_test_data` and an `alert_legacy_closed` receipt (actor, authority, before/after, review reason).
  Current and simulated records are refused; an **emergency is refused unless a written human disposition** is given,
  which is recorded in the close notes and receipt.
- Alerts board: defaults to **Current**, with a counted **Older, needs review** view (reason per row, simulator state,
  per-row "Close as reviewed…" and a batch close for non-emergencies); SIM rows show their run id. Department queues
  (e.g. Nursing): older open requests hidden behind a counted banner with "Show older"; rows marked "needs review".

## Tests
- Backend gate **547 passed, 0 failed, 31 skipped** (+2 `test_operations_currency.py`: classification rules; alerts/tasks
  views; counts and simulator state; admin-only; refusals for current and for an emergency without disposition; receipted
  alert and task closes). Existing overview and alert-receipt tests unchanged and passing.
- Frontend **76 suites / 592**; build compiled.
- Browser (scratch stack, seeded historical + fresh real + current SIM + real-resident emergency): **13/13, 0 failed API
  calls** — default view shows only the fresh real and current SIM items; counts separate current from review; SIM row
  shows its run id; older view shows reasons and "Simulator: RUNNING run …"; the emergency close stays disabled until a
  disposition is written, then closes with it recorded and a receipt; the batch close closes 5 non-emergency items with 5
  receipts and leaves current items alone; after STOP the stopped run's SIM item leaves current work; the Nursing queue
  hides the 49-day mock request behind a counted banner and reveals it on demand, unchanged; 390 px clean. Screenshots:
  `docs/reports/assets/2026-10-11-current-operations/`.

## Not done (deliberately)
- **No record on the dev or production database was closed.** The 322 old alerts and the mock tasks stay open until an
  administrator reviews and closes them in the new view (the owner's call; emergencies need a written disposition).
- No simulator was started; "current SIM information" will appear once a run is started from Live Operations.
- Not deployed; production `ff87c22`.

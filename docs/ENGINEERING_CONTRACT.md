# Engineering Contract — placeholder

**Not yet written.** This document is meant to define how agents are expected to work specifically within CAOSCare — the project-specific complement to the universal engineering principles in the global `~/.claude/CLAUDE.md` (understand before changing, one source of truth, verify the exact path the user uses, documentation describes reality, etc.).

Meant to cover things specific to this repository: the required-reading order and when it applies (canonical: `AGENTS.md` / `docs/CAOSCARE_PRODUCT_BASELINE.md` §9), the code-size discipline (**aim below 300, 300-line hard cap** — see the section below and Product Baseline §8; this replaced the earlier "200 soft / 400 hard" wording that still appears in older docs), how/when to update `docs/PROJECT_STATE.md` and `docs/CURRENT_NODE_STATUS.md`, how contradictions between docs and running code should be surfaced and resolved, and any CAOSCare-specific SOPs for recurring operations (deploying, restarting services, testing voice paths, etc.).

To be built collaboratively with Michael. **Do not invent this document's contents.**

---

## Code file size (Michael-directed, 2026-08-21)

The rest of this document is still unwritten — this section is an explicit rule Michael gave directly, not an agent inference, recorded here so it isn't lost before the full contract exists.

Handwritten production code files must not exceed 300 lines unless Michael explicitly approves an exception.

- Aim below 300 lines.
- Split by clear domain or responsibility, never arbitrary line chopping.
- Do not create God files.
- Do not launch a broad refactor solely to shorten an untouched legacy file that is already over the cap.
- If modifying an existing code file already above 300 lines, do not make it larger — extract the responsibility being changed when practical.
- Before finishing any coding task, report the line counts of every created or materially modified production-code file.

Documentation, informational files, reports, generated files, static data, lockfiles, and necessary configuration files are exempt.

This replaces the prior 400-line hard cap recorded in `AGENTS.md`.

---

## Operational service-layer architecture (Michael-directed, 2026-09-20)

Same status as the section above: an explicit rule Michael gave directly,
recorded verbatim so it is not lost before the full contract exists — not
an agent inference, not invented content. Ratified after a multi-AI review
of `docs/reports/2026-09-20-operational-workflow-audit.md` (read that
report first for the evidence trail — file/line citations for every
finding referenced below live there, not here). This section is the
**canonical, single location** for these decisions; every other document
that touches the same ground (`docs/reports/RUNNING_FACILITY_TESTBED.md`,
`docs/CAOSCARE_FACILITY_OPERATIONS_CONTRACT.md`,
`docs/CAOSCARE_OPERATIONS_GAP_MAP.md`, `docs/CAOSCARE_PRODUCT_BASELINE.md`)
cross-references this section rather than restating it.

### Ratified architecture decisions

1. **One canonical operational/service layer.** Human UI, Aria, the
   simulator (§ below), front desk, and external adapters (email/SMS/
   Twilio) must call the same canonical business-rule functions rather
   than each maintaining a parallel state system. Concretely, this means:
   the functions the 2026-09-20 audit already identified as canonical
   (`resident_requests.py::create_resident_request()`, `tasks.py::create_task()`,
   `task_assignment.py`'s assign/ack/start/complete, `resident_activation.py::
   record_resident_activation()`, `transportation_engine.py::find_or_create_run()`,
   `menu_ingest.py::create_menu_upload()`, `schedule_ingest.py::create_schedule_items()`,
   `escalation.py::tick()`) remain the ONLY way any caller — human, Aria,
   simulator, or adapter — creates or transitions these domain objects. No
   caller writes `db.staff_tasks`/`db.alerts`/`db.transport_runs` directly.
2. **Aria is a natural-language interface to CAOSCare, not a separate
   operational authority.** Aria's tools call the same canonical service
   functions decision 1 names. Aria never holds domain state that CAOSCare
   itself does not also hold and expose to a human.
3. **Every state-changing service operation receives an explicit,
   authenticated `ActorContext`** (or equivalent canonical actor
   structure) — who/what is acting, and under what authority — at the
   callable service/business-layer function itself, not only enforced in
   an HTTP route or UI middleware. An in-process caller (Aria's tool
   dispatch, a future simulator driver) must pass a real `ActorContext`
   and go through the same authorization check an HTTP caller would; it
   must never bypass authorization by virtue of calling the Python
   function directly instead of the route. **Not implemented today** — the
   audit confirmed every canonical function currently takes plain
   parameters (`resident_id`, `created_by: Optional[str]`, etc.), not a
   structured actor object, and authorization currently lives in the
   FastAPI route's `Depends(...)` rather than in the service function
   itself. This is real, scoped Track 2 work (see below), not yet built.
4. **Simulation provenance derives from an authenticated simulation actor
   context.** Simulation writes must be explicitly identifiable — e.g.
   `simulated: true` plus a `simulation_run_id`/`source` value reusing the
   existing `TaskSource`/`EventSource` literal pattern — so reset/filtering
   logic can never accidentally match or damage real activity (Room 214's
   real resident/RF data included). **Not implemented today.** The only
   existing precedent for distinguishing generated from real data is a
   **naming convention**, not a schema flag (`seed_demo_community.py`'s
   `"Demo - "` name prefix and reserved `3W01`–`3W10` room range) — real,
   working, but fragile at scale. A future simulator should get the
   stronger `simulated: bool` field; the naming convention remains valid
   as a secondary/legacy-compatible signal, not replaced.
5. **Internal state vs. external side effect — a real boundary, not
   elegance.** Object lifecycle/state transitions belong in an
   append-only event history (`Alert.event_log[]` already does this
   correctly — `{at, field, from, to}`, `models.py:329`). Receipts
   (`db.receipts`, `create_receipt()`/`update_receipt_status()`) represent
   an **externally observable side effect crossing the system boundary**:
   a notification sent, an email/SMS attempted, a spoken confirmation
   given, a dispatch/contact made. The same lifecycle fact must never be
   represented as a second, competing receipt ledger. A repeated external
   effect (a second notification for the same still-open item) creates a
   **new** receipt; a historical receipt is never rewritten as though the
   original event changed. **Real, confirmed violation today:**
   `receipts.py::update_receipt_status()` (`receipts.py:83-111`) mutates
   the MOST RECENT receipt for an object in place on every status change,
   so `db.receipts` for a task shows only "created" + whatever its last
   update was, not the true sequence. This must become append-on-transition,
   not overwrite-in-place, wherever a receipt is meant to prove an audit
   trail (Track 2 work, not yet built).
6. **`StaffTask` needs append-only transition history analogous to
   `Alert.event_log[]`.** `StaffTask` today has only 5 named timestamp
   fields (`created_at`/`acknowledged_at`/`started_at`/`completed_at`/
   `last_re_requested_at`) and no record of intermediate reassignment,
   pausing, or any transition not covered by one of those five names. If
   full "what happened between X and Y" reconstruction matters (it does
   for the replay/history goal below), `StaffTask` needs the same
   `event_log`-style array `Alert` already has. **Do not fabricate
   historical transitions for legacy tasks that predate this field** —
   a legacy task simply has a shorter, honestly incomplete log starting
   from whenever the field was added, never a backfilled guess.
7. **Existing test/demo/stale data needs an explicit migration/quarantine
   policy before any simulator write.** Per the audit's real counts
   (2026-09-20): 319 of 337 `db.alerts` are `status="active"`, ages
   342–1010 hours, almost entirely 2026-08-29→09-06 RF hardware-test
   debris. Prefer **preserving and classifying** this uncertain historical
   evidence over silently inventing clean history or destroying it — no
   bulk delete/rewrite of this data is authorized by this document.
   Dedup/reset behavior for any future simulation run must be scoped
   safely (by `simulation_run_id`, never a blanket collection wipe) so one
   run's reset can never touch another run's or real data's records.
8. **Escalation: two implementations exist and disagree; here is the
   canonical one.** `docs/reports/2026-09-20-operational-workflow-audit.md`
   §5 confirmed both concretely: `alerts.py::alerts_feed` (a GET/read
   endpoint) computes inline escalation as a side effect of being polled,
   using hardcoded 60/180/420-second thresholds and levels 0-3;
   `escalation.py::tick()` uses an admin-configurable `EscalationRule`
   (`level_2_seconds`/`level_3_seconds`, default 90/150) and writes
   `status: "escalated"` — a value **not present** in the `AlertStatus`
   literal (`models.py:259` = exactly `["active","acknowledged","resolved"]`),
   a live, real data-integrity bug.
   - **Canonical decision: `escalation.py::tick()` is the sole escalation
     authority going forward.** Rationale: it is admin-configurable
     (matches decision 1's "one canonical service layer," not a hardcoded
     rule embedded in an unrelated read path); a GET endpoint silently
     mutating state as a side effect of being polled is itself an
     architecture smell independent of this decision.
   - `alerts.py::alerts_feed`'s inline escalation computation must be
     **retired** — it should read whatever `tick()` last computed, never
     compute its own competing escalation state.
   - `AlertStatus` must gain `"escalated"` as a valid value (or `tick()`
     must stop writing a value the model doesn't declare — either way,
     the mismatch is fixed, not left standing).
   - **Preserve, do not flatten:** `Alert.aria_state` (voice-session
     state) and `Alert.live_line_state` (phone-routing state) are
     genuinely distinct concepts from `Alert.status` (staff workflow) and
     from escalation level. They represent three different questions
     ("has staff acknowledged this," "is Aria currently engaged with the
     resident about this," "is a live phone line being offered/rung") and
     must remain separate fields, not merged for schema elegance.
   - **Ownership note, explicitly flagged, not resolved here:** `alerts.py`
     is also actively owned by the Level-1/Aria conversation-substrate
     lane (`docs/ARIA_SUBSTRATE_IMPLEMENTATION_PLAN.md`). Whoever
     implements this reconciliation must coordinate with that lane before
     editing `alerts.py`, per the standing lane-ownership rule in
     `docs/reports/MULTI_AGENT_EXECUTION_PLAN.md`. **Not implemented
     today** — this is a ratified decision awaiting Track 2 execution.
9. **Production time processing and simulation are separate systems.**
   The real facility's scheduler/background processing (at minimum, an
   automatic caller for `escalation.py::tick()` — confirmed today to have
   **no automatic caller anywhere**, admin-button-only) is required for
   real CAOSCare **even with simulation permanently disabled.** The
   simulator (see `docs/reports/RUNNING_FACILITY_TESTBED.md`) is a
   test/demo harness, independently disable-able, and real escalation
   logic must never import, depend on, or be gated by simulator code.
10. **Reuse `resolve_operational_state()` (Layer E) for human current-state
    aggregation; do not build a third competing "what is open now?"
    model.** `backend/routes/aria_operational_state.py::resolve_operational_state()`
    already unifies open `db.alerts` + open `db.staff_tasks` into one
    lifecycle-normalized snapshot for Aria's own prompt context, and is
    explicitly documented as **read-only** by its own module's invariant
    (`docs/ARIA_SUBSTRATE_IMPLEMENTATION_PLAN.md`: "This module is
    read-only; lifecycle transitions stay in alerts.py /
    alert_lifecycle_events.py / resident_requests.py"). The audit found
    THREE independent "what's open right now" implementations already
    exist (`ops_overview.py`'s attention ranking, `alerts.py::alerts_feed`'s
    inline view, and Layer E) with none calling each other. Live Board
    aggregation should call Layer E, read-only, rather than adding a
    fourth. This does not require moving or rewriting Layer E — it is
    Claude 2's / the Aria substrate lane's code and stays there; Live
    Board becomes a new caller of it, nothing more.
11. **Live Board means "what requires human attention right now."** It is
    an aggregate/read model over the canonical domain objects (`Alert`,
    `StaffTask`, via decision 10's reused Layer E where practical), never
    a second source of truth. If Live Board's own numbers ever disagree
    with the underlying `Alert`/`StaffTask` records, Live Board is wrong
    by definition — this is the same "one source of truth" invariant
    already stated in `docs/CAOSCARE_PRODUCT_BASELINE.md` §8, made
    concrete for this specific surface.
12. **Role interfaces are compositions of shared operational components,
    not separate role-specific applications.** Front Desk, Maintenance,
    Nursing, and Owner/Admin views all read/act on the same canonical
    domain objects through the same canonical service functions (decision
    1); only which components render and which actions are authorized
    differs per role. Backend authorization remains authoritative; UI
    presentation follows authorized capability, never the reverse (a
    screen must not show an action a role isn't authorized to take, and
    must not be the only place that authorization is enforced).
13. **The simulator must exercise canonical services/workflows, never
    manufacture finished DB rows or animated dashboard state.** See the
    Living-Building Simulation Architecture addendum in
    `docs/reports/RUNNING_FACILITY_TESTBED.md` for the concrete function
    list and sequencing (thin-slice-first, per decision 15).
14. **Capture history now; historical playback/time-machine UI is
    explicitly NOT a pilot requirement.** `Alert.event_log[]` already
    makes "what did this event look like at time T" reconstructable for
    resident-assistance events; `StaffTask` needs decision 6's equivalent
    field if that reconstruction matters for tasks too. No replay/scrub
    UI is to be built against this pass's decisions — recording the data
    correctly is the requirement, not a viewer for it.
15. **Simulation coverage matters before duration.** Before any
    month-long synthetic-activity run, first prove one small, deterministic
    scenario end-to-end: request → dedup/routing (reusing decision 1's
    canonical dedup — see `create_resident_request()`) → acknowledge/assign
    → start → complete, PLUS a deliberately-unanswered case that exercises
    decision 8's canonical escalation path. A month of synthetic activity
    is generated/replayed only after that thin slice passes — it is not
    hand-authored data.

### GATE

**NO SIMULATOR WRITES** (beyond the dev-only one-shot seed scripts that
already exist) **until all of the following are ratified AND implemented,
not merely decided:** provenance/`simulated` marking (decision 4), actor
context/authorization at the service layer (decision 3), `StaffTask`
lifecycle history (decision 6), canonical escalation semantics (decision
8), and legacy-data migration/quarantine treatment (decision 7). This gate
is binding on any future session/lane, including one operating under
`docs/reports/RUNNING_FACILITY_TESTBED.md`'s Lane F.

### Two-track execution model

**Track 1 — low-risk operational correctness, does NOT wait for this
contract's remaining implementation work.** These reuse existing domain
models and existing canonical functions; they invent no new lifecycle/
state system, so none of them are gated above:
- Age-bound the stale-alert/exception reporting in `ops_overview.py` (and
  `alerts.py::alert_stats`) so historical RF-test debris stops reading as
  "hundreds of active events" — audit §6/§9 Option B.
- Fix `TasksTab.jsx`'s "Today" tab to actually pass the `day=` filter
  `tasks.py::list_tasks` already supports — audit §6#4.
- Refresh current menu/schedule seed data for the live date window using
  the already-existing idempotent seed scripts — audit §6#2.
- Reuse `create_resident_request()`'s existing dedup logic for an
  authenticated front-desk entry path (loosen its `source` allow-list, or
  extract the dedup block into a shared helper) — audit §12.
- Wire `DepartmentWorkspaceDialog.jsx` to the already-existing assign/
  acknowledge/start/complete endpoints, mirroring `MaintenanceWorkspace.jsx`
  — audit §8/§11.

**Track 2 — architecture contract, single-threaded before simulation
writes begin.** This is exactly decisions 3, 4, 6, 7, 8, and the
canonical-current-state-aggregation reuse in decision 10, plus reconciling
`docs/reports/RUNNING_FACILITY_TESTBED.md` against the 2026-09-20 audit
(done as a documentation addendum by this same pass — see that file).
None of Track 2 is implemented as of this section being written
(2026-09-20); this section is the ratified decision record Track 2's
implementation must follow.

See `docs/reports/2026-09-20-operational-workflow-audit.md` for the full
evidence trail every finding above cites, and
`docs/reports/RUNNING_FACILITY_TESTBED.md` for the simulation-specific
architecture addendum (decisions 4, 7, 9, 13, 14, 15 in that context).

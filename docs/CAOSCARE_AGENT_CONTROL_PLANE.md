# CAOSCare Agent Control Plane — design (Phase 1)

**Status: active control-plane branch — mock command slice + owner UI + read-only discovery + autonomous foreman/persistence scaffolding. Live worker delivery remains unverified until EliteDesk acceptance.** Branch
`pilot/agent-control-plane` from `integration/2026-09-27` `31f5c03`. The
slice is tested in-process but **not mounted** in `server.py` (shared file) —
see §15. No live Claude session is touched.

## 1. Goal

Michael supervises the Claude workers on the EliteDesk from a CAOSCare admin
page instead of switching terminal tabs and copying text between agents:

```
Owner (signed in) → Admin → Agent operations
  → registered agents and their real status
  → send a command to the coordinator or one worker
  → command recorded → delivered → acknowledged → completed / failed
  → every step is a receipt with provenance
```

Later (not Phase 1): the same control API exposed to Aria/ChatGPT through a
governed API/MCP layer, Claude Agent SDK workers, coordinator delegation,
mobile view, alerts, remote access.

## 2. What exists today (inspected 2026-10-05, read-only)

| Fact | Evidence |
|---|---|
| tmux is **not installed** | `which tmux` → not found |
| Claude workers run as interactive `claude` CLI processes in plain terminals (pts/0…pts/8), most with cwd `~` | `ps`, `/proc/<pid>/cwd` |
| Claude Code keeps a local session registry: `~/.claude/sessions/<pid>.json` with `name` (e.g. `caoscare-1-25`), `status` (`idle`/`busy`), `updatedAt`, `cwd`, `sessionId`, and a `messagingSocketPath` | file read (non-secret fields only) |
| Each session also has a `<pid>.<hash>.key` file and a unix socket under `/run/user/1000/cc-socks/` — Claude Code's internal peer-messaging transport | directory listing; keys **not read** |
| 8 Claude sessions on the host; which one is "Agent 3", etc. is **not recorded anywhere machine-readable** | `ListAgents` shows names like `caoscare-1-25`, no role mapping |
| No existing agent/session management code in the repo | grep |

Consequences:

- There is no safe way to type into the running sessions today. Injecting
  keystrokes into an existing pts, or speaking Claude Code's internal socket
  protocol with its keys, is not acceptable (undocumented, holds secrets,
  could corrupt a live worker). **Phase 1 does not touch the live sessions.**
- Truthful *status* (idle/busy, last update) of real sessions can be read
  from the registry JSON with a field allowlist. That is internal Claude Code
  state, not a contract; treat it as best-effort and label it so.
- The agent-id → session binding (`claude-3-simulator` = `caoscare-1-xx`) must
  be entered by Michael. It is not inferred.

## 3. Architecture

```
AgentOperations.jsx  (Admin tab, owner only)
        │  HTTPS, JWT
routes/agent_control.py          thin routes, auth + feature flag
        │
agent_control/commands.py        command service: issue, transition, receipts
agent_control/registry.py        agent records (db.agent_registry)
        │
agent_control/supervisor.py      picks the adapter configured for the agent,
        │                        runs delivery, records the outcome
        ▼
AgentAdapter (interface)
   ├── MockAdapter               Phase 1 — in-process test agent, simulated
   ├── ClaudeRegistryReader      Phase 1b — read-only real status
   ├── TmuxAdapter               Phase 2 — one NEW disposable worker in tmux
   └── AgentSdkAdapter           later — Claude Agent SDK workers
```

The UI never knows which adapter is behind an agent. The browser never sends
a session name, pane, path or executable — only `agent_id` + instruction.

### Adapter interface

```python
class AgentAdapter(Protocol):
    kind: str                                   # "mock" | "claude_registry" | "tmux" | "agent_sdk"
    async def get_agent_status(self, binding) -> AgentStatus      # online/offline/working/waiting/unknown + last_activity_at
    async def send_command(self, binding, command) -> Delivery     # delivered | failed (+ evidence)
    async def get_agent_events(self, binding, since) -> list[AgentEvent]
    async def pause_agent(self, binding) -> Delivery               # may return "unsupported"
```

`list_agents()` lives in the registry, not the adapter: the list of agents
is CAOSCare's record, the adapter only reports on a bound target.

`binding` comes from server-side configuration only
(`agent_control/bindings.yaml` or env, never the DB-from-browser): which
adapter, which target (e.g. tmux target `caos-agents:test`). An owner can
*select* among configured bindings; cannot enter a new target string.

## 4. Data (MongoDB, new collections; no shared model changed)

Pydantic models live in `backend/agent_control/models.py`, **not**
`backend/models.py` (no change to shared contracts).

`db.agent_registry` — one document per agent:

```
agent_id          "claude-1-coordinator" … "claude-6-security"   (fixed seed list)
display_name, role
binding_id        configured binding or null
session_ref       e.g. "caoscare-1-25" (owner-entered) or null
branch, current_task, blocked_on     owner/agent-reported text, null = UNKNOWN
status            computed at read time from the adapter; never stored as truth
last_activity_at, last_message, last_receipt_id
```

Unbound agents show **OFFLINE / UNKNOWN**. No values are invented.

`db.agent_commands` — one document per command:

```
command_id                server-generated
client_command_id         browser-generated UUID, unique index (replay guard)
issued_by                 {user_id, name, role} from the JWT — never from the body
target_agent_id           must exist in the registry
instruction               ≤ 4000 chars, control characters rejected
based_on_integration_sha  optional, 7-40 hex, recorded as given (not verified)
parent_command_id         optional, must exist
status                    queued | delivered | acknowledged | completed | failed | cancelled
status_log[]              append-only {at, from, to, by, receipt_id, note}
origin_receipt_id, delivery_receipt_id, completion_receipt_id
created_at
```

`status` is the latest value of `status_log`; history is never rewritten.

## 5. Receipts (reuse `routes/receipts.py::create_receipt`)

Same pattern as the simulator run chain (`backend/simulation/scheduler.py`):

| Step | action_type | actor | result_label |
|---|---|---|---|
| owner issues | `agent_command_issued` (origin) | `actor_from_user(owner)` | `verified` |
| adapter delivers | `agent_command_delivered` / `agent_command_delivery_failed` | `actor_system("agent_control:<adapter>")` | `verified` for tmux paste confirmed by tmux exit code; `simulated` for mock |
| agent acknowledges | `agent_command_acknowledged` | the agent's actor | `unverified` (self-report) |
| completed / failed | `agent_command_completed` / `agent_command_failed` | agent or owner | agent self-report → `unverified`; owner confirmation → `verified` |
| owner cancels | `agent_command_cancelled` | owner | `verified` |
| refused (auth ok but not allowed: unknown agent, unbound, duplicate, disabled adapter) | `agent_command_refused` | owner | `failed` |
| binding changed | `agent_binding_changed` | owner | `verified` |

Every receipt: `related_object_type="agent_command"` (or `"agent"`),
`related_object_id`, `parent_receipt_id` = previous receipt of that command,
`correlation_id` = the origin receipt, `before_state` / `after_state`,
`authority` (`owner_only`), `next_state`. `source` uses existing
`TaskSource` values (`staff` for the owner, `system` for the adapter) — no new
literal. Per the receipt law, an agent saying "done" is never recorded as
verified completion.

## 6. API (all under `/api/agent-control`, owner only)

| Method | Path | Purpose |
|---|---|---|
| GET | `/agents` | registry + live adapter status |
| GET | `/agents/{agent_id}` | one agent, recent commands |
| PUT | `/agents/{agent_id}/binding` | choose a configured binding / set session_ref text (receipt) |
| POST | `/commands` | issue `{client_command_id, target_agent_id, instruction, parent_command_id?, based_on_integration_sha?}` |
| GET | `/commands?agent_id=` | command list |
| GET | `/commands/{command_id}` | command + its receipt chain |
| POST | `/commands/{command_id}/complete` | owner records the outcome (verified) |
| POST | `/commands/{command_id}/cancel` | cancel if not yet delivered |
| GET | `/agents/{agent_id}/events` | adapter events (mock: test responses; tmux: last N lines, Phase 2) |

Not provided, by design: any endpoint that takes a shell command, file path,
session name, pane id or executable.

## 7. Security model

- **Owner only** (`deps.require_owner`). `admin` in this codebase is the
  clinical admin tier; directing coding agents is a system-owner function.
  (Decision for Michael: allow `admin` too?)
- **Feature flag** `CAOSCARE_AGENT_CONTROL_ENABLED` (default off). Off →
  every route returns 404. Production/Linode stays off; there are no local
  agents there.
- **No public exposure**: no `/public` route; anonymous → 401; staff/front desk → 403.
- **Command injection**: adapters call `subprocess` with an argument list,
  never a shell. tmux delivery (Phase 2) = `tmux load-buffer -` (instruction
  on stdin) + `tmux paste-buffer -p -t <configured target>` + `send-keys Enter`,
  so text is pasted literally, never interpreted as key names or shell.
- **Forged agent identity**: the target comes from the registry + server
  binding; acknowledgements/completions from agents need a per-agent token
  (Phase 2; Phase 1 has no agent write-back except the mock).
- **Replay**: unique `client_command_id`; duplicates → 409 + refusal receipt.
- **Cross-session delivery**: one binding → one target; the browser cannot
  name a target.
- **Terminal content leakage** (Phase 2 tmux capture): only on explicit
  owner request, last 200 lines max, never stored in receipts, shown only to
  the owner; Claude session `.key` files and sockets are never read.
- **Rate limit**: max 10 commands/minute/owner.
- **Input**: instruction 1–4000 chars, NUL and other control characters
  except `\n`/`\t` rejected.

## 8. Remote access ("from anywhere")

Not built in Phase 1. EliteDesk `:3000` is reachable only on the LAN. Options
for Michael to decide later: (a) Tailscale on the EliteDesk + phone;
(b) Linode relay where the EliteDesk polls outbound for queued commands (no
inbound ports at home). Both touch infrastructure outside this lane. Linode
deployment is out of scope.

## 9. UI

`/admin?tab=agent-operations`, owner-only tab (added inside the existing
`user?.role === "owner"` group in `adminTabGroups.js`).

- Agent table: name, role, status (ONLINE/WORKING/WAITING/BLOCKED/OFFLINE/UNKNOWN,
  with adapter kind and "simulated" badge for mock), current task, branch,
  last activity, last receipt, last message.
- Command box: target selector (defaults to coordinator), instruction, send.
- Command list with status; click → receipt chain (reuses the receipt-trace
  idea from Live Operations).
- Refresh button; poll every 5 s while the tab is open.

## 10. Files (Phase 1)

New:
```
backend/agent_control/__init__.py
backend/agent_control/models.py          pydantic models, seed list
backend/agent_control/registry.py
backend/agent_control/commands.py        service + receipts
backend/agent_control/supervisor.py
backend/agent_control/adapters/__init__.py
backend/agent_control/adapters/base.py
backend/agent_control/adapters/mock.py
backend/routes/agent_control.py
backend/tests/test_agent_control.py
frontend/src/pages/AgentOperations.jsx
frontend/src/components/agentOps/AgentTable.jsx
frontend/src/components/agentOps/CommandComposer.jsx
frontend/src/components/agentOps/CommandTrace.jsx
frontend/src/lib/agentOps.js
frontend/src/lib/__tests__/agentOps.test.js
```
Shared files touched (small, flagged): `backend/server.py` (+2, router),
`frontend/src/pages/Admin.jsx` (+2, import + TabsContent),
`frontend/src/lib/adminTabGroups.js` (+1), `docs/PROJECT_STATE.md`,
`docs/REPO_MAP.md`. No change to `models.py`, `receipts.py`,
`actor_context.py`, task/request modules.

Phase 1b (optional, after Phase 1 acceptance):
`backend/agent_control/adapters/claude_registry.py` — read-only status from
`~/.claude/sessions/*.json`, fields `name,status,updatedAt,cwd` only.

## 11. Tests

Backend (`scripts/run_backend_tests.sh`, flag on in the test env):
1. anonymous → 401; staff, front desk, admin → 403 (unless Michael allows admin); owner → 200.
2. flag off → 404 on every route.
3. unknown / unbound agent → refusal receipt, nothing queued.
4. body fields `issued_by`, `status`, `target`, `session_ref`-as-target are ignored or rejected.
5. duplicate `client_command_id` → 409 + refusal receipt, one command.
6. mock lifecycle: queued → delivered → acknowledged → completed; 4 receipts,
   parent chain unbroken to origin, one correlation id, status_log append-only.
7. mock delivery failure → `failed` receipt with reason.
8. instruction limits / control characters rejected.
9. no route accepts a path, shell, session name or executable (route table check).
10. owner completion is `verified`; agent self-report is `unverified`.

Frontend: `agentOps.test.js` (status labels, UNKNOWN when unbound, trace
ordering by parent link) + `CI=true` build. Browser: owner sends a command to
the mock agent and sees the receipt chain; staff user cannot see the tab.

## 12. Smallest vertical slice

Mock adapter only. Registry seeded with six agents, all OFFLINE/UNKNOWN except
one configured test agent `claude-test-mock` bound to the mock adapter. Owner
sends a command → mock delivers and replies → four receipts visible in the
UI. No real Claude session is touched.

Phase 2 (separate authorization): install tmux (needs sudo — Michael), start
ONE new disposable Claude worker inside tmux session `caos-agents`, bind it,
deliver one command, capture its reply. Existing workers are migrated only
when Michael restarts them himself, using this procedure:

```
tmux new-session -d -s caos-agents -n <agent-id> -c <worktree> 'claude'
# owner binds <agent-id> → tmux target caos-agents:<agent-id> in bindings.yaml
```

## 13. Collision analysis (open PRs, 2026-10-05)

| PR | Files | Overlap |
|---|---|---|
| #59 | — | already merged into integration (`31f5c03`), this branch is based on it |
| #63 RF bridge backoff | `android-bridge/*`, PROJECT_STATE, REPO_MAP | docs append only |
| #64 aria-session auth | `realtime.py`, realtime frontend libs, `AriaVoice.jsx` | none |
| #46 wake research | `firmware/voice-pe-aria/*`, PROJECT_STATE, REPO_MAP | docs append only |

Only append-only log files can conflict; resolved by keeping both sides.

## 14. Open decisions for Michael

1. Owner only, or owner + admin?
2. Phase 1 = mock slice only (recommended), then Phase 1b read-only status?
3. Phase 2: install tmux and start a disposable test worker?
4. Remote access route (Tailscale vs Linode relay) — later.
5. Which Claude session is which agent (session_ref binding)?

## 15. First slice — as built (2026-10-06)

Chain proven: registered test agent `claude-test-mock` (mock adapter) → one
command → `agent_command_issued` (owner, authenticated, verified) →
`agent_command_delivered` (system, simulated) → `agent_command_acknowledged`
(agent self-report, simulated, never verified). Receipts chain by
`parent_receipt_id`, share one `correlation_id`, before = previous after;
`status_log` entries carry their receipt ids.

Files (all new, this lane only):
```
backend/agent_control/__init__.py, models.py, registry.py, commands.py
backend/agent_control/adapters/__init__.py, base.py, mock.py
backend/routes/agent_control.py          (router, not mounted)
backend/tests/test_agent_control.py      (in-process app, scratch DB)
```
Built: `GET /agents`, `GET /agents/{id}`, `POST /commands`, `GET /commands`,
`GET /commands/{id}` (with receipt chain). Not built yet: binding changes,
owner complete/cancel, events, rate limit, frontend tab.

Tests: `test_agent_control.py` 9 passed (access control incl. admin/staff/
front desk 403, flag off → 404, unbound agents offline with UNKNOWN fields,
the receipt chain, replay 409 + refusal receipt, unknown/unbound target
refusal receipts, instruction validation, delivery failure receipt, no route
takes a target/path/shell). Mutation check: breaking the self-report label,
owner check, feature flag or replay index each fails one test. Full backend
gate on this branch (port 8079, throwaway DB, no OpenAI key): 277 passed,
0 failed, 31 skipped.

### Shared-core requests (this lane does not edit shared files)

- **SCR-ACP-1** — mount the router: `backend/server.py` +2 lines
  (`from routes import agent_control as agent_control_routes`;
  `api.include_router(agent_control_routes.router)`). Safe everywhere because
  every route is 404 unless `CAOSCARE_AGENT_CONTROL_ENABLED` is set.
- **SCR-ACP-2** — admin tab (after the frontend page exists): `Admin.jsx` +2,
  `adminTabGroups.js` +1 inside the owner-only group.
- **SCR-ACP-3** — Receipt `related_object_type` gains the values
  `agent_command` / `agent` (free-text field today; no model change needed,
  recorded for the contract).
- PROJECT_STATE / REPO_MAP entries: left to the coordinator at merge, per the
  "do not edit shared Pilot 1 files" constraint for this lane.

## 16. Agent Operations page + read-only discovery — as built (2026-10-06)

Decisions applied (Michael, via the coordinator, 2026-10-06): owner only; no tmux; the six real agents
stay OFFLINE/UNKNOWN until verified; command delivery stays mock-only.

**Frontend (new files only, not mounted):** `pages/AgentOperations.jsx`; `components/agentOps/`
(`AgentTable`, `CommandComposer`, `CommandHistory`, `ReceiptChainDialog`, `LiveSessionsPanel`,
`StatusBadge`); `lib/agentOps.js` (+ test). It shows each agent's id/name, role, status, current task,
branch, last activity and last receipt, plus recent commands with replies. Controls: choose an agent,
enter a command, submit, inspect the receipt chain, refresh. Unknown values show UNKNOWN, and an agent
that is not bound to an adapter cannot be sent anything. Receipt ordering reuses `lib/simulator.js`'s
`orderChain`.

**Read-only discovery:** `backend/agent_control/discovery.py` + `GET /agent-control/sessions` (owner only).
- It reads Claude Code's own registry `~/.claude/sessions/*.json` (allow-listed fields only) and `/proc/<pid>`.
- It reads the git branch only when the session's start directory is a checkout.
- It never reads `*.key` files, sockets or transcripts, and never writes to or signals a process.
- The registry's `procStart` must equal `/proc/<pid>/stat` start time, so a reused pid is not mistaken for the session.
- When two live processes resume one session id, the page says so.

**Browser check (headless Chrome, isolated stack: mount patch applied in a scratch worktree, backend
:8098, frontend :3014, scratch DB; all stopped and dropped afterwards):**
- The owner saw 7 agents: six OFFLINE/UNKNOWN, and the mock ONLINE + SIMULATED.
- A command to the mock was sent; the history showed ACKNOWLEDGED and the mock's reply.
- The receipt chain showed issued VERIFIED → delivered SIMULATED → acknowledged SIMULATED, with parent links and before/after states.
- With an unbound agent selected, Send was disabled and a "not connected" notice was shown.
- At 390 px there was no page overflow.
- The admin role saw neither the tab nor the page.
- The 8 live sessions were listed read-only.

### Runtime snapshot discipline

Live PIDs, PTYs, Claude session names and proposed bindings are **runtime evidence**, not canonical design. They belong in dated PROJECT_STATE entries or PR comments and must be re-read from the host before use. The discovery method remains: allow-listed Claude registry fields plus /proc liveness; never keys, sockets or transcripts.

The 2026-10-06 host snapshot was intentionally removed from this design document during the 2026-10-07 foreman upgrade. Do not infer a current binding from historical PID/session data.

## 17. Live command delivery — adapter comparison

| Path | Works for the EXISTING sessions without restarting them? | Risk | Verdict |
|---|---|---|---|
| **tmux** (`send-keys` / `paste-buffer`) | No. A session must be started inside tmux, and none is (tmux isn't installed). | Typing into an interactive TUI races with permission prompts and approvals; output only by screen scraping | Later, for new workers only; not primary |
| **PTY / process control** (TIOCSTI, writing to `/dev/pts/N`, ptrace / reptyr) | No. `dev.tty.legacy_tiocsti = 0` (kernel blocks input injection); writing to a pts writes *output*, not input; ptrace/reptyr hijack the process | High: can corrupt a live worker | **Rejected** |
| **Claude Agent SDK** | No. It starts its own managed agent processes; `--resume` of a session that is open interactively makes two writers on one transcript (already seen: db41a1a3) | Low for new workers | **Recommended for new workers** (structured messages, real session ids, no scraping) |
| **Claude Code peer messaging** (the documented `ListAgents` / `SendMessage` tools between local sessions) | **Yes.** Every live session already advertises it (`peerProtocol: 1`). The message arrives as a normal incoming message; the recipient acts under its own permissions | Low; no keystroke injection, no restart. The relay must forward verbatim (checked by hash); the reply is a self-report (unverified) | **Recommended for the existing sessions** |
| **Remote MCP / terminal connector** | Only via one of the above | Adds a network surface | Later, as the Aria/ChatGPT access layer over the control API, not as a delivery path |

**Recommendation for the existing live sessions: a peer-message relay adapter.**
```
Owner → POST /agent-control/commands (receipt: issued)
  → command queued for a binding of kind "peer_relay"
  → relay: a dedicated new Claude Code session (started by Michael, its own worktree, no repo write work)
      polls GET /agent-control/relay/next   (relay credential, owner-issued, revocable)
      re-checks the binding: name + pid:procStart still alive in discovery
      SendMessage(to=<bound session name>, message=<instruction verbatim>)
      POST /agent-control/relay/{command_id}/delivered {sha256(text), tool result}   (receipt: delivered)
  → the agent replies to the relay via SendMessage
      POST /agent-control/relay/{command_id}/reply {text}   (receipt: acknowledged/completed, UNVERIFIED)
```
The CAOSCare backend never reads Claude Code's keys or sockets. Only a Claude Code session uses its own
documented tool. The relay is an LLM in the loop, so its instructions forbid rewording, and the
delivery receipt carries a hash of the exact text it sent, compared against the queued instruction.

## 18. Exact next step before ONE real Claude can receive a command

1. **Michael confirms one binding.** Suggested first target: `claude-6-security` → `caoscare-1-72`
   (idle, bounded lane). Also: confirm that `caoscare-1-97` (stale twin of the coordinator) can be closed.
2. **Coordinator applies SCR-ACP-1/2.** The patch `docs/patches/agent-control-mount.patch` (server.py +2,
   Admin.jsx +2, adminTabGroups.js +4/−1) was checked in a scratch worktree. Then set
   `CAOSCARE_AGENT_CONTROL_ENABLED=1` on the EliteDesk backend only and restart it (never Linode).
3. **Authorize the `peer_relay` adapter slice.** It needs `relay/next`, `relay/{id}/delivered`, `relay/{id}/reply`;
   a relay credential; and binding-time liveness re-check with `pid:procStart`. Tests use mock discovery.
4. **Michael starts one relay Claude session.** It is a new process, so no existing session is touched.
5. **Send one harmless command:** "Reply with your agent id and current branch." Accept only if all four
   hold: issued, delivered (hash matches), and reply receipts exist; the reply text matches what the agent
   shows in its own terminal.

Until step 3 is authorized, no live session receives anything.

## 19. Updated shared-core requests

- **SCR-ACP-1/2** — apply `docs/patches/agent-control-mount.patch` (exact diff, 3 files).
- **SCR-ACP-3** — Receipt `related_object_type` values `agent_command` / `agent` (no model change).
- **SCR-ACP-4** — EliteDesk-only env `CAOSCARE_AGENT_CONTROL_ENABLED=1` (and later
  `CAOSCARE_CLAUDE_SESSIONS_DIR` if the backend ever runs as another user). Never set on Linode.


## 20. 2026-10-07 autonomous foreman directive

Michael authorized the persistent-team operating model in `docs/CAOSCARE_AGENT_FOREMAN.md`.

This **extends** the existing control plane; it does not create a second queue. The authoritative work sources remain `PILOT1_READY_QUEUE.md`, `PILOT1_ACTIVE_WORK.md`, `PILOT1_EXECUTION_CHECKLIST.md` and `PROJECT_STATE.md`.

New dedicated Claude sessions may be launched under tmux using `scripts/caos-agent-team`. Existing historical interactive sessions are not hijacked or injected into. The dedicated team is expected to survive SSH disconnects; reboot recovery is documented and requires host-side prerequisites.

The Agent Operations API/UI remains owner-only and EliteDesk-only. Production/Linode stays disabled. The foreman loop may coordinate workers and queue state, but external deployments, spending, resident/customer contact and protected merges remain separately governed.

# Resident Aria core — current-state capture and proposal (careops-resident-aria-core-reconciliation-001, step 1–3)

Read-only capture, 2026-10-12 ~00:45 CDT. No listener restart, no paid call, no configuration change. Voice is recorded as PARKED in `docs/CURRENT_PRIORITY.md` (owner, 2026-10-10); this capture follows the supervisor's 2026-10-12 directive (#129 comment 6118421076) that reopens the conversation side on Michael's latest observation. Implementation beyond offline preparation waits for Michael's confirmation.

## 1. What Room 214 runs right now

| Item | Value | Source |
|---|---|---|
| Room page | production build from 2026-10-09 20:14 (`main.18cb3cf4.js`), served by `aria-wake-page.service` on :3002 → backend :8092 | build dir timestamp; service log |
| Wake listener | `aria-wake.service`, running since 2026-10-08 21:02; settings unchanged | systemd |
| Backend | dev :8092, runtime commit `198fee4` (pid 1213230) | restart receipt |
| Realtime model | `gpt-realtime` (code default; `OPENAI_REALTIME_MODEL` not set in `.env` or the running process) | `routes/realtime.py:38`, process env |
| Voice | default `shimmer`; allowed list `alloy, ash, ballad, coral, echo, sage, shimmer, verse` | `routes/realtime.py:64-65` |
| Resident identity | kiosk `kio_dc8c06a19608` pinned to `res_2425767f4a51` (Room 214 home test identity) | `db.kiosks` |
| Resident prompt | 20,610 chars, sha256/12 `4aaa94880297` (built offline for that resident) | `_build_companion_instructions` |
| Resident tools | 29, including `research_topic`, schedule, menu, requests, transport, room devices, `end_call` | `_build_tools()` |
| Live research | **off** (`CAOSCARE_RESEARCH_PROVIDER` unset → `none`); `research_topic` answers from general knowledge and says so | `live_research_enabled()` = False |
| Owner `/aria` tools | 3: `request_staff_help`, `check_request_status`, `end_conversation` | `_build_aria_tools()` |
| Cross-session continuity | resident sessions: up to 3 sessions within 18 h (`aria_continuity.py`); owner `/aria`: **not used** | code |
| Phone calling | SIP/Asterisk sideband exists (`phone_aria*.py`: transfer to front desk, call approved family) but **not installed or configured**; not reachable from a room voice session | code; no Asterisk on host |
| Latest Room 214 sessions | `rt_cbngaruf…` (2026-10-11 21:08Z, 7 turns), `rt_nr04pf1j…` (16:42Z, 9), `rt_qhkfp0f8…` (15:24Z, 5) | `db.conversations` |

## 2. Gaps against the owner's experience contract

1. **Live lookup**: built (RQ-047, Responses API web search, citations, `live` flag) but switched off. It needs a model choice, a smoke call and a budget — owner decisions (`docs/OWNER_APPROVALS_RESEARCH_AND_AB.md`).
2. **Michael's own Aria is thin**: 3 tools, no continuity, no live lookup, no room/schedule/menu tools. The resident build has all of those; the owner build was never brought up to it.
3. **Short-interval continuity**: exists for residents (needs live acceptance: speak, pause ~2 min, return). Missing for the owner build.
4. **Calls from a room conversation**: no tool. The phone lifecycle (call records, receipts, approved contacts) exists only for inbound SIP calls; outbound needs Asterisk, an ATA/handset and a trunk (owner purchases and accounts).
5. **Personality / naturalness**: the prompt exists; Michael's firsthand judgement says it is bland. Only a firsthand session can accept this.
6. **Voice**: the allowed list predates the voices OpenAI introduced with `gpt-realtime` (reported as more expressive, e.g. "marin", "cedar") — **to verify against the provider's current docs before use**.

## 3. Smallest architecture that meets the contract (proposal, not built)

- Keep one Realtime session per conversation as the voice front end (no second assistant). Upgrade the voice and, if the provider's current docs support it, move to the newest expressive realtime model — chosen by quality first per the owner's 2026-10-12 priority, verified with one approved test call.
- Keep delegated work behind tools: live lookup through the existing `/research` (Responses API web search, citations, `live:true` only with a search and a citation); requests, schedule, menu, transport, devices through the existing canonical routes.
- One experience contract for both builds: the owner `/aria` session reuses the resident context layers (continuity, operational state, profile/memory) and tool catalogue, minus resident-only safety tools, instead of its own thin copy.
- Calls: one `call_contact` tool that creates a canonical call request through the existing call lifecycle (approved contacts only, front desk), and speaks only from real call-state receipts ("calling isn't set up here yet" until Asterisk exists).

## 4. What needs Michael

| Decision | Why |
|---|---|
| Confirm voice/conversation work is un-parked | `CURRENT_PRIORITY.md` still says PARKED |
| Research model, one smoke call, budget | enables live lookup (paid) |
| Realtime model/voice change and one test call on Room 214 | changes the live room (paid) |
| Asterisk host, ATA/handset, trunk account | outbound calls |

## 5. Offline preparation possible without those decisions
- Bring the owner `/aria` build onto the resident context layers and tool catalogue (code + tests, no live switch).
- Add the `call_contact` tool on the existing call lifecycle with an honest "not set up" result until telephony exists.
- Add the newer voices to the allowed list once verified, without changing the default.

## 6. Michael-facing (`/aria`) versus resident Aria — discrepancy list (code, 2026-10-12)

| Layer | Resident session (`realtime_resident_session.py` + `realtime_companion_prompt.py`) | Michael's `/aria` (`realtime.py::_build_aria_instructions`) |
|---|---|---|
| Self-knowledge + truth rules (no invented lookups, actions only from tool results) | yes (`_system_self_knowledge`, `TRUTH_INVARIANTS`, research line) | no |
| Profile / durable memory | resident profile + two-bin memory | operator memory (`aria_memories`), written only by manual CRUD — no automatic extraction |
| Short-interval continuity (≤3 sessions, 18 h) | yes (`resolve_continuity`) | **no** |
| Current operations state (open requests/alerts) | yes (`resolve_operational_state`) | no |
| This-call state (reconnect) | yes (`resolve_conversation_state`) | no |
| Learned speech patterns | yes (`list_patterns`) | no |
| Persona wording | warm companion persona | developer-assistant persona that says it "will eventually have memory, tools, Home Assistant control" — i.e. tells itself it is limited |
| Tools | 29 (room, schedule, menu, requests, transport, research, time, weather, end_call…) | 3 (`request_staff_help`, `check_request_status`, `end_conversation`) |
| Model / voice | `gpt-realtime` / `shimmer` | same |
| Live research | tool present, provider off | not present |
| Calls | none from a voice session | none |

## 7. Bounded implementation plan (code preparation; nothing switched on live)

Each step is its own commit with tests; none restarts the listener; none changes Room 214 until a separate owner receipt. The dev backend at :8092 also serves Room 214, so **no step is loaded there** until Michael approves; code is merged behind defaults that keep today's behaviour.

1. **Owner build onto the shared context layers** — `_build_aria_instructions` gains the self-knowledge, truth rules, continuity (keyed by the owner's own sessions), and drops the "will eventually have" limitation text. Guarded by `CAOSCARE_ARIA_OWNER_V2=1` (default off). Tests: prompt contains continuity of a seeded prior session; truth rules present; flag off = byte-identical to today.
2. **Owner tool parity** — owner sessions get the read-only resident tools (time, weather, schedule, menu, request status/history, research) behind the same flag; no room-device tools (the owner session is not bound to a room). Tests: tool list with flag on/off.
3. **Voices** — after checking the provider's current documentation, add the newer voices to `ALLOWED_VOICES` without changing `DEFAULT_VOICE`. Test: default unchanged.
4. **`call_contact` tool** — resident and owner: creates a canonical call request on the existing call lifecycle for the front desk or an approved family contact; until telephony exists it returns `ok:false` "calling isn't set up here yet" and writes a refusal receipt. Tests: unapproved contact refused, no fake "calling" text.
5. **Live lookup** — no code needed; turned on only by the owner-approved env (`CAOSCARE_RESEARCH_PROVIDER=openai_web_search`, `OPENAI_RESEARCH_MODEL`) after the approved smoke call.

## 8. Exact rollback
- Steps 1–2: unset `CAOSCARE_ARIA_OWNER_V2` (or leave it unset) and restart the dev backend with `scripts/restart_dev_backend.sh`; behaviour returns to today's.
- Step 3: the default voice never changes; removing the new names from `ALLOWED_VOICES` is a one-line revert.
- Step 4: the tool only refuses until telephony exists; `git revert <commit>` + restart removes it.
- Step 5: set `CAOSCARE_RESEARCH_PROVIDER=none` and restart (`docs/RESEARCH_PROVIDER.md`).
- Room page: untouched by all steps; if ever rebuilt, `ctl.sh` keeps `build.prev` (`mv build build.bad && mv build.prev build`, `ctl.sh restart-page`).

## 9. Code preparation done (2026-10-12, all default-off)

| Step | What | Setting (default) | Commit |
|---|---|---|---|
| Continuity on a quick return | when the last session ended within N minutes, Aria may pick the thread up naturally from what was actually said | `CAOSCARE_CONTINUITY_RECENT_MINUTES` (0 = off) | `50a659b` |
| Michael's `/aria` on the shared layers | truth rules, continuity from `db.aria_conversations` (same resolver, no copy), read-only tools (time, weather, research, activities, menu), facility context; the "will eventually have…" limitation text removed | `CAOSCARE_ARIA_OWNER_V2` (off) | `50a659b` |
| `call_contact` | front desk or an approved family contact (allow_calls + phone); answers "calling isn't set up here yet" with a refusal receipt; never creates a call record; unapproved → not approved; needs a live session or the owner | `CAOSCARE_CALL_TOOL` (off) | `50a659b` |
| Voices | `marin`, `cedar` allowed; default stays `shimmer` | — | this commit |

Verified on the dev backend restarted at `50a659b` with no flags set: Room 214 gets 29 tools, no `call_contact`, and the continuity block is unchanged. Tests: backend gate 586 passed / 0 failed / 31 skipped; frontend 87 suites / 624; new tests `test_continuity_recent_return.py`, `test_aria_owner_v2.py`, `test_room_call_request.py`, `test_realtime_voices.py`, `realtimeCallTool.test.js`.

## 10. Provider evidence (checked 2026-10-12) and recommendation — not applied

From the provider's changelog and Realtime guide:
- Realtime models released after the room's `gpt-realtime`: `gpt-realtime-1.5` (2026-02-23), `gpt-realtime-2` (2026-05-07), **`gpt-realtime-2.1`** and `gpt-realtime-2.1-mini` (2026-07-06; improved alphanumerics, silence/noise handling and interruptions).
- **`gpt-live-1`** (generally available 2026-09-10): full-duplex voice, $0.05 per minute billed per second, on a different endpoint (`v1/live/sessions`) — an architecture change, not a setting.
- Voices: `alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar`; "For best quality, we recommend using `marin` or `cedar`."
- **Risk found:** `gpt-4o-transcribe` (the room's speech-to-text model) is announced for shutdown on **2027-02-26**; replacements `gpt-transcribe` / `gpt-live-transcribe` (2026-07-28).

Recommendation for Michael's decision (quality first, smallest change): **`gpt-realtime-2.1` with `marin` (or `cedar`)** on the existing Realtime path — one setting change each (`OPENAI_REALTIME_MODEL`, the session voice), same endpoint, same tools — verified by one approved test call. `gpt-live-1` is the next option if 2.1 still feels stiff, but it needs a new session path and its own build. Plan the transcription-model move before February 2027.

Rollback for the recommendation: unset `OPENAI_REALTIME_MODEL` (back to `gpt-realtime`) and keep `shimmer`; restart with `scripts/restart_dev_backend.sh`.

Sources: provider changelog (developers.openai.com/api/docs/changelog); Realtime conversations guide (developers.openai.com/api/docs/guides/realtime-conversations).

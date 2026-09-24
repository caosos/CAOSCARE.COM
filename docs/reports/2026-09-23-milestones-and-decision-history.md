# CAOSCare milestones and decision history (to 2026-09-23)

**Purpose.** A concise engineering record so a future engineer or agent can
answer "what is CAOSCare now, why is it built this way, what was tried and
superseded, what is physically proven, what is only experimental, what is
broken, and what must not be reintroduced" without Michael's chat history.

**Sources.** `git log origin/main --first-parent` plus branch
`aria/wake-word-proof`, and the dated entries in `docs/PROJECT_STATE.md`
(append-only; the detailed record for everything below). This report is a
navigational summary, not a replacement: each row points at its evidence.
Where a rationale is not recorded anywhere, it is marked **rationale
unrecorded** rather than reconstructed.

**Status vocabulary** (used throughout):
`RATIFIED` (Michael-directed architecture/requirement) · `IMPLEMENTED`
(in code) · `PHYSICALLY VERIFIED` (real hardware, real room) ·
`EXPERIMENTAL` (under evaluation) · `PLANNED` · `SUPERSEDED` ·
`DEBT` (known technical debt).

Canonical durable truth remains `docs/CAOSCARE_PRODUCT_BASELINE.md`; current
build state remains `docs/PROJECT_STATE.md`.

---

## 1. Chronological milestones

Trivial commits are grouped under the milestone they served.

| Date | Commit(s) | Capability / change | Recorded reason | Verification evidence | Resulting limitation / next step |
|---|---|---|---|---|---|
| 2026-04-17 → 04-29 | `eec94db` … (~65 `auto-commit` commits) | Initial app scaffold generated on the Emergent platform: FastAPI + Mongo backend, React frontend, Android surfaces | rationale unrecorded (platform-generated) | none recorded | Emergent branding/auth/tooling later removed (below) |
| 2026-05-02 → 05-17 | `6d97c4e`, `36c28f7`, `0e909bc`, PRs #3–#13 (`cf2537a`, `a0d80ba`, `1528744`…) | Repo map, facility-operations/memory/room-privacy contracts; Emergent branding + visual-edit tooling removed; owner bootstrap script; public registration locked to staff; deployment-prep docs | Make the repo self-owned and deployable; stop public owner self-registration | PR merges; docs | Google auth still Emergent-relayed |
| 2026-06-10 → 06-14 | `3e47c14`, `aeb5903`, `b5f84f1` | Direct Google Sign-In (Google token verification in `auth.py`), replacing Emergent auth; first local prototype on a Lenovo laptop | Remove Emergent dependency | Browser sign-in verified end-to-end (PROJECT_STATE 2026-06-14) | Some docs kept saying OAuth "not implemented" (**stale — see §5**) |
| 2026-07-28 | (no code; env only) | `caoscare-1` host stood up; owner bootstrapped; password login verified | New dedicated node | PROJECT_STATE 2026-07-28 | Dev processes, not services |
| 2026-08-02 | `fde20d8`, `c9c5f0f`, `6b9445e`, `8c4bddb`, `f9987aa` | EliteDesk node build: Home Assistant OS VM on libvirt; Aria voice-first directive; Aria's own Realtime session; **"Aria" set as the three-syllable wake word requirement**; capability portfolio | Terminal 3/5/5A directives | HA onboarding page reachable; session mint verified | Wake word not built; voice untested live |
| 2026-08-09 | `51b23de`, `6d6d9ad`, `f1f9620`, `bb04004`, `4878047`, `229280b`, `3a4bd7f` | **Realtime (WebRTC) becomes the only resident voice path; turn-based STT→chat→TTS retired.** Resident persona unified under the name Aria. Receipt foundation + resident request bus (Terminal 8). `/negotiate` fixed to use the minted session key | Two voice paths with independently drifting prompts caused a real live bug (`docs/ARIA_VOICE_FIRST.md`) | Live acceptance pass recorded; faucet-leak request end-to-end | Aria identity still duplicated across prompt builders (**DEBT**) |
| 2026-08-21 → 08-23 | `fa6b7ac`, `3f18386`, `38f93b0`, lane merges `2a6e661`, `bfbec64` | Transportation engine/calendar, Front Desk role, Resident Record, voice trust/provenance guards, deploy/rollback scripts, admin blueprint, multi-agent lane model | Terminal 9 + Michael acceptance findings | Checkpoint pushed; many live fixes recorded | `semantic_vad` tried and reverted (**§3**) |
| 2026-08-24 → 08-27 | `909da1f`, `371e698`, `27b2121`, docs | Voice config **frozen** after forensic comparison; facility record wired into voice; mock room devices; Home Assistant adapter with read-back; **room audio architecture decision** (one eMeet = one capture/playback endpoint) | Evidence showed split mic/soundbar caused echo; one-device topology performed better | Room 401/403/408 forensics; `docs/ROOM_AUDIO_ARCHITECTURE.md` | TV audio into the AEC path unbuilt |
| 2026-08-28 → 08-31 | `403e5ae`, `6c65021`, `e6c4f47`, `afbb1e0` | TSB-001 (name attribution + unaudited profile write); real Nooelec SDR + Interlogix pendant chain; room lease singleton; TSB-002 (fabricated emergency + periodic RF frame + 60-min zombie session); turn-grounding fixes; production deploys | Live incidents | TSBs + PROJECT_STATE incident entries | TSB-001/002 still OPEN in `docs/tsb/INDEX.md` |
| 2026-09-05 | `4ef11d2` | **Resident voice control of a real Matter bulb** via the generic device contract (HA adapter, read-back verification) | Prove real room control | PHYSICALLY VERIFIED (Room 214 bulb) | Midea AC Matter path unstable (uncommitted, blocked) |
| 2026-09-06 | `d22b3d2`, `b0e3c3e`, `d6cb486`, `d994331` | Real pendant pairing hardening; multi-device `device_id` fix; **Level 1 resident-assistance event model** (ResidentEvent = extended `Alert`); event lifetime decoupled from session lifetime | Pendant break-test | Tests + live Room 214 frames | Pendant path still served by stale `:8000` at 2026-09-22 (§4) |
| 2026-09-07 | `ab3243b`, `3951ef6`, admin-ops commits | Inactivity timer = two-flag silence state machine (fixed a 5-min absolute cutoff); request status current-vs-history; Admin operations console | Room 214 forensics (`rt_mkqn5z8x`) | Tests; live evidence | — |
| 2026-09-08 → 09-10 | `7050710`, `6f0f876`, `a03d5b5`, `b864bfa`, `0c95352`, `12cf89c` | Aria conversation substrate: Layer E (operational state), B (continuity), C (conversation state); Terminal 10 multilingual + interpretation patterns + turn-taking metrics; wake-word **plan** documented | Room 214 conversation evidence | Unit/integration tests | Layers D/F not built |
| 2026-09-13 | `75e1b07` | Five-lane integration merged to `main` (admin-ops, level1 ×2, substrate, baselines) | Consolidate lanes | Fresh-DB backend + frontend gates | Stale lane backends kept running locally (§4) |
| 2026-09-16 → 09-19 | `04d087a`, `4b47646`, `e0438dd`, `7bad624` | Responsive phone/tablet layouts; Room 401 identity contamination repaired (data); idempotent menu/schedule seeds; Room 214 touch brightness | Michael usability + data findings | Deployed + smoke-tested | Name-extraction guard gap (see PROJECT_STATE 09-19) |
| 2026-09-20 | `e092e36`, `ec7b3c5`, `85c2c52`, `9b2f1c4`, `1179a62`, `c0668e5`, `fb216d4` | Resend inbound-email adapter for menu/activities; operational workflow audit; **15 ratified service-layer decisions + GATE** (`docs/ENGINEERING_CONTRACT.md`); Track 1 lanes 1–4 | Audit | Commit messages + tests (lanes not separately logged in PROJECT_STATE — recorded 2026-09-23) | Track 1 lane 5 (seed refresh) and all of Track 2 not done |
| 2026-09-21 | `1f44536` | File-size rule 300–400 lines, relocated to `AGENTS.md` | Michael-directed | Doc grep | Oversized files remain (see `2026-09-23-oversized-files-audit.md`) |
| 2026-09-23 | branch `aria/wake-word-proof`: `12dadd4`, `ab2ef40` | **Local "Aria" wake word → existing Realtime session → real HA light → verified → rest → wake again**; refused-rest silence bug fixed | Resident voice-activation requirement (§2) | **PHYSICALLY VERIFIED** close range, Room 214 (`docs/ARIA_WAKE_WORD_ARCHITECTURE.md`) | Far-field capture; false-wake rate unmeasured; not yet merged to `main` |

---

## 2. Decision chains (how the current architecture came to be)

### 2.1 Resident voice activation
```
tap / pendant only (screen button, RF pendant opens an Alert)
  → requirement: natural voice activation, "Aria" three syllables   RATIFIED 2026-08-02 (8c4bddb)
  → re-elevated as a conversation-parity item                        Terminal 10, 2026-09-10
  → local wake-word architecture documented (plan)                   2026-09-10 (12cf89c)
  → engine evaluation: openWakeWord (no usable "Aria" model) vs
    Porcupine (proprietary) vs sherpa-onnx KWS (no training)         2026-09-23
  → local "Aria" detection built; plan's /activate step corrected    IMPLEMENTED 2026-09-23 (12dadd4)
  → physical Room 214 proof (4 voice-started sessions, light off/on) PHYSICALLY VERIFIED 2026-09-23
  → far-field audio capture identified as the next constraint        OPEN
```
Pronunciation is **"air-ee-uh"**; the two-syllable "Arya" is not a
substitute. The pendant remains the separate safety path.

### 2.2 Resident voice pipeline
```
turn-based STT → text chat → TTS  (drifting separate prompt)   SUPERSEDED 2026-08-09 (51b23de)
  → OpenAI Realtime over WebRTC, browser ↔ OpenAI audio,
    backend mints ephemeral key                               IMPLEMENTED, in daily use
  → semantic_vad + eagerness "low"                            SUPERSEDED (reverted) 2026-08-23 — 38 s dead zone
  → server_vad 0.5 / 300 / 1000 ms + far_field NR            IMPLEMENTED (current)
  → GPT-Live (backend delegation) vs Realtime + sideband      EXPERIMENTAL — decision pending Michael
```

### 2.3 Room hardware
```
wall-mounted / docked resident tablet                SUPERSEDED (Product Baseline §2)
  → room node (EliteDesk) behind TV + eMeet + TV     RATIFIED, ACTIVE
  → split eMeet mic + separate soundbar              SUPERSEDED 2026-08-25 (echo evidence)
  → one eMeet = single capture + playback endpoint   RATIFIED 2026-08-27
  → managed Android phone + dock endpoint            EXPERIMENTAL / UNDER EVALUATION (not ratified, nothing built)
```

### 2.4 Room device control
```
optimistic state at command-queue time           DEBT identified 2026-08-25
  → mock adapter for dev rooms                   IMPLEMENTED 2026-08-27
  → Home Assistant adapter, read-back verified,
    failure = HTTP 502, Aria confirms only verified results
                                                 IMPLEMENTED; PHYSICALLY VERIFIED (lights 2026-09-05, 2026-09-23)
  → HA "changed-list" success check              SUPERSEDED 2026-09-05 (wrong on real Matter hardware)
```
Boundary: Aria → CAOSCare service layer → HA → device → read-back →
CAOSCare state/receipt → Aria (Product Baseline §2). **DEBT:** the browser
still calls the unauthenticated `/devices/public/...` endpoint.

### 2.5 Operational architecture
15 decisions ratified 2026-09-20 (`docs/ENGINEERING_CONTRACT.md`): one
canonical service layer; Aria as an interface, not an authority;
`ActorContext`; simulation provenance; event_log vs receipt boundary;
StaffTask history; legacy-data quarantine; `escalation.py::tick()` as the
sole escalation authority; production scheduling independent of simulation;
Live Board as a read model; plus the no-simulator-writes GATE.
**Ratified, largely not implemented** (Track 2).

---

## 3. Superseded approaches — do NOT reintroduce

| Approach | Why it was superseded | Evidence |
|---|---|---|
| Resident-room tablet / dock as the room interface | Replaced by room node + eMeet + TV | Product Baseline §2 |
| Turn-based STT → chat → TTS resident voice | Separate drifting prompt caused a live bug | `51b23de`, `docs/ARIA_VOICE_FIRST.md` |
| `semantic_vad` with `eagerness: "low"` | 38 s speech-detection dead zone live | `docs/reports/2026-08-23-1345-semantic-vad-failed-experiment.md` |
| Split eMeet mic + separate soundbar | Echo / phantom turns | Rooms 401/403/408 forensics 2026-08-25 |
| A second, TV-side microphone for TV noise | Multiplies AEC paths | `docs/ROOM_AUDIO_ARCHITECTURE.md` |
| Trusting Home Assistant's service-call `changed` list as success | Returns `[]` on real Matter success | PROJECT_STATE 2026-09-05 |
| Fixed 8-second RF press-coalescing window | Created duplicate events; replaced by open-incident check | PROJECT_STATE 2026-08-30 |
| Absolute 5-minute companion timer | Cut off an active conversation mid-song | `ab3243b`, session `rt_mkqn5z8x` |
| `alerts.py::alerts_feed` inline escalation | Ratified to retire in favour of `escalation.tick()` (not yet removed in code) | `docs/ENGINEERING_CONTRACT.md` §8 |
| Wake-word listener calling `POST /realtime/room/{room}/activate` | Would claim the lease and block the page's own session mint | `docs/ARIA_WAKE_WORD_ARCHITECTURE.md` "Correction" |
| 200/400-line and 300-line hard caps | Replaced by the 300–400 heuristic | `AGENTS.md` |

---

## 4. What is physically proven vs only experimental (as of 2026-09-23)

**Physically verified:** EliteDesk room node; eMeet as mic and speaker;
Nooelec SDR + rtl_433 + real Interlogix/Lifeline pendants; OpenAI Realtime
resident conversation; real Home Assistant Matter lights controlled by
voice and touch with read-back; local "Aria" wake word at close range
(~3–4 ft) in Room 214.

**Experimental / under evaluation:** wake-word engine choice (sherpa-onnx
proof vs a future custom openWakeWord model); far-field wake capture;
Android phone + dock endpoint; GPT-Live vs Realtime-with-sideband.

**Known broken or unresolved:** Midea AC Matter session drops (uncommitted
work, blocked); TSB-001/TSB-002 open; `AlertStatus` lacks `"escalated"`;
unauthenticated browser device/request endpoints; Aria identity defined in
four places; wake-word false-wake rate unmeasured; local runtime runs a
stale `:8000` backend for the RF bridge (see `docs/CURRENT_NODE_STATUS.md`).

---

## 5. Contradictions between documentation and code found 2026-09-23

| Document | Claim | Reality |
|---|---|---|
| `docs/REPO_MAP.md` | `frontend/yarn.lock` missing; direct Google OAuth "not implemented"; Emergent Google auth "pending replacement" | `frontend/yarn.lock` committed since 2026-06-14; direct Google verification in `backend/routes/auth.py` + `GoogleSignIn.jsx` since `3e47c14` (2026-06-10). Corrected in place 2026-09-23. |
| `docs/ARIA_WAKE_WORD_ARCHITECTURE.md` (2026-09-10 plan) | `/activate` is the complete activation contract | It only claims the lease; corrected in place 2026-09-23 |
| `docs/ARIA_CONTRACT.md` | Aria's instructions are duplicated between two builders in `realtime.py` | At least four sources: `realtime_companion_prompt.py`, `realtime.py::_build_aria_instructions`, `ai.py::CAOS_SYSTEM_PROMPT` (legacy `/api/ai/chat`), `admin_assistant.py`. Pointer note added; doctrine still to be authored with Michael. |
| `backend/routes/realtime_self_knowledge.py` | "11 voices available" in the voice picker | Code lists 8 Realtime voices; picker offers 11 including three (nova, fable, onyx) the Realtime path silently replaces with shimmer. Not fixed (code). |
| `docs/CURRENT_NODE_STATUS.md` | Backend on `:8000`, frontend nohup, 2026-08-29 snapshot | Runtime moved; reconciled snapshot added 2026-09-23 |
| `frontend/src/pages/AuthCallback.jsx` (+ `lib/auth.jsx` hash check) | Handles a `session_id=` OAuth callback by POSTing `/auth/google/session` | No backend route `/auth/google/session` exists; this is dead legacy Emergent-auth code superseded by `GoogleSignIn.jsx`. Not removed (code change, outside this documentation pass). |
| `docs/tsb/INDEX.md` | TSB-001/002 "documented, not remediated" | Later PROJECT_STATE entries record partial remediation; not changed here (TSB rule requires re-verification) |

No name has been chosen for the phone dock under evaluation; use neutral
terms ("phone dock", "CAOSCare dock") until Michael names it.

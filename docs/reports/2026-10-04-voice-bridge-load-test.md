# Voice bridge load test: 1 to 80 concurrent rooms (2026-10-04)

Branch `spike/voice-bridge`. Machine: the EliteDesk (`caoscare1-hp-elitedesk`),
AMD Ryzen 5 PRO 2400GE (4 cores / 8 threads), 15 GB RAM, local MongoDB 7.
Harness: `backend/loadtest/` (`python -m loadtest.run`). Raw results:
`backend/loadtest/results/*.json`.

## What was and was not tested

- **Real:** the CAOSCare backend and the actual `/api/voice-bridge/turn`
  route over HTTP; real Mongo writes; the real tools, request bus, device
  command path (mock devices), transportation and help-escalation services;
  real receipts. Each room has its own community, apartment, resident,
  Voice PE device id and conversation id.
- **Simulated:** Home Assistant (the harness sends what HA would send after
  speech-to-text), speech-to-text and text-to-speech (latency and concurrency
  limits on the client side, because Home Assistant owns them), and the
  language model (`loadtest/mock_provider.py`: 1.2 s ± 0.4 s per call,
  optional concurrency/RPM limits, outage and slow windows). No paid or
  external provider call was made: the test server runs with every provider
  key blank and the OpenAI base URL pointed at a closed local port.
- **Not tested:** real OpenAI latency, rate limits and token quotas; Home
  Assistant; a physical Voice PE; network between Home Assistant and CAOSCare.
- **Load shape:** all rooms of a level start speaking at the same instant and
  then talk through a 2–4 turn script plus a closing phrase. This is a
  worst-case burst, not normal traffic. The load generator runs on the same
  EliteDesk, so host CPU includes it.

## Test mix per room (`loadtest/scenarios.py`)

Rooms rotate through ten scripts: ordinary conversation, menu, activities,
lighting (on/off), thermostat, maintenance with an immediate HA retry of the
same words and a status question, transportation, staff help (front desk
towels), nursing with a status question, and an emergency ("I fell and I
can't get up") followed by conversation. Every room ends with one of the five
closing phrases. Provider failures, timeouts and rate limits are separate
scenarios (below).

## Changes made to the bridge for this test

The bridge had no capacity limit and no emergency path. Added:

- **Priority classes** (`routes/voice_bridge_admission.py`), decided from the
  resident's words before any model call: 1 emergency, 2 staff help /
  nursing, 3 operational requests, 4 room/device actions, 5 information,
  6 conversation.
- **Emergency fast path:** priority 1 is escalated at once through the
  canonical `ai_escalate` help path (opens/enriches the resident's help event,
  places the nursing dispatch). No language model, no capacity wait. The reply
  says only what the dispatch confirmed. Receipt `voice_emergency_escalated`.
- **Admission control:** `CAOSCARE_VOICE_BRIDGE_MAX_ACTIVE` model slots per
  worker (default 16), of which `CAOSCARE_VOICE_BRIDGE_RESERVED` (default 4)
  only staff help may use. The highest priority waiting is served first. A
  turn that gets no slot within its class's limit (2–6 s) is answered at once,
  "I'm helping a lot of people right now…", with a `voice_turn_deferred`
  receipt; nothing is executed and nothing is dropped.
- **Provider threads:** model calls run on a dedicated thread pool sized to
  the slots. Before this change they shared asyncio's default pool (12
  threads on this machine), which capped concurrent model calls at 12
  regardless of configuration (visible in `levels_w1.json`, run before the
  change).
- **One rate-limit retry:** a 429 from the provider is retried once after
  0.5–1.5 s when the turn budget allows.
- **Room actions on the bridge:** lights, thermostat, transportation and call
  for help, through the same services the room screen uses
  (`devices.execute_room_command` was extracted from the room-screen route so
  both use one path).
- **Per-room community:** a kiosk may name its facility (`Kiosk.facility_id`);
  otherwise the single active facility is used.

## Results by concurrency level

`levels_w1.json` = one worker, 16 slots (before the thread-pool change).
`levels_w2.json` = two workers × 40 slots (8 reserved each), the recommended
configuration.

**levels_w1.json** — workers 1, model slots/worker 16 (reserved 4), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 4 | 0.46 | 1.5/2.6/2.6 | 3.0 | 0 | 0 | 0 | 11.2 | 7.5 | 19.0 | 80 | 1 | 0/0 | 0 | 0 | 1/1 |
| 5 | 14 | 1.42 | 2.3/3.0/3.2 | 3.6 | 0 | 0 | 0 | 15.0 | 11.3 | 21.3 | 81 | 5 | 0/0 | 0 | 0 | 5/5 |
| 10 | 29 | 3.18 | 1.3/2.7/3.1 | 3.4 | 0 | 0 | 0 | 33.6 | 18.6 | 24.6 | 82 | 10 | 0/0 | 0 | 0 | 10/10 |
| 20 | 58 | 5.34 | 1.7/3.0/4.4 | 3.6 | 2 | 0 | 0 | 48.5 | 29.8 | 26.9 | 84 | 20 | 0/0 | 0 | 0 | 20/20 |
| 40 | 116 | 9.68 | 2.0/5.4/6.0 | 6.1 | 24 | 0 | 0 | 74.5 | 33.2 | 33.3 | 87 | 40 | 0/0 | 0 | 0 | 40/40 |
| 80 | 232 | 16.54 | 2.1/5.7/7.9 | 7.4 | 88 | 0 | 0 | 111.0 | 49.8 | 41.3 | 91 | 80 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
   1 rooms ████████ 2.6
   5 rooms █████████ 3.0
  10 rooms ████████ 2.7
  20 rooms █████████ 3.0
  40 rooms ████████████████ 5.4
  80 rooms █████████████████ 5.7
backend CPU p95 (% of one core)
   1 rooms █ 11.2
   5 rooms █ 15.0
  10 rooms ███ 33.6
  20 rooms ████ 48.5
  40 rooms ██████ 74.5
  80 rooms ████████ 111.0
```

**levels_w1.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 1 | - | - | - | - | 3/0/0/2.6 | - | 1/0/0/0.0 | - |
| 5 | - | - | 2/0/0/3.0 | 3/0/0/2.9 | 1/0/0/2.5 | 2/0/0/3.2 | 5/0/0/0.0 | 1/0/0/0.0 |
| 10 | 1/0/0/0.2 | 1/0/0/2.1 | 3/0/0/3.1 | 3/0/0/2.7 | 4/0/0/2.6 | 6/0/0/2.5 | 10/0/0/0.0 | 1/0/0/0.0 |
| 20 | 2/0/0/0.3 | 2/0/0/2.9 | 6/0/0/4.4 | 6/0/0/4.2 | 8/0/0/3.0 | 12/2/0/2.4 | 20/0/0/0.0 | 2/0/0/0.0 |
| 40 | 4/0/0/0.6 | 4/0/0/3.7 | 12/0/0/5.4 | 12/0/0/5.9 | 16/9/0/2.3 | 24/15/0/4.1 | 40/0/0/0.1 | 4/0/0/0.1 |
| 80 | 8/0/0/1.0 | 8/0/0/4.8 | 24/6/0/7.3 | 24/15/0/4.7 | 32/28/0/2.9 | 48/39/0/3.0 | 80/0/0/0.2 | 8/0/0/0.1 |

**levels_w2.json** — workers 2, model slots/worker 40 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 4 | 0.44 | 1.2/2.5/2.5 | 3.2 | 0 | 0 | 0 | 11.5 | 7.4 | 20.1 | 192 | 1 | 0/0 | 0 | 0 | 1/1 |
| 5 | 14 | 1.62 | 2.1/2.9/2.9 | 3.4 | 0 | 0 | 0 | 14.9 | 11.2 | 20.6 | 193 | 5 | 0/0 | 0 | 0 | 5/5 |
| 10 | 29 | 3.01 | 1.3/3.0/3.2 | 3.8 | 0 | 0 | 0 | 29.5 | 18.5 | 36.3 | 195 | 10 | 0/0 | 0 | 0 | 10/10 |
| 20 | 58 | 5.74 | 1.4/2.9/3.3 | 3.6 | 0 | 0 | 0 | 100.6 | 37.2 | 35.4 | 197 | 20 | 0/0 | 0 | 0 | 20/20 |
| 40 | 116 | 11.58 | 1.4/3.0/3.3 | 3.5 | 0 | 0 | 0 | 107.3 | 42.2 | 52.9 | 202 | 40 | 0/0 | 0 | 0 | 40/40 |
| 80 | 232 | 20.95 | 1.6/3.6/5.1 | 4.2 | 0 | 0 | 0 | 179.5 | 88.3 | 57.1 | 210 | 80 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
   1 rooms ████████ 2.5
   5 rooms █████████ 2.9
  10 rooms █████████ 3.0
  20 rooms █████████ 2.9
  40 rooms █████████ 3.0
  80 rooms ███████████ 3.6
backend CPU p95 (% of one core)
   1 rooms █ 11.5
   5 rooms █ 14.9
  10 rooms ██ 29.5
  20 rooms ████████ 100.6
  40 rooms ████████ 107.3
  80 rooms █████████████ 179.5
```

**levels_w2.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 1 | - | - | - | - | 3/0/0/2.5 | - | 1/0/0/0.0 | - |
| 5 | - | - | 2/0/0/2.5 | 3/0/0/2.9 | 1/0/0/2.1 | 2/0/0/2.5 | 5/0/0/0.0 | 1/0/0/0.0 |
| 10 | 1/0/0/0.2 | 1/0/0/2.5 | 3/0/0/3.2 | 3/0/0/2.6 | 4/0/0/2.2 | 6/0/0/2.6 | 10/0/0/0.1 | 1/0/0/0.1 |
| 20 | 2/0/0/0.2 | 2/0/0/2.6 | 6/0/0/3.3 | 6/0/0/2.8 | 8/0/0/2.9 | 12/0/0/2.2 | 20/0/0/0.1 | 2/0/0/0.0 |
| 40 | 4/0/0/0.4 | 4/0/0/3.1 | 12/0/0/3.1 | 12/0/0/3.0 | 16/0/0/3.0 | 24/0/0/2.8 | 40/0/0/0.1 | 4/0/0/0.1 |
| 80 | 8/0/0/0.9 | 8/0/0/3.9 | 24/0/0/4.5 | 24/0/0/4.1 | 32/0/0/2.8 | 48/0/0/2.9 | 80/0/0/0.1 | 8/0/0/0.1 |


Every level: no missing or orphan receipts, no receipt filed under the wrong
resident, no cross-resident leakage (neither in the model's context nor in
any reply), no duplicate workflow (the HA retry was answered once; one open
request per resident per category), every closing phrase closed its session,
every emergency answered (p95 ≤ 1 s at 80 rooms).

Deferrals in `levels_w1` at 20–80 rooms are the 16-slot / 12-thread cap
answering honestly, not failures: emergencies and staff help were never
deferred.

## Finding the limit: worker count and bursts beyond 80

**sweep80_w1_m16.json** — workers 1, model slots/worker 16 (reserved 4), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 80 | 232 | 17.34 | 2.1/5.7/8.2 | 6.8 | 87 | 0 | 0 | 105.1 | 53.6 | 41.3 | 90 | 80 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
  80 rooms █████████████████ 5.7
backend CPU p95 (% of one core)
  80 rooms ████████ 105.1
```

**sweep80_w1_m16.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 80 | 8/0/0/1.1 | 8/0/0/5.3 | 24/4/0/7.9 | 24/13/0/4.7 | 32/30/0/2.7 | 48/40/0/4.0 | 80/0/0/0.1 | 8/0/0/0.1 |

**sweep80_w1_m80.json** — workers 1, model slots/worker 80 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 80 | 232 | 19.6 | 1.7/4.4/4.7 | 5.0 | 0 | 0 | 0 | 114.5 | 65.1 | 44.8 | 96 | 81 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
  80 rooms █████████████ 4.4
backend CPU p95 (% of one core)
  80 rooms █████████ 114.5
```

**sweep80_w1_m80.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 80 | 8/0/0/1.7 | 8/0/0/4.5 | 24/0/0/4.6 | 24/0/0/4.6 | 32/0/0/3.1 | 48/0/0/3.2 | 80/0/0/0.9 | 8/0/0/0.2 |

**sweep80_w2_m40.json** — workers 2, model slots/worker 40 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 80 | 232 | 19.88 | 1.5/3.5/4.8 | 4.1 | 0 | 0 | 0 | 159.0 | 68.8 | 56.3 | 210 | 80 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
  80 rooms ██████████ 3.5
backend CPU p95 (% of one core)
  80 rooms ████████████ 159.0
```

**sweep80_w2_m40.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 80 | 8/0/0/0.9 | 8/0/0/3.8 | 24/0/0/4.4 | 24/0/0/4.3 | 32/0/0/2.9 | 48/0/0/2.9 | 80/0/0/0.1 | 8/0/0/0.1 |

**sweep80_w4_m20.json** — workers 4, model slots/worker 20 (reserved 4), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 80 | 232 | 21.86 | 1.5/3.3/4.5 | 3.8 | 0 | 0 | 0 | 247.1 | 93.8 | 70.3 | 369 | 80 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
  80 rooms ██████████ 3.3
backend CPU p95 (% of one core)
  80 rooms ███████████████████ 247.1
```

**sweep80_w4_m20.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 80 | 8/0/0/0.8 | 8/0/0/3.2 | 24/0/0/3.6 | 24/0/0/4.2 | 32/0/0/2.9 | 48/0/0/3.0 | 80/0/0/0.1 | 8/0/0/0.2 |

**beyond80_w1.json** — workers 1, model slots/worker 160 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | 348 | 16.95 | 3.1/5.8/8.5 | 6.5 | 0 | 0 | 0 | 114.6 | 61.0 | 46.3 | 104 | 120 | 0/0 | 0 | 0 | 120/120 |
| 160 | 464 | 18.96 | 4.9/9.6/11.7 | 10.1 | 0 | 0 | 0 | 119.8 | 74.7 | 48.6 | 112 | 160 | 0/0 | 0 | 0 | 160/160 |

```
first-answer p95 (s)
 120 rooms █████████████████ 5.8
 160 rooms █████████████████████████████ 9.6
backend CPU p95 (% of one core)
 120 rooms █████████ 114.6
 160 rooms █████████ 119.8
```

**beyond80_w1.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 120 | 12/0/0/2.6 | 12/0/0/6.0 | 36/0/0/5.9 | 36/0/0/7.0 | 48/0/0/3.9 | 72/0/0/5.5 | 120/0/0/4.9 | 12/0/0/5.1 |
| 160 | 16/0/0/3.7 | 16/0/0/7.7 | 48/0/0/8.1 | 48/0/0/9.9 | 64/0/0/11.0 | 96/0/0/9.2 | 160/0/0/7.8 | 16/0/0/10.7 |

**beyond80_w2.json** — workers 2, model slots/worker 80 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | 348 | 22.51 | 2.6/5.2/6.9 | 6.0 | 0 | 0 | 0 | 196.9 | 78.1 | 59.5 | 218 | 120 | 0/0 | 0 | 0 | 120/120 |
| 160 | 464 | 23.27 | 3.3/7.6/10.8 | 8.3 | 10 | 0 | 0 | 195.0 | 101.2 | 60.1 | 225 | 160 | 0/0 | 0 | 0 | 160/160 |

```
first-answer p95 (s)
 120 rooms ████████████████ 5.2
 160 rooms ███████████████████████ 7.6
backend CPU p95 (% of one core)
 120 rooms ███████████████ 196.9
 160 rooms ███████████████ 195.0
```

**beyond80_w2.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 120 | 12/0/0/2.3 | 12/0/0/4.7 | 36/0/0/5.1 | 36/0/0/6.0 | 48/0/0/5.1 | 72/0/0/5.2 | 120/0/0/4.2 | 12/0/0/4.0 |
| 160 | 16/0/0/2.4 | 16/0/0/6.1 | 48/0/0/7.0 | 48/0/0/7.6 | 64/2/0/9.0 | 96/8/0/9.0 | 160/0/0/5.7 | 16/0/0/8.2 |

**beyond80_w4.json** — workers 4, model slots/worker 40 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | 348 | 23.08 | 2.4/5.2/7.3 | 5.8 | 0 | 0 | 1 | 253.7 | 99.9 | 65.1 | 378 | 122 | 0/0 | 0 | 0 | 120/120 |
| 160 | 464 | 23.7 | 3.2/7.3/9.9 | 8.0 | 2 | 0 | 1 | 326.7 | 134.3 | 81.8 | 386 | 159 | 0/0 | 0 | 0 | 159/160 |

```
first-answer p95 (s)
 120 rooms ████████████████ 5.2
 160 rooms ██████████████████████ 7.3
backend CPU p95 (% of one core)
 120 rooms ███████████████████ 253.7
 160 rooms █████████████████████████ 326.7
```

**beyond80_w4.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 120 | 12/0/0/1.2 | 12/0/0/4.3 | 36/0/0/4.7 | 36/0/0/6.3 | 48/0/0/5.3 | 72/0/0/5.8 | 120/0/0/4.5 | 12/0/0/4.7 |
| 160 | 16/0/0/1.6 | 16/0/0/4.8 | 48/0/0/5.8 | 48/0/0/7.7 | 64/0/0/9.0 | 96/2/0/7.7 | 160/0/0/5.7 | 16/0/0/9.1 |

**beyond80_w4_rerun160.json** — workers 4, model slots/worker 40 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 160 | 464 | 24.59 | 3.0/7.1/9.4 | 7.7 | 2 | 0 | 1 | 318.0 | 125.7 | 77.1 | 384 | 160 | 0/0 | 0 | 0 | 160/160 |

```
first-answer p95 (s)
 160 rooms █████████████████████ 7.1
backend CPU p95 (% of one core)
 160 rooms ████████████████████████ 318.0
```

**beyond80_w4_rerun160.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 160 | 16/0/0/1.7 | 16/0/0/5.0 | 48/0/0/5.4 | 48/0/0/7.5 | 64/0/0/8.5 | 96/2/0/7.3 | 160/0/0/5.1 | 16/0/0/6.2 |


The one dropped turn (`beyond80_w4.json`, 160 rooms, 4 workers) was a
`ReadError` on an immediate HA retry. It did not recur in three reruns of the
same configuration and the server log showed no error; the cause is
unproven (most likely a keep-alive connection closed by the server as the
client reused it). In production the Home Assistant agent would speak its
fallback for such a turn.

## Saturation, provider failures, speech limits

**Contention notice.** The final runs of `ratelimit_80.json` (00:18) and
`failure_20.json` (00:19) overlapped a wake-word training job from the
firmware lane that started at 00:17:32 and used about 7 of 8 cores (host CPU
p95 100% in both files). Their correctness results stand (no drops, no missing
receipts, honest fallbacks, recovery after the outage), but their latency
figures do not represent the bridge alone. All other runs finished before
00:17:30 with host CPU p95 at or below 82%. Rerun both when the EliteDesk is
otherwise idle.

**saturation_80_m8.json** — workers 1, model slots/worker 8 (reserved 2), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 80 | 232 | 16.63 | 2.1/5.5/8.3 | 6.7 | 110 | 0 | 0 | 103.7 | 50.0 | 26.8 | 88 | 80 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
  80 rooms ████████████████ 5.5
backend CPU p95 (% of one core)
  80 rooms ████████ 103.7
```

**saturation_80_m8.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 80 | 8/0/0/0.9 | 8/0/0/5.9 | 24/16/0/7.4 | 24/15/0/6.1 | 32/31/0/2.5 | 48/48/0/2.5 | 80/0/0/0.1 | 8/0/0/0.2 |

**ratelimit_80.json** — workers 2, model slots/worker 40 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 80 | 232 | 15.77 | 1.4/4.5/6.6 | 5.4 | 0 | 67 | 0 | 135.3 | 50.6 | 100.0 | 208 | 80 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
  80 rooms ██████████████ 4.5
backend CPU p95 (% of one core)
  80 rooms ██████████ 135.3
```

**ratelimit_80.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 80 | 8/0/0/2.0 | 8/0/5/5.0 | 24/0/15/5.5 | 24/0/13/5.5 | 32/0/12/4.3 | 48/0/22/4.4 | 80/0/0/0.2 | 8/0/0/0.1 |

**speech_limits_80.json** — workers 2, model slots/worker 40 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 80 | 232 | 11.66 | 1.2/2.9/3.1 | 6.6 | 0 | 0 | 0 | 107.7 | 45.5 | 24.5 | 202 | 43 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
  80 rooms █████████ 2.9
backend CPU p95 (% of one core)
  80 rooms ████████ 107.7
```

**speech_limits_80.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 80 | 8/0/0/0.2 | 8/0/0/2.9 | 24/0/0/3.0 | 24/0/0/3.1 | 32/0/0/2.8 | 48/0/0/3.1 | 80/0/0/0.1 | 8/0/0/0.1 |

**slowllm_80.json** — workers 2, model slots/worker 40 (reserved 8), simulated model 3000±1000 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 80 | 232 | 9.12 | 3.3/7.7/10.2 | 8.5 | 8 | 0 | 0 | 99.9 | 40.8 | 23.7 | 210 | 80 | 0/0 | 0 | 0 | 80/80 |

```
first-answer p95 (s)
  80 rooms ███████████████████████ 7.7
backend CPU p95 (% of one core)
  80 rooms ███████ 99.9
```

**slowllm_80.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 80 | 8/0/0/0.9 | 8/0/0/8.4 | 24/0/0/9.9 | 24/0/0/9.3 | 32/3/0/7.4 | 48/5/0/7.1 | 80/0/0/0.1 | 8/0/0/6.2 |

**failure_20.json** — workers 2, model slots/worker 40 (reserved 8), simulated model 1200±400 ms

| rooms | turns | turns/s | first answer p50/p95/max s | full response p95 s | deferred | degraded | dropped | app CPU p95 % | mongod CPU p95 % | host CPU p95 % | RSS MB | conns | receipts missing/orphan | leaks | dup workflows | endings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 225 | 5.1 | 0.1/17.3/17.9 | 3.4 | 0 | 78 | 0 | 52.9 | 25.6 | 100.0 | 199 | 20 | 0/0 | 0 | 0 | 20/20 |

```
first-answer p95 (s)
  20 rooms ██████████████████████████████ 17.3
backend CPU p95 (% of one core)
  20 rooms ████ 52.9
```

**failure_20.json** — per priority class (turns / deferred / degraded / first-answer p95 s)

| rooms | emergency | staff_help | operational | room_action | information | conversation | session_end | retry |
|---|---|---|---|---|---|---|---|---|
| 20 | 10/0/0/0.6 | 6/0/2/3.0 | 26/0/17/17.8 | 24/0/15/17.3 | 26/0/15/17.3 | 46/0/29/17.3 | 81/0/0/0.1 | 6/0/0/0.1 |


- **Saturation** (`saturation_80_m8.json`, one worker, 8 slots, 2 reserved,
  80 rooms): all 8 emergencies answered (p95 0.9 s) and all 8 staff-help
  requests served (reserved slots). 110 lower-priority turns were deferred,
  each with an immediate honest reply and a receipt. Conversation never
  blocked help.
- **Provider concurrency limit** (`ratelimit_80.json`, 80 slots against a
  simulated provider limit of 10 concurrent calls per worker): 161 rate-limit
  refusals; after one retry each, 67 turns could not be served and got an
  honest fallback with a `failed` receipt. Emergencies unaffected. Lesson:
  the configured slots must not exceed the provider's concurrency quota.
- **Failure and recovery** (`failure_20.json`, 20 rooms talking for 32 s;
  provider down 4–12 s, ok 12–16 s, slow (no answer) 16–22 s, then ok):
  while down, turns were answered in ~0.1 s with the apology and a `failed`
  receipt; service resumed as soon as the provider returned; while slow,
  turns ended at ~17 s (bridge budget) with the apology, inside Home
  Assistant's 25 s limit. Each slow turn holds a slot for its full budget, so
  a slow provider is the fastest way to exhaust capacity; emergencies bypass
  slots. 0 dropped turns, 0 missing receipts.
- **Speech-to-text / text-to-speech limits** (`speech_limits_80.json`, 8
  concurrent STT and 8 concurrent TTS on the Home Assistant side): bridge
  answers unchanged (p95 2.9 s); the resident-perceived full response grew to
  p95 6.6 s with up to 4 s waiting for TTS. These limits belong to the Home
  Assistant pipeline, not CAOSCare.
- **Slower model** (`slowllm_80.json`, 3 s ± 1 s per call): first answer p95
  7.7 s, 8 low-priority turns deferred.

## EliteDesk bottleneck

1. **One worker's event loop** (one CPU core). A worker saturates at about
   100–120 % CPU from about 40 simultaneous rooms on; latency then grows
   (one worker: p95 5.8 s at 120 rooms, 9.6 s at 160). Per turn the backend
   spends about 0.04 CPU-seconds and MongoDB about 0.016
   (instructions, history, operational state, ingest, receipts).
2. **MongoDB** is second: mongod reached 88 % (80 rooms, two workers) and
   134 % (160 rooms, four workers) of one core.
3. **The model provider**, in production: each model call carries about
   33,000 characters (about 8,000 tokens) of instructions, history and tool
   definitions, and a turn with a tool makes two calls. Provider concurrency
   and tokens-per-minute quotas, not EliteDesk CPU, will be the first limit
   with a real provider, and prompt size drives cost.
Memory is not a constraint: 90 MB per worker; 386 MB with four workers at 160
rooms.

## Safe measured concurrency

With two workers (40 slots each, 8 reserved) and a 1.2 s simulated model, 80
rooms speaking at the same instant were served with no deferrals, drops,
missing receipts, leaks or duplicate work; first answer p95 3.6 s (max
5.1 s), emergencies p95 0.9 s. 120 simultaneous rooms also passed (p95
5.2 s); at 160 some low-priority turns were deferred. **Measured safe burst:
80 simultaneous rooms on this EliteDesk with two workers, with headroom to
about 120, under the simulated provider.** This is not proof for a real
provider: its latency, concurrency quota and token quota were not tested and
must be checked before claiming 80 rooms in production.

## Recommended worker count for 80 rooms

Two uvicorn workers, `CAOSCARE_VOICE_BRIDGE_MAX_ACTIVE=40`,
`CAOSCARE_VOICE_BRIDGE_RESERVED=8` (80 model slots, 16 reserved for staff
help), and a provider concurrency quota of at least 80 concurrent requests
(otherwise lower the slots to the quota). Four workers gave little extra
(p95 3.3 s vs 3.5 s at 80 rooms) for twice the CPU and memory.
Admission state is per worker; Home Assistant's requests are spread across
workers by the OS.

## Capacity estimates (not measured unless stated)

- **Cloud model (primary):** measured EliteDesk cost about 0.055 CPU-seconds
  per turn (backend + MongoDB). If a resident in conversation speaks about
  once every 10 seconds, 80 actively talking rooms are about 8 turns/s;
  the two-worker configuration sustained 21 turns/s in the 80-room burst.
  The binding limits are the provider's: about 80 concurrent requests, and
  tokens. At ~8,000 input tokens per call and about 1.5 calls per turn, 8
  turns/s is about 5–6 million input tokens per minute - beyond many
  accounts' quotas and expensive. In practice far fewer than 80 rooms talk at
  once, but the prompt size should be reduced before relying on 80 active
  rooms. Check the account's limits.
- **Local model on this EliteDesk:** not measured (no local model installed).
  The CPU and integrated GPU here would process an 8,000-token prompt far
  more slowly than the 18 s turn budget allows, even for one room. Local
  inference for 80 rooms needs dedicated GPU servers or a much shorter
  prompt; size it with a separate test.

## Scaling architecture that keeps one CAOSCare state

- Keep Home Assistant → bridge as stateless HTTP; scale by adding uvicorn
  workers (then hosts) behind one address. All conversation, session,
  request, alert and receipt state is already in MongoDB; workers hold only
  admission counters.
- Admission is per worker today. For more than one host, move the slot
  counter to a shared store (a MongoDB collection with atomic counters, or a
  queue), keeping the same priority rules and the emergency bypass.
- Scale MongoDB vertically first, then a replica set; one database stays the
  single source of truth.
- Reduce per-turn work before adding hardware: the ~33,000-character context
  is rebuilt and sent on every model call.

## Reproduce

```
cd backend
.venv/bin/python -m loadtest.run --levels 1,5,10,20,40,80 --workers 2 --max-active 40 --reserved 8 \
    --out loadtest/results/levels_w2.json
.venv/bin/python -m loadtest.run --scenario saturation --levels 80 --max-active 8 --reserved 2
.venv/bin/python -m loadtest.run --scenario failure --levels 20 --workers 2 --max-active 40 --duration 32
.venv/bin/python -m loadtest.report levels_w2.json        # tables
```
Options: `--llm-ms/--llm-jitter-ms/--llm-max-conc/--llm-rpm` (simulated
model), `--stt-ms/--stt-max-conc/--tts-ms/--tts-max-conc` (simulated Home
Assistant speech), `--keep-db`. Each run uses a throwaway `caos_vb_load_*`
database and drops it afterwards.

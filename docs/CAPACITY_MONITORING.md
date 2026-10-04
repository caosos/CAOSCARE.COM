# Capacity monitoring and scalability alerts

Status (2026-10-04, branch `spike/voice-bridge`): implemented and tested with
synthetic samples, a live load run and the full backend suite. Not deployed.

## Where to look

Admin → Community → **Capacity** (`frontend/src/pages/CapacityTab.jsx`):
- current status;
- resident, staff, simulator and background load;
- voice sessions, queue and latency;
- provider problems;
- CPU, memory, disk, database, devices and receipt writes;
- emergency reserve;
- the current bottleneck and remaining safe headroom;
- projected capacity need;
- open capacity alerts, with acknowledge and resolve controls.

No SSH is needed. API: `GET /api/capacity/status`, `/samples`, `/alerts`; `POST
/api/capacity/alerts/{id}/acknowledge|resolve`; `GET/PUT /api/capacity/config`;
`POST /api/capacity/evaluate` (admin only).

## How it works (reuses existing pieces)

- **Telemetry** (`backend/routes/capacity_telemetry.py`). Three things feed it:
  - an HTTP middleware that labels every API request with one of ten traffic classes;
  - the voice bridge, which records each turn's priority class, outcome, latency, provider error, and whether it is real or simulated;
  - `create_receipt`, which records how long each receipt write takes.

  Host readings come from `/proc` and `/sys`: CPU overall and per core, load, memory, swap, disk space and latency, I/O wait, network and temperature.
- **Monitor** (`backend/routes/capacity_monitor.py`). Each worker publishes its counters. One worker, holding a lock in Mongo, writes a `capacity_samples` document every `CAOSCARE_CAPACITY_INTERVAL_S` (default 15 s); samples are kept 30 days. Each sample adds:
  - database ping and connection count;
  - voice sessions;
  - device commands and pendant events;
  - recent requests that have no receipt;
  - CPU for each CAOSCare worker and for mongod, and CAOSCare's share of host CPU.

  `CAOSCARE_CAPACITY_MONITOR=0` switches it off.
- **Model** (`backend/routes/capacity_model.py`). It compares each metric with its tested safe value. Safe values marked `measured` come from the voice-bridge load test (`docs/reports/2026-10-04-voice-bridge-load-test.md`); `configured` ones are defaults with no test behind them yet (disk, memory, database latency, device events). All are editable in `PUT /capacity/config`, and each change writes a receipt. The model also produces:
  - the bottleneck, which is the metric with the highest share of its safe value;
  - the remaining headroom;
  - the emergency reserve;
  - a projection: a 14-day trend of daily peaks, and the date the bottleneck would reach ACTION NEEDED.
- **Alerts** (`backend/routes/capacity_alerts.py`). Capacity alerts are stored in `capacity_alerts`, separate from resident help events, because they concern the system rather than a resident. Their receipts and provenance use the shared receipt store.

## Traffic classes

The ten classes:
- `resident_voice`
- `resident_device`
- `pendant_help`
- `staff_dashboard`
- `staff_workflow`
- `simulator_resident`
- `simulator_staff`
- `background_jobs`
- `email_notification`
- `receipt_audit_writes`

A turn counts as simulated when it comes from a synthetic resident; any request counts as simulated when it carries `X-CAOSCare-Traffic: simulator`. Simulated traffic is never counted as real resident or staff demand, and simulator voice turns cannot use the model slots reserved for real staff-help requests.

## Alert levels

| Level | Share of tested safe value (default) | Must hold for |
|---|---|---|
| WATCH | 60% | 4 samples |
| ACTION NEEDED | 80% | 4 samples |
| CRITICAL | 95% | 2 samples |

- **Hysteresis:** an alert resolves automatically only after 8 samples below its level minus 10 points.
- **Cooldown:** the same metric does not reopen at the same or a lower level for 15 minutes.
- **Escalation:** an alert escalates in place when a higher level holds for its sample count; it never steps down.

Every alert records:
- component, metric, measured value, tested safe value and remaining headroom;
- the traffic class causing it, and whether that traffic is real or simulated;
- the recommendation, the evidence and the sample it came from;
- the time;
- acknowledgment and resolution state.

Receipts are written for:
- opened;
- escalated;
- recommendation issued;
- acknowledged;
- capacity added or configuration changed;
- resolved.

All of an alert's receipts are chained to its opening receipt.

Manual resolution always requires written evidence. If the metric is still at the alert's level, it also requires the action that was taken.

## Recommendations

| Cause | Recommendation |
|---|---|
| Simulator traffic is more than half the load | Pause or slow simulator traffic |
| Host CPU high, but CAOSCare uses less than half of it | Reduce or reschedule background work (another process) |
| Worker CPU, voice slots, voice latency or voice throughput | Add another voice-processing worker |
| Provider 429 responses | Increase provider concurrency or quota |
| Provider failures or timeouts | Repair a failing provider |
| Database ping, receipt-write latency or API errors | Investigate database latency |
| Device events above the safe rate | Correct an abnormal device-event flood |
| Host CPU (mostly CAOSCare), memory or swap, disk | Add CPU, RAM or storage |

Hardware recommendations require two things: ACTION NEEDED or higher, and the alert having held for 15 minutes (`hardware_after_s`). A brief spike never produces a recommendation to buy hardware.

The live load check showed this working: the firmware lane's training job pushed host CPU to 100%, and the alert attributed it to `non_caoscare_host_process` and recommended rescheduling background work, not more hardware.

## Emergency reserve

Emergency words never wait for capacity; the voice bridge escalates them directly. Staff-help turns have reserved model slots (`CAOSCARE_VOICE_BRIDGE_RESERVED`), which lower priorities and simulator traffic cannot use. The Capacity page shows the reserve and how much of it is in use.

## Limitations

- **Not observable from CAOSCare:**
  - Speech-to-text and text-to-speech failures happen inside Home Assistant.
  - Dropped audio cannot be seen, because CAOSCare receives text, not audio.
- **Not yet traffic-classed:**
  - Background jobs such as escalation ticks and email are counted only when they make API requests.
  - The monitor's own work appears as a loop count.
- **Receipt backlog** is always 0, because receipts are written synchronously. Write latency and recent requests without a receipt are reported instead.
- **Staff counts:** "active staff clients" counts distinct credentials seen in the interval, not logged-in sessions.
- **Bridge admission and the emergency reserve** apply only to voice turns. Reports and background work share the event loop and are not CPU-reserved.
- **Configured safe values** (disk, memory, database latency, device events) are defaults, not test results.
- **Projection** needs at least 3 days of samples.
- **Multi-host deployment** would need the admission counter in shared storage (see the load-test report).

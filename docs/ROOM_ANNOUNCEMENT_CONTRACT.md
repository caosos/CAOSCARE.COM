# Room announcement contract (Voice PE slice 1)

CAOSCare may ask one room's voice endpoint to speak, using Home Assistant's
official Assist satellite `announce` service. This contract was authorized by
Michael on 2026-10-04 ("Voice PE integration slice 1"). It implements the
first recommendation of `docs/VOICE_PE_EXTERNAL_COMPONENT_AUDIT.md`.

## Code

| File | Responsibility |
|---|---|
| `backend/models_announcements.py` | `RoomAnnouncementRequest` (what a caller may send); `RoomAnnouncement` (the workflow document) |
| `backend/routes/room_announcement_policy.py` | room routing, origin check, authority decision |
| `backend/routes/room_announcements.py` | `announce()` service, lifecycle, receipts, HTTP routes |
| `backend/announcement_providers.py` | provider interface + Home Assistant Assist satellite provider |
| `backend/tests/test_room_announcements.py` | focused tests |

Everything except the provider reuses existing canonical parts:

- `create_receipt` and its provenance fields;
- `ActorContext`;
- `deps.get_current_user`, `staff_scope.acts_for`;
- the Kiosk room mapping and `voice_device_ids`;
- the facility record;
- the HA credentials in `device_adapters`.

No new request, resident, receipt, device or authorization system was added.
The announcement document plays the same role for an announcement that
StaffTask plays for a request.

## Request schema (`POST /api/room-announcements`, or `announce()` in-process)

| Field | Required | Notes |
|---|---|---|
| `community_id` | yes | must equal the room's community (`Kiosk.facility_id`, else the active facility) |
| `room` | yes | the room string used by Kiosk and Resident |
| `message` | yes | 1–300 characters, spoken as given |
| `purpose` | yes | `request_update`, `transport_update`, `facility_notice`, `staff_message` or `reminder` |
| `priority` | no | `routine` (default) or `important`. `emergency` is refused: no emergency announcement policy exists. |
| `origin_type` | yes | `task`, `alert`, `system_workflow` or `staff_direct` |
| `origin_id` | yes, unless `staff_direct` | the task or alert. It must exist and be in the same room. |
| `idempotency_key` | no | caller's retry key. Otherwise one is derived from origin, room, message and actor (see "Duplicates" below). |
| `scheduled_for` | no | a future time is refused (`scheduling_not_available`); there is no scheduler yet |

Actor, authority, resident, target device and provider are **never** taken
from the request. They are resolved server-side.

The stored document also records:

- `announcement_id`, `resident_id`, `kiosk_id`, `target_device_id`;
- `actor_id`, `actor_type`;
- `authority` and the `authorization` decision;
- `provider`, `provider_request`, `provider_response`;
- `evidence_level`, `failure_reason`;
- `next_action`, `outcome`;
- `correlation_id` (the origin receipt id), `last_receipt_id`,
  `final_receipt_id`;
- `history` (state, time, receipt id);
- `created_at`.

## Lifecycle

```
requested → authorized | rejected
authorized → queued → sent_to_provider
sent_to_provider → playback_started (only with provider evidence)
                 → playback_finished (only with provider evidence) | failed
every path ends → receipt_recorded (outcome + final_receipt_id set)
```

| Outcome | Meaning |
|---|---|
| `played` | the provider reported the announcement finished |
| `unconfirmed` | the provider accepted the request but gave no finish evidence. The state stays at the last evidenced step (`sent_to_provider` or `playback_started`); the receipt status is `acknowledged`, labelled `unverified`. |
| `failed` | not delivered (`device_unavailable`, `satellite_busy`, `provider_error`, `not_configured`) |
| `unverified_timeout` | no answer within `CAOSCARE_ANNOUNCE_TIMEOUT_S` (default 30 s). It may still play. It is not retried automatically, and the next action is `staff_check`. |
| `rejected` | refused before anything was sent |

## Authorization (slice 1)

Allowed:

- **owner, admin, front_desk:** any room in the community, any origin.
- **department staff:** only for a `task` origin in their own department
  (`acts_for`), spoken in that task's room.
- **system workflows:** only the named in-process workflows
  `request_status_update`, `transport_update`, `staff_dispatch_update`,
  and only with an origin object.

Refused, each with a `room_announcement_rejected` receipt:

- anonymous callers (`unauthenticated`, HTTP 401);
- family and other roles (`not_authorized`, HTTP 403);
- unknown system workflows;
- speaker recognition, which is never an input.

Policies not yet defined in CAOSCare are recorded, not invented:

- `authorization.quiet_hours_policy = "none_defined"` (no quiet-hours rule is
  applied);
- `authorization.emergency_policy = "none_defined"` (emergency priority is
  refused).

## Routing safety

| Problem | Refusal reason |
|---|---|
| Room has no endpoint | `unknown_room` |
| Room is in another community | `cross_community` |
| Room has no mapped voice device | `room_disconnected` |
| Room has more than one voice endpoint | `ambiguous_room` |
| Origin is in another room | `origin_room_mismatch` |
| Origin missing or unknown | `missing_origin`, `unknown_origin` |

The target is the room's mapped `assist_satellite.*` entity when one is
listed, otherwise its HA device id.

## Duplicates

Idempotency keys are unique (unique index on
`room_announcements.idempotency_key`), so concurrent or repeated identical
requests produce one announcement and one provider call.

Each repeat writes `room_announcement_duplicate_ignored` against the original
announcement. Its parent and correlation are the original's origin receipt,
and it sits outside the lifecycle chain. A deliberate re-announcement needs a
new key.

A derived key for `staff_direct` includes a 10-minute window: the same words
to the same room by the same person within 10 minutes count as a retry.

## Adapter boundary

`announcement_providers.AnnouncementProvider`:

- `name`, `simulated`;
- `announce(target_device_id, message, *, preannounce, timeout_s)`, which
  returns a `ProviderResult`: accepted, evidence level, started, finished,
  failure, timed out, sanitised request/response.

The canonical service never calls Home Assistant directly. A future approved
custom firmware, a realtime path or an external room speaker is added as
another provider.

Home Assistant provider (`ha_assist_satellite`):

1. For a satellite entity target, it first reads `/api/states/<entity>` and
   refuses an `unavailable` entity or a missing one (404).
2. It calls `POST /api/services/assist_satellite/announce` with
   `{entity_id|device_id, message, preannounce: true}`.

This depends on Home Assistant core behaviour (home-assistant/core
`275e8b6`):

- the REST API runs the service with `blocking=True` and returns the states
  changed under that call's context (`components/api/__init__.py` 425–475);
- the satellite sets `responding` and then `idle` around a blocking
  `async_announce` (`components/assist_satellite/entity.py` 198–240).

## Evidence levels

| Level | Meaning | Reported as |
|---|---|---|
| `none` | not sent, or no answer | rejected / failed / unverified_timeout |
| `provider_accepted` | HTTP 200, no satellite state change for the target | `unconfirmed`, never played |
| `provider_reported_started` | target satellite went `responding` | `playback_started`; `unconfirmed` without finish |
| `provider_reported_finished` | `responding` then `idle` within the blocking call | `played` (label `verified`, or `simulated` for a simulated provider) |

**Limitation:** all levels are reported by Home Assistant and the device
firmware. None is an acoustic confirmation that a person heard the message.
Each provider-evidence receipt says so.

## Receipt linkage

- Every state change writes one receipt through `create_receipt`:
  - `action_type` is `room_announcement_<state>`;
  - `related_object_type` is `room_announcement`, and `related_object_id` is
    the announcement id;
  - `correlation_id` is the origin (`requested`) receipt, fixed when the
    document is created;
  - `parent_receipt_id` is the previous receipt;
  - it also carries the actor fields, authority, before/after state, result
    label, next state and evidence (community, kiosk, target device, origin,
    purpose, priority, idempotency key, provider request/response, evidence
    level).
- Every receipt points at an existing announcement document. The document's
  `history` lists each receipt id, so there are no orphan receipts.

## Known limitations

- No live Home Assistant or Voice PE test has been run. HA was down; all
  tests use fakes and a mocked HTTP transport.
- No acoustic confirmation of playback.
- If HA's REST call returns before playback ends, the result is
  `unconfirmed`, not `played`. This was not verified on real hardware.
- No scheduler (future `scheduled_for` is refused), no quiet-hours policy,
  and no emergency announcement policy.
- Recovery after a timeout is a staff check (`next_action: staff_check`);
  there is no automatic retry.
- The HTTP route is not yet linked from any UI. Callers are staff tools or
  in-process workflows.
- No raw room audio is involved or retained.

## Physical Voice PE acceptance still required

1. Map a real Voice PE's satellite entity id to a test room.
2. As front desk, announce to that room and confirm:
   - it plays only in that room;
   - the outcome is `played`, with receipts `requested` through
     `playback_finished`.
3. Repeat the same request. Confirm no second playback and a
   `duplicate_ignored` receipt.
4. Unplug or disconnect the device. Confirm `failed`/`device_unavailable`
   and no false `played`.
5. Announce while the device is answering a resident. Record the actual HA
   behaviour (busy or interrupting) and confirm the receipt matches.
6. Confirm a family or anonymous request is refused, with a receipt.

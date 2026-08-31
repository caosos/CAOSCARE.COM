# CAOSCare Distributed RF Location Standard

_Status: implementation / deployment contract_

_Branch: `feature/runtime-agent-lanes-20260830`_

## Purpose

CAOSCare should use the RF hardware already planned for room edge nodes not only to recognize resident pendant presses, but also to estimate **where the resident was when the pendant transmitted**.

The existing building pendant system may remain in place. CAOSCare adds its own distributed receive layer at room edge nodes and uses those observations to create a building-level RF location map.

This is an extension of the existing CAOSCare RF architecture, not a second pendant system. The current backend already supports sub-GHz pendant fingerprinting through room/kiosk bridge daemons, RF-device pairing, signal-strength metadata, room/zone identity, location records, and pendant events including `press` and `periodic_ping`.

## Terminology

If the room hardware only listens, call it a **receiver** or **SDR receiver**, not a transceiver.

Do not call ordinary RSSI-based room localization precise triangulation unless the deployed hardware and algorithm genuinely support angle-of-arrival or another geometry-based method.

Initial CAOSCare location methods should be described as:

- multi-receiver location estimation
- nearest-receiver inference
- calibrated RSSI weighting
- RF fingerprinting / zone classification

Future hardware may support more precise methods, but accuracy claims must be evidence-based.

## Core architecture

Every commissioned room edge node may include a receive-only sub-GHz RF device such as the currently implemented Nooelec NESDR SMArt v5 class receiver.

When a resident pendant transmits, multiple room receivers may hear the same physical transmission.

Example:

```text
Pendant P-204 transmits

Room 219 receiver:  -42 dBm
Room 218 receiver:  -61 dBm
Hallway receiver:   -54 dBm
Room 220 receiver:  -73 dBm

Grand Central RF Location service:
  -> group all observations into ONE transmission
  -> identify pendant/resident
  -> estimate most likely location
  -> create ONE alert if this was a call press
  -> retain all receiver observations as location evidence
```

The system must never create one resident call per receiver.

## One transmission, many observations, one alert

This is non-negotiable.

A physical pendant press may produce multiple RF frames, and every frame may be heard by many receivers. CAOSCare must distinguish:

```text
physical resident action
    -> one logical pendant transmission / press event
        -> many receiver observations
            -> one resident alert/call
            -> one location estimate
```

The existing press-coalescing logic remains relevant, but distributed reception adds another deduplication dimension: identical or near-identical observations from different receivers must be grouped before alert creation.

The grouping key should use the strongest evidence available, including:

- paired RF device / pendant identity
- RF fingerprint / frame identity
- frequency
- tight receive-time window
- event type
- correlation/transmission ID when generated at the edge or aggregator

Repeated delivery/replay must remain idempotent.

## Receiver observation contract

Each room receiver observation should eventually record at least:

```text
observation_id
transmission_id / correlation_id
facility_id
receiver_node_id
receiver_kiosk_id
receiver_room
receiver_zone
rf_device_id / pendant_id when matched
frequency_hz
fingerprint/frame hash
rssi_dbm or signal_strength
snr when available
received_at
software/receiver version
quality metadata
```

Receiver identity must come from the commissioned room-node binding. Do not trust a free-text room supplied by an unverified client.

## Location estimate contract

The central RF Location service should create an estimate from all observations belonging to one transmission.

At minimum record:

```text
location_estimate_id
transmission_id
facility_id
resident_id
rf_device_id
estimated_room
estimated_zone
method
confidence
receiver_count
candidate_locations[]
observed_at
supporting_observation_ids[]
```

If confidence is weak, return a broader zone or `unknown` rather than inventing an exact room.

Never present an estimated location as exact unless the deployed system has been validated to that precision.

## Initial localization strategy

The first implementation should favor robustness over mathematical elegance.

Recommended progression:

1. **Nearest receiver** — strongest valid receiver observation wins when clearly dominant.
2. **Weighted multi-receiver estimate** — combine several RSSI values and known receiver zones.
3. **Calibrated RF fingerprinting** — collect real pendant readings at known building locations and compare live observation vectors to calibrated signatures.
4. More advanced geometry/time/angle methods only if later hardware supports them reliably.

Indoor RF is affected by walls, doors, people, furniture, antenna orientation, reflections, and multipath. Raw RSSI should not be converted directly into a claimed precise distance without calibration.

## Building map / calibration

Administrator setup should support a floor/zone map tied to commissioned receiver nodes.

For every receiver store:

```text
facility
floor
room/zone
map position or coordinates when available
receiver hardware identity
antenna configuration
commissioning/calibration status
```

Calibration mode should allow a pendant to be carried to known locations and pressed/transmitted repeatedly. The system stores the multi-receiver signal pattern for that known location.

Example calibrated locations:

```text
Room 219 bed area
Room 219 bathroom
Room 219 doorway
Hallway outside 219
Dining room north
Lobby
Courtyard door
```

The first practical goal is useful **room/zone-level location**, not false centimeter precision.

## Press-only versus periodic location

If a pendant transmits only when the resident presses it, CAOSCare knows location **at the time of the press**.

If the pendant also emits a periodic beacon/ping that CAOSCare can receive and identify, the same distributed receiver system may maintain a rolling location estimate.

The existing model already anticipates `periodic_ping` events; implementation agents should determine whether the actual deployed pendant emits a usable periodic transmission before promising continuous tracking.

No software should claim continuous location from a press-only pendant.

## Alert integration

When a pendant press becomes an alert, attach the best available RF-location result to the alert without replacing the resident's assigned room.

These are different facts:

```text
resident home room: Room 219
estimated press location: Dining Room
```

Staff surfaces should be able to show both.

Suggested alert metadata:

```text
estimated_location
location_confidence
location_method
receiver_count
transmission_id
```

The location estimate is evidence for response routing; it must not mutate the resident's permanent room assignment.

## Grand Central events

Suggested event flow:

```text
rf.observation.received
rf.transmission.grouped
rf.location.estimated
pendant.press.confirmed
alert.created
```

All receiver observations for the same physical transmission share one correlation chain.

Grand Central must preserve provenance so staff/QA can inspect exactly which receivers contributed to the estimate.

## Edge Agent responsibilities

The Room Edge Agent should eventually:

- verify RF receiver presence
- report exact receiver hardware identity
- bind receiver identity to commissioned room/zone
- run receiver diagnostics locally
- verify frequency/band capability
- report RSSI/quality metadata
- send signed observations to the facility server
- expose receiver health
- detect/report receiver offline state
- participate in calibration mode

RF tests execute locally on the room node just like audio/device tests.

## Failure behavior

The pendant alert path and location-estimation path must degrade independently where practical.

Examples:

- one receiver offline: other receivers still contribute
- insufficient receivers: create alert, location may be broad/unknown
- localization service failure: never suppress an otherwise valid pendant alert
- duplicate observations: one alert, observations deduplicated/grouped
- receiver reports impossible room identity: reject/quarantine observation

Location enrichment must improve response; it must not become a new reason for an alert to disappear.

## Required tests

At minimum:

1. one physical press heard by 8 receivers creates one alert, not 8
2. multiple RF frames from one press remain one logical press according to the coalescing contract
3. receiver replay does not create duplicate observations/effects
4. strongest receiver clearly in Room A yields Room A when confidence threshold is met
5. ambiguous signals return broader/low-confidence location instead of false precision
6. resident assigned to Room 219 can correctly produce an estimated location in Dining Room without changing their home-room assignment
7. receiver A cannot claim to be receiver B / another room without failing identity validation
8. one offline receiver does not break the whole location estimate
9. press-only pendant does not produce fabricated continuous tracking history
10. periodic ping tracking is enabled only after the real pendant behavior is verified
11. all contributing receiver observations are traceable from the alert/location estimate
12. room/resident isolation remains intact

## Current repository alignment

This contract intentionally reuses the existing CAOSCare RF and location concepts rather than replacing them.

Existing code already includes:

- room/kiosk RF bridge reception
- Nooelec NESDR SMArt v5 implementation direction
- RF fingerprint matching
- paired RF devices assigned to residents
- signal-strength fields
- room/zone receiver context
- press coalescing
- `LocationUpdate`
- `PendantEventInput` with `press`, `periodic_ping`, and `fall`

Implementation should extend those authoritative domains to multi-receiver observations and central location estimation.

## Non-negotiable summary

```text
Put receive-only RF hardware at room edge nodes where practical.
Every receiver knows its commissioned room/zone identity.
One pendant transmission may be heard by many receivers.
Many receiver observations must still produce ONE logical resident alert.
Use all observations to estimate the press location.
Start with room/zone-level calibrated RSSI/fingerprinting.
Do not promise exact triangulation from commodity RSSI.
Press-only pendants provide location at press time.
Periodic tracking requires a verified periodic pendant transmission.
Location evidence enriches alerts but never overwrites the resident's home room.
Keep every estimate traceable to the receivers that heard it.
```

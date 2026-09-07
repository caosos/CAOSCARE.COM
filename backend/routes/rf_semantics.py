"""RF transmission-semantics classification (Level 1 directive, 2026-09-07).

WHO vs WHAT are separate questions:

  * IDENTITY  - "who transmitted?"  - answered by fingerprint matching in
    routes/rf.py (frequency band + Hamming similarity of bit_pattern_hex).
  * SEMANTICS - "what did they transmit?" - answered HERE.

A successfully matched transmission from a paired pendant is NOT
automatically a resident help request. The real Room 214 Lifeline pendant
(rfd_6e8f06632b41) emits at least two proven classes on the SAME identity:

  help_press    decoded switch5 = CLOSED (switch1-4 OPEN); a deliberate
                button press; long multi-frame burst (~8-40 frames,
                ~2.6-36s) - live-evidenced 2026-09-06 (Michael's own tests).
  supervisory   all decoded switches OPEN; short unsolicited burst (~3
                frames, ~0.5-1.1s); periodic (~64-67 min cadence) - this is
                the pendant's automatic check-in, live-evidenced 2026-09-06
                / 2026-09-07 as the cause of spontaneous Aria wakes.

Only `help_press` is authorised to enter record_resident_activation().

This is deliberately NOT hard-coded to one pendant: `classify_transmission`
returns an extensible `RfClass` (help_press | supervisory | tamper |
battery_status | unknown). Decoded protocol/status semantics are preferred;
frame count / burst duration / cadence are SUPPORTING evidence only, never
the sole basis. Anything from a matched device that does not positively
match a known semantic is `unknown` - preserved, surfaced for diagnostics,
never silently promoted to help.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from models import now_utc

# Proven-signature thresholds. Overridable per deployment / pendant family
# later; these are the live-measured Interlogix/Lifeline values (Room 214).
SUPERVISORY_MAX_FRAMES = 4          # observed 3
SUPERVISORY_MAX_SPAN_SEC = 1.6     # observed 0.5-1.1
PRESS_MIN_FRAMES_CORROBORATION = 6  # observed 8-40 (support only, not required)
PRESS_MIN_SPAN_SEC_CORROBORATION = 2.4
# A prior same-signature supervisory frame this long before "confirms" the
# periodic cadence (observed ~64-67 min). Outside the window the class is
# still supervisory, just tagged cadence_unconfirmed.
SUPERVISORY_CADENCE_MIN_SEC = 30 * 60
SUPERVISORY_CADENCE_MAX_SEC = 130 * 60

ACTIVATION_CLASS = "help_press"     # the ONLY class allowed into the activation path


@dataclass
class RfClass:
    semantic: str                       # help_press | supervisory | tamper | battery_status | unknown
    allows_activation: bool
    reasons: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "semantic_class": self.semantic,
            "allowed_activation": self.allows_activation,
            "class_reasons": self.reasons,
            "class_evidence": self.evidence,
        }


def _switch_state(decoded: dict) -> dict:
    return {k: decoded.get(k) for k in ("switch1", "switch2", "switch3", "switch4", "switch5") if k in decoded}


def _all_switches_open(switches: dict) -> bool:
    return bool(switches) and all((v or "").upper() == "OPEN" for v in switches.values())


def classify_transmission(
    fingerprint: dict,
    *,
    matched: bool,
    burst_frames: int,
    burst_span_sec: float,
    prior_same_device_gap_sec: Optional[float],
    device: Optional[dict] = None,
) -> RfClass:
    """Classify one matched RF frame in the context of its burst.

    `burst_frames` / `burst_span_sec` describe the frames already seen from
    this device inside the current burst window (this frame included).
    `prior_same_device_gap_sec` is the interval since the last burst from
    the same device BEFORE this one (None if unknown / first ever).
    """
    decoded = fingerprint.get("decoded") or {}
    switches = _switch_state(decoded)
    battery_ok = decoded.get("battery_ok")
    ev = {
        "switches": switches,
        "battery_ok": battery_ok,
        "burst_frames": burst_frames,
        "burst_span_sec": round(burst_span_sec, 3),
        "prior_same_device_gap_sec": round(prior_same_device_gap_sec, 1) if prior_same_device_gap_sec is not None else None,
        "rssi": fingerprint.get("rssi"),
        "frequency_hz": fingerprint.get("frequency_hz"),
        "bit_pattern_hex": fingerprint.get("bit_pattern_hex"),
        "matched": matched,
    }

    if not matched:
        return RfClass("unknown", False, ["identity_not_matched"], ev)

    # 1. TAMPER - decoded protocol flag wins outright (scaffold: no proven
    #    tamper capture from this pendant yet, but the branch is real).
    if str(decoded.get("tamper", "")).upper() in ("1", "TRUE", "CLOSED", "YES") or decoded.get("tamper") is True:
        return RfClass("tamper", False, ["decoded_tamper_flag"], ev)

    # 2. BATTERY / STATUS - an explicit low-battery report (short unsolicited
    #    burst, switches OPEN, battery_ok falsey).
    if battery_ok is not None and not bool(battery_ok) and _all_switches_open(switches) and burst_frames <= SUPERVISORY_MAX_FRAMES:
        return RfClass("battery_status", False, ["decoded_battery_not_ok", "supervisory_shape"], ev)

    # 3. HELP PRESS - the PROVEN deliberate-press semantic signature:
    #    switch5 CLOSED with switch1-4 OPEN. Decoded semantics are the gate;
    #    a long/large burst is corroboration only, recorded but not required
    #    (a real press's very first frame already carries switch5=CLOSED).
    s5 = (switches.get("switch5") or "").upper()
    others_open = all((switches.get(k) or "OPEN").upper() == "OPEN" for k in ("switch1", "switch2", "switch3", "switch4"))
    if s5 == "CLOSED" and others_open:
        reasons = ["decoded_press_signature_switch5_closed"]
        if burst_frames >= PRESS_MIN_FRAMES_CORROBORATION:
            reasons.append("burst_frame_count_corroborates")
        if burst_span_sec >= PRESS_MIN_SPAN_SEC_CORROBORATION:
            reasons.append("burst_duration_corroborates")
        return RfClass("help_press", True, reasons, ev)

    # 4. SUPERVISORY / CHECK-IN - the PROVEN periodic beacon signature: all
    #    switches OPEN, short burst. Cadence is supporting evidence.
    if _all_switches_open(switches) and burst_frames <= SUPERVISORY_MAX_FRAMES and burst_span_sec <= SUPERVISORY_MAX_SPAN_SEC:
        reasons = ["all_switches_open", "supervisory_burst_shape"]
        gap = prior_same_device_gap_sec
        if gap is not None and SUPERVISORY_CADENCE_MIN_SEC <= gap <= SUPERVISORY_CADENCE_MAX_SEC:
            reasons.append("periodic_cadence_confirmed")
        else:
            reasons.append("cadence_unconfirmed")
        return RfClass("supervisory", False, reasons, ev)

    # 5. UNKNOWN - matched identity, but the message matches no proven
    #    semantic (e.g. switches OPEN yet a long/large burst, or a switch
    #    pattern we have never mapped). Preserve + surface, never promote.
    why = ["matched_device_unmapped_message"]
    if switches and not _all_switches_open(switches) and s5 != "CLOSED":
        why.append("unmapped_switch_pattern")
    if _all_switches_open(switches):
        why.append("supervisory_switches_but_offshape_burst")
    return RfClass("unknown", False, why, ev)


BURST_GAP_SEC = 2.0        # a gap longer than this ends a contiguous burst


async def burst_context(db, rf_device_id: str, now: Optional[datetime] = None, lookback_sec: float = 90.0) -> dict:
    """Describe the CONTIGUOUS burst this frame belongs to (frames within
    BURST_GAP_SEC of each other), plus the gap since the previous burst.
    Read-only over db.rf_events. This frame is not yet inserted, so it is
    counted here but its timestamp is `now`."""
    now = now or now_utc()
    since = (now - timedelta(seconds=lookback_sec)).isoformat()
    rows = await db.rf_events.find(
        {"matched_device_id": rf_device_id, "received_at": {"$gte": since}},
        {"_id": 0, "received_at": 1},
    ).sort("received_at", 1).to_list(400)
    times = [datetime.fromisoformat(r["received_at"]) for r in rows] + [now]

    # Walk backwards from `now`, staying inside the current contiguous burst.
    burst_start_idx = len(times) - 1
    for i in range(len(times) - 1, 0, -1):
        if (times[i] - times[i - 1]).total_seconds() > BURST_GAP_SEC:
            burst_start_idx = i
            break
        burst_start_idx = i - 1
    burst = times[burst_start_idx:]
    frames = len(burst)
    span = (burst[-1] - burst[0]).total_seconds() if frames > 1 else 0.0
    gap = None
    if burst_start_idx > 0:
        gap = (burst[0] - times[burst_start_idx - 1]).total_seconds()
    return {"burst_frames": frames, "burst_span_sec": span, "prior_same_device_gap_sec": gap}

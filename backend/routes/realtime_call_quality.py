"""Realtime call-quality receipts (WebRTC diagnostics).

Owner report 2026-10-16 (aria-room-runtime-fixes-001): Room 214 audio
"sounded like a poor cellular connection". The room page can be local while
the Realtime voice still crosses the internet, so a bad call needs evidence
that separates the local page (UI stalls), the network (loss, jitter, round
trip), concealment the browser applied, the peer connection state, and the
provider's response latency.

The browser (frontend lib/callQualityMonitor.js) samples RTCPeerConnection
getStats() every few seconds and posts ONE summarized window about every 30
seconds plus one final window at teardown - never per-packet, never audio.
This module owns the thresholds (one source of truth), grades each window
GOOD / DEGRADED / BAD with the evidence that decided it, keeps a bounded set
of interval windows per session, and folds them into one final call-quality
receipt per session.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from deps import db, get_current_user
from models import now_utc

router = APIRouter(prefix="/realtime-diagnostics", tags=["realtime-diagnostics"])

MAX_INTERVALS = 240          # 30 s windows -> two hours of call; older windows are dropped
GRADES = ("GOOD", "DEGRADED", "BAD")

# metric -> (DEGRADED at or above, BAD at or above, cause)
THRESHOLDS = {
    "loss_pct": (2.0, 8.0, "network"),
    "remote_loss_pct": (2.0, 8.0, "network"),
    "jitter_ms": (30.0, 60.0, "network"),
    "rtt_ms": (300.0, 600.0, "network"),
    "concealed_pct": (3.0, 10.0, "network"),
    "ui_lag_ms_max": (250.0, 1000.0, "local_page"),
    "response_latency_ms_median": (2500.0, 5000.0, "provider_latency"),
}
_BAD_STATES = {"failed", "disconnected", "closed"}


class QualityWindow(BaseModel):
    session_id: str
    phase: str = Field("interval", pattern="^(interval|final)$")
    room: Optional[str] = None
    reason: Optional[str] = None                 # final only: why the call ended
    window_ms: Optional[int] = None
    metrics: dict = Field(default_factory=dict)  # numbers / short strings only (see THRESHOLDS)


def grade_window(metrics: dict) -> dict:
    """{grade, evidence[], causes[]} - pure, deterministic."""
    evidence, level, causes = [], 0, set()
    for name, (warn, bad, cause) in THRESHOLDS.items():
        v = metrics.get(name)
        if not isinstance(v, (int, float)):
            continue
        if v >= bad:
            level = max(level, 2)
        elif v >= warn:
            level = max(level, 1)
        else:
            continue
        evidence.append({"metric": name, "value": v, "degraded_at": warn, "bad_at": bad})
        causes.add(cause)
    state = metrics.get("connection_state")
    if state in _BAD_STATES:
        level = 2
        evidence.append({"metric": "connection_state", "value": state})
        causes.add("network")
    return {"grade": GRADES[level], "evidence": evidence, "causes": sorted(causes)}


def _clean(metrics: dict) -> dict:
    """Numbers, booleans and short strings only - nothing else is stored."""
    out = {}
    for k, v in list(metrics.items())[:40]:
        if isinstance(v, bool) or isinstance(v, (int, float)):
            out[str(k)[:40]] = v
        elif isinstance(v, str):
            out[str(k)[:40]] = v[:40]
    return out


def summarize(windows: list) -> dict:
    """Fold graded windows into the call's receipt summary."""
    counts = {g: 0 for g in GRADES}
    worst, peaks, causes = 0, {}, set()
    for w in windows:
        counts[w["grade"]] += 1
        worst = max(worst, GRADES.index(w["grade"]))
        causes.update(w.get("causes") or [])
        for name in THRESHOLDS:
            v = (w.get("metrics") or {}).get(name)
            if isinstance(v, (int, float)):
                peaks[name] = max(peaks.get(name, v), v)
    return {"overall": GRADES[worst], "window_grades": counts, "peaks": peaks, "causes": sorted(causes),
            "windows": len(windows)}


@router.post("/call-quality")
async def post_call_quality(data: QualityWindow):
    """Public, same trust model as /event. Bounded and fire-and-forget."""
    metrics = _clean(data.metrics)
    graded = {"session_id": data.session_id, "room": data.room, "phase": data.phase,
              "window_ms": data.window_ms, "metrics": metrics, **grade_window(metrics),
              "created_at": now_utc().isoformat()}
    count = await db.realtime_call_quality_windows.count_documents({"session_id": data.session_id})
    if count < MAX_INTERVALS:
        await db.realtime_call_quality_windows.insert_one(dict(graded))
    if data.phase != "final":
        return {"ok": True, "grade": graded["grade"]}
    windows = await db.realtime_call_quality_windows.find(
        {"session_id": data.session_id}, {"_id": 0}).sort("created_at", 1).to_list(MAX_INTERVALS)
    receipt = {"session_id": data.session_id, "room": data.room, "ended_reason": data.reason,
               "final_window": graded, **summarize(windows), "created_at": now_utc().isoformat(),
               "kind": "realtime_call_quality_receipt"}
    await db.realtime_call_quality.replace_one({"session_id": data.session_id}, receipt, upsert=True)
    receipt.pop("_id", None)
    return {"ok": True, "grade": graded["grade"], "receipt": receipt}


@router.get("/call-quality/{session_id}")
async def get_call_quality(session_id: str, user=Depends(get_current_user)):
    """Staff/admin: the call's receipt plus its graded windows."""
    receipt = await db.realtime_call_quality.find_one({"session_id": session_id}, {"_id": 0})
    windows = await db.realtime_call_quality_windows.find(
        {"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(MAX_INTERVALS)
    return {"session_id": session_id, "receipt": receipt, "windows": windows}

#!/usr/bin/env python3
"""
CAOS Care — Sub-GHz RF Bridge (Reference Implementation)

This is the host-side daemon that pairs the Nooelec NESDR SMArt v5 (any
RTL-SDR will do) with the CAOS Care backend. It runs on the Android kiosk
tablet via Termux, or on any USB-OTG Linux host attached to the SDR.

It implements the [FW-006] blueprint:
  - Polls /api/rf/bridge/{kiosk_id}/pending for an open capture window.
  - When a window is open, runs the SDR across the requested bands.
  - When a button press is detected, decodes the OOK/ASK pulse train
    into a hex bit pattern and POSTs it to the backend.
  - In the absence of an open capture window, still listens passively
    on the configured "always-on" bands and reports any presses to
    /api/rf/event so paired devices auto-fire alerts.

Hardware:
  - Nooelec NESDR SMArt v5 (or compatible RTL-SDR)
  - Optional UGREEN USB hub for power + data on Android

Protocol decode:
  - This stub uses `rtl_433` (https://github.com/merbanan/rtl_433) as the
    decoding engine. rtl_433 ships with thousands of pre-built decoders
    plus a `-G` mode that captures raw OOK pulse trains for unknown
    devices — which is what makes this vendor-agnostic.

  - Run with:
        rtl_433 -F json -M utc -G 4 -f 319M -f 433.92M ...
    rtl_433 emits JSON per packet on stdout. We parse, fingerprint, POST.

Configuration:
  Environment variables (or /etc/caos-bridge.env):
    CAOS_API_URL        e.g. https://your-facility.caoscare.com
    CAOS_KIOSK_ID       this tablet's kiosk_id
    CAOS_RF_SECRET      shared HMAC secret for this kiosk (from admin UI)
    CAOS_BANDS          comma-separated MHz, e.g. "315,319,433.92,868,915"

Run:
  python3 caos_rf_bridge.py
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import signal
import sys
import threading
import time
import uuid
from typing import Optional

from rf_restart_policy import RestartSupervisor, RunResult, run_forever
from sdr_control import RTL_433_BIN, run_rtl433

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests", file=sys.stderr)
    sys.exit(2)


API_URL = os.environ.get("CAOS_API_URL", "").rstrip("/")
KIOSK_ID = os.environ.get("CAOS_KIOSK_ID", "")
RF_SECRET = os.environ.get("CAOS_RF_SECRET", "").encode() if os.environ.get("CAOS_RF_SECRET") else None
DEFAULT_BANDS_MHZ = [float(x) for x in os.environ.get("CAOS_BANDS", "315,319,433.92,868,915").split(",")]
POLL_INTERVAL = 2.0


def _sign(body: bytes) -> Optional[str]:
    if not RF_SECRET:
        return None
    return hmac.new(RF_SECRET, body, hashlib.sha256).hexdigest()


def _post(path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    sig = _sign(body)
    if sig:
        headers["X-RF-Signature"] = sig
    r = requests.post(f"{API_URL}{path}", data=body, headers=headers, timeout=8)
    r.raise_for_status()
    return r.json()


def _get(path: str) -> dict:
    r = requests.get(f"{API_URL}{path}", timeout=6)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Sequence counter — replay protection. Persisted to disk so a reboot
# doesn't reset to 0 (which the backend would reject as <= last_seq).
# Pick a state dir we can actually write to. Order: systemd-friendly
# /var/lib/caos-bridge if writable (production), then ~/.local/state, then
# ~/.caos-bridge as a last resort. This gracefully handles every install
# style — running as root via systemd, running as a user via terminal, or
# running on Termux/Android where /var/lib is read-only.
# ---------------------------------------------------------------------------


def _pick_state_dir() -> Optional[str]:
    candidates = [
        "/var/lib/caos-bridge",
        os.path.expanduser("~/.local/state/caos-bridge"),
        os.path.expanduser("~/.caos-bridge"),
    ]
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            test_path = os.path.join(d, ".write-test")
            with open(test_path, "w") as f:
                f.write("ok")
            os.remove(test_path)
            return d
        except (PermissionError, OSError):
            continue
    return None


_STATE_DIR = _pick_state_dir()
_SEQ_FILE = os.path.join(_STATE_DIR, "seq") if _STATE_DIR else None
if _STATE_DIR:
    print(f"[rf-bridge] state dir: {_STATE_DIR}", flush=True)
else:
    print("[rf-bridge] WARNING: no writable state dir — sequence counter will reset on restart", file=sys.stderr, flush=True)


def next_sequence() -> int:
    """Monotonic, persistent sequence number for replay protection. Falls
    back to in-process monotonic if disk persistence isn't available — a
    restart will then increment from a fresh time-based seed, still
    monotonic against the previous run as long as wallclock advances."""
    if _SEQ_FILE is None:
        # No disk persistence — bootstrap from current time, then keep
        # incrementing within this process via a module-level counter.
        global _RUNTIME_SEQ
        try:
            _RUNTIME_SEQ += 1
        except NameError:
            _RUNTIME_SEQ = int(time.time())
        return _RUNTIME_SEQ
    try:
        with open(_SEQ_FILE, "r") as f:
            seq = int(f.read().strip() or "0")
    except FileNotFoundError:
        seq = int(time.time())  # bootstrap from epoch so we never collide
    seq += 1
    try:
        with open(_SEQ_FILE, "w") as f:
            f.write(str(seq))
    except OSError as e:
        print(f"[rf-bridge] could not persist seq counter: {e}", file=sys.stderr, flush=True)
    return seq


# ---------------------------------------------------------------------------
# rtl_433 wrapper. Spawns the binary, reads JSON-per-line, yields fingerprints.
# ---------------------------------------------------------------------------


# rtl_433 record keys that carry per-transmission noise (rolling/whitening
# bits, parity, a counter) rather than stable device identity, observed
# directly against a real Interlogix-Security pendant on 2026-08-29: `id`
# and the decoded semantic fields (e.g. battery_ok, switch1-5) were IDENTICAL
# across 4 separate presses / 32 frames, while `raw_message` differed on
# every single press (Hamming similarity ~0.83 between presses — below the
# 0.85 default match_threshold, so two presses of the same real pendant
# would NOT reliably match under the old priority). Evidence, not a guess —
# see docs/tsb or PROJECT_STATE for the capture.
_NOISY_FALLBACK_KEYS = ("code", "data", "raw_signal", "raw_message", "dipswitch", "button")
# Extra decoded fields worth preserving as evidence when a known decoder
# supplies them, even though they aren't used for matching.
_DECODED_EVIDENCE_KEYS = ("subtype", "battery_ok", "switch1", "switch2", "switch3", "switch4", "switch5")


def fingerprint_from_rtl433(record: dict, default_freq_mhz: Optional[float] = None) -> Optional[dict]:
    """Convert an rtl_433 JSON record into our blueprint fingerprint shape.

    Priority: a known decoder's own `model`+`id` FIRST (evidenced stable
    across repeat presses of a real pendant), then the noisy catch-all
    fields below for genuinely unidentified/unknown-protocol captures,
    where `model`+`id` aren't available at all.

    rtl_433 has thousands of brand-specific decoders, and for UNKNOWN
    protocols they publish raw bits under different keys depending on
    brand:
      • Generic OOK remotes:    `code`
      • Honeywell, GE legacy:   `data`
      • Unknown OOK captures:   `raw_signal`
      • DIP-switch remotes:     `dipswitch`
      • Some doorbells:         `button`
    """
    sanitized = None
    if record.get("model") and record.get("id") is not None:
        # Deterministic, ALWAYS-valid-hex synthesis. A brand name like
        # "Interlogix-Security" is English text, not hex data — naively
        # stripping it down to whatever a-f letters happen to appear in
        # the model name produces an unpredictable (sometimes odd) length,
        # which silently broke matching entirely (bytes.fromhex() rejects
        # odd-length input; the matcher's ValueError guard turned that
        # into a hard 0.0 similarity for EVERY future press of a real
        # pendant — found live, 2026-08-29, evidenced in db.rf_events).
        # A short hash of the model name + the id's own hex digits is
        # always even-length and never depends on what letters the brand
        # name happens to contain.
        model_hash = hashlib.sha1(str(record["model"]).encode()).hexdigest()[:8]
        id_hex = "".join(ch for ch in str(record["id"]).strip().lower() if ch in "0123456789abcdef")
        if not id_hex:
            id_hex = hashlib.sha1(str(record["id"]).encode()).hexdigest()[:8]
        sanitized = model_hash + id_hex
    if not sanitized:
        pattern = None
        for k in _NOISY_FALLBACK_KEYS:
            if record.get(k):
                pattern = record[k]
                break
        if not pattern:
            return None
        pattern = str(pattern).strip().lower()
        if pattern.startswith("0x"):
            pattern = pattern[2:]
        # Hex-only sanitize — legitimate here since these fields ARE raw
        # hex/text encodings of real bits, unlike a synthesized model name.
        sanitized = "".join(ch for ch in pattern if ch in "0123456789abcdef")
        if not sanitized:
            # Pure-text fallback — keep something so the backend can still match
            sanitized = "".join(ch.lower() for ch in pattern if ch.isalnum())[:32]
    # Defensive backstop: bytes.fromhex() (used for matching) rejects any
    # odd-length hex string outright — never let one reach the backend.
    if len(sanitized) % 2:
        sanitized = "0" + sanitized

    # Some decoders (e.g. Interlogix-Security) don't echo a frequency per
    # record at all. When we told rtl_433 to tune to exactly one band, that
    # ambiguity doesn't exist — use it rather than store a false "0 Hz".
    # With multiple bands configured and no per-record freq, frequency
    # genuinely is unknown — leave it as 0 rather than guess which band.
    freq_mhz = record.get("freq") or record.get("frequency") or default_freq_mhz or 0.0
    decoded = {k: record[k] for k in _DECODED_EVIDENCE_KEYS if k in record} or None
    return {
        "frequency_hz": int(float(freq_mhz) * 1_000_000),
        "modulation": (record.get("modulation") or "OOK").split("_")[0].upper(),
        "bit_pattern_hex": sanitized,
        "bit_length": len(sanitized) * 4,  # 4 bits per hex char
        "rssi": record.get("rssi"),
        "decoded": decoded,
    }


# ---------------------------------------------------------------------------
# Two modes of operation:
#
# 1) PASSIVE — always running in background. Reports every press as
#    /api/rf/event so paired pendants auto-fire alerts.
#
# 2) CAPTURE — when /bridge/{kiosk_id}/pending returns a capture window,
#    we briefly switch focus to that window's bands, take the strongest
#    press, and POST it as /listen/{capture_id}/captured.
# ---------------------------------------------------------------------------


_state = {
    "active_capture": None,    # dict from /bridge/.../pending (or None)
    "shutdown": False,
}
# Set by SIGINT/SIGTERM. Every wait in the spawn loop is stop.wait(...), so
# shutdown interrupts a restart backoff at once instead of sleeping it out.
_stop = threading.Event()


def poll_loop():
    while not _state["shutdown"]:
        try:
            data = _get(f"/api/rf/bridge/{KIOSK_ID}/pending")
            cap = data.get("capture")
            if cap and cap.get("status") == "listening":
                _state["active_capture"] = cap
            else:
                _state["active_capture"] = None
        except Exception as e:
            print(f"[rf-bridge] poll err: {e}", file=sys.stderr, flush=True)
        time.sleep(POLL_INTERVAL)


def on_record(rec: dict):
    # Always log the raw arrival so admins can see presses landing in real
    # time. This was missing before and made it impossible to tell whether
    # rtl_433 was capturing nothing vs. capturing but the bridge was dropping.
    model = rec.get("model") or "?"
    rid = rec.get("id", "?")
    freq = rec.get("freq", "?")
    print(f"[rf-bridge] decoded: model={model} id={rid} freq={freq}MHz", flush=True)

    single_band = DEFAULT_BANDS_MHZ[0] if len(DEFAULT_BANDS_MHZ) == 1 else None
    fp = fingerprint_from_rtl433(rec, default_freq_mhz=single_band)
    if not fp:
        print(f"[rf-bridge]   skipped — no fingerprint extracted (keys: {sorted(rec.keys())})", flush=True)
        return
    cap = _state["active_capture"]
    if cap:
        # Capture mode — send as the captured fingerprint, then drop the window
        try:
            _post(f"/api/rf/listen/{cap['capture_id']}/captured", fp)
            print(f"[rf-bridge] captured for window {cap['capture_id']}: {fp['frequency_hz']/1e6:.3f} MHz", flush=True)
        except Exception as e:
            print(f"[rf-bridge] capture POST err: {e}", file=sys.stderr, flush=True)
        _state["active_capture"] = None
    else:
        # Passive mode — fire as a live event
        try:
            _post("/api/rf/event", {
                "kiosk_id": KIOSK_ID,
                "fingerprint": fp,
                "sequence": next_sequence(),
                "captured_at": rec.get("time"),
            })
        except Exception as e:
            print(f"[rf-bridge] event POST err: {e}", file=sys.stderr, flush=True)


def main():
    if not API_URL or not KIOSK_ID:
        print("CAOS_API_URL and CAOS_KIOSK_ID must be set in env.", file=sys.stderr)
        sys.exit(2)

    def _shutdown(signum, frame):
        _state["shutdown"] = True
        # Set the event from a helper thread: Event.set() takes a lock the
        # interrupted main thread may be holding inside Event.wait(), so
        # calling it directly in the handler could deadlock.
        threading.Thread(target=_stop.set, daemon=True).start()
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    threading.Thread(target=poll_loop, daemon=True).start()
    print(f"[rf-bridge] kiosk={KIOSK_ID} bands={DEFAULT_BANDS_MHZ} api={API_URL}", flush=True)

    def _run_once(verbose: bool) -> RunResult:
        try:
            return run_rtl433(DEFAULT_BANDS_MHZ, on_record, stop=_stop, verbose=verbose)
        except FileNotFoundError:
            return RunResult.failed(
                f"rtl_433 binary not found ({RTL_433_BIN}). Install with `apt install rtl-433` "
                "(Linux) or via Termux.")
        except Exception as e:
            return RunResult.failed(f"rtl_433 err: {e}")

    # A failed or short-lived rtl_433 (e.g. no SDR plugged in) is respawned
    # with a 1-2-5-10-30-60 s backoff, not in a tight loop (rf_restart_policy.py).
    supervisor = RestartSupervisor(log=lambda m: print(m, file=sys.stderr, flush=True))
    run_forever(_run_once, _stop, supervisor)
    print("[rf-bridge] shutting down", flush=True)


if __name__ == "__main__":
    main()

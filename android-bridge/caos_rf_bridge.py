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
import shlex
import signal
import subprocess
import sys
import threading
import time
import uuid
from typing import Optional

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests", file=sys.stderr)
    sys.exit(2)


API_URL = os.environ.get("CAOS_API_URL", "").rstrip("/")
KIOSK_ID = os.environ.get("CAOS_KIOSK_ID", "")
RF_SECRET = os.environ.get("CAOS_RF_SECRET", "").encode() if os.environ.get("CAOS_RF_SECRET") else None
DEFAULT_BANDS_MHZ = [float(x) for x in os.environ.get("CAOS_BANDS", "315,319,433.92,868,915").split(",")]
RTL_433_BIN = os.environ.get("RTL_433", "rtl_433")
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
# ---------------------------------------------------------------------------

_SEQ_FILE = "/var/lib/caos-bridge/seq" if os.path.isdir("/var/lib") else os.path.expanduser("~/.caos-bridge.seq")


def next_sequence() -> int:
    try:
        with open(_SEQ_FILE, "r") as f:
            seq = int(f.read().strip() or "0")
    except FileNotFoundError:
        seq = int(time.time())  # bootstrap from epoch so we never collide
    seq += 1
    os.makedirs(os.path.dirname(_SEQ_FILE), exist_ok=True)
    with open(_SEQ_FILE, "w") as f:
        f.write(str(seq))
    return seq


# ---------------------------------------------------------------------------
# rtl_433 wrapper. Spawns the binary, reads JSON-per-line, yields fingerprints.
# ---------------------------------------------------------------------------


def fingerprint_from_rtl433(record: dict) -> Optional[dict]:
    """Convert an rtl_433 JSON record into our blueprint fingerprint shape.

    rtl_433 emits records like:
        {"time":"...", "model":"Generic-Remote", "id":12345, "code":"a3f1c2",
         "freq":319.000000, "rssi":-58, "modulation":"OOK_PWM"}

    We tolerate missing fields — anything we don't have we return None for
    (the backend handles it). The bit pattern is whatever's in `code` /
    `data` / `raw_signal` (whichever is present and most specific)."""
    pattern = record.get("code") or record.get("data") or record.get("raw_signal")
    if not pattern:
        return None
    pattern = str(pattern).strip().lower()
    if pattern.startswith("0x"):
        pattern = pattern[2:]

    freq_mhz = record.get("freq") or record.get("frequency") or 0.0
    return {
        "frequency_hz": int(float(freq_mhz) * 1_000_000),
        "modulation": (record.get("modulation") or "OOK").split("_")[0].upper(),
        "bit_pattern_hex": pattern,
        "bit_length": len(pattern) * 4,  # 4 bits per hex char
        "rssi": record.get("rssi"),
    }


def run_rtl433(bands_mhz: list[float], on_record):
    """Spawn rtl_433 across `bands_mhz` and call `on_record(record_dict)`
    for every parsed JSON line. Blocks until the subprocess exits or
    on_record() raises."""
    cmd = [RTL_433_BIN, "-F", "json", "-M", "utc"]
    for b in bands_mhz:
        cmd += ["-f", f"{b:.3f}M"]
    print(f"[rf-bridge] spawning: {shlex.join(cmd)}", flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                on_record(rec)
            except StopIteration:
                break
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        proc.wait(timeout=2)


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
    fp = fingerprint_from_rtl433(rec)
    if not fp:
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
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    threading.Thread(target=poll_loop, daemon=True).start()
    print(f"[rf-bridge] kiosk={KIOSK_ID} bands={DEFAULT_BANDS_MHZ} api={API_URL}", flush=True)

    while not _state["shutdown"]:
        try:
            run_rtl433(DEFAULT_BANDS_MHZ, on_record)
        except FileNotFoundError:
            print(f"[rf-bridge] rtl_433 binary not found ({RTL_433_BIN}). Install with `apt install rtl-433` (Linux) or via Termux.", file=sys.stderr)
            time.sleep(15)
        except Exception as e:
            print(f"[rf-bridge] rtl_433 err: {e}", file=sys.stderr, flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()

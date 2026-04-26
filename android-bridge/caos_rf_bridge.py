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

# Watchdog — when only one resident's pendant lives on this kiosk, real
# transmissions are sparse (a press here, a press there). But the SDR's
# kernel-driven sample stream should NEVER be silent: rtl_433 emits
# stderr heartbeats and we sample noise constantly. If we haven't seen
# ANY stderr/stdout activity for this long, the SDR has hung — usually
# USB autosuspend, occasionally PLL drift on long runs. We tear rtl_433
# down and respawn. The pilot transcript captured this exact failure
# mode at the ~6-minute mark; this watchdog is the fix.
WATCHDOG_STALL_SECONDS = float(os.environ.get("CAOS_WATCHDOG_SECONDS", "90"))
HEARTBEAT_INTERVAL_SECONDS = 60.0  # log "alive" every minute so admins know the daemon hasn't crashed


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


def fingerprint_from_rtl433(record: dict) -> Optional[dict]:
    """Convert an rtl_433 JSON record into our blueprint fingerprint shape.

    rtl_433 has thousands of brand-specific decoders, and they DO NOT use
    a single field name for "the unique signal." Different brands publish
    their identifying bits under different keys:

      • Generic OOK remotes:    `code`
      • Honeywell, GE legacy:   `data`
      • Unknown OOK captures:   `raw_signal`
      • Interlogix-Security:    `raw_message`     ← the user's pendant
      • DIP-switch remotes:     `dipswitch`
      • Some doorbells:         `button`

    If NONE of those are present but the brand decoder did identify a
    `model` + `id` pair, we synthesize a stable fingerprint from those
    two — two presses of the same pendant produce the same model+id, so
    matching still works. This makes the bridge brand-agnostic: any
    pendant rtl_433 can decode, CAOS Care can pair.
    """
    pattern = (
        record.get("code")
        or record.get("data")
        or record.get("raw_signal")
        or record.get("raw_message")
        or record.get("dipswitch")
        or record.get("button")
    )
    if not pattern and record.get("model") and record.get("id") is not None:
        pattern = f"{record['model']}_{record['id']}"
    if not pattern:
        return None
    pattern = str(pattern).strip().lower()
    if pattern.startswith("0x"):
        pattern = pattern[2:]
    # Hex-only sanitize: replace anything that isn't 0-9a-f with empty.
    # When we synthesized from "Interlogix-Security_3ef83c", the dash
    # would otherwise leak through and confuse the matcher.
    sanitized = "".join(ch for ch in pattern if ch in "0123456789abcdef")
    if not sanitized:
        # Pure-text fallback — keep something so the backend can still match
        sanitized = "".join(ch.lower() for ch in pattern if ch.isalnum())[:32]

    freq_mhz = record.get("freq") or record.get("frequency") or 0.0
    return {
        "frequency_hz": int(float(freq_mhz) * 1_000_000),
        "modulation": (record.get("modulation") or "OOK").split("_")[0].upper(),
        "bit_pattern_hex": sanitized,
        "bit_length": len(sanitized) * 4,  # 4 bits per hex char
        "rssi": record.get("rssi"),
    }


def _usb_reset_sdr() -> bool:
    """Software-reset the Nooelec via the Linux USBDEVFS_RESET ioctl.

    When rtl_433 stalls (PLL drift, autosuspend leak, USB endpoint hang),
    a physical unplug/replug fixes it instantly — but that requires a human
    in the room. This issues the same hardware reset the kernel performs on
    replug, *programmatically*, so a 24/7 deployed kiosk recovers without
    anyone touching it. Returns True on success, False if we couldn't reset
    (e.g. no SDR plugged in, permissions denied).

    Used by the watchdog when it detects a stall before respawning rtl_433."""
    if not sys.platform.startswith("linux"):
        return False
    try:
        import fcntl
        # USBDEVFS_RESET ioctl number = 0x5514 (from <linux/usbdevice_fs.h>)
        USBDEVFS_RESET = 0x5514
        # Find the Nooelec by USB ID. 0bda:2838 is the Realtek RTL2838 chip
        # used in every NESDR variant we support.
        for entry in os.listdir("/sys/bus/usb/devices"):
            path = f"/sys/bus/usb/devices/{entry}"
            try:
                with open(f"{path}/idVendor") as f:
                    vid = f.read().strip()
                with open(f"{path}/idProduct") as f:
                    pid = f.read().strip()
            except FileNotFoundError:
                continue
            if vid == "0bda" and pid == "2838":
                # Resolve to /dev/bus/usb/BUS/DEV — the device file we ioctl
                with open(f"{path}/busnum") as f:
                    busnum = int(f.read().strip())
                with open(f"{path}/devnum") as f:
                    devnum = int(f.read().strip())
                dev_path = f"/dev/bus/usb/{busnum:03d}/{devnum:03d}"
                try:
                    fd = os.open(dev_path, os.O_WRONLY)
                except PermissionError:
                    print("[rf-bridge] USB reset needs permission — try running with sudo, or add yourself to the plugdev group", file=sys.stderr, flush=True)
                    return False
                try:
                    fcntl.ioctl(fd, USBDEVFS_RESET, 0)
                    print(f"[rf-bridge] USB reset issued to SDR at {dev_path}", flush=True)
                    return True
                finally:
                    os.close(fd)
        print("[rf-bridge] USB reset: no Nooelec (0bda:2838) currently enumerated", file=sys.stderr, flush=True)
        return False
    except Exception as e:
        print(f"[rf-bridge] USB reset failed: {e}", file=sys.stderr, flush=True)
        return False


def run_rtl433(bands_mhz: list[float], on_record):
    """Spawn rtl_433 across `bands_mhz` and call `on_record(record_dict)`
    for every parsed JSON line. Blocks until the subprocess exits, the
    watchdog detects a stall, or on_record() raises.

    Stall detection: rtl_433 normally writes stderr lines (sample-rate,
    block-size, occasional warnings) every few seconds even when no RF
    is being captured. If both stdout AND stderr are silent for
    WATCHDOG_STALL_SECONDS, the SDR has hung — kill the process so the
    outer main() loop respawns it. This recovers from USB autosuspend
    automatically (the respawn re-opens the device, waking it up)."""
    cmd = [RTL_433_BIN, "-F", "json", "-M", "utc"]
    for b in bands_mhz:
        cmd += ["-f", f"{b:.3f}M"]
    print(f"[rf-bridge] spawning: {shlex.join(cmd)}", flush=True)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # line-buffered — events stream as they happen, not in chunks
    )

    # Activity tracking: any line on either stream resets the clock.
    last_activity = [time.monotonic()]
    last_heartbeat = [time.monotonic()]

    def _stderr_drain():
        # rtl_433 talks to us on stderr (PLL warnings, "Allocating buffers",
        # "Found tuner", etc.). Print EVERYTHING — admins need to see startup
        # messages to know rtl_433 actually launched cleanly. Without this,
        # a stuck SDR or libusb error shows as "no output at all" which is
        # impossible to debug.
        try:
            for line in proc.stderr:
                last_activity[0] = time.monotonic()
                line = line.rstrip()
                if line:
                    print(f"[rtl_433] {line}", file=sys.stderr, flush=True)
        except Exception:
            pass

    threading.Thread(target=_stderr_drain, daemon=True).start()

    try:
        while True:
            # Use the stdout pipe with a small read timeout so we can poll
            # the watchdog. select() on a subprocess pipe is portable on Linux.
            import select
            if proc.poll() is not None:
                # Process exited on its own — let the outer loop respawn
                break
            ready, _, _ = select.select([proc.stdout], [], [], 1.0)
            now = time.monotonic()

            # Heartbeat — proves to admins that the daemon is alive even
            # when the resident hasn't pressed the pendant for hours
            if now - last_heartbeat[0] >= HEARTBEAT_INTERVAL_SECONDS:
                print(f"[rf-bridge] heartbeat — listening on {','.join(f'{b}M' for b in bands_mhz)}", flush=True)
                last_heartbeat[0] = now

            # Stall watchdog — SDR went silent, kill it so the outer loop respawns.
            # Before respawning, issue a USB reset to the Nooelec so the
            # restart starts from a clean hardware state. This eliminates
            # the manual "unplug/replug" recovery step a human used to do.
            if now - last_activity[0] > WATCHDOG_STALL_SECONDS:
                print(
                    f"[rf-bridge] WATCHDOG: rtl_433 silent for {WATCHDOG_STALL_SECONDS:.0f}s "
                    "— issuing USB reset and restarting...",
                    file=sys.stderr,
                    flush=True,
                )
                # Tear down rtl_433 first so it releases the SDR handle,
                # otherwise the USB reset will fail with -EBUSY.
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                # Small grace period for the kernel to release the device
                time.sleep(0.5)
                _usb_reset_sdr()
                # Another grace period for the SDR to enumerate cleanly
                time.sleep(2.0)
                break

            if not ready:
                continue
            line = proc.stdout.readline()
            if not line:
                # EOF — process is closing
                break
            last_activity[0] = now
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
        try:
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


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
    # Always log the raw arrival so admins can see presses landing in real
    # time. This was missing before and made it impossible to tell whether
    # rtl_433 was capturing nothing vs. capturing but the bridge was dropping.
    model = rec.get("model") or "?"
    rid = rec.get("id", "?")
    freq = rec.get("freq", "?")
    print(f"[rf-bridge] decoded: model={model} id={rid} freq={freq}MHz", flush=True)

    fp = fingerprint_from_rtl433(rec)
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

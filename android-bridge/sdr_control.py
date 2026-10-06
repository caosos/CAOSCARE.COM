"""rtl_433 process control for the RF bridge: spawn rtl_433, read its JSON
records, watch for a stalled SDR, and reset the SDR over USB.

Moved out of caos_rf_bridge.py (2026-10-05) when the restart backoff was
added; the watchdog and USB-reset behaviour are unchanged. The restart
policy itself lives in rf_restart_policy.py.
"""
from __future__ import annotations

import json
import os
import select
import shlex
import subprocess
import sys
import threading
import time
from typing import Optional

from rf_restart_policy import HEALTHY_RUN_SECONDS, RunOutput, RunResult

RTL_433_BIN = os.environ.get("RTL_433", "rtl_433")

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


def usb_reset_sdr() -> bool:
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


def run_rtl433(bands_mhz: list[float], on_record, stop: Optional[threading.Event] = None,
               verbose: bool = True) -> RunResult:
    """Spawn rtl_433 across `bands_mhz` and call `on_record(record_dict)`
    for every parsed JSON line. Blocks until the subprocess exits, the
    watchdog detects a stall, on_record() raises StopIteration, or `stop`
    is set. Returns a RunResult the restart supervisor uses to decide the
    next spawn (rf_restart_policy.py).

    Stall detection: rtl_433 normally writes stderr lines (sample-rate,
    block-size, occasional warnings) every few seconds even when no RF
    is being captured. If both stdout AND stderr are silent for
    WATCHDOG_STALL_SECONDS, the SDR has hung — kill the process, reset the
    USB device, and let the supervisor respawn it. This recovers from USB
    autosuspend automatically (the respawn re-opens the device, waking it up).

    verbose=False (set while rtl_433 keeps failing): the spawn line and
    rtl_433's output are held back and returned in RunResult.output_tail
    instead of printed, so a missing SDR does not print the same banner on
    every retry. If the run turns healthy, the held output is printed."""
    stop = stop or threading.Event()
    # "-M level" is what actually makes rtl_433 report per-record signal
    # strength (rssi/snr/noise, dB) - without it every record's "rssi" key
    # is simply absent, which is why pairing/events always showed rssi as
    # null despite the fingerprint schema having a field for it
    # (2026-09-06, real "I want signal strength as pairing data" request).
    cmd = [RTL_433_BIN, "-F", "json", "-M", "utc", "-M", "level"]
    for b in bands_mhz:
        cmd += ["-f", f"{b:.3f}M"]
    out = RunOutput(verbose, f"[rf-bridge] spawning: {shlex.join(cmd)}")
    started = time.monotonic()
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
    records = 0
    stalled = False

    def _stderr_drain():
        # rtl_433 talks to us on stderr (PLL warnings, "Allocating buffers",
        # "Found tuner", etc.). Admins need its startup messages to know
        # rtl_433 launched cleanly; RunOutput prints them, or holds them back
        # while the supervisor is quiet (repeated identical failures).
        try:
            for line in proc.stderr:
                last_activity[0] = time.monotonic()
                line = line.rstrip()
                if line:
                    out.emit(line)
        except Exception:
            pass

    drain = threading.Thread(target=_stderr_drain, daemon=True)
    drain.start()

    def _handle(line: str) -> bool:
        """Parse one stdout line; True means on_record asked to stop."""
        nonlocal records
        line = line.strip()
        if not line.startswith("{"):
            return False
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return False
        records += 1
        try:
            on_record(rec)
        except StopIteration:
            return True
        return False

    try:
        while not stop.is_set():
            if proc.poll() is not None:
                # Exited on its own: handle anything it printed before exiting,
                # then let the supervisor decide when to respawn.
                for line in proc.stdout:
                    if _handle(line):
                        break
                break
            ready, _, _ = select.select([proc.stdout], [], [], 1.0)
            now = time.monotonic()
            if not out.live and (records or now - started >= HEALTHY_RUN_SECONDS):
                out.go_live()

            # Heartbeat — proves to admins that the daemon is alive even
            # when the resident hasn't pressed the pendant for hours
            if now - last_heartbeat[0] >= HEARTBEAT_INTERVAL_SECONDS:
                print(f"[rf-bridge] heartbeat — listening on {','.join(f'{b}M' for b in bands_mhz)}", flush=True)
                last_heartbeat[0] = now

            # Stall watchdog — SDR went silent, kill it so the supervisor respawns.
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
                stalled = True
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
                stop.wait(0.5)
                usb_reset_sdr()
                # Another grace period for the SDR to enumerate cleanly
                stop.wait(2.0)
                break

            if not ready:
                continue
            line = proc.stdout.readline()
            if not line:
                # EOF — process is closing
                break
            last_activity[0] = now
            if _handle(line):
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
        drain.join(timeout=1.0)

    if stalled:
        reason = f"stalled: no output for {WATCHDOG_STALL_SECONDS:.0f}s"
    elif out.last_line:
        reason = f"{out.last_line} (exit {proc.returncode})"
    else:
        reason = f"exited with code {proc.returncode}"
    return RunResult(duration=time.monotonic() - started, records=records, stalled=stalled,
                     stopped=stop.is_set(), reason=reason, output_tail=out.tail())

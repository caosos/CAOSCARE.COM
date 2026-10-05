"""RF bridge rtl_433 restart backoff (no-SDR log storm, 2026-10-05).

Deterministic: policy tests use a fake clock and a fake stop event that
records waits instead of sleeping. Process tests run small stand-in rtl_433
shell scripts. Nothing here touches a real SDR, a backend, or the running
bridge's state directory (HOME is a temp dir wherever the bridge is loaded).
"""
import itertools
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


BRIDGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

import sdr_control  # noqa: E402
from rf_restart_policy import RestartSupervisor, RunResult, run_forever  # noqa: E402

NO_SDR_REASON = "No supported devices found. (exit 2)"
NO_SDR_BANNER = """echo 'rtl_433 version 21.12 (2021-12-14) inputs file rtl_tcp RTL-SDR SoapySDR' >&2
echo 'Registered 176 out of 207 device decoding protocols' >&2
echo 'No supported devices found.' >&2
"""
PRESS = ('{"time":"2026-10-05 12:00:00","model":"Interlogix-Security","subtype":"keyfob",'
         '"id":"3ef83c","battery_ok":1,"switch5":"CLOSED","rssi":-0.1}')


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeStop:
    """Stands in for threading.Event: records each wait and advances the
    fake clock instead of sleeping; sets itself after `limit` waits."""

    def __init__(self, clock, limit):
        self.clock, self.limit = clock, limit
        self.waits, self._set = [], False

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    def wait(self, seconds):
        self.waits.append(seconds)
        self.clock.t += seconds
        if len(self.waits) >= self.limit:
            self._set = True
        return self._set


def no_sdr():
    return RunResult(duration=0.1, reason=NO_SDR_REASON,
                     output_tail=["[rf-bridge] spawning: rtl_433 -F json",
                                  "[rtl_433] No supported devices found."])


def drive(results, limit, status_interval=300.0):
    """Run the real spawn loop against scripted run results."""
    clock, logs, verbose_flags = Clock(), [], []
    stop = FakeStop(clock, limit)
    sup = RestartSupervisor(log=logs.append, clock=clock, status_interval=status_interval)
    it = iter(results)

    def run_once(verbose):
        verbose_flags.append(verbose)
        r = next(it)
        clock.t += r.duration
        if r.stopped:
            stop.set()
        return r

    run_forever(run_once, stop, sup)
    return stop.waits, logs, verbose_flags


# --- policy -----------------------------------------------------------------

def test_immediate_failures_back_off_and_cap_at_60s():
    waits, _, _ = drive(itertools.repeat(no_sdr()), limit=9)
    assert waits == [1, 2, 5, 10, 30, 60, 60, 60, 60]


def test_failed_start_without_any_output_also_backs_off():
    missing = RunResult.failed("rtl_433 binary not found (rtl_433)")
    waits, _, _ = drive(itertools.repeat(missing), limit=3)
    assert waits == [1, 2, 5]


def test_healthy_run_resets_the_backoff():
    healthy = RunResult(duration=45.0, reason="exited with code 0")
    waits, logs, _ = drive([no_sdr(), no_sdr(), no_sdr(), healthy, no_sdr(), no_sdr()], limit=5)
    # No wait after the healthy run; the next failure starts again at 1 s.
    assert waits == [1, 2, 5, 1, 2]
    assert any("recovered after 3 failed start(s)" in line for line in logs)


def test_short_run_that_decoded_a_record_is_healthy():
    decoded = RunResult(duration=0.5, records=1, reason="exited with code 0")
    waits, _, _ = drive([no_sdr(), no_sdr(), decoded, no_sdr()], limit=3)
    assert waits == [1, 2, 1]


def test_stall_watchdog_restart_stays_immediate():
    # A run the watchdog killed after 90 s of silence lived long enough to
    # count as healthy, so the respawn is immediate, as before.
    stalled = RunResult(duration=92.5, stalled=True, reason="stalled: no output for 90s")
    waits, _, _ = drive([stalled, stalled, no_sdr()], limit=1)
    assert waits == [1]


def test_quiet_while_failing_and_verbose_again_after_recovery():
    healthy = RunResult(duration=45.0)
    _, _, verbose_flags = drive([no_sdr(), no_sdr(), healthy, no_sdr()], limit=3)
    assert verbose_flags == [True, False, False, True]


def test_failure_logged_once_then_periodic_status_not_per_spawn():
    waits, logs, _ = drive(itertools.repeat(no_sdr()), limit=1000)
    assert len(waits) == 1000
    # The rtl_433 output and the failure line appear once, not per spawn.
    assert logs.count("[rtl_433] No supported devices found.") == 1
    assert sum("rtl_433 failed after" in line for line in logs) == 1
    # Then one status line per 300 s of failing (~59,700 s here).
    status = [line for line in logs if "still failing" in line]
    assert 190 <= len(status) <= 200
    assert "last: No supported devices found. (exit 2)" in status[-1]
    assert len(logs) < 210  # vs. 1000 spawns, ~9 lines each, before the fix


def test_new_failure_reason_is_logged_in_full():
    other = RunResult(duration=0.1, reason="usb_claim_interface error -6 (exit 2)",
                      output_tail=["[rtl_433] usb_claim_interface error -6"])
    _, logs, _ = drive([no_sdr(), no_sdr(), other, other], limit=4)
    assert logs.count("[rtl_433] usb_claim_interface error -6") == 1
    assert sum("rtl_433 failed after" in line for line in logs) == 2


def test_shutdown_interrupts_a_backoff_wait_promptly():
    stop = threading.Event()
    first_run_done = threading.Event()
    sup = RestartSupervisor(schedule=(60.0,), log=lambda m: None)

    def run_once(verbose):
        first_run_done.set()
        return no_sdr()

    t = threading.Thread(target=run_forever, args=(run_once, stop, sup))
    t.start()
    assert first_run_done.wait(2)
    time.sleep(0.2)  # now inside the 60 s backoff wait
    started = time.monotonic()
    stop.set()
    t.join(2)
    assert not t.is_alive()
    assert time.monotonic() - started < 0.5


# --- rtl_433 process --------------------------------------------------------

def stub(tmp_path, name, body):
    p = tmp_path / name
    p.write_text("#!/bin/sh\n" + body)
    p.chmod(0o755)
    return str(p)


def test_missing_sdr_run_is_reported_as_a_fast_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(sdr_control, "RTL_433_BIN", stub(tmp_path, "rtl_433", NO_SDR_BANNER + "exit 2\n"))
    quiet = sdr_control.run_rtl433([319.5], lambda rec: None, verbose=False)
    assert not quiet.healthy and quiet.records == 0 and quiet.duration < 5
    assert quiet.reason == NO_SDR_REASON
    assert quiet.output_tail[0].startswith("[rf-bridge] spawning:")
    assert "[rtl_433] No supported devices found." in quiet.output_tail
    # Verbose runs print as they go, so nothing is held back to print again.
    assert sdr_control.run_rtl433([319.5], lambda rec: None, verbose=True).output_tail == []


def test_decoded_records_still_reach_on_record(tmp_path, monkeypatch):
    body = f"echo 'Found 1 device(s)' >&2\necho '{PRESS}'\necho 'not json'\necho '{PRESS}'\nexit 0\n"
    monkeypatch.setattr(sdr_control, "RTL_433_BIN", stub(tmp_path, "rtl_433", body))
    seen = []
    result = sdr_control.run_rtl433([319.5], seen.append, verbose=False)
    assert [r["id"] for r in seen] == ["3ef83c", "3ef83c"]
    assert result.records == 2 and result.healthy


def test_decoded_record_is_posted_as_a_live_rf_event(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))  # keep the bridge off the real state dir
    sys.modules.pop("caos_rf_bridge", None)
    import caos_rf_bridge as bridge
    posts = []
    monkeypatch.setattr(bridge, "_post", lambda path, payload: posts.append((path, payload)) or {})
    monkeypatch.setattr(bridge, "next_sequence", lambda: 41)
    monkeypatch.setattr(bridge, "DEFAULT_BANDS_MHZ", [319.5])
    monkeypatch.setitem(bridge._state, "active_capture", None)
    body = f"echo '{PRESS}'\nexit 0\n"
    monkeypatch.setattr(sdr_control, "RTL_433_BIN", stub(tmp_path, "rtl_433", body))
    sdr_control.run_rtl433([319.5], bridge.on_record, verbose=True)
    assert len(posts) == 1
    path, payload = posts[0]
    assert path == "/api/rf/event" and payload["sequence"] == 41
    assert payload["fingerprint"]["frequency_hz"] == 319_500_000
    assert payload["fingerprint"]["decoded"]["switch5"] == "CLOSED"


def test_stop_ends_a_running_rtl433_promptly(tmp_path, monkeypatch):
    monkeypatch.setattr(sdr_control, "RTL_433_BIN",
                        stub(tmp_path, "rtl_433", "echo 'Found 1 device(s)' >&2\nexec sleep 30\n"))
    stop, out = threading.Event(), {}
    t = threading.Thread(target=lambda: out.setdefault(
        "r", sdr_control.run_rtl433([319.5], lambda rec: None, stop=stop)))
    t.start()
    time.sleep(0.5)
    started = time.monotonic()
    stop.set()
    t.join(5)
    assert not t.is_alive() and out["r"].stopped
    assert time.monotonic() - started < 3


def test_stall_watchdog_still_kills_and_resets_the_sdr(tmp_path, monkeypatch):
    resets = []
    monkeypatch.setattr(sdr_control, "WATCHDOG_STALL_SECONDS", 1.0)
    monkeypatch.setattr(sdr_control, "usb_reset_sdr", lambda: resets.append(1) or True)
    monkeypatch.setattr(sdr_control, "RTL_433_BIN", stub(tmp_path, "rtl_433", "exec sleep 30\n"))
    result = sdr_control.run_rtl433([319.5], lambda rec: None)
    assert result.stalled and resets == [1]
    assert result.reason == "stalled: no output for 1s"


# --- the bridge process, end to end -----------------------------------------

def test_bridge_without_sdr_does_not_spin_and_exits_on_sigterm(tmp_path):
    spawns = tmp_path / "spawns"
    rtl = stub(tmp_path, "rtl_433", f"echo x >> '{spawns}'\n" + NO_SDR_BANNER + "exit 2\n")
    env = dict(os.environ, HOME=str(tmp_path), RTL_433=rtl, CAOS_BANDS="319.5",
               CAOS_API_URL="http://127.0.0.1:9", CAOS_KIOSK_ID="kio_test")
    env.pop("CAOS_RF_SECRET", None)
    proc = subprocess.Popen([sys.executable, str(BRIDGE_DIR / "caos_rf_bridge.py")], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(4.0)
    proc.send_signal(signal.SIGTERM)
    started = time.monotonic()
    output, _ = proc.communicate(timeout=10)
    assert time.monotonic() - started < 2, "SIGTERM did not interrupt the backoff wait"
    assert proc.returncode == 0
    # Spawns at ~0 s, ~1 s and ~3 s (backoff 1, 2, 5 s). Before the fix this
    # was hundreds of spawns in 4 s.
    assert 2 <= len(spawns.read_text().splitlines()) <= 4
    assert output.count("[rtl_433] No supported devices found.") == 1
    assert output.count("spawning:") == 1
    assert output.count("rtl_433 failed after") == 1
    assert "[rf-bridge] shutting down" in output

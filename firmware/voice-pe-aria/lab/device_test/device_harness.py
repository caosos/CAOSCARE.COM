"""Physical Voice PE test harness - records wake detections + operator trials.

Reads the ESPHome log stream of the test device (stdin, or runs
`esphome logs <yaml>` itself) and appends every micro_wake_word detection to a
CSV with a timestamp, the wake word, its probabilities and the trial that was
active. The operator types commands on the keyboard:

  t <trial-id> [notes...]   start a trial (e.g. "t A-1m-seated-quiet-03 speaker=R2")
  m                         mark: the speaker just said the wake phrase once
  e                         end the current trial
  q                         quit

Each 'm' without a detection within 3 s is a MISSED wake; each detection
without an 'm' within the previous 3 s is a FALSE wake. Soak tests use a trial
with no 'm' marks at all - every detection is a false wake.

usage:
  python device_harness.py --yaml ../caoscare-voice-pe.yaml --out runs/session1.csv
  esphome logs ../caoscare-voice-pe.yaml | python device_harness.py --stdin --out ...
Nothing here flashes or reconfigures the device; it only reads its log.
"""
import argparse
import csv
import datetime
import re
import subprocess
import sys
import threading
import time

DETECT = re.compile(r"micro_wake_word.*Detected '([^']+)'(?:.*?average probability (?:is )?([0-9.]+))?"
                    r"(?:.*?max probability (?:is )?([0-9.]+))?", re.I)
MATCH_S = 3.0


def now():
    return datetime.datetime.now().isoformat(timespec="milliseconds")


class Session:
    def __init__(self, out):
        self.f = open(out, "a", newline="")
        self.w = csv.writer(self.f)
        if self.f.tell() == 0:
            self.w.writerow(["time", "event", "trial", "wake_word", "avg_prob", "max_prob", "notes"])
        self.trial, self.marks, self.lock = None, [], threading.Lock()

    def row(self, *r):
        with self.lock:
            self.w.writerow([now(), *r])
            self.f.flush()

    def detection(self, word, avg, mx):
        t = time.time()
        with self.lock:
            hit = next((m for m in self.marks if 0 <= t - m < MATCH_S), None)
            if hit is not None:
                self.marks.remove(hit)
        self.row("TRUE_WAKE" if hit is not None else "FALSE_WAKE", self.trial or "", word, avg, mx, "")
        print(f"  detection: {word} avg={avg} max={mx} -> {'TRUE' if hit is not None else 'FALSE'}", flush=True)

    def sweep(self):
        while True:
            time.sleep(0.5)
            t = time.time()
            with self.lock:
                missed = [m for m in self.marks if t - m >= MATCH_S]
                self.marks = [m for m in self.marks if t - m < MATCH_S]
            for _ in missed:
                self.row("MISSED_WAKE", self.trial or "", "", "", "", "")
                print("  MISSED", flush=True)


def read_log(stream, s):
    for line in stream:
        m = DETECT.search(line)
        if m:
            s.detection(m.group(1), m.group(2) or "", m.group(3) or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaml")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    s = Session(a.out)
    threading.Thread(target=s.sweep, daemon=True).start()
    if a.stdin:
        threading.Thread(target=read_log, args=(sys.stdin, s), daemon=True).start()
        cmds = open("/dev/tty")
    else:
        p = subprocess.Popen(["esphome", "logs", a.yaml], stdout=subprocess.PIPE, text=True)
        threading.Thread(target=read_log, args=(p.stdout, s), daemon=True).start()
        cmds = sys.stdin
    print("commands: t <trial> [notes] | m | e | q")
    for line in cmds:
        parts = line.strip().split(maxsplit=2)
        if not parts:
            continue
        if parts[0] == "t":
            s.trial = parts[1] if len(parts) > 1 else f"trial-{int(time.time())}"
            s.row("TRIAL_START", s.trial, "", "", "", parts[2] if len(parts) > 2 else "")
        elif parts[0] == "m":
            with s.lock:
                s.marks.append(time.time())
            s.row("SPOKEN", s.trial or "", "", "", "", "")
        elif parts[0] == "e":
            s.row("TRIAL_END", s.trial or "", "", "", "", "")
            s.trial = None
        elif parts[0] == "q":
            break


if __name__ == "__main__":
    main()

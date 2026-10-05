# RF bridge log audit and rotation plan (RQ-008)

**Host:** the central EliteDesk. **Date:** 2026-10-05 (measured ~02:00–02:20 UTC). **By:** Claude Code (Opus 5.5), Agent Five.
**Scope:** read-only. Nothing was truncated, deleted, restarted, reconfigured or installed. Companion to `2026-10-04-elitedesk-storage-audit.md` (Phase 2 item H).

## Findings

| Question | Answer (evidence) |
|---|---|
| Process writing it | `python3 android-bridge/caos_rf_bridge.py`, run from the `~/CAOSCARE.COM` checkout. Started 2026-09-06 12:31 CDT and running ever since. The bridge itself is running now; `rtl_433`, which it starts, is not. |
| Exact path | `/tmp/claude-1000/-home-caoscare-1-CAOSCARE-COM/7fe37737-8dd2-4d3d-99ac-83c929f2d3c3/scratchpad/rf_bridge2.log`, an agent session's scratch folder. stdout **and** stderr both point at it. |
| How it was started | By hand from an agent shell, with `>` redirection; the parent has since exited and the process now belongs to init. It is **not** a systemd system or user service (none exists for it). There is no cron entry. Configuration comes only from its environment (API URL, kiosk id, band 319.5 MHz). |
| Growth, from evidence | 2,760,476 bytes in a measured 60.0 s = **3.97 GB/day**. Size at 02:04 UTC: 2,638,842,363 bytes (2.64 GB). |
| What fills it | Since ~2026-10-04 11:22 UTC, `rtl_433` starts, prints ~1.2 KB of startup text, reports `No supported devices found` (the SDR is not enumerated, as RQ-004 also recorded), exits, and the bridge starts it again with no delay. 3,570,043 spawns in total. Also 22,906 watchdog USB resets and 23,713 heartbeats. |
| When it started | The last real decode is at byte 77,762,987. This bridge's last event in MongoDB `rf_events` was received 2026-10-04 11:22:49 UTC. The 2.56 GB written after that point, at 3.97 GB/day, is ~15.5 h, which agrees with that time. |
| Unique evidence? | **A little, at the start of the file.** The first ~78 MB holds 3,552 `decoded:` lines from two Interlogix-Security pendants (ids `3e043c` ×1,952, `3ef83c` ×1,600), plus POST errors (11 "max retries", 1 read timeout, 2 conflicts). MongoDB has 3,491 events from this kiosk since the process started, so about 61 decodes exist only here. The log has **no timestamps**, so those lines can't be dated exactly. The loop section has no evidence value beyond its rate and pattern. |
| Duplicated elsewhere? | The decodes are mostly duplicated as structured records in MongoDB `rf_events` (5,123 from this kiosk; first 2026-08-29, last 2026-10-04 11:22 UTC). There is no other copy of the log file. |
| Logrotate | It does not know about the file. Nothing in `/etc/logrotate.d` matches it, and there is no user logrotate setup. |
| Reopen / SIGHUP | **Not supported.** The code handles only SIGINT and SIGTERM (graceful shutdown). It logs with `print()` to file descriptors it inherited, so it cannot reopen the log. **SIGHUP's default action would terminate the bridge** — never send it. |
| How the file is open | Write-only **without `O_APPEND`**. |
| Other exposure | `/tmp` is on the root disk, and systemd-tmpfiles clears it at boot. A reboot would delete the log (and its ~61 unique decodes) and also stop the bridge, since nothing restarts it. |

## Truncation vs rotation

| Method | What happens here | Verdict |
|---|---|---|
| `truncate -s 0` / `: >` | Blocks are freed, but the bridge keeps writing at its old ~2.6 GB offset because the file isn't in append mode. The file becomes sparse: its apparent size keeps growing, and copying or reading it hits a large run of NUL bytes. Done before archiving, it loses the unique decodes. | Not recommended |
| `mv` (rename) + new file | The bridge keeps writing to the renamed file (same inode). Nothing is freed and the growth continues. | Does nothing |
| logrotate `copytruncate` | Same problem as truncation (no append mode), plus a full 2.6 GB copy first. | Not recommended |
| Archive, then restart the bridge with a managed log, then remove the old file | The old descriptor closes, the space is actually freed, and the new log can be rotated cleanly. | **Recommended** (needs approval: restart) |

## Proposed plan (each step needs Michael's approval; nothing done yet)

**R1 — Preserve (no runtime change; safe to run first)**

```bash
LOG=/tmp/claude-1000/-home-caoscare-1-CAOSCARE-COM/7fe37737-8dd2-4d3d-99ac-83c929f2d3c3/scratchpad/rf_bridge2.log
mkdir -p ~/rf_log_archive
gzip -6 -c "$LOG" > ~/rf_log_archive/rf_bridge2-2026-09-06_to-$(date -u +%F).log.gz   # ~30 s; ~13 MB
gzip -t ~/rf_log_archive/rf_bridge2-*.log.gz && sha256sum ~/rf_log_archive/rf_bridge2-*.log.gz > ~/rf_log_archive/SHA256SUMS
```

- Measured compression is about 200:1: an 80 MB decode slice became 0.46 MB, and a 100 MB loop slice became 0.49 MB.
- Reading the file doesn't disturb the writer.
- Do this before any reboot.

**R2 — Stop the growth.** Any one of these works; (a) or (c) removes the cause:
- (a) **Restore the SDR** (reseat it; check USB enumeration). The loop stops by itself and normal logging is a few MB/day. Hardware and RF lane.
- (b) **Restart the bridge under a systemd user service** with `StandardOutput=journal` / `StandardError=journal`. journald then handles rotation, size caps and rate limiting, with no logrotate and no file in `/tmp`. Example caps: `SystemMaxUse`/`MaxRetentionSec` in the user journal settings.
  - Alternative: `StandardOutput=append:~/.local/state/caos-bridge/rf_bridge.log`, with a user logrotate entry (`daily`, `rotate 14`, `maxsize 100M`, `compress`, `copytruncate`). copytruncate is safe once the file is in append mode.
  - The restart interrupts pendant reception for a few seconds. The RF lane's runtime owner and Michael must agree on a window.
- (c) **Code fix (RF lane):** back off when `rtl_433` exits immediately (for example 2 s doubling to 60 s), and log "no SDR" once per state change instead of every spawn. This cuts the loop's output from ~4 GB/day to a few KB/day and removes ~38 process spawns a second.

**R3 — Reclaim.** Only after R1 is verified **and** the bridge is no longer holding the old file: `ls -l /proc/[0-9]*/fd 2>/dev/null | grep -c rf_bridge2.log` must print 0. Then:

```bash
rm "$LOG"
```

**Retention (proposed):**
- Keep the R1 archive (~13 MB) at least until Pilot 1 review, or 90 days, whichever is later; it holds the only copy of ~61 decodes.
- Going forward: 14 days or 500 MB of bridge log, whichever comes first.
- MongoDB `rf_events` stays the system of record for RF events; it is unaffected by any of this.

**Expected reclaimed disk:** the file's size on the day of R3 (2.64 GB at 02:04 UTC, plus ~3.97 GB per day until R2), minus ~13 MB for the archive. Once R2 is in place, the ~4 GB/day ongoing growth stops.

## Risks

- Leaving it alone fills the disk: at 51 GB free, together with wake-lab growth, roughly 10 days.
- A reboot deletes the log (unique evidence) and silently stops RF reception.
- Truncation: a sparse, misleading file, and lost evidence if it isn't archived first.
- A restart: a few seconds without pendant reception — none at all while the SDR is missing, as now.
- SIGHUP kills the bridge.

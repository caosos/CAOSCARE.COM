# Home Assistant VM recovery and autostart (Pilot blocker)

Owner: Agent Four, Round 5. Branch `ops/ha-vm-recovery` from integration
`81a4f92`. Host: EliteDesk `caoscare1-hp-elitedesk`. Scope: the
`caoscare-homeassistant` libvirt domain only. No CAOSCare code, no Linode,
no qcow2 recreation or replacement.

## 1. Audit (read-only, 2026-10-04 ~19:50–20:00 CDT)

### Domain configuration (`virsh dominfo` / `dumpxml`)
| Item | Value |
|---|---|
| Name / UUID | `caoscare-homeassistant` / `814dd584-dd09-4468-a518-70159e031bcc` |
| State | `shut off (crashed)` |
| Memory | 4194304 KiB (4 GiB), max = current |
| vCPUs | 2 (static), `host-passthrough` |
| Firmware / machine | EFI, `pc-i440fx-jammy` |
| Disk | `/var/lib/libvirt/images/caoscare-homeassistant.qcow2`, virtio, qcow2 |
| NIC | virtio on libvirt network `default`, MAC `52:54:00:09:90:eb` |
| Autostart | **enabled** (already) |
| `on_poweroff` / `on_reboot` / `on_crash` | destroy / restart / destroy |
| Snapshots | none |
| Managed save | no |

### Why it is off — proven
Kernel journal, 2026-10-03 20:19:36 CDT:
`oom-kill: ... global_oom, task_memcg=/machine.slice/machine-qemu-1-caoscare-homeassistant.scope ... Killed process 1669 (qemu-system-x86) total-vm:8673128kB, anon-rss:2761772kB`
followed by `systemd: machine-qemu-1-caoscare-homeassistant.scope: A process of this unit has been killed by the OOM killer` and `Machine qemu-1-caoscare-homeassistant terminated`.

- It was a **host-wide (global) OOM**, not a guest failure. From 19:42 the
  kernel killed processes repeatedly under memory pressure while `cc1plus`
  (a native compile — the firmware build) and Chrome were running.
- qemu was the largest process on the host (~2.7 GB resident + ~1.2 GB in
  swap, `oom_score_adj 0`), so it was eventually chosen.
- More global OOMs followed on 2026-10-04 02:20 (a ~3–4 GB `python`
  process, killed repeatedly).
- The VM had been up since the host boot (~28 h of CPU time consumed).
- `on_crash=destroy` and libvirt autostart do not restart a domain whose
  qemu process was killed; autostart only runs when libvirtd starts (host
  boot). So the VM stays off until someone starts it.

### Disk health
`qemu-img check`: **no errors**; 32 GiB virtual, 8.4 GiB on disk, 26%
allocated, 6.5% fragmented. Last write 2026-10-03 20:19 (the kill). Host `/`
has 55 GB free.

### Host resources (at audit time)
- RAM 14 GiB total; 9.3 GiB available; 8 CPUs.
- Swap: 2 GiB swapfile, **fully used** (left over from the OOM period).
- No compile/training job running. Largest processes: dev frontend servers
  (~0.7 / 0.4 / 0.3 GB), several Claude sessions (0.3–0.5 GB each), mongod
  (~0.25 GB).

### Network / dependencies
- libvirt network `default`: active, autostart yes; fixed DHCP reservation
  `52:54:00:09:90:eb → 192.168.122.137`.
- CAOSCare backends (`CAOSCARE-INTEGRATION`, `CAOSCARE.COM`,
  `CAOSCARE-ADMIN`) all use `HA_BASE_URL=http://192.168.122.137:8123` — the
  fixed address, so they depend on that reservation (present).
- LAN access to 8123 uses host iptables DNAT/MASQUERADE rules (present now,
  **runtime-only**, lost on host reboot — recorded 2026-08-02 / 09-05).
  CAOSCare itself does not need them.
- Inside the VM, the extra IPv6 address used for the Midea AC's Matter
  path (2026-09-05) was never persisted; a VM restart drops it.

### Anything requiring the VM to stay off
None found. The board records the VM as crashed, not deliberately stopped.
Claude Two's wake-training batches are not running now; the 10-03 OOM
happened during a heavy native build.

## 2. Design — smallest safe fix

1. **Start the existing domain** (`virsh start`). No XML change: autostart
   is already enabled, so a clean host reboot will start it.
2. Verify: HA reaches running state, 8123 answers, CAOSCare's own
   `device_adapters.ha_health()` connects with the existing token, and the
   existing configuration (entities, integrations, config entries) is
   unchanged against a baseline.
3. Verify restart behavior without a host reboot:
   - HA core restart (`homeassistant.restart` service) → back with the same
     configuration.
   - VM graceful shutdown + start (`virsh shutdown` / `start`) → back with
     the same configuration.
4. **Host reboot test is NOT done here** — it needs Michael's approval.

### Not fixed by this design (proposed, needs approval)
The VM will not come back by itself after another OOM kill, which is the
failure that happened. Evidence-based proposals, smallest first:
- **P1 — protect qemu from the OOM killer**: a libvirt `qemu` hook that sets
  `oom_score_adj` (e.g. −800) on the domain's qemu process at start, so a
  runaway build or browser is killed first. Host config only; reversible by
  deleting the hook.
- **P2 — crash restart without SSH**: a root systemd timer (1 min) that runs
  `virsh start` only when the domain state is `shut off (crashed)`; a
  deliberate shutdown (`shutdown`/`destroyed`) is left alone.
- **P3 — keep heavy builds from taking the host**: run firmware/wake builds
  under a memory cap (`systemd-run --user -p MemoryMax=…`) — a process rule
  for the build lane, not a host change.
- VM size: no change proposed. The guest used ~2.7 GB of its 4 GiB; the
  OOM came from host pressure, not from the VM's allocation.

## 3. Receipts

All times CDT, 2026-10-04. Commands run as `caoscare-1` via
`virsh -c qemu:///system`. No domain XML, qcow2, network, firewall or
Home Assistant configuration was changed. Design committed first (`4d19963`).

**R1 — pre-start state (20:01:08).** `domstate --reason`: `shut off
(crashed)`; autostart `enable`; 4 GiB / 2 vCPU. qcow2 9 023 062 016 bytes,
mtime 2026-10-03 20:19:28, sha256 prefix `88f62da3c548840c`. Host: 9.1 GiB
available, swap 2040/2047 MiB used.

**R2 — start existing VM (20:01:58).** `virsh start caoscare-homeassistant`
→ `running (booted)`. Autostart unchanged (`enable`).

**R3 — HA operational (20:02:48–20:02:55).** `GET :8123/manifest.json` 200
~50 s after start. With the CAOSCare `HA_TOKEN` (not printed):
`/api/config` state `RUNNING`, version 2026.7.4, 166 components, tz
America/Chicago; 68 entities. Room 214 entities present:
`light.smart_multicolor_bulb` off, `light.smart_multicolor_bulb_2` on,
`climate.bedroom_midea_ac` unavailable (unavailable since 2026-09-05; not
changed by this work). No device command was sent.

**R4 — CAOSCare reaches HA.** `device_adapters.ha_health()` from
`~/CAOSCARE-INTEGRATION/backend` with its own `.env`:
`{'status': 'connected', 'base_url': 'http://192.168.122.137:8123',
'entity_count': 68}`. :8092 `/api/health` ok.

**R5 — baseline.** 68 entity ids and 14 config entries (analytics, backup,
go2rtc, google_translate, hassio, matter, media_extractor, met, 2×
mobile_app, mqtt, radio_browser, shopping_list, sun) saved for comparison.

**R6 — HA core restart (20:03:17).** `POST
/api/services/homeassistant/restart` returned 504 (HA drops the request
while restarting). Logbook confirms the restart: stopped 01:03:18Z, started
01:03:43Z. After restart: `RUNNING`; entity ids and config entries identical
to R5.

**R7 — VM graceful shutdown + start (20:04:25–20:06:10).** Checked first: 0
active Aria leases, 0 device commands in the last 10 min. `virsh shutdown`
→ `shut off (shutdown)` in 20 s (graceful, not crash); `virsh start`;
:8123 200 at 20:05:28 (~41 s). `RUNNING`; entity ids and config entries
identical to R5; both bulbs reporting state; `ha_health()` connected, 68
entities. No SSH or console needed for either restart.

**R8 — host after tests (20:06).** 6.8 GiB available; swap 2047/2047 MiB
used (still full from the 10-03 OOM period; not reclaimed). LAN DNAT/
MASQUERADE rules for 8123 still present (host rules, untouched).

## 4. Acceptance status

| Criterion | Status |
|---|---|
| Existing VM boots, HA reachable | **Done** (R2, R3) |
| CAOSCare can connect | **Done** (R4) |
| Restart does not destroy config | **Done** (R6, R7) |
| Normal restart without SSH | **Done** (R6, R7) |
| Host keeps resources for CAOSCare | **Done for now** (R8: 6.8 GiB free; swap full — see P1–P3) |
| VM starts after an EliteDesk reboot | **Not tested** — autostart `enable` is configured; proof needs a host reboot, which needs Michael's approval |
| Recovers from another OOM kill without SSH | **Not done** — needs approval of P1/P2 (host changes) |
| Receipt of exact config changes | **Done** — no configuration was changed; only start/stop/restart actions (R1–R7) |

Known host-reboot loss (unchanged, recorded 2026-08-02/09-05): the 8123
DNAT/MASQUERADE rules and the in-VM IPv6 address for the Midea AC are
runtime-only. CAOSCare uses 192.168.122.137 directly and is unaffected; LAN
phone/browser access to `192.168.1.151:8123` would need the rules restored.

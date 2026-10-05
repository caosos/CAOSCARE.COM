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
(appended below as each step runs)

# HA VM OOM protection + crash restart (PROPOSAL — nothing here is installed)

Implements P1 and P2 from `docs/HA_VM_RECOVERY.md` (cause: host OOM on
2026-10-03 killed the qemu process of `caoscare-homeassistant`; autostart only
runs at host boot). Written for Michael's review. **Do not install without a
yes.** Only `virsh domstate` was run while writing these; `bash -n` passed on
both scripts. Behaviour of the hook on this libvirt version is UNVERIFIED
until installed and tested.

| File | Installs to | Purpose |
|---|---|---|
| `qemu-hook-oom-protect.sh` | `/etc/libvirt/hooks/qemu` | P1: sets `oom_score_adj=-800` on the VM's qemu at start |
| `ha-vm-restart-if-crashed.sh` | `/usr/local/sbin/` | P2: starts the VM only if state is `shut off (crashed)` |
| `ha-vm-restart-if-crashed.service` / `.timer` | `/etc/systemd/system/` | runs the P2 script every minute |

P2 guards: a deliberate shutdown/destroy is never restarted; at most one start
per 5 minutes; no start while `MemAvailable` < 5 GiB; one run at a time. All
actions are logged to the journal (`journalctl -t ha-vm-restart`,
`-t ha-vm-oom-hook`).

## Before installing
- `ls /etc/libvirt/hooks/qemu` — if a hook exists, merge instead of replacing.
- Note the current VM state: `virsh domstate --reason caoscare-homeassistant`.

## Install (root)
```
sudo install -d /etc/libvirt/hooks
sudo install -m 0755 -o root -g root qemu-hook-oom-protect.sh /etc/libvirt/hooks/qemu
sudo install -m 0755 -o root -g root ha-vm-restart-if-crashed.sh /usr/local/sbin/ha-vm-restart-if-crashed.sh
sudo install -m 0644 ha-vm-restart-if-crashed.service ha-vm-restart-if-crashed.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ha-vm-restart-if-crashed.timer
```
libvirt reads a new hook at the next event; if it is not picked up,
`sudo systemctl reload libvirtd` (no restart of running guests needed).

The hook only acts when the VM *starts*. To protect the already-running VM
once, without restarting it:
```
pid=$(sudo cat /run/libvirt/qemu/caoscare-homeassistant.pid)
echo -800 | sudo tee /proc/$pid/oom_score_adj
```

## Verify
```
systemctl list-timers ha-vm-restart-if-crashed.timer
pid=$(sudo cat /run/libvirt/qemu/caoscare-homeassistant.pid); cat /proc/$pid/oom_score_adj   # expect -800
journalctl -t ha-vm-oom-hook -t ha-vm-restart --since today
```
Optional crash test (stops HA for ~2 minutes; do it only when OK with that):
`sudo kill -9 $pid` → state becomes `shut off (crashed)` → within ~1–2 minutes
the journal shows "started it" and `virsh domstate` reports `running`. Also
confirm `virsh shutdown caoscare-homeassistant` is **not** restarted.

## Uninstall
```
sudo systemctl disable --now ha-vm-restart-if-crashed.timer
sudo rm /etc/systemd/system/ha-vm-restart-if-crashed.{service,timer} /usr/local/sbin/ha-vm-restart-if-crashed.sh
sudo rm /etc/libvirt/hooks/qemu      # or remove only the block added to an existing hook
sudo rm -rf /var/lib/ha-vm-restart
sudo systemctl daemon-reload
```
The running VM keeps its current `oom_score_adj` until its next start.

## Limits
- `-800` makes qemu a last-choice victim; it does not stop host memory
  exhaustion. P3 (memory caps for heavy builds) is still a process rule.
- A VM that crashes repeatedly is retried every 5 minutes at most.
- Does not touch libvirt domain XML, qcow2, networking, or Home Assistant.

# EliteDesk Full CAOSCare Node Build

Living build/architecture record for turning `caoscare1-hp-elitedesk` into the first practical, local-first CAOSCare node, per `commands/TERMINAL_3_ELITEDESK_FULL_NODE_BUILD.md`.

Do not replace or erase prior entries in this file. Append dated sections as the build progresses.

---

## 2026-08-02 — Phase 1: Host inspection (truth established)

### Agent / tool
Claude Code with Michael on the `caoscare1-hp-elitedesk` host.

### Branch / ref
`main` at `fde20d8` — `Add EliteDesk full CAOSCare node build directive`. `docs/PROJECT_STATE.md` has an uncommitted local addition (prior session's entries, not yet committed).

### Host facts

```text
Hostname:        caoscare1-hp-elitedesk
Hardware:        HP EliteDesk 705 G4 DM 35W (TAA)
OS:              Ubuntu 22.04.5 LTS (jammy), kernel 6.8.0-136-generic
CPU:             AMD Ryzen 5 PRO 2400GE w/ Radeon Vega Graphics, 8 threads
Virtualization:  AMD-V present, /dev/kvm exists and is accessible (crw-rw----+ root:kvm)
RAM:             14Gi total, 11Gi available (2.4Gi used, 3.0Gi buff/cache)
Swap:            2.0Gi, unused
Disk:            /dev/nvme0n1p2, 234G total, 23G used, 199G available, mounted at /
Network:         wlp6s0 (Wi-Fi) UP, 192.168.1.151/24 — this is the ONLY active network interface.
                 eno1 (wired Ethernet) is present but DOWN/unplugged.
Uptime:          ~49 min at inspection time (host was recently rebooted)
```

### Network implication for Phase 3

The host reaches the LAN only via Wi-Fi (`wlp6s0`). A true Linux bridge (`br0`) across a Wi-Fi NIC is unreliable in practice — most Wi-Fi drivers/APs won't forward frames for multiple MAC addresses over one wireless association (4-address-mode/WDS is not broadly supported here), so bridging the Home Assistant VM directly onto the Wi-Fi network risks breaking host connectivity or simply not working. Per the directive's guidance to prefer the least-disruptive working mode when bridging isn't safe: **the HA OS VM will use libvirt's default NAT network (`virbr0`)** with an explicit port-forward for `8123` (and `1883` once MQTT is added), rather than a Wi-Fi bridge/macvlan. This makes the VM reachable at the host's own LAN IP (`192.168.1.151:8123`) without touching the host's network configuration, so there is no risk of a network interruption. Documented as a tradeoff, not a blocker: this is not true LAN L2 presence, so protocols that need broadcast/multicast discovery on the physical LAN (e.g. some mDNS/SSDP-based device discovery) may not see the HA VM as a first-class LAN citizen until/unless a wired NIC becomes available for a real bridge.

### Git state

```text
Branch: main
HEAD:   fde20d8 Add EliteDesk full CAOSCare node build directive
Remote: origin -> https://github.com/caosos/CAOSCARE.COM.git
Working tree: 1 modified file (docs/PROJECT_STATE.md, uncommitted local addition from a prior session)
```

### CAOSCare application state at inspection time

- Backend (`uvicorn`) and frontend (`yarn start`/craco) are **not running** — no matching processes found. This is consistent with the host having rebooted ~49 minutes ago: both were previously started as detached `setsid`/`nohup` dev processes (per `docs/PROJECT_STATE.md`, 2026-07-28 entries), which do not survive a reboot.
- `mongod` **is active** (`systemctl is-active mongod` → `active`), listening on `127.0.0.1:27017` — MongoDB is a systemd-enabled service and survived the reboot correctly.
- Listening ports at inspection time: `127.0.0.1:27017` (mongod), `127.0.0.53:53` (systemd-resolved), `127.0.0.1:631` / `[::1]:631` (CUPS). No port 8000 or 3000 listener.
- See Phase 2 section below for the restart and re-verification.

### Installed tooling relevant to this build

```text
Present:      node v24.18.0, npm 11.16.0, yarn 1.22.22 (via nvm), python3.10.12, gh 2.4.0 (auth'd as caosos), bluetoothctl
Not present:  docker, qemu-kvm, libvirt-daemon-system, libvirt-clients, bridge-utils, virsh, cockpit-bridge,
              mosquitto, node-red, nginx, caddy, cloudflared, rtl_433
```

None of the KVM/libvirt/Home Assistant/MQTT stack is installed yet — this build starts from zero on that side.

### Attached hardware relevant to Home Assistant / CAOS device work

```text
USB:
  Logitech Wireless Receiver (keyboard/mouse) — not device-relevant
  Logitech Keyboard K120 (wired) — not device-relevant
  EMEET OfficeCore Luna Plus — USB conferencing speaker/mic (shows as ALSA card 2, USB Audio)
  Intel Wireless-AC 9260 Bluetooth Adapter (internal, on-board) — bluetoothctl confirms controller present: 3C:58:C2:A4:D6:5B

Bluetooth: one controller present and available (Intel AC 9260), not yet paired to anything.

SDR / RF: no rtl_433-class SDR dongle attached; rtl_433 binary not installed.
Serial:   no /dev/ttyUSB*, no /dev/ttyACM* devices present — no Zigbee/Z-Wave/RF USB coordinator attached yet.
Audio:    onboard HD-Audio (HDMI outputs + analog CX20632) plus the EMEET USB mic/speaker — usable for local voice testing, not a dedicated always-on room mic/speaker.
```

**Hardware still needed** for the fuller CAOS Care hardware direction (pendant/RF bridge, Zigbee/Z-Wave coordinator, dedicated SDR): none of that hardware is attached to this host yet. Phase 4 will document specific optional Home Assistant services (Zigbee JS, Z-Wave JS, Matter, ESPHome, etc.) as *pending with an exact hardware dependency* rather than installing them speculatively, per the directive.

### What was verified this phase
- Host meets Home Assistant OS VM requirements on paper: AMD-V + `/dev/kvm` available, 11Gi RAM free (HA OS official minimum is far lower), 199G disk free.
- No conflicting virtualization/container stack already installed (clean slate for KVM/libvirt).
- CAOSCare's own application processes are down (reboot artifact); MongoDB is up and correctly systemd-managed.

### What is blocked
- Backend/frontend need to be restarted and re-verified before any Home Assistant install work begins (Phase 2, next section).
- No wired network interface is available for a true LAN bridge; VM networking will use NAT + port-forward instead (documented above).

### Next safe step
Proceed to Phase 2 — restart and re-verify the existing CAOSCare backend/frontend/MongoDB stack before installing anything new, so the "preserve the working application" requirement is provably satisfied before Home Assistant is added.

---

## 2026-08-02 — Phase 2: Existing CAOSCare application preserved and re-verified

### What changed
- Restarted the backend (`uvicorn server:app --host 127.0.0.1 --port 8000`) and frontend (`yarn start` / craco dev server) as detached `setsid`/`nohup` processes, exactly as they were run in the 2026-07-28 session — same commands, same `.env` files, untouched.
- No `.env` file was replaced, read aloud, or modified. No owner account was touched. No application code or MongoDB data was changed.

### What was verified
- `curl http://127.0.0.1:8000/api/health` → `{"ok":true,"db":"up"}`.
- `curl -o /dev/null -w "%{http_code}" http://localhost:3000` → `200`. Frontend compiled successfully via craco with no errors (only routine webpack-dev-server deprecation warnings).
- `systemctl is-active mongod` → `active`.
- Frontend log shows it is also reachable on the LAN at `http://192.168.1.151:3000` (craco's own network-interface detection), independent of anything this build adds.

### How each process currently starts (recorded per directive)
```text
mongod:    systemd service, enabled, survives reboot automatically.
backend:   manual `setsid nohup uvicorn server:app --host 127.0.0.1 --port 8000 &`, run from backend/ with .venv activated.
           NOT managed by systemd. Confirmed this session: did not survive the host's last reboot.
frontend:  manual `setsid nohup yarn start &`, run from frontend/ with nvm's Node active.
           NOT managed by systemd. Confirmed this session: did not survive the host's last reboot.
```

### Blocked / not yet done
- Backend and frontend remain detached dev processes, not systemd-managed — this is a known reliability gap for "the node must recover after restart" (Phase 6 requirement). Per the directive, this conversion is deliberately **not** done in this step ("do not convert them to systemd in the same step unless doing so is necessary... and can be tested without losing the working state") — it is deferred to Phase 6, where it will be done and tested as part of the overall boot-reliability pass so Home Assistant's own autostart can be verified alongside it in one clean reboot test.

### Next safe step
Proceed to Phase 3 — install the Home Assistant OS VM foundation (KVM/libvirt), now that the existing application is confirmed healthy and its current (non-systemd) start method is documented.

---

## 2026-08-02 — Phase 3: Home Assistant OS VM foundation installed and reachable

### Agent / tool
Claude Code with Michael on the `caoscare1-hp-elitedesk` host (same session as Phases 1–2 above).

### Branch / ref
`main` at `fde20d8`. No commits made yet this phase — see Blocked section.

### What changed
- Installed `qemu-kvm`, `libvirt-daemon-system`, `libvirt-clients`, `bridge-utils`, `virtinst`, `libguestfs-tools` via apt (pulls in `ovmf` for UEFI firmware, `qemu-system-x86`, ~150 packages total, all standard KVM/libvirt-stack dependencies — no unrelated software installed).
- Enabled/confirmed `libvirtd` active and enabled (systemd).
- Defined, built, started, and autostarted a libvirt storage pool named `default` at `/var/lib/libvirt/images` (209.91 GiB available).
- Downloaded the **official** Home Assistant OS 18.2 release asset `haos_ova-18.2.qcow2.xz` directly from the `home-assistant/operating-system` GitHub repo via the authenticated `gh` CLI (release tag `18.2`, published 2026-07-30). This is the OVA/qcow2 variant, the correct artifact for KVM per Home Assistant's own Linux/KVM installation documentation (as opposed to the `generic-x86-64` variant, which is for bare-metal/Proxmox raw installs).
- **No official checksum file was published for this release** (checked the release assets and body for a `.sha256`/checksums file — none exists for 18.2). Recorded the computed sha256 of the downloaded archive for the record: `254e53f354df0739e3afc09be5431a07df53f0df6b703885404f665c454f254e`. Provenance instead rests on: official upstream repo, authenticated GitHub API download (not a mirror), TLS in transit.
- Decompressed the image (`unxz`), verified it with `qemu-img info` (valid QCOW2 v3, 32 GiB virtual size), copied it into the storage pool as `/var/lib/libvirt/images/caoscare-homeassistant.qcow2`, owned by `libvirt-qemu:kvm`, and deleted the scratch copies.
- Created a persistent libvirt domain `caoscare-homeassistant` via `virt-install --import` (no OS install step — imported the existing HAOS disk directly):
  - 4096 MiB RAM, 2 vCPUs, `--cpu host-passthrough`
  - disk: virtio bus, the qcow2 above
  - firmware: UEFI (`--boot uefi`, via the `ovmf` package)
  - network: attached to libvirt's existing NAT network `default` (`virbr0`, `192.168.122.0/24`), virtio NIC — per the Phase 1 network-implication note, since this host's only active interface is Wi-Fi and a true bridge is not reliable over it.
  - `--graphics none`, serial console only (no VNC/SPICE surface opened)
- Set `virsh autostart caoscare-homeassistant` (VM starts automatically when the host boots and libvirtd comes up).
- Added a static DHCP host reservation to the `default` libvirt network (`virsh net-update`) pinning the VM's MAC `52:54:00:09:90:eb` to `192.168.122.137`, so its address is stable across VM reboots rather than floating.
- Added a LAN reachability path for Michael's browser: an `iptables` NAT `PREROUTING` DNAT rule forwarding `tcp/8123` arriving on `wlp6s0` (the host's LAN interface) to `192.168.122.137:8123`, plus a matching `FORWARD` accept rule. This makes the VM reachable from other devices on the `192.168.1.0/24` LAN at the host's own address, without any Wi-Fi bridge and without changing the host's own IP/DNS/firewall posture otherwise.

### What was verified
- `virsh pool-list --all` → `default` pool active, autostart yes.
- `virsh list --all` → `caoscare-homeassistant` running, persistent yes, autostart enable.
- VM acquired DHCP lease `192.168.122.137` on first boot; confirmed the reservation now pins that same address going forward.
- `curl http://192.168.122.137:8123/` → HTTP 200, genuine Home Assistant onboarding HTML (`<title>Home Assistant</title>`, HA frontend assets) on the **first** attempt after boot — no long onboarding wait was needed.
- Re-verified after all of the above that the existing CAOSCare app and host network were undisturbed: `curl http://127.0.0.1:8000/api/health` → `{"ok":true,"db":"up"}`, frontend → HTTP 200, `wlp6s0` still up with its original address.
- Confirmed `net.ipv4.ip_forward = 1` (already enabled, libvirt's own default-network setup depends on it) and that the new `FORWARD`/`PREROUTING` rules sit correctly relative to libvirt's own `LIBVIRT_FWX/FWI/FWO` chains (policy `ACCEPT`, our rule evaluated first, no conflict).

### Known limitation, not yet resolved
- The LAN port-forward (`192.168.1.151:8123` → `192.168.122.137:8123`) could **not** be self-tested from the host, because a Linux host cannot cleanly hairpin NAT back to itself through a `PREROUTING` DNAT rule scoped to a physical ingress interface — packets the host itself originates to its own address take the `OUTPUT` path, not `PREROUTING`. This is expected Linux behavior, not a sign the rule is wrong. The rule was verified as structurally correct (`iptables -t nat -L PREROUTING`, `iptables -L FORWARD`) but genuine confirmation requires a test from a second device on the `192.168.1.0/24` LAN (see "Next safe step").

### Blocked / not yet done
- **The `iptables` DNAT/FORWARD rules added this phase are runtime-only and will not survive a reboot** — no `iptables-persistent`/`netfilter-persistent` package is installed. Per the same precedent as Phase 2 (leaving backend/frontend as non-systemd dev processes for now), persistence of these firewall rules is deferred to Phase 6's boot-reliability pass, where it will be done and tested together with the systemd conversion and a real reboot test, rather than half-solving reliability piecemeal.
- Home Assistant's own onboarding wizard (create HA account, name the home, set location) has **not** been completed — this requires Michael's browser and is exactly the kind of step the build directive says to stop for.
- No Home Assistant Supervisor add-ons (Mosquitto MQTT, etc. — Phase 4) have been installed yet; Supervisor's add-on store is only usable after onboarding completes.
- Nothing has been committed to git yet this phase (VM disk images, downloaded release artifacts, and libvirt runtime state are correctly excluded from the repo per the directive; only this documentation update is pending a commit).
- No repository commit has been made yet for Phases 1–3 documentation — `docs/PROJECT_STATE.md` also still carries the uncommitted 2026-07-28 entries from a prior session.

### Next safe step — action required from Michael
1. On any device connected to the same LAN as the EliteDesk, open a browser to **`http://192.168.1.151:8123`** (or, if that doesn't load yet since the port-forward is unverified end-to-end, try **`http://192.168.122.137:8123`** from a browser running directly on the EliteDesk itself as a fallback — that address is confirmed working).
2. Complete the Home Assistant onboarding wizard (create the local HA account, set home name/location/unit system). Do not enable remote access / Nabu Casa cloud unless Michael explicitly wants that — it is out of scope for this local-first build.
3. Tell Claude once onboarding is complete so Phase 4 (Mosquitto MQTT broker and other node services) can proceed via the now-available Supervisor API/UI.

---

## 2026-08-02 — Phase 3 closeout: Michael completed HA onboarding

### What changed
Michael opened the VM's internal address (`http://192.168.122.137:8123`) directly from a browser on the EliteDesk itself (the LAN port-forward to `192.168.1.151:8123` hits the expected host-hairpin-NAT limitation described above when tested *from the EliteDesk's own browser* — confirmed working as intended, not a defect; a genuine test from a second LAN device is still pending) and completed the Home Assistant onboarding wizard: local HA admin account created, home name/location/unit system set, remote access/Nabu Casa skipped as instructed.

### What was verified
- `curl http://192.168.122.137:8123/api/` → HTTP `401` (not an onboarding redirect) — confirms onboarding is complete and the API layer is live and correctly requiring auth.
- Michael confirms landing on the live HA dashboard with no "start here"/onboarding prompt remaining.

### Next safe step
Proceed to Phase 4 — install the Mosquitto MQTT broker and evaluate the other optional node services against currently-attached hardware.

---

## 2026-08-02 — Phase 4 (in progress): optional service evaluation against actual attached hardware

### What changed
Evaluated each optional Home Assistant Supervisor add-on listed in the directive against the Phase 1 hardware inventory, before installing anything. Per the directive ("install an evaluated service only when the required hardware and immediate CAOSCare use are present"), none of these are installed yet — the required Mosquitto broker (a required, not optional, service) is a separate, in-progress step that needs Michael's browser (Supervisor add-on store) and is not covered by this evaluation.

### Evaluation

```text
Zigbee coordinator services  — PENDING HARDWARE. No Zigbee USB coordinator (ConBee/SkyConnect/etc.)
                                attached; Phase 1 found no /dev/ttyUSB* or /dev/ttyACM* devices at all.
Z-Wave JS                    — PENDING HARDWARE. Same — no Z-Wave USB stick attached.
Matter Server                — PENDING HARDWARE. No Matter devices/border router present. Also: this is
                                exactly the Terminal 4 (Midea/Matter LAN) scope, which is deliberately
                                paused per Terminal 5A's priority order — do not resume without Michael's ask.
OpenThread Border Router      — PENDING HARDWARE. Needs a Thread-capable radio (e.g. HA SkyConnect/Yellow);
                                none attached.
ESPHome                       — PENDING HARDWARE. No ESP32/ESP8266 devices to flash/manage yet. The add-on
                                itself has no hardware dependency to *install*, but there is nothing for it
                                to do yet — install on demand when Michael has an ESP-based device.
Piper (local TTS) /
Whisper (local STT) /
openWakeWord                  — PENDING PRODUCT DECISION, not hardware. These power Home Assistant's own
                                "Assist" voice pipeline, which is a *different* voice system from CAOSCare's
                                own Aria/resident voice pipeline (OpenAI Realtime, already built — see
                                docs/ARIA_VOICE_FIRST.md). Installing these would stand up a second,
                                redundant voice assistant inside HA itself. Not installed until Michael
                                decides HA's own Assist pipeline is wanted alongside Aria.
Samba                         — NO HARDWARE DEPENDENCY, deferred to Michael's preference. Convenience LAN
                                file share for editing HA's /config over the network. Overlaps with Studio
                                Code Server below; only one is really needed.
Studio Code Server             — NO HARDWARE DEPENDENCY, deferred. Browser-based VS Code for editing HA
                                YAML config directly inside the Supervisor. Useful once the MQTT integration
                                (Phase 5) needs manual config; not installed yet since nothing requires
                                manual YAML editing so far (UI-driven config has covered everything to date).
InfluxDB/Grafana               — NO HARDWARE DEPENDENCY, deferred. Long-term history/monitoring dashboards;
                                adds real resource overhead (a second database) for a single-node build
                                that doesn't have enough history yet to make dashboards meaningful. Revisit
                                once the node has been running long enough to have real data.
Node-RED                       — NO HARDWARE DEPENDENCY, deferred. General-purpose automation-flow editor.
                                CAOSCare's own backend is the intended place for CAOSCare-specific logic
                                (see Phase 5's MQTT contract) rather than duplicating that logic in Node-RED
                                flows; only install if a specific HA-side automation need comes up that the
                                CAOSCare backend shouldn't own.
```

### What is verified
Every "pending hardware" item above was checked against the actual Phase 1 device inventory (`lsusb`, `/dev/ttyUSB*`/`/dev/ttyACM*`, `bluetoothctl list`), not assumed — none of the required coordinators/radios are attached to this host as of this entry.

### Blocked / not yet done
- Mosquitto broker install itself: needs Michael in the HA Supervisor add-on store (browser-only step, requested separately).
- A Home Assistant Long-Lived Access Token has been requested from Michael so the rest of Phase 4/5 (verifying Mosquitto is actually listening, wiring the MQTT integration, building the CAOSCare↔HA contract) can proceed via HA's API instead of further browser round-trips.

### Next safe step
Once Michael confirms Mosquitto is installed/started and provides a Long-Lived Access Token: verify the broker is listening (port 1883 inside the VM), confirm the MQTT integration is configured in HA, then proceed to Phase 5 (the CAOSCare↔Home Assistant MQTT topic contract).

---

## 2026-08-09 — Phase 4 closeout: Mosquitto installed, MQTT integration wired up, HA API token secured

### What changed
- Michael installed the official **Mosquitto broker** add-on via the Supervisor add-on store (navigation in this HA version: Settings → **Apps** → Add-on Store, not "Add-ons" — the label has changed in recent HA releases), enabled Start on boot/Watchdog, and started it.
- Getting a Long-Lived Access Token via copy/paste from the browser did not work for Michael (repeated, confirmed clipboard failures across this and prior sessions — noted here for future agents so this isn't re-attempted the same way). Michael instead **typed the token by hand into a new local file** using a desktop text editor and saved it to `/home/caoscare-1/TOKEN`. Claude located it, verified it, and moved it to `/home/caoscare-1/.config/caoscare/ha_long_lived_token` (`chmod 600`, outside any git-tracked directory, never printed to any log/chat).
- Used that token to drive the rest of Phase 4 entirely through HA's REST API from the host (no further browser clicks needed):
  - Confirmed the broker is reachable: raw TCP check to `192.168.122.137:1883` succeeds.
  - `GET /api/config` confirmed the HA Core version (`2026.7.4`), location config, and (initially) that the `mqtt` integration was **not yet loaded** — the add-on running is necessary but not sufficient; HA Core needs its own MQTT config entry pointing at the broker.
  - Started the `mqtt` config flow (`POST /api/config/config_entries/flow` with `{"handler": "mqtt"}`), which offered a menu (`addon` vs `broker`) — HA auto-detected the running Mosquitto add-on. Submitted `{"next_step_id": "addon"}` to the flow, which completed immediately with `"state": "loaded"` — no broker host/port/credentials needed manually since it used the add-on's own internal connection info.
  - Re-checked `GET /api/config` → `mqtt` now present in `components`, confirming the integration is live.

### What was verified
- `curl -H "Authorization: Bearer <token>" http://192.168.122.137:8123/api/` → `{"message":"API running."}`.
- Mosquitto broker: TCP port `1883` open on the VM.
- HA's own `mqtt` integration: config entry `title: "Mosquitto Mqtt Broker"`, `state: "loaded"`, confirmed present in `/api/config` component list after setup.
- Token is usable for all future Phase 5+ API-driven work without further browser interaction.

### Note for future agents on this host
If a Long-Lived Access Token or similar credential is needed again, **do not ask for copy/paste** — it does not work reliably in this environment. Ask Michael to type it by hand into a local text file instead (as done here), then read the file directly from disk.

### Next safe step
Proceed to Phase 5 — define the CAOSCare↔Home Assistant MQTT topic contract and prove one round-trip test.

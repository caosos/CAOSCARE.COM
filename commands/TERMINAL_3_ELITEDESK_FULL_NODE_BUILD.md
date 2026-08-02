# Terminal 3 — EliteDesk Full CAOSCare Node Build

## Mission

Turn the current Ubuntu HP EliteDesk host into the first practical, local-first CAOSCare node while preserving the CAOSCare application already running on this machine.

This directive authorizes bounded host setup, package installation, service configuration, virtual-machine creation, repository documentation updates, testing, and commits required to establish the node foundation.

Do not expose the machine publicly, change DNS, deploy to production, erase disks, repartition storage, or remove the working CAOSCare application.

## Required first reads

Before changing anything, read and follow:

1. `AGENTS.md`
2. `README.md`
3. `docs/PROJECT_STATE.md`
4. `docs/REPO_MAP.md`
5. `docs/BUILD_STATUS.md`
6. `docs/DEPLOYMENT_RUNBOOK.md`
7. `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md`

Inspect the current Git branch, working tree, recent commits, services, processes, ports, storage, RAM, CPU virtualization support, network interfaces, USB devices, and the current CAOSCare frontend/backend/MongoDB state before acting.

## Architecture decision

Use only currently supported Home Assistant installation methods.

Default architecture, if this EliteDesk supports hardware virtualization and has sufficient resources:

- Keep Ubuntu as the CAOSCare host operating system.
- Keep the existing CAOSCare frontend, FastAPI backend, MongoDB, Claude Code, SDR tools, and future bridge services on Ubuntu.
- Install KVM/libvirt and run **Home Assistant Operating System in a dedicated virtual machine**.
- Give the Home Assistant OS VM persistent storage, automatic boot, and local-network access suitable for device discovery.
- Use Home Assistant OS because the requested full Home Assistant stack requires Supervisor-managed apps.

Do not install deprecated Home Assistant Core or Home Assistant Supervised.

Fallback architecture only if a Home Assistant OS VM is technically unavailable on this machine:

- Install Home Assistant Container with Docker Engine and Docker Compose.
- Document clearly that Container does not include Supervisor/apps.
- Run required companion services, such as MQTT, as separate managed containers.

Do not choose the fallback merely because it is faster. Prefer the full Home Assistant OS VM when the host can support it.

Use current official Home Assistant documentation and official release artifacts. Do not rely on old community instructions when official guidance differs.

## Phase 1 — Establish the truth

Record without exposing secrets:

- hostname and Ubuntu version
- CPU model, architecture, virtualization flags, and KVM availability
- RAM and free memory
- disk layout and available storage
- current IP addresses and active network interface
- current Git branch, commit, cleanliness, and remote
- CAOSCare frontend/backend/MongoDB status
- listening ports
- installed Docker, KVM, libvirt, QEMU, Cockpit, Home Assistant, MQTT, Node-RED, Nginx, Caddy, cloudflared, SDR, Bluetooth, and USB tooling
- attached USB radios, microphones, speakers, serial devices, Bluetooth adapters, and SDR receivers

Write the inspection result into a new dated node-build document under `docs/`.

## Phase 2 — Preserve the current CAOSCare application

Before adding Home Assistant:

1. Verify the existing CAOSCare backend health endpoint.
2. Verify the frontend responds locally.
3. Verify MongoDB is active and bound locally.
4. Record how each process currently starts.
5. Do not replace working `.env` files or print their values.
6. Do not delete or recreate the current owner account.
7. Preserve all existing local application data.

If the CAOSCare processes are still detached development processes, document that fact. Do not convert them to systemd in the same step unless doing so is necessary for reliable node boot and the conversion can be tested without losing the working state.

## Phase 3 — Install the full Home Assistant foundation

If the default VM architecture is viable:

1. Install the minimum supported KVM/QEMU/libvirt packages.
2. Enable and verify libvirt.
3. Download the current official Home Assistant OS KVM image.
4. Verify the artifact source and checksum when officially provided.
5. Create a persistent VM named `caoscare-homeassistant`.
6. Allocate sensible resources based on the host, with at least the official minimum and enough headroom for apps.
7. Configure the VM to start automatically when the EliteDesk boots.
8. Use a networking mode that allows reliable local access and device discovery. Prefer a bridged/local-LAN presence when it can be configured without breaking the host network. If bridging would interrupt the active connection, use the least disruptive working mode and document the tradeoff.
9. Start the VM and verify Home Assistant onboarding is reachable at its local address on port `8123`.
10. Record the VM name, resource allocation, storage path, MAC address, IP address, and boot behavior.

Stop and report before making a network change that would disconnect Michael from the machine or before changing firmware/BIOS settings.

## Phase 4 — Home Assistant apps and node services

After Home Assistant OS is running and onboarding can be completed:

Prepare the full node service plan. Install only services that can be configured correctly now.

Initial required services:

- Home Assistant Core under Home Assistant OS
- Supervisor and managed apps
- Mosquitto MQTT broker
- a supported local file/configuration access method
- backup capability
- local health visibility

Evaluate but do not blindly install:

- Node-RED
- Matter Server
- OpenThread Border Router
- Z-Wave JS
- Zigbee coordinator services
- ESPHome
- Piper local text-to-speech
- Whisper local speech-to-text
- openWakeWord
- Samba
- Studio Code Server
- InfluxDB/Grafana

Install an evaluated service only when the required hardware and immediate CAOSCare use are present. Otherwise document it as pending with the exact dependency.

## Phase 5 — CAOSCare ↔ Home Assistant integration foundation

Create the smallest working integration contract between CAOSCare and Home Assistant.

The first integration should be local, explicit, inspectable, and reversible.

Preferred first transport:

- MQTT for events, state, and commands
- Home Assistant REST/WebSocket API for functions that do not fit MQTT

Define and document a versioned MQTT topic structure such as:

```text
caoscare/v1/node/<node_id>/status
caoscare/v1/node/<node_id>/events
caoscare/v1/node/<node_id>/commands
caoscare/v1/room/<room_id>/state
caoscare/v1/room/<room_id>/events
caoscare/v1/room/<room_id>/commands
```

Do not commit credentials or tokens.

Create a focused integration document under `docs/` that defines:

- node identity
- topic names
- payload envelopes
- timestamps
- correlation IDs
- acknowledgment/receipt behavior
- offline behavior
- reconnect behavior
- authorization boundaries
- human escalation handoff fields

If a minimal local test publisher/subscriber can be created cleanly, implement it in a small focused module and prove one round-trip test without touching resident data.

## Phase 6 — Reliability and boot behavior

The first node must recover after restart.

Verify and document:

- Ubuntu boots normally
- MongoDB starts
- CAOSCare backend and frontend startup method
- libvirt starts
- Home Assistant VM autostarts
- Home Assistant becomes reachable
- MQTT becomes reachable after Home Assistant starts
- no service requires an interactive terminal to remain open
- logs have known locations
- local health checks can be run manually

Do not reboot until the configuration is ready for a controlled reboot test and Michael has been told that the next action is a reboot.

## Phase 7 — Repository records

Create or update focused documentation for:

- EliteDesk node architecture
- installed services and ports
- Home Assistant installation method
- VM details
- MQTT integration contract
- startup and recovery behavior
- current blockers
- hardware still needed
- exact next step

Append a dated entry to `docs/PROJECT_STATE.md` containing:

- Date
- Agent/tool
- Branch/ref
- What changed
- What was verified
- What is blocked
- Next safe step

Do not erase earlier project history.

Commit repository documentation and any focused integration code in small logical commits. Do not commit `.env` files, secrets, VM disk images, databases, logs, downloaded installation images, or generated runtime data.

## Acceptance criteria for this directive

This directive is complete when the following are true, or when a specific technical blocker is proven and documented:

1. The current CAOSCare application remains operational.
2. A supported Home Assistant architecture has been selected from verified host facts.
3. Home Assistant OS is running in a persistent autostart VM, or the technically necessary Container fallback is running and the missing full-stack capabilities are documented.
4. Home Assistant is reachable locally on port `8123`.
5. The node has a defined MQTT-based CAOSCare integration contract.
6. Required node services and pending hardware dependencies are documented.
7. Startup, recovery, and health-check behavior are documented.
8. `docs/PROJECT_STATE.md` contains a dated continuation entry.
9. No secret or private resident information is committed.
10. Claude reports exactly what Michael must do next in the browser or physically at the machine.

## Operating instruction

Work continuously through the phases that can be completed without Michael's browser interaction or physical input.

When browser onboarding, a password, a BIOS change, a network interruption, a reboot, or a physical USB action is required, stop at that exact point and give Michael one clear instruction. Do not replace the remaining work with a generic plan.

# Terminal 4 — Midea Matter and Home Assistant LAN Setup

## Mission

Prepare the existing Home Assistant OS virtual machine on the EliteDesk to pair the Midea portable air conditioner model `MAP14AS1TWT-C` through Matter.

The air conditioner is a Midea Duo Smart Inverter portable unit with a Matter QR code. Do not use the `Midea ccm15 AC Controller` integration; that integration is for a separate commercial CCM15 controller and is not the correct path for this appliance.

## Required first reads

Before changing anything, read and follow:

1. `AGENTS.md`
2. `README.md`
3. `docs/PROJECT_STATE.md`
4. `docs/ELITEDESK_NODE_BUILD.md`
5. `commands/TERMINAL_3_ELITEDESK_FULL_NODE_BUILD.md`

Inspect the current branch, working tree, Home Assistant VM state, libvirt networking, CAOSCare frontend/backend/MongoDB health, and current LAN connectivity before acting.

## Required work

1. Confirm the Home Assistant OS VM is healthy and preserve its existing onboarding/account state.
2. Determine whether the VM is still behind libvirt NAT on `192.168.122.x`.
3. Move or reconfigure the Home Assistant VM so it has its own address on the same physical LAN as the EliteDesk and the Midea appliance, using a supported bridged or equivalent LAN-attached libvirt configuration.
4. Preserve the working CAOSCare frontend, FastAPI backend, MongoDB, owner account, SSH access, and host network connectivity.
5. Do not expose the machine publicly, change public DNS, erase storage, or reinstall Home Assistant.
6. Verify after the network change:
   - Home Assistant loads from another LAN device at its new `192.168.1.x:8123` address;
   - the VM persists and autostarts;
   - Home Assistant has working IPv4, IPv6 where available, mDNS, and local-LAN discovery suitable for Matter;
   - CAOSCare frontend, backend health, MongoDB, and SSH still work.
7. Install/configure the official Home Assistant Matter integration and Matter Server app only through the supported Home Assistant OS/Supervisor path.
8. Stop before scanning the appliance QR code. Michael must perform the phone/Bluetooth/QR-code pairing step.
9. Update `docs/ELITEDESK_NODE_BUILD.md` and `docs/PROJECT_STATE.md` with what changed, what was verified, what remains blocked, the new Home Assistant LAN address, and the exact next step for Michael.
10. Commit and push completed documentation/configuration changes in small logical commits.

## Stop conditions

Stop and ask Michael before:

- interrupting the EliteDesk LAN connection;
- changing the host's primary IP configuration in a way that could break SSH;
- rebooting the host;
- requiring router changes;
- needing browser, phone, Bluetooth, QR-code, BIOS, password, or physical-device input;
- deleting or replacing the existing Home Assistant VM.

## Completion handoff

When the VM is directly reachable on the LAN and Matter is ready, give Michael exactly:

1. the new Home Assistant URL;
2. confirmation that CAOSCare and SSH still work;
3. the exact phone steps to pair the `MAP14AS1TWT-C` by scanning its Matter QR code;
4. one sentence telling him what to report back after pairing.

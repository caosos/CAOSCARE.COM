# XIAO Smart IR Mate — room infrared reference

The Seeed XIAO Smart IR Mate is an ESP32-C3 infrared puck for one room. CAOSCare reaches it through
Home Assistant's ESPHome integration and the `ir_blaster` adapter (`backend/device_ir_adapter.py`)
plus a brand code table (`backend/ir_codesets.py`). This file records the exact hardware behavior and
the interim setup procedure. It is **not yet the completed installer manual**; final provisioning,
mounting, rollback, fleet naming, acceptance receipts, and resident handoff remain open.

## Owner decision: keep touch as TV power

Michael's decision on 2026-10-12 is to **keep the top touch control** and use it as a local TV-power
button. Do not disable it.

The implementation detail matters: a single touch vibrates and presses the firmware's `Send` action,
which transmits the **currently selected learned slot**. The selector starts at `Signal0`, but the
firmware does not permanently hard-wire touch to slot 0 or to TV power. The approved room setup is:

1. Put the TV's power command in learned slot `Signal0`.
2. Select `Signal0` and leave it selected after setup or service work.
3. Prove one touch changes the intended TV and record the unverified-IR receipt before acceptance.
4. Recheck the selected slot after a restart, factory reset, relearn, or Home Assistant service visit.

**Pickup warning:** the top is a live capacitive touch surface. Picking up, wiping, stacking, or
gripping the puck by its top can vibrate the unit and send the selected IR command, toggling the TV.
Mount it where it will not be casually handled. Disconnect power before moving or cleaning it when an
accidental TV command would be disruptive. This behavior is intentional, not a wake-word indication.

## Exact capabilities in the current CAOSCare firmware

| Capability | Current behavior |
|---|---|
| Controller | Seeed XIAO ESP32-C3; ESPHome project `xiao.smart-ir-mate` 2.0. |
| IR transmit | GPIO3, 50% carrier duty. Home Assistant API actions send Sony SIRC, NEC, Samsung, LG, RC5, Pronto, or raw timing data. Raw learned replay uses 38 kHz. |
| IR receive / learn | GPIO4 receiver captures raw timings for learning and decodes/logs Sony, NEC, Samsung, LG, and RC5 traffic. Receiver logs prove what the puck heard; they do **not** prove the TV changed state. |
| Learned storage | Ten NVS-backed slots, `Signal0` through `Signal9`. Home Assistant exposes slot selection, Learn, Send, and learned/not-learned status. Long/repeating captures can truncate; prefer the standard protocol actions/code tables when reliable repeatable control is required. |
| Touch | GPIO5. A single touch vibrates, waits about 300 ms, then sends the currently selected learned slot. Double/triple-touch actions are not implemented in this CAOSCare firmware. |
| Vibration | GPIO6 motor. Used for touch and reset feedback; Home Assistant also exposes the vibration switch. |
| RGB | One WS2812 RGB LED on GPIO7. It turns on after Wi-Fi connects and blinks white while disconnected. Home Assistant exposes the light. |
| Physical reset | GPIO9 button. Release before 5 seconds: vibrate briefly and restart. Hold for at least 5 seconds: clear all ten learned slots, vibrate longer, and invoke ESPHome factory reset. Factory reset requires Wi-Fi reprovisioning and may require Home Assistant reconnection. |
| Network | 2.4 GHz Wi-Fi, ESPHome native API, fallback captive-portal access point, and password-protected ESPHome OTA firmware updates. The device name carries a MAC suffix. Reserve its DHCP address or maintain an equally durable hostname/IP mapping. |

`caoscare_ir_mate.yaml` is the CAOSCare firmware configuration. Build with ESPHome 2025.7.5 using
`esphome compile caoscare_ir_mate.yaml`; upload over Wi-Fi with
`esphome upload --device <ip> caoscare_ir_mate.yaml`. OTA normally retains stored Wi-Fi settings;
a USB flash or factory reset can require provisioning again. Never copy device credentials into an
installer report or receipt.

## Truth and read-back tiers

Infrared is one-way. A successful API/adapter response proves that the puck was asked to transmit; it
does not prove the TV received the signal, powered on/off, muted, or reached a numeric volume. The
puck's receiver can log remote-control traffic, but it still does not read the television's state.

- **Tier 1 — one-way IR:** report **command sent / unverified**. Stored power or volume is a last-command
  estimate, not an observation. Aria must not say “the TV is on,” “the TV turned off,” or “volume 20”
  solely from IR state. Relative volume/mute can be sent, followed by a resident check such as “Is that
  better?”
- **Tier 2 — state-reporting TV integration:** a supported network/HA integration may confirm power and
  numeric volume by read-back. Only that verified result supports an exact-state statement. IR remains
  a fallback, and its receipt remains unverified even if a separate integration later observes state.

## Room setup and placement

1. **Choose the control tier.** Prefer a supported state-reporting TV integration when exact power or
   volume is required. Register IR as the one-way fallback with the correct room, endpoint, and code
   table; never advertise IR as read-back capable.
2. **Power it reliably near the TV.** Prefer a dedicated, stable USB supply near the television. A TV
   USB port is acceptable only after proving that it remains powered while the TV is off/in standby;
   if that port loses power, the puck cannot turn the TV back on. Included cable/supply contents must
   be recorded during site intake rather than assumed.
3. **Aim for line of sight.** Place the IR face near and aimed at the TV's IR receiver window. Avoid
   cabinets, opaque doors, decor, or cable routing that blocks the path. Do not promise a distance:
   prove the actual room's seated distance and angles, including the farthest intended position.
4. **Protect the touch surface.** Fix the puck in place, keep the top reachable for deliberate use but
   away from routine pickup/cleaning contact, and label it “TV power — touch once.”
5. **Provision Wi-Fi.** After an authorized factory reset, join the advertised XIAO/Seeed fallback AP,
   open `192.168.4.1`, and select the room's 2.4 GHz network. Add the device to Home Assistant through
   ESPHome by IP when discovery cannot cross the HA VM/network boundary.
6. **Configure TV power touch.** Learn/provision power into `Signal0`, select it, test physical touch,
   and then test Home Assistant Send. If learned replay truncates or is unreliable, use a standard code
   table for remote control and leave touch acceptance open until Signal0 itself replays reliably.
7. **Register CAOSCare.** The TV device uses `protocol: "ir_blaster"`, the exact ESPHome endpoint and
   code-table identifier, and only capabilities proven on that TV. Every command needs its normal
   receipt/provenance and must remain labeled unverified unless a separate read-back path proves it.
8. **Acceptance.** From every intended room position, test deliberate touch power, network power,
   relative volume/mute, restore-after-call behavior, restart recovery, Wi-Fi recovery, and the pickup
   warning. Record exact device, room, firmware revision, tested/loaded revision, timestamps, receipts,
   and whether state was sent-only or independently read back.

## Evidence to date

Proven on 2026-10-12 in Room 214 with the Sony Bravia: physically observed standard Sony power
on/off/on plus volume-down and volume-up transmissions; the later room-command `volume_step` path had
CAOSCare receipts. Michael also physically observed that pickup/top touch vibrates and toggles the TV,
and explicitly chose to retain that feature. The IR adapter correctly records command results as
unverified. A learned long/repeating capture previously failed from truncation. Formal labeled Signal0
acceptance with an exact loaded revision and receipt, the permanent mounting/power arrangement, and the
completed installer manual are still pending.

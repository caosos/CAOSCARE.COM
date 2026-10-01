# Pilot Room 1 hardware list (BOM)

Created: 2026-10-01, for ready-queue item RQ-004 (Pilot hardware inventory).
Based on: `integration/2026-09-27` @ `c8c61d1` and `pilot/communications` @ `0978bb1`.
Method: repository evidence only (PROJECT_STATE, ELITEDESK_NODE_BUILD, ROOM_AUDIO_ARCHITECTURE, ARIA_WAKE_WORD_ARCHITECTURE, Lane F `PILOT1_COMMUNICATIONS.md` §2). No hardware, Home Assistant or database was inspected. Where the repo does not record a make, model or protocol, this file says **unknown**; nothing is guessed.

**Which room.** Michael's own room is the proving ground (direction given 2026-09-30). Every real device recorded in the repo sits in the **Room 214** test set-up in Michael's bedroom on the EliteDesk (Home Assistant names the AC `climate.bedroom_midea_ac`). This file assumes Room 1 = that room; Michael to confirm (question 1 below).

Status words: **Proven** = worked on real hardware with recorded evidence. **Owned** = Michael has it, not proven in CAOSCare. **Failing** = owned, tried, not dependable. **Needed** = not owned or not chosen.

## Inventory

| # | Item | Make / model | Protocol / path into CAOSCare | Owned? | Status | Evidence |
|---|---|---|---|---|---|---|
| 1 | Room node | HP EliteDesk 705 G4 DM (`caoscare1-hp-elitedesk`): AMD Ryzen 5 PRO 2400GE, 14 GiB RAM, 234 GB NVMe, Ubuntu 22.04.5 | Runs backend, room page, Home Assistant VM, RF decode, wake listener | Owned | Proven | `ELITEDESK_NODE_BUILD.md`; PROJECT_STATE 2026-08-02 |
| 2 | Home Assistant | Home Assistant OS 18.2 VM (`caoscare-homeassistant`) on the EliteDesk, NAT network, Matter Server add-on | `home_assistant` device adapter (`backend/device_adapters.py`) with read-back verification | Owned (software) | Proven | PROJECT_STATE 2026-08-02, 2026-09-05 |
| 3 | Lights | 2 × TP-Link Tapo L535E colour bulbs | Matter over Wi-Fi → Home Assistant (`light.smart_multicolor_bulb`, `…_bulb_2`) | Owned | Proven — voice and touch, power/brightness/colour/colour temperature, each confirmed by HA read-back | PROJECT_STATE 2026-09-05, 09-06, 09-19, 09-23 |
| 4 | Room cooling | Midea Duo Smart Inverter portable AC, model `MAP14AS1TWT-C` | Matter → Home Assistant `climate.bedroom_midea_ac`; modes off / cool / fan only; 61–86 °F | Owned | Failing — Matter session drops within minutes; Midea app discontinued; no verified voice temperature change | PROJECT_STATE 2026-09-05, 09-06; checklist Phase 7 |
| 5 | Thermostat | **unknown** | **unknown** | Owned (Michael, per `CURRENT_PRIORITY.md`) | Not tried. Room 214's thermostat record in CAOSCare is a `mock` device | `CURRENT_PRIORITY.md`; recovery checkpoint §5 |
| 6 | Smart plugs | **unknown** (count unknown) | **unknown** | Owned (Michael) | Not tried. Recorded intended use: TV power shut-off | PROJECT_STATE 2026-09-05 |
| 7 | TV | **unknown** | Control path **unknown** (IR, HDMI-CEC or network). Audio output type unknown (needed for TV-audio-through-eMeet) | Assumed owned — not recorded | Not tried. Room 214's TV record is a `mock` device | `ROOM_AUDIO_ARCHITECTURE.md`; PROJECT_STATE 2026-08-27 |
| 8 | IR transmitter | Not chosen | No IR adapter exists in code (`ir` is only a protocol name in `models.py`) | Needed | Needed if the TV is controlled by IR | Checklist Phase 7 |
| 9 | Room audio | eMeet OfficeCore Luna Plus speakerphone (USB; browser label "EMEET OfficeCore Luna Plus Mono") | One unit as the room's microphone **and** speaker | Owned | Proven for conversation (~10–12 ft with a fan running); wake detection practical only at ~3–4 ft | PROJECT_STATE 2026-08-25, 08-27, 08-29; `ARIA_WAKE_WORD_ARCHITECTURE.md` |
| 10 | Wake phrase | Local on-device listener (sherpa-onnx), `room-node/aria_wake/` | eMeet audio, local only | Software | Off. Single-word "Aria" rejected (false wakes 2026-09-24); phrase being chosen in the Wake Phrase Lab | `WAKE_PHRASE_LAB.md` |
| 11 | RF receiver | Nooelec NESDR SMArt v5 (SN 14054003) | `rtl_433` → `android-bridge/caos_rf_bridge.py` → `/api/rf/event`; currently single band 319.5 MHz | Owned | Proven | PROJECT_STATE 2026-08-29, 09-06 |
| 12 | Pendant | Lifeline pendant, decoded as Interlogix-Security at 319.5 MHz (`rfd_6e8f06632b41`, Room 214). A second test pendant (`rfd_07d25dc68a6b`) is disabled | RF receiver above | Owned | Proven press → event; staff response loop not accepted | PROJECT_STATE 2026-09-06; checklist Phase 7 |
| 13 | Room handset | Analog corded phone, simple large-button base. Model not chosen | RJ11 → ATA | **unknown** whether owned | Needed | Lane F §2.9 |
| 14 | ATA | Not chosen. Must support an off-hook auto-dial delay ("warm line") and one FXS port per room; confirm the setting before buying | SIP to Asterisk on the EliteDesk | Needed | Needed | Lane F §2.3, §2.9 |
| 15 | Front desk phone | SIP desk phone, extension 200 (PoE or own power supply). Model not chosen | SIP to Asterisk | Needed | Needed | Lane F §2.9 |
| 16 | Phone system | Asterisk 18 (Ubuntu package) on the EliteDesk; config in `telephony/asterisk/` on `pilot/communications` | Local | Software | Not installed | Lane F README |
| 17 | Phone line | SIP trunk (Telnyx recommended, prices not checked), one number per pilot room with an E911 address including the room number | Asterisk registration | Needed (account) | Not bought | Lane F §2.8 |
| 18 | Network | Today the EliteDesk is on Wi-Fi only (Intel Wireless-AC 9260, `192.168.1.151`); wired port `eno1` unplugged | Calling needs a stable, ideally wired LAN; router must allow outbound TLS 5061 and RTP to OpenAI; a tunnel exposes only the phone webhook | Partly | Wi-Fi works for current use; wired link and router rules not done | `ELITEDESK_NODE_BUILD.md`; Lane F §2.9 |

Not required for Pilot 1 per the repo: Zigbee, Z-Wave and blinds. Nothing in the repo records owning them.

## Known risks recorded in the repo

- Home Assistant's Matter networking depends on manual `iptables`/`ip6tables` rules that do not survive a reboot (PROJECT_STATE 2026-09-05). Pilot Room 1 must survive a reboot (RQ-006).
- The listener, backend and room page run as `nohup` processes, not boot services (PROJECT_STATE 2026-09-23).
- The facility's own pendant/call-button system must not be interfered with; the RF path stays listen-only and additive.

## One request for Michael

These answers unblock rows 5, 6, 7, 13 and 18. A photo of the label is enough for each device.

1. **Room.** Is Pilot Room 1 your bedroom — the Room 214 set-up? Does the Midea AC stay in it?
2. **Thermostat.** Brand and model (label photo). What does it control: wall heating/cooling, or something else? Which app does it use?
3. **Smart plugs.** Brand and model, and how many. Which app do they use?
4. **TV.** Brand and model number (sticker on the back). Is it a smart TV, and which audio outputs does it have (headphone, optical, HDMI-ARC)?
5. **Phones.** Do you already own an analog handset, an ATA or a SIP desk phone? If so, which models?
6. **Network.** Can the EliteDesk get a network cable to the router?

If these answers can't be provided, this item should move to BLOCKED rather than guessing models.

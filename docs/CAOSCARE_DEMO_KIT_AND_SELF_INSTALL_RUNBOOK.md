# CAOSCare demo kit and self-install runbook

Status: Room 214 development/demo procedure. A novice second-room installation has not yet passed, so this is not yet a production self-install claim.

## Keep the three installations distinct

| Installation | Hardware truth |
|---|---|
| Standard community | One central EliteDesk server; Home Assistant Voice Preview Edition room endpoints. Voice PE physical acceptance remains open. |
| Room 214 home/demo rig | EliteDesk + EMEET OfficeCore Luna Plus + Sony Bravia-family TV + XIAO Smart IR Mate + two Tapo L535E Matter bulbs. This path is physically demonstrated. |
| Future self-install package | Planned only until a novice repeats the installation in a second room using this manual without developer intervention. |

Do not market the Room 214 EliteDesk/eMeet rig as the settled community-room package.

## Before touching a device

Create one record containing:

- site and room;
- resident-facing name and CAOSCare device ID;
- manufacturer, exact model, serial/MAC, firmware, and a label photograph;
- installed location, line of sight, power source, and standby-power behavior;
- network/protocol, Home Assistant entity or endpoint, and code-table identifier;
- supported controls and which controls have independent read-back;
- reset, replacement, rollback, and reprovision steps;
- installer, timestamp, tested revision, loaded revision, and receipt link.

Never put Wi-Fi, OTA, Matter, Home Assistant, or API credentials in the record.

## Identify and name equipment

1. Photograph the product label, ports, remote, and intended installed location.
2. Identify an EliteDesk with DMI data and the eMeet by USB ID. Identify an unmarked puck through its ESP chip/MAC and Home Assistant identity.
3. Map one bulb/plug at a time by toggling it and physically confirming the fixture.
4. Treat a smart bulb/plug and the lamp or fixture it powers as separate physical records.
5. Use room-and-role names such as `Room 214 desk lamp`, never `Light 1`.
6. Save a mapping only after physical confirmation.

## Control truth

| Control path | What Aria may say |
|---|---|
| Matter/Home Assistant with current read-back | State is verified only after command and read-back agree. |
| TV LAN/API integration with current entities | Exact power/volume only after fresh read-back. |
| Bluetooth | Connectivity only unless that exact integration reports the requested state. |
| Infrared | Command sent / unverified. The resident's explicit physical confirmation is separate evidence. |
| Puck receiver log | The puck heard IR; it does not prove the TV changed. |

“Bluetooth-capable smart TV” alone is not enough for numeric volume. The integration must expose and read the number.

## Set up a TV remote by voice

Aria uses this governed sequence:

1. Ask for manufacturer and exact model when available.
2. Use live web research only to identify likely control methods. A web result is never executable IR code.
3. Match only a server-held, sourced, allowlisted control candidate.
4. Name one reversible test and ask permission: “I found a possible match. May I lower the TV by one step to test it?”
5. After a clear yes in a non-suspect turn, send exactly one volume-down test and say it was sent/unverified.
6. Ask whether the physical TV volume changed.
7. On a clear no, restore one step, reject the candidate, and save nothing.
8. On a clear yes, restore one step, bind the exact confirmation to the exact test receipt, and save the logical remote setting with a registry receipt.
9. Raw IR data never comes from the model/browser. A missing catalog candidate stops the process honestly.

The current catalog contains the physically proven Sony SIRC12 candidate. Other brands remain unsupported until sourced candidates and physical tests are added. The current firmware cannot write arbitrary catalog data into one of its learned NVS slots; do not claim that it did. Learned-slot provisioning still requires the real remote and the puck’s Learn function.

## XIAO Smart IR Mate

- Ten NVS-backed learned slots exist: `Signal0` through `Signal9`.
- Reserve `Signal0` for TV power. The top touch surface sends the currently selected learned slot, not permanently slot 0.
- Leave `Signal0` selected after setup or service and retest after restart, reset, relearn, or replacement.
- Standard Sony/NEC/Samsung/LG/RC5/Pronto actions do not prove a learned slot is configured.
- If touch access is wanted, place the puck beside the resident’s chair/stand only when IR line-of-sight testing passes. Label it “TV power — touch once.”
- Test pickup, wiping, and cleaning. Touch is intentionally retained, but casual handling can transmit.
- If TV-adjacent placement is required for reliable IR, record that touch is not resident-accessible.
- Use dedicated power unless that TV’s USB port is physically proven to stay powered while the TV is off.

Use the detailed firmware/reset/HA checklist in `room-node/ir_mate/README.md`.

## Conversation and TV-audio profiles

Two conversation styles are supported:

- **Supportive guidance (default):** respectful adult language, up to two choices, brief confirmation and one simple next step when useful. Never childish.
- **Concise and natural:** direct one- or two-sentence responses, silent continuity, and no recency comments or lingering availability offers.

The style never changes safety, truth, privacy, emergencies, wake brevity, or goodbye behavior. Voice selection remains separate.

Room 214’s accepted conversation-audio behavior is TV mute on wake and restore on close. A future opt-out must warn that loud TV audio can reduce wake and conversation accuracy. One-way IR cannot know an exact prior volume; verified numeric restoration requires a state-reporting integration.

## Acceptance checklist

- [ ] Exact inventory and label photographs are complete.
- [ ] EliteDesk cold boot restores required services without SSH.
- [ ] eMeet is selected for microphone and speaker; capture/playback are physically heard.
- [ ] `Aria` alone does not wake; `Hey Aria` does.
- [ ] Labeled wake series passes at normal seat/farthest location with TV off and on.
- [ ] TV mutes on conversation open and restores on close.
- [ ] Goodbye produces exactly `Okay, bye for now.` and closes once.
- [ ] Both bulbs operate by voice and agree with Home Assistant read-back.
- [ ] Puck `Signal0`, touch, HA Send, and Aria remote command operate the intended TV.
- [ ] IR wording remains sent/unverified until physical confirmation.
- [ ] Saved conversation style appears in a newly minted session and survives restart.
- [ ] Network loss reports unavailable truthfully and recovers unaided.
- [ ] A second room is installed by a novice using only this runbook.

Current Room 214 truth: hardware identity is substantially established; wake discrimination, TV mute/restore, concise goodbye, IR transmission, and touch behavior have physical evidence. Still open: exact Sony model label, formal Signal0/power/mount acceptance, far-field wake series, Voice PE acceptance, production per-device secrets, and second-room repeatability.

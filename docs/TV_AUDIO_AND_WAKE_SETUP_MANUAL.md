# TV audio and “Hey Aria” setup manual

This is the installer contract for any CAOSCare room with a television or room speaker. The goal is simple: “Hey Aria” must remain usable while the TV is playing, and the system must never pretend it knows a volume level that the hardware cannot report.

## Required default

`tv_audio_duck` is **on by default** for every kiosk, including records created before this setting existed.

When Aria opens a conversation:

1. Lower the room TV/speaker volume; never change TV power as a side effect of wake.
2. Start Aria's greeting immediately—the volume operation must not delay it.
3. Keep the lower volume for the conversation.
4. On every normal or abnormal conversation exit, restore the prior level. If the resident chose a new level through a state-reporting TV during the conversation, restore to that new chosen level instead.

The current infrared behavior sends 15 volume-down steps at conversation start and 15 volume-up steps at close. Because IR cannot report a boundary, this restoration is best-effort and can drift if the TV was already near minimum volume. A supported state-reporting TV lowers by 15 volume points from its observed baseline and verifies the result.

## Hardware capability classes

| TV connection | Can lower/restore for conversation? | Can Aria safely change volume during the conversation? | What Aria may claim |
|---|---:|---:|---|
| One-way infrared | Yes, by matched down/up steps | **No** | Only that commands were sent; never an exact volume |
| Two-way, state-reporting TV control | Yes | **Yes** | The volume returned by the device after the command |
| Bluetooth without readable volume state | Possibly | **No** | Bluetooth alone is not proof of readable volume |

A resident who wants “turn the TV up/down” while Aria is open needs a supported connection that both writes **and reads back** the current numeric volume. The adapter implemented in this repository today is a Home Assistant `media_player` entity with verified `volume_level` read-back. A future TV network API, suitable Bluetooth profile, Matter adapter, or other transport does not count until it implements the same verified contract. A “Bluetooth capable” label by itself does not pass.

For relative requests, Aria starts from the last verified resident baseline or the most recent verified choice, changes the resident's desired post-conversation level by the requested amount, and keeps the physical conversation level 15 points below that target while Aria is listening. It reads the result back and asks: **“Is that good?”** Further adjustments start from the newly chosen target. One-way IR volume commands are refused during the conversation rather than guessing.

## Opt-out and voice confirmation

Automatic TV lowering is recommended. A room may opt out, but the setting is durable and confirmation-gated.

Aria's opt-out confirmation is:

> To confirm, when I wake up, you don't want me to lower the TV volume; you want it to stay the same. That can make it harder for us to hear each other. Is that right?

The first tool call records only a five-minute pending proposal. It does not change the setting. A second call from the same live room session must carry a clear affirmative response such as “yes,” “correct,” or “that's right.” The completed change writes a receipt with resident, room, session, previous value, new value, and voice provenance. A suspect/echo-like turn cannot change it.

An administrator may also change **TV volume dip** on the kiosk settings screen. That write is receipted. Installers should leave it on unless the resident explicitly chooses otherwise.

## IR Mate placement and power

Seeed documents the XIAO Smart IR Mate as having three high-power IR emitters for 360-degree coverage, but does not publish a dependable room-distance rating. Treat range as an acceptance test, not a specification.

- Prefer a short USB cable and mount the IR Mate close to the TV's IR receiver window, with clear line of sight. Do not leave the board mechanically hanging from the TV's USB socket.
- Twelve feet with clear line of sight may work, but it is not an accepted installation until every required command passes the test matrix below.
- TV USB power is acceptable only if that USB port remains powered while the TV is in standby. If the port turns off with the TV, use an always-on 5 V USB supply; otherwise the IR Mate cannot send a power-on command.
- Strong sunlight and other infrared sources can reduce reliability. Reposition before changing firmware drive levels. Do not overdrive the emitters beyond the hardware/firmware design.

Seeed reference: <https://wiki.seeedstudio.com/XIAO_IR_Mate_Smart_IR_Remote/>

## Room acceptance before handoff

Record the exact TV model, connection type, adapter, capabilities, and whether each result has read-back.

1. At the resident's normal seat, with the TV at normal listening volume, say “Hey Aria” ten times at a normal voice. Record every detection and miss; do not replace evidence with a louder test voice.
2. Verify each detected wake lowers volume without changing TV power, Aria remains audible, and the microphone continues to understand normal speech.
3. End with “Goodbye” and “That'll be all for now.” Verify one brief goodbye and exact audio restoration on every end path.
4. For infrared: run at least ten power-on, power-off, volume-down, and volume-up commands from the mounted position. Receipts remain unverified because IR has no read-back.
5. For a state-reporting TV: verify the initial numeric volume, lower it for Aria, request up/down twice, confirm each returned number, hear “Is that good?”, and verify conversation close preserves the resident's latest chosen level.
6. Test the opt-out flow: the first request must only warn and ask for confirmation; a “no” must leave the setting unchanged; a clear “yes” must change it and produce one receipt. Re-enable the recommended default unless the resident chose the opt-out for actual use.

Wake-word misses are a microphone/detection problem, not an infrared-distance problem. The TV lowering happens only after “Hey Aria” has already been detected. Diagnose missed wakes with the configured microphone source, room noise, seat distance, input levels, and labeled attempts; do not tune TV commands or change the required wake phrase to hide a weak detector.

## Interaction profile setup

Voice and interaction profile are related user choices but separate settings. A voice changes how Aria sounds. The interaction profile changes how much orientation, reassurance, and explanation she gives. Changing a voice must not silently change a resident's interaction needs.

- **Guided** (default): brief orientation and reassurance when the resident appears unsure. This retains the existing more supportive behavior, but still forbids an extra availability speech after a clear goodbye.
- **Natural**: concise adult conversation. A wake gets one short answer such as “Yes, Michael?” It does not point out that the resident called again, say “didn't I just talk to you,” offer to hang around, or append an invitation. A clear ending receives exactly “Okay, bye for now.”

Select the interaction profile in the kiosk's room setup. This first slice is a **room/kiosk default**, not yet a resident-specific override or a complete personality catalog. Record the resident's choice; do not infer it from age. Resident overrides, voice/profile pairing, and additional personality styles remain future work and must not weaken the same truth, confirmation, receipt, and safety rules.

## Troubleshooting: identify the failing layer

| What the installer observes | Failing layer to inspect first | Evidence to collect |
|---|---|---|
| “Hey Aria” is said but the TV does not lower and Aria does not answer | Wake microphone/detector | Configured input source, speech/noise levels, labeled miss timestamp, seat distance, TV level |
| Aria answers, but the TV does not lower | TV command/adapter | Wake timestamp, device-command receipt, adapter response, TV power, IR line of sight |
| TV lowers, but Aria mishears the next sentence | Conversation microphone/audio competition | Mic source, VAD/transcript, TV level after lowering, speaker/mic placement |
| TV power or an unrelated control changes on wake | Command wiring defect | Exact receipt/action/value and device ID; wake must issue volume only |
| Infrared command works only nearby | IR placement/interference | Distance, angle, receiver-window location, light conditions, 10-command pass count |
| TV volume is changed but Aria cannot state the real level | One-way device | Adapter capabilities and read-back result; install a state-reporting connection |
| Aria says “back again” or offers to linger when unwanted | Interaction profile/prompt | Kiosk profile and prompt hash; use Natural |
| “Goodbye” produces more instructions or repeated confirmation | End-intent/tool grounding | User transcript, tool receipt/result, assistant transcript, session-end event |

The setup assistant should report the failing layer and the missing evidence instead of guessing. A successful command without hardware read-back remains **unverified**; a detected wake is not proof that the microphone will understand far-field conversation; and a configuration value is not acceptance until the physical room test passes.

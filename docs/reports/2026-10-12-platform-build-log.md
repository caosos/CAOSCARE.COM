# Platform build log — 2026-10-12 (coordinator session caoscare-1-64, with Michael)

Room 214 is Michael's home test room: everything below is **platform-wide** (every resident,
every room); only device records (which TV, which IR blaster) are per room. Branch
`integration/2026-09-27`. Production `06e7e2b` (website statuses + HC wrap only); everything
else is on the development runtime (EliteDesk), not yet released to caoscare.com.

## 1. What was built

| Area | What it does now | Commits | Proof |
|---|---|---|---|
| Dining: dietary & allergen labels | Staff-entered labels and "contains" allergens on each menu item; normalized, bounded, versioned with corrections, receipted; residents/Aria repeat them verbatim with a fixed "unlisted is not absent" note | `b2faae1` | backend tests, frontend tests, dev browser 11/11 (1280 + 390 px) — `2026-10-12-dining-dietary-allergen-truth.md` |
| Public website statuses | Everything proven in the test room is "In pilot" with its limits stated; TV/climate stay "In development"; planned stays planned | `ec51a8b` → PR #132 → **production `06e7e2b`** | Claude Chrome on caoscare.com after deploy |
| Room screen accessibility | Top row wraps on phones so the high-contrast (HC) button is visible | `042ef84` (prod `ec0297b`) | live kiosk screenshot 390 px |
| Lights: on/off truth | A light power change must agree with what the resident said; otherwise Aria asks "on or off?" | `8126a7b` | replay of 146 past light calls: 25 blocked incl. every wrong-direction case |
| Aria opening | "Hey Aria" gets a short answer to the name ("Hey, Michael."), never the previous call's opener; within 15 min of the last call she notices it ("Back again, Michael?") | `7bac843`, `40f7c3e` | live Room 214 voice 17:39, 17:55, 17:56 |
| Aria goodbye | "Bye for now" → "Okay, bye for now." and the call ends; open tool calls answered first; no second (browser) voice | `9f71f10`, `77e3351` | live voice 17:39, 17:45, 17:55 |
| Continuity across days | Recent talk recap 18 h → 72 h; calendar-day wording ("yesterday", not "earlier today"); clock time on each prior call | `9d15215`, `40f7c3e` | live: "When's the last time I talked to you?" → "Just a minute or two ago … you said 'Bye for now'" |
| **Lifelong memory** | Every finished conversation summarized once into the existing memory store and folded into one bounded life story per resident; loaded every call | `2013d53`, `46b99d4` | backfill of 49 Room 214 conversations → 34 summaries + life story |
| Home Assistant reachable on the LAN | User service relays the HA VM (libvirt NAT) to `http://<server>:8123` for Wi-Fi room devices and phones | `bcfeae7` | 200 from the LAN address |
| IR Mate firmware | Seeed's IR Mate config + Home Assistant actions to send standard codes (Sony, NEC, Samsung, LG, RC5, Pronto, raw) + decoded-code logging | `f198372` | OTA install; device decoded its own send as Sony 0xA90 |
| **Infrared TV control (`ir_blaster` adapter)** | Any room's TV via an HA IR blaster + a brand code table (`ir_codesets.py`, Sony Bravia first): discrete power, exact volume (reset-and-count, then estimate), volume steps, mute. Always "sent, not verified". Aria's "louder" = a few presses + "how's that?" | `ffeca1a` | live: Sony power on/off/on; 100 down + 50 up; room command path `volume_step` ±3 |
| Test suite health | Two tests that had failed all day fixed (configured voice; auth header) | `9d15215` | backend 661/0/13, frontend 97/663 |

## 2. Problems hit and how they were fixed

| Problem (evidence) | Cause | Fix |
|---|---|---|
| "Hey Aria" missed often | On-device detector recall (not backend/model) | Shadow detector at 0.01/3.5 logs what a more sensitive setting would catch; live setting unchanged pending labelled tries |
| Aria turned the light the **opposite** way ("Turn on my overhead light" → off), Oct 9, 10, 12 | The model decides from audio; the transcript is separate; nothing compared them | Direction check before any light power change (`8126a7b`) |
| A false wake at 02:04 turned the light off ("Overhead line") | Same as above: no power words in the sentence | Same check refuses a power change the sentence never asked for |
| "I'm still waiting on that to finish" on goodbye | The model's end_call arrived ~120 ms before the transcript; the goodbye was requested while end_call had no answer | End controller answers open tool calls before the goodbye (`9f71f10`) |
| Two voices said goodbye | Aria's goodbye started before the end was granted; the browser fallback also spoke | A goodbye already playing counts as heard (`77e3351`) |
| Same long greeting every call | Prompt always said "greet appropriately ('good afternoon')"; the session never used how the call started | `aria_opening.py` (`7bac843`) |
| Re-wake 4 min later felt like a new call; "no timestamp" | Wake rule dominated; recap had no clock times | Re-wake opener + clock times (`40f7c3e`) |
| Aria forgot after 18 h; long-term memory had 1 entry from 49 calls | Only single-exchange "facts" were extracted; nothing kept what conversations were about | Lifelong memory (`2013d53`) |
| Life story invented "his friend Momdani" / cut mid-word | Fold prompt allowed labels; hard character cut | Fold forbids unstated relationships; trims at a sentence (`46b99d4`) |
| "Yesterday 9 PM" read as "earlier today" | Age wording counted 24-hour blocks | Facility calendar days (`9d15215`) |
| Website showed "In development" for work done in pilot | Status registry not updated since 09-27 | Registry + limits text (`ec51a8b`), deployed |
| HC button "gone" | Top row overflowed on phones | Wrap (`042ef84`) |
| Merge to `main`, starting the HA relay, writing its files | Claude Code auto mode guards (merge without review, expose local services) | Michael merged PR #132; permission rules added for the relay |
| "Voice PE" not found anywhere | The device in hand was the XIAO IR Mate (ESP32-C3), not the Voice PE (ESP32-S3) | Identified by chip id; Voice PE still to arrive |
| IR Mate hotspot not visible | Not in setup mode; EliteDesk Wi-Fi scans 5 GHz only | Factory reset (long press); Michael provisioned Wi-Fi from his phone |
| Learned TV power did nothing | Capture truncated (`idle: 65.5 ms` catches repeat frames; buffer overflow) | Send standard Sony codes instead of recordings (`f198372`, `ffeca1a`) |
| IR Mate vibrated / sent when picked up | Its top is a touch sensor that sends slot 0 | Explained; disabling touch-send is on the list |
| Firmware build failed | Seeed's config needs a newer ESPHome than Python 3.10 allows | Built with 2025.7.5, one log line adjusted |
| TV went off every time a call opened | Old room-page "auto-mute": powers off TVs it thinks are on; restores only on cancel, not normal end | Kept by owner choice for now (wake indicator); platform fix proposed |
| TV then stopped going off | One-way IR: CAOSCare thought the TV was off after the real remote turned it on | The core IR limit — see "What's left" |
| Dev backend restart killed its own shell | `pgrep -f` matched the command itself | Restarts now stop the process found by its port |
| A status comment claimed a relay was committed when it was not | Comment posted in the same step as a refused write | Public correction posted on #129 |

## 3. What's left (owner-visible checklist)

- [ ] **Call-start TV behaviour, platform-wide:** replace "power off" with "volume down N steps, restore N steps at call end" for one-way TVs (reversible, state-independent); add a non-TV wake signal (chime/light).
- [ ] **Bravia network control** (HA `braviatv`, Michael sets a Pre-Shared Key on the TV): verified power/volume read-back; IR stays as fallback.
- [ ] **IR Mate:** disable touch-to-send; reserve its address on the router; one IR Mate per room in provisioning docs.
- [ ] **Voice PE** (not yet in hand): stock-firmware bring-up on Wi-Fi + HA, room microphone test, then the "Hey Aria" firmware (PR #46) and CAOSCare as the conversation agent.

### Correction — 2026-10-13

Michael explicitly retained touch-to-TV-power after physically observing it. This supersedes the earlier “disable touch-send” notes without erasing them. Touch sends the currently selected learned slot; setup reserves `Signal0` for TV power, leaves it selected, labels placement, and requires physical acceptance. See `room-node/ir_mate/README.md` and `docs/CAOSCARE_DEMO_KIT_AND_SELF_INSTALL_RUNBOOK.md`.
- [ ] **Wake recall:** labelled "Hey Aria" tries (normal / across the room / TV on) → set the live score.
- [ ] **Re-wake opener** still adds a question after "Back again"; trim.
- [ ] **Start-of-call mis-transcriptions** (foreign-language fragments) — investigate transcription language/settings.
- [ ] **Receipts for device record edits** (`PUT /devices/{id}` writes none).
- [ ] **Release:** 300+ integration commits are not yet in production; cut a release candidate, test, merge to `main`, deploy, LIVE_VERIFY.
- [ ] **Owner decisions still open:** Alerts acknowledge/close roles; review-flag ownership; family re-notify on repeat presses; Front Desk message scope.
- [ ] Twilio credentials (SMS/calls) when Michael has them.

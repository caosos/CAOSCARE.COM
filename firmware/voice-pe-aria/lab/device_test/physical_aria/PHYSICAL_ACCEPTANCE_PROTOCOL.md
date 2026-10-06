# Voice PE physical wake test — operator sheet

**Hey Aria · Hey Sivia · Hey Callista**

> **RESEARCH ONLY — NOT COMMERCIALLY RELEASABLE.** These models were trained with non-commercial
> data. This is a test build, not shipping firmware.
> **Do not flash until Michael has authorized flashing.** Nothing in this sheet has been run yet.
> The product wake phrase remains **Hey Aria**. Hey Sivia is a usability candidate; Hey Callista is
> an acoustic benchmark. Hey Kookaburra is not in this build.

Everything below runs on the EliteDesk (`caoscare1-hp-elitedesk`), user `caoscare-1`.

---

## 1. What you are testing

| Wake phrase | Say it exactly | In Home Assistant it appears as | Model file | Model SHA-256 |
|---|---|---|---|---|
| **Hey Aria** (active at first boot) | "hey **AR**-ee-uh" | Hey Aria | `hey_aria.tflite` | `981d660be48098280756f9b21d6f5830842a31cbd904b62194ac8c1a61a8c4fe` |
| Hey Sivia | "hey **SIV**-ee-uh" (SIV as in *civil*) | Hey Sivia | `hey_sivia_siv_ee_uh.tflite` | `896c4e2bc6f5bcbd31858828dfb6eee4a7bbec078a74ca4254d79a31c43e8af7` |
| Hey Callista | "hey kuh-**LISS**-tuh" | Hey Callista | `hey_callista_kuh_liss_tuh.tflite` | `f1ff21a0d35d32bb1644f536d24b9885bb7ad7b56e30669363f5e11b856f0ef9` |

**Sensitivity** ("Wake word sensitivity" select in Home Assistant; applies to all three):

| Setting | Hey Aria | Hey Sivia | Hey Callista |
|---|---|---|---|
| **Slightly sensitive** (default; the lab's matched cutoff) | 0.90 | 0.99 | 0.98 |
| Moderately sensitive | 0.80 | 0.89 | 0.88 |
| Very sensitive | 0.70 | 0.79 | 0.78 |

Lower numbers wake more easily (and falsely more often).

**Lab expectations** (synthetic voices and rooms — the room test is the real evidence):

| | Catch | Catch, TV on | Simulated older voice | Wrong-word wakes | Simulated false wakes/h |
|---|---|---|---|---|---|
| Hey Aria | 44.5% | 13.9% | 6.9% | 1.63% | 0.36 |
| Hey Sivia | 38.8% | 15.3% | 4.9% | 0.18% | 0.00 |
| Hey Callista | 58.0% | 42.4% | 20.8% | 0.22% | 0.36 |

## 2. Artifacts

Ready-to-flash copies (outside git, with checksums):
`/home/caoscare-1/caoscare-firmware-work/artifacts/voice-pe-physical_aria/`

| File | Bytes | SHA-256 |
|---|---|---|
| `caoscare-voice-pe-physical_aria.factory.bin` — full image, for USB | 3,252,832 | `a885d3ef9d6733353f3624ca1dd951867f7dc29cf0131230af848af9f42ec8da` |
| `caoscare-voice-pe-physical_aria.ota.bin` — over-the-air update image | 3,187,296 | `92778bad2f86b27940cfed4d2bee124d69c9b40f86d318ac0823b6ce9e9be399` |
| `physical_aria-voice-pe.yaml` — build config | 3,700 | `843925ab0f116762f8b495cea9ca784541614bc0f224d5a85c9dbabb637999bb` |
| `models/` — the three `.tflite` models and their manifests | | see `SHA256SUMS` |

- Same list in this folder: `SHA256SUMS`. Build record: `../../results/device_test_physical_aria.json`.
- Build: ESPHome 2026.9.0, official Voice PE package 26.9.0, compile exit 0, RAM 50.9%
  (174,087 / 341,760 B), flash 39.2% (3,187,179 / 8,126,464 B). Device firmware version string:
  `26.9.0-lab.physical_aria`.
- To rebuild from the repo instead: in `firmware/voice-pe-aria/lab/`, run
  `~/caoscare-firmware-work/venv-mww/bin/python build_device_test.py physical_aria hey_aria hey_sivia_siv_ee_uh hey_callista_kuh_liss_tuh`
  and check the new hashes match the table.

## 3. Before you start (checklist)

- [ ] Michael's written authorization to flash this build.
- [ ] Voice PE, USB-C **data** cable to the EliteDesk.
- [ ] Serial access: `caoscare-1` is not in the `dialout` group today. Either run the serial
      commands below with `sudo`, or once run `sudo usermod -aG dialout caoscare-1` and log in again.
- [ ] The room: Voice PE where a resident's unit would sit (dresser/nightstand, ~1 m high). Note the
      room size and the TV's distance from the device.
- [ ] A phone sound-meter app (optional) to note the TV level at the device.
- [ ] Speakers: Michael at minimum. Better: 6 people (3 women, 3 men), at least 3 aged 75+ (one soft
      voice, one raspy voice, one with dentures). Give each an ID (S1, S2 …) — no names in the record.
- [ ] About 1 hour per speaker for the wake trials, plus the soaks (section 7).

## 4. Flash (only after authorization)

Use `E=~/caoscare-firmware-work/venv-esphome/bin` and
`A=~/caoscare-firmware-work/artifacts/voice-pe-physical_aria`.

1. **Write down the current state** in Home Assistant (Settings → Devices → Voice PE): firmware
   version and selected wake word.
2. **Check the image:** `cd $A && sha256sum -c SHA256SUMS` — every line must say `OK`.
3. **Connect** the Voice PE by USB-C and find its port: `ls /dev/ttyACM*` (usually `/dev/ttyACM0`).
   If nothing appears, enter bootloader mode: unplug, hold the centre button, plug the cable back
   in, keep holding ~2 s, release.
4. **Back up the current firmware (rollback copy, ~3 min):**
   `$E/esptool --chip esp32s3 --port /dev/ttyACM0 read-flash 0x0 0x1000000 $A/backup-before-flash-$(date +%F).bin`
   Keep this file; it restores the device exactly as it was.
5. **Flash:**
   `$E/esptool --chip esp32s3 --port /dev/ttyACM0 --baud 460800 write-flash 0x0 $A/caoscare-voice-pe-physical_aria.factory.bin`
6. **Unplug and re-plug** (or press reset). If Wi-Fi is not kept, provision it again with Improv
   (Bluetooth or USB), the same as a new device.
7. **Verify in Home Assistant:** version `26.9.0-lab.physical_aria`; the wake-word select lists
   exactly Hey Aria, Hey Sivia, Hey Callista; sensitivity shows "Slightly sensitive".
8. **Verify the boot log** (from the repo copy of the config, which has the build cache):
   `cd ~/CAOSCARE-WAKE-FUNNEL/firmware/voice-pe-aria/lab/device_test && $E/esphome logs physical_aria/physical_aria-voice-pe.yaml --device /dev/ttyACM0` —
   no `micro_wake_word` error and no tensor-arena error. Say "hey AR-ee-uh" once at 1 m and look
   for a line like `Detected 'Hey Aria' with sliding average probability is …`. Ctrl-C to stop.

If any check fails: stop and roll back (section 9).

## 5. Logging during the test

Keep the Voice PE on USB to the EliteDesk and record every detection with the harness:

```
cd ~/CAOSCARE-WAKE-FUNNEL/firmware/voice-pe-aria/lab/device_test
mkdir -p physical_aria/runs
$E/esphome logs physical_aria/physical_aria-voice-pe.yaml --device /dev/ttyACM0 \
  | python3 device_harness.py --stdin --out physical_aria/runs/$(date +%F)-session1.csv
```

Keyboard commands are typed in the same terminal (the harness reads them from the keyboard while the
log streams in). Harness keys: `t <trial-id>` start a block · `m` right after each attempt · `e` end the block ·
`q` quit. A mark with no detection within 3 s is a miss; a detection with no mark is a false wake.
Trial IDs: `<phrase>-<condition>-<speaker>-<sensitivity>`, e.g. `ARIA-Q1-S1-slight`,
`SIVIA-TD-S2-slight`, `CALLISTA-SOAK_TV-none-slight`.

## 6. Wake trials — exact sequence

For each speaker, run the three phrases in a rotated order: session 1 Aria → Sivia → Callista,
session 2 Sivia → Callista → Aria, session 3 Callista → Aria → Sivia.

**For each phrase:**

1. In Home Assistant select that phrase only, sensitivity **Slightly sensitive**.
2. Read the pronunciation to the speaker once; then let them say it their own way. Note the form
   they actually used.
3. Run the blocks below in this order, **10 attempts each**, about 5 s apart, `m` after every
   attempt:

| # | Code | Condition | Distance | Position | TV |
|---|---|---|---|---|---|
| 1 | Q1 | quiet | 1 m | seated, facing device | off |
| 2 | Q2 | quiet | 2 m | seated, facing | off |
| 3 | Q4 | quiet | 4 m | standing, facing | off |
| 4 | FA | facing away | 2 m | seated, back to device | off |
| 5 | BS | from bed / seated | bed or armchair, ~2–3 m | as a resident would | off |
| 6 | SV | softer voice | 2 m | seated, facing | off — deliberately quiet |
| 7 | CS | casual speech | 2 m | seated, facing | off — in a sentence: "oh, hey Aria, what time is it?" |
| 8 | TL | TV low | 2 m | seated, facing | on, low volume |
| 9 | TN | TV normal | 2 m | seated, facing | on, normal volume |
| 10 | TD | TV dialogue-heavy | 2 m | seated, facing | on, normal volume, news or talk show |
| 11 | RN | repeated natural attempts | wherever the speaker is | natural | as it happens — 10 intended wakes; after a miss the speaker simply tries again as they would in real life; mark every try |

4. **Wrong-phrase block** (quiet, 1 m, same selected phrase): say each item 3 times with `m` after
   each; any wake is a wrong-phrase wake — note which phrase caused it.
   - the other two candidates' phrases;
   - for Hey Aria: area, "hey area", Maria, "hey Maria", Ari, "hey Ari", Ariel, Daria, Victoria;
   - for Hey Sivia: Sylvia, "hey Sylvia", Olivia, Siri, Syria, severe, trivia, "see via";
   - for Hey Callista: Calista, Krista, Crystal, Melissa, Clarissa, Christmas;
   - the launcher alone: "hey", "hey there".
5. Fill one row per block in `PHYSICAL_ACCEPTANCE_RECORD.csv` (section 8).

## 7. Unsolicited-wake soaks (nobody says any wake phrase)

One phrase selected per soak, sensitivity Slightly sensitive, harness running with a soak trial
(`t <PHRASE>-SOAK_<type>-none-slight`, no `m` marks — every detection is unsolicited).

| Day | Soak | Duration | Content |
|---|---|---|---|
| 1 night | Hey Aria overnight | 8 h | room as normal, TV off |
| 2 night | Hey Sivia overnight | 8 h | same |
| 3 night | Hey Callista overnight | 8 h | same |
| days 2–4 | TV soak, one phrase per day | 4 h | TV at normal volume — news, game shows, a movie, commercials; nobody in the room |
| days 2–4 | Daytime soak, one phrase per day | 8–12 h | normal activity: TV, conversation, phone calls, visitors |

Record each soak as one row (hours and unsolicited wakes; what was playing, if known).

## 8. Recording

`PHYSICAL_ACCEPTANCE_RECORD.csv` (this folder) is pre-filled with one row per phrase × block. Copy
a fresh set of rows for each additional speaker or sensitivity. Columns:

`date, session, speaker_id, phrase_selected, sensitivity, condition_code, distance_m, position,
tv_level, pronunciation_used, attempts, successful_wakes, misses, wrong_phrase_wakes,
wrong_phrase_said, unsolicited_wakes, soak_hours, notes`

- `misses = attempts − successful_wakes`.
- Wrong-phrase rows: `attempts` = phrases said, `wrong_phrase_wakes` + `wrong_phrase_said`.
- Soak rows: `unsolicited_wakes` + `soak_hours`.
- Keep the harness CSVs in `physical_aria/runs/`; they are the raw evidence behind the sheet.

## 9. Rollback / recovery

- **Restore exactly what was there before:**
  `$E/esptool --chip esp32s3 --port /dev/ttyACM0 --baud 460800 write-flash 0x0 $A/backup-before-flash-<date>.bin`
- **Official stock firmware:** open https://esphome.github.io/home-assistant-voice-pe/ in Chrome or
  Edge with the device on USB-C → Connect → Install. Restores Okay Nabu and the update entity.
- **Device unresponsive:** bootloader mode (section 4, step 3), then either of the above.
- **Factory reset** (wipes Wi-Fi, encryption key, light settings): hold the centre button ~30 s
  until the red ring completes.
- Switching phrases needs no reflash: use the wake-word select in Home Assistant.

## 10. Pass / fail criteria

Fixed before any trial. Michael may change them **before** testing starts, not after. A phrase
passes only if **every** line holds **at one sensitivity setting** (catch blocks and soaks at the
same setting), counted over all speakers combined:

| Measure | Pass |
|---|---|
| Q1, Q2 (quiet, 1–2 m) | ≥ 90% caught, and no speaker below 7/10 |
| Q4, FA, BS (distance, facing away, bed/seated) | ≥ 80% |
| SV, CS (soft voice, casual speech) | ≥ 80% |
| TL, TN (TV low / normal) | ≥ 80% |
| TD (TV dialogue-heavy) | ≥ 70% |
| RN (repeated natural attempts) | ≥ 95% of intended wakes succeed within 2 tries |
| Wrong-phrase wakes on the other two candidates' phrases | 0 |
| Wrong-phrase wakes on the sound-alike list + launcher | ≤ 1 per phrase per speaker |
| Unsolicited — overnight 8 h | 0 |
| Unsolicited — TV soak 4 h | ≤ 1 |
| Unsolicited — daytime soak | ≤ 1 per 12 h |

- If a phrase fails at Slightly sensitive only on catch, you may repeat its failed catch blocks at
  Moderately sensitive — but then its three soaks must also be repeated at Moderately sensitive.
- **Outcome:** Hey Aria passes → it is the candidate for the product path (still research models:
  a shippable version needs retraining on commercially licensed data). Hey Aria fails → record why
  (which conditions); whether Hey Sivia or Hey Callista goes forward is Michael's decision.

## 11. When finished

Commit to `research/wake-phrase-funnel` (or hand the files over): the filled
`PHYSICAL_ACCEPTANCE_RECORD.csv`, the harness CSVs in `physical_aria/runs/`, and a note of the
backup file's name and SHA-256. Leave the device on this build or roll back, and record which.

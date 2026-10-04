# Physical Voice PE wake-phrase test sheet

**Purpose:** choose the wake phrase from real-device evidence. Synthetic lab
results only decide which candidates reach this sheet. The finalists are listed
in `../RESULTS.md`, under "Physical-test finalists".

**Not yet run.** The Voice PE has not arrived, and no device has been flashed.

## Setup (once)

1. Build the research firmware with the finalist models and record its
   SHA-256 here: ____________________.
   **Research firmware only**: the models were trained with non-commercial
   data (see `../LICENSES.md`).
2. Flash over USB as described in `../../README.md` → "Flash / recovery".
   Record the device's firmware version in Home Assistant.
3. Put the Voice PE where a resident's unit would sit (dresser or nightstand),
   about 1 m high, and record the room size and furnishing.
4. Start the harness, run every trial through it, and keep the CSV:
   `python device_harness.py --yaml ../../caoscare-voice-pe.yaml --out runs/<date>-<room>.csv`
5. Before each finalist's block, select its wake word in Home Assistant and
   set "Wake word sensitivity". Record both.
6. Run the finalists in a rotated order (A-B-C, B-C-A, C-A-B), so fatigue and
   time of day don't favour one.

## Speakers

- **Minimum:** 6 real speakers: 3 women and 3 men.
- **At least 3 aged 75+**, including at least one each of:
  - soft voice;
  - raspy or hoarse voice;
  - dentures or missing teeth;
  - slower speech;
  - a Southern US accent.
- **Record per speaker** (no names): ID, age band, sex, accent, dentures y/n,
  hearing aid y/n.
- **Pronunciation:** read the pronunciation once, then let them say it their
  own way. Record the form actually used, e.g. "AR-ee-uh" or "AIR-ee-uh". Don't
  coach mid-trial.

## Wake trials: 10 utterances per cell, per speaker, per finalist

Type `m` in the harness right after each utterance. Leave about 5 s between
utterances.

| Cell | Distance | Posture | Room condition | Facing | Notes |
|---|---|---|---|---|---|
| Q1 | 1 m | seated | quiet (TV off, HVAC normal) | toward device | |
| Q2 | 2 m | seated | quiet | toward | |
| Q4 | 4 m | standing | quiet | toward | |
| B1 | bed (~2–3 m) | lying down | quiet | ceiling / away | |
| T2 | 2 m | seated | TV on, normal volume, news or talk show | toward | measure TV dB at the device: ___ |
| T4 | bed | lying down | TV on | away | |
| S2 | 2 m | seated | quiet, deliberately soft voice | toward | |
| O2 | 2 m | seated | second person talking nearby | toward | |

**Per finalist, record:**
- true activations ÷ utterances, and missed;
- false activations during the cell;
- wake-to-LED latency, if measured with a stopwatch or video.

## Confusion trials

Each speaker says each phrase 3 times at 1 m: area, Maria, Daria, Ari, Ariel,
Victoria, malaria, "hey Maria", "hey Ari", Krista, Crystal, Christmas,
Melissa, Cassandra, extra, listen, very, various. Add each finalist's top
sound-alikes from `../results/phase2_confusion.csv` and launcher-only words
(hey, hello, okay).

- Count every activation as a false activation.
- Record which phrase caused it.

## False-wake soak (no one says the wake phrase)

| Soak | Duration | Content | Record |
|---|---|---|---|
| Overnight | 8 h, 22:00–06:00 | room as normal; TV off | every detection (time, phrase) |
| Full day | 12 h | normal activity: TV on several hours, conversations, phone calls, staff visits | every detection plus what was playing or said, if known |
| TV-only | 4 h | TV at normal volume on news, game shows, movies and commercials, nobody in the room | detections per hour |

Report false activations per hour for each soak and each finalist. Use the HA
logbook as a cross-check of the harness CSV.

## Sensitivity persistence after reboot

1. Set "Wake word sensitivity" to "Moderately sensitive" and select the
   finalist.
2. Power-cycle the device: unplug for 10 s, then plug back in.
3. After boot, confirm in HA:
   - the sensitivity still reads "Moderately sensitive";
   - the selected wake word is unchanged.
4. Say the wake phrase 5 times at 2 m and record detections.
5. Repeat after an OTA reboot, if OTA is used.

Result: pass / fail ______.

## Also verify on the device

- **Boot log:** no `micro_wake_word` tensor-arena errors.
- **Stop word:** ends a ringing timer.
- **Controls:** mute switch stops detection; the centre button and LED ring behave
  as in stock firmware.
- **End to end** (only if the HA→CAOSCare voice bridge is installed): wake →
  Assist → CAOSCare → spoken reply. The bridge (`spike/voice-bridge` @ `aa3d2f1`)
  is not installed or accepted yet.

## Decision rule (for Michael)

**Prefer the finalist with the lowest soak false activations per hour that
also reaches:**
- at least 90% true activation in Q1, Q2 and B1 for every speaker;
- at least 80% in T2.

Any phrase older residents could not remember or say comfortably is
disqualified regardless of numbers. Record that judgement from the speakers
themselves.

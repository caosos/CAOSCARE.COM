# Voice PE "Aria" wake-word firmware — spike

**Status: spike, evaluation only. Nothing here has been flashed to any device.**
The Voice PE has not arrived. Offline results come from synthetic speech only,
not from real voices in a real room. Do not ship this to a resident room until
the device tests at the end have passed.

## Provenance

- On 2026-10-03, Michael corrected the earlier Naboo direction. The assistant
  identity is **ARIA**, and the wake-word candidates are "Hey Aria" and "Aria",
  pronounced **AR-ee-uh**.
- "Naboo", "Hey Naboo", "Hey Nabu" and "Okay Nabu" are not CAOSCare product
  wake words. "Eria" was not created or trained.
- This branch (`firmware/voice-pe-aria`) starts from `firmware/voice-pe-naboo`
  @ `9dff64b`. That branch is preserved unchanged as historical evidence.

This folder holds a Home Assistant Voice PE firmware config with two custom
microWakeWord models, `aria` and `hey_aria`, plus the scripts that trained and
evaluated them. CAOSCare backend, room-node, website and the voice-bridge
branch are untouched.

## Device flow this firmware is part of

```
"Aria" / "Hey Aria"  ->  Voice PE wakes on-device (microWakeWord, no cloud audio)
  ->  Home Assistant Assist pipeline carries the voice turn
  ->  CAOSCare handles conversation, resident memory, governance, tools,
      workflows, actions, provenance and receipts
  ->  Voice PE plays Aria's spoken response
```

This firmware covers the first step only: local wake detection. The rest of
the pipeline (HA → CAOSCare conversation agent → response audio) is built and
configured outside this firmware. **It is not built or verified here.** It
needs its own end-to-end test once a device is on the network.

## What it is

| Item | Value |
|---|---|
| Upstream source | `github.com/esphome/home-assistant-voice-pe`, tag `26.9.0` (commit `2644f4c`), file `home-assistant-voice.factory.yaml`, pulled as a remote package and not edited |
| ESPHome | 2026.9.0 (the upstream `min_version`) |
| Added | two microWakeWord models, `aria` and `hey_aria` |
| Default on first boot | **Aria**, because it has better offline results. ESPHome enables only the first model in the list. |
| Selectable in Home Assistant | Aria, Hey Aria |
| Removed | stock wake words Okay Nabu, Hey Jarvis, Hey Mycroft; the stock "Wake word sensitivity" select, replaced by one with the same name that tunes the Aria models; the factory `update` entity, the "Beta firmware" switch and `dashboard_import` (an OTA update to stock firmware would silently remove the Aria wake words) |
| Unchanged from the official firmware | microphones and XMOS audio front end, speaker / media player, buttons, LED ring, mute switch, timers, the internal "stop" word and VAD, Home Assistant API, Improv (BLE/serial) provisioning |

Renaming a model in YAML does not create a new wake word. Both `.tflite` files
are newly trained models; neither is a relabelled stock model.

## Pronunciation — an important finding

The speech generator uses espeak to turn text into sounds. espeak reads the
plain spelling **"Aria" as /ˈɛɹiə/ ("AIR-ee-uh")**. That is the same sound as
the word **"area"** (/ˈɛɹiə/).

The target AR-ee-uh (/ˈɑːɹiə/) comes from respellings, so the training
positives are "Ahria", "Ahreea" and "Ahrya" (with "Hey " for the `hey_aria`
model). Clips of the plain spelling ("Aria" as TTS reads it, i.e.
"AIR-ee-uh") are reported separately as a diagnostic. They count neither as
hits nor as false accepts.

**Real-world risk:** a resident who says "AIR-ee-uh" is saying "area". On
2026-09-24 the earlier room listener false-woke on exactly that word (see
`docs/WAKE_PHRASE_LAB.md`).

## Training method and data

The models follow microWakeWord's official `basic_training_notebook`: the same
augmentation, features and `mixednet` architecture, trained for 10,000 steps
on CPU. Pinned commits are in `training/MICROWAKEWORD_COMMIT` and
`training/PIPER_SAMPLE_GENERATOR_COMMIT`.

- **Positives:** Piper LibriTTS-R multi-speaker generator, 1,000 clips per
  spelling, speaking speed varied 0.8–1.25×.
- **Hard negatives (added to the notebook recipe):** 47 phrases at 60 clips
  each, including all the required confusions:
  - area, the area, that area, this area, common area, hey area;
  - Maria, hey Maria, Daria, hey Daria, Ari, hey Ari, Hey Siri, Siri;
  - more sound-alikes: Korea, Ria, Ariel, Harry, sorry, malaria, Gloria,
    Mario, Arianna, "are you there", and others.

  The `hey_aria` model also trains on bare "Aria" (AR-ee-uh) as a negative.
- **Augmentation:** MIT room impulse responses plus FMA and AudioSet
  backgrounds, at −5…10 dB SNR (notebook settings).
- **Negative feature sets:** `kahrendt/microwakeword` `speech`,
  `dinner_party` and `no_speech`. Validation uses `dinner_party_eval`
  (CHiME-6); the final test uses DiPCo (5.3 h of ambient audio).
- **Local patch to microWakeWord:**
  `training/microwakeword-chunked-ambient-validation.patch`. Validation now
  evaluates the ambient set in chunks; built as one array, it was OOM-killed
  on this 14 GB machine. The patch only changes memory use.
- **Licence limit:** the notebook states that the augmentation and negative
  datasets are for **non-commercial personal use**. These models are research
  artifacts; a commercial build needs licensed training data.

## Offline evaluation

The evaluation scripts are `training/eval_model.py` and
`training/summarize_eval.py`. Raw scores are in `results/*_heldout_eval.json`
and the tables in `results/summary.txt`.

The model under test is the quantized streaming model that runs on the
device. The detection rule is the device's: the mean of 5 consecutive
probabilities must exceed the cutoff.

**Voices:** six Piper VITS voices never used in training (lessac, amy, ryan,
joe, alan, cori), with speaking speed varied 0.8–1.25×.

**Clip sets:**
- 270 positives per model.
- 270 opposite-phrase clips.
- 120 "AIR-ee-uh" diagnostic clips.
- 744 sound-alike clips, split into:
  - 384 from 18 phrases never trained on (Valeria, Victoria, cafeteria,
    criteria, Syria, Austria, Ariana, hey Gloria, hey Victoria, hey Mario,
    "hey Siri, are you there", Marie, diary, Laria, hey Larry, I'm sorry,
    hurry, "Harry, are you here");
  - 360 from 13 required phrases that were also training negatives, spoken
    by new voices.
- 180 ordinary sentences with similar sounds, never trained on. Examples:
  "The common area is on the second floor.", "Maria said she would be here
  at noon.", "Hey Siri, what time is it?".

**Seven listening conditions:**
- clean;
- −12 dB and −24 dB (volume);
- a simulated 5 × 4.5 × 2.7 m room at 1 m, 2 m and 4 m from the device;
- 4 m with background noise at 10 dB SNR.

### Results

Counts are clips over the cutoff out of clips tested.

**Aria @ 0.90 (shipped default)**

| Condition | True activations | Missed | False: held-out sound-alikes | False: trained sound-alikes | False: sentences |
|---|---|---|---|---|---|
| clean | 235/270 (87%) | 35 | 50/384 (13%) | 32/360 (9%) | 6/180 (3%) |
| quiet −12 dB | 243/270 (90%) | 27 | 49/384 | 34/360 | 4/180 |
| very quiet −24 dB | 246/270 (91%) | 24 | 46/384 | 32/360 | 4/180 |
| room 1 m | 173/270 (64%) | 97 | 18/384 | 28/360 | 1/180 |
| room 2 m | 173/270 (64%) | 97 | 20/384 | 25/360 | 3/180 |
| room 4 m | 174/270 (64%) | 96 | 22/384 | 30/360 | 1/180 |
| room 4 m + noise | 143/270 (53%) | 127 | 30/384 | 32/360 | 8/180 |

**Hey Aria @ 0.97 (shipped default)**

| Condition | True activations | Missed | False: held-out sound-alikes | False: trained sound-alikes | False: sentences |
|---|---|---|---|---|---|
| clean | 184/270 (68%) | 86 | 57/384 (15%) | 81/360 (23%) | 15/180 (8%) |
| quiet −12 dB | 181/270 (67%) | 89 | 55/384 | 76/360 | 11/180 |
| very quiet −24 dB | 179/270 (66%) | 91 | 52/384 | 69/360 | 10/180 |
| room 1 m | 181/270 (67%) | 89 | 42/384 | 63/360 | 7/180 |
| room 2 m | 181/270 (67%) | 89 | 47/384 | 72/360 | 8/180 |
| room 4 m | 181/270 (67%) | 89 | 53/384 | 86/360 | 7/180 |
| room 4 m + noise | 154/270 (57%) | 116 | 43/384 | 62/360 | 10/180 |

**DiPCo ambient test (5.3 h, from the training test split):**
- Aria: 0 false activations per hour at cutoff ≤ 0.86 (14.7% missed), so also
  0 at the shipped 0.90.
- Hey Aria: no cutoff below 1.0 reaches 0 false activations; at 0.94 it has
  0.375 per hour (2 false activations) with 11.3% missed.

**Clips most often falsely accepted (all conditions):**
- Aria: Ari, Ariana, Harry, Marie, hey Victoria, Maria, hurry, that area,
  cafeteria.
- Hey Aria: hey Mario, hey Ari, the area, hey area, hey Gloria, hey Maria,
  hey Daria.

**"AIR-ee-uh" diagnostic** (plain "Aria" spelling, i.e. "area"): accepted 3%
by `aria` and 43% by `hey_aria` at the shipped cutoffs.

### Which candidate is better

**Aria performed better than Hey Aria on every measure in this test.** It had:
- more true activations (87% vs 68% clean);
- fewer false activations on held-out sound-alikes, trained sound-alikes and
  sentences;
- 0 versus at least 0.375 ambient false activations per hour on DiPCo.

**"Hey Aria" did not give materially better separation; it gave worse.** The
"hey" prefix let "hey Mario / hey Maria / hey Ari / hey area" through, and its
positives were inconsistent: two voices, alan and ryan, mostly produced
rejected AR-ee-uh renditions.

**Neither model is ready for residents.** Even the better one:
- falsely accepts about 1 in 8 held-out sound-alike clips (Ari, Ariana, Marie);
- misses about a third of distant-talker clips in the simulated room.

For comparison, the earlier "Hey Naboo" model on the same recipe falsely
accepted 1/696 sound-alikes. "Aria" sits inside many common words and names
(area, Maria, Ariana, Victoria), which this offline test reflects.

### Limits of these checks

- Everything is synthetic text-to-speech: no real elderly voices or accents.
- Nothing was recorded through the Voice PE's microphones, XMOS AEC/beamformer
  or its gain stage.
- The room is a simple simulation, and its background noise comes from the
  AudioSet clips also used in training.
- The held-out set is small: 6 voices.

## Build

```bash
python3 -m venv venv && venv/bin/pip install "esphome==2026.9.0"
venv/bin/esphome compile caoscare-voice-pe.yaml
```

Output goes to `.esphome/build/home-assistant-voice/build/`:
- `firmware.factory.bin`: full image, for USB.
- `firmware.ota.bin`: app only, for OTA.

Build evidence (2026-10-03, EliteDesk, ESPHome 2026.9.0; both builds exit 0):

| Build | factory.bin | ota.bin | Flash used | RAM used |
|---|---|---|---|---|
| Stock factory, tag 26.9.0 (reference) | 3,272,096 B | 3,206,560 B | 39.5% | 51.1% (174,591 B) |
| This config (Aria) | 3,190,224 B | 3,124,688 B | 38.4% | 50.7% (173,215 B) |

SHA-256 of this build:
- `firmware.factory.bin`: `376003f01c522d9ce5ed40436e8ec3095b711848fae4c9ab03714d4f2a71d3f0`
- `firmware.ota.bin`: `b1fe3c861d9cc0de6bbcc9d24c7f2100076d91381dc1faeff437db4daf15dbdb`

Contents check on `firmware.ota.bin`:
- **Present:** the project string `CAOSCare.Voice PE Aria spike` and the wake
  word "Hey Aria".
- **Absent:** "Okay Nabu", "Hey Jarvis", "Hey Mycroft", "Naboo", and the
  `firmware.esphome.io` update URL.
- **Models:** each is 62,304 B; measured TFLite-Micro arena is 25,584 B, and
  the manifests use 34,000 B.

The image is smaller than stock because three stock wake-word models were
removed and two added.

The binaries are build outputs and are not committed; rebuild from this config.

To retrain:
1. Copy `training/*.py` into a work directory and apply the patch to a
   microWakeWord checkout at the pinned commit.
2. Run `fetch_data.py`, then `gen_samples.py`, then
   `train_model.py <aria|hey_aria>`.
3. Run `eval_model.py <run> [cutoffs]`, then
   `summarize_eval.py <run> <cutoff>`.
4. Run `make_manifest.py <run> <cutoff> <arena>` from the work directory.
   Manifests are written to this folder's `models/`.

## Flash / recovery (physical Voice PE) — not performed; device has not arrived

**Before flashing:** note the device's firmware version and wake word in Home
Assistant (Settings → Devices → Voice PE).

**First flash over USB (recommended):**
1. Connect the Voice PE to a computer with a USB-C data cable.
2. Either:
   - run `venv/bin/esphome run caoscare-voice-pe.yaml --device /dev/ttyACM0`
     from this folder (macOS: `/dev/cu.usbmodem*`; Windows: `COMx`); or
   - open ESPHome Web at https://web.esphome.io (Chrome/Edge), choose Connect,
     then Install, and select `firmware.factory.bin`.
3. If no serial port appears, enter bootloader mode: unplug the device, press
   and hold the centre button, plug the USB-C cable back in, keep holding
   briefly, then release. Then retry step 2.
4. The build keeps Improv provisioning. If Wi-Fi is not retained, provision it
   again over Bluetooth or USB (Improv), the same as a new device.
5. In Home Assistant, check that:
   - the device reports `CAOSCare.Voice PE Aria spike 26.9.0-aria.1`;
   - the wake word is Aria, with Hey Aria selectable.

**Later updates over the air:** from an ESPHome dashboard that has adopted
this device, install `firmware.ota.bin`.

> "Take control" in ESPHome changes how the device is managed. Prefer USB for
> a single test unit.

**Switching wake words without reflashing:** pick Aria or Hey Aria in Home
Assistant. The stock wake words are not in this build.

**Full recovery to stock firmware:**
1. Open the official installer at https://esphome.github.io/home-assistant-voice-pe/
   in Chrome or Edge, with the device on USB-C.
2. Choose Connect, then Install. This writes the latest official firmware,
   restoring Okay Nabu and the update entity.
3. If the device is unresponsive, use bootloader mode (step 3 above) first.

**Factory reset** (wipes Wi-Fi, the encryption key and light settings): hold
the centre button for about 30 s, until the red ring completes and the device
says to stop.

## Still requires testing on the actual device

1. **Boot and load:** both models load without a tensor-arena error. Check
   `esphome logs caoscare-voice-pe.yaml` at boot for `micro_wake_word` errors.
2. **Real speakers:** true/missed activations with the people who will say
   it, at 1, 2 and 4 m, seated and lying down, quiet and with TV on. Include:
   - the AR-ee-uh pronunciation;
   - how often people actually say "AIR-ee-uh".
3. **False activations:** an overnight and full-day soak in the target room
   with TV, conversation, and names like Maria/Ari/Victoria. Record wake
   events from the HA logbook. This is the deciding test for "Aria" given the
   offline numbers.
4. **Sensitivity select:** "Slightly / Moderately / Very sensitive" changes
   the Aria cutoffs (0.90 / 0.80 / 0.60; Hey Aria 0.97 / 0.94 / 0.89). Confirm
   the select persists its value across reboot.
5. **Behaviour:**
   - LEDs, mute switch, centre button and timers still work;
   - the stop word still ends a ringing timer;
   - switching between Aria and Hey Aria takes effect.
6. **End to end:** wake → HA Assist → CAOSCare conversation → spoken response.
   This depends on the HA/CAOSCare pipeline, which is outside this firmware.
7. **Recovery:** reflashing stock firmware through the official installer,
   verified on this exact unit.
8. **Licence decision** on the training data before any non-personal use.

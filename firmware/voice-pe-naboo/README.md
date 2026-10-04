# Voice PE "Naboo" wake-word firmware — spike

**Status: spike, evaluation only. Nothing here has been flashed to any device.**
Offline results come from synthetic speech only, not from real voices in a real room.
Do not ship this to a resident room until the device tests listed at the end have passed.

This folder holds a Home Assistant Voice PE firmware config with two custom
microWakeWord models, "Hey Naboo" and "Naboo". It also holds the scripts that trained and
evaluated them. CAOSCare backend, room-node, and website code are untouched.

## What it is

| Item | Value |
|---|---|
| Upstream source | `github.com/esphome/home-assistant-voice-pe`, tag `26.9.0` (commit `2644f4c`), file `home-assistant-voice.factory.yaml`, pulled as a remote package and not edited |
| ESPHome | 2026.9.0 (the upstream `min_version`) |
| Added | two microWakeWord models, listed **before** the stock ones |
| Default on first boot | **Hey Naboo** (ESPHome enables only the first model in the list) |
| Still selectable in HA (fallback) | Naboo (experimental), **Okay Nabu**, Hey Jarvis, Hey Mycroft — all stock models, unchanged |
| Removed | the factory `update` entity, the "Beta firmware" switch, and `dashboard_import`. Accepting an OTA update to stock firmware would silently remove the custom wake words. |

Renaming a model in YAML does not create a new wake word. Both `.tflite` files here
are newly trained models; neither is a relabelled stock model.

## Training method and data

The models follow microWakeWord's official `basic_training_notebook`: the same
augmentation, features and `mixednet` architecture, trained for 10,000 steps.
Pinned commits are in `training/MICROWAKEWORD_COMMIT` and
`training/PIPER_SAMPLE_GENERATOR_COMMIT`.

- **Positives:** synthetic speech from Piper's LibriTTS-R multi-speaker generator.
  The spelling is varied so the model hears both pronunciations: espeak reads
  "Naboo" as /ˈnæbuː/ (NAB-oo) and "Nahboo"/"Nabu" as /ˈnɑːbuː/.
  - Naboo model: "Nahboo", "Nah-boo", "Naboo", 1,000 clips each.
  - Hey Naboo model: "Hey Nahboo", "Hey Nah-boo", "Hey Naboo", 1,000 clips each.
- **Hard negatives (added to the notebook recipe):** 47 sound-alikes such as taboo, bamboo,
  Nobu, nobody, Kabul, "hey nurse", "hey Bob", at 60 clips each. The Hey Naboo model also
  trains on bare "Naboo" as a negative.
- **Augmentation:** MIT room impulse responses plus FMA and AudioSet backgrounds,
  at −5…10 dB SNR (notebook settings).
- **Negative feature sets:** `kahrendt/microwakeword` `speech`, `dinner_party`
  and `no_speech`. Validation uses `dinner_party_eval` (CHiME-6). The final test uses
  DiPCo (5.3 h of ambient dinner-party audio).
- **Local patch to microWakeWord:** `training/microwakeword-chunked-ambient-validation.patch`.
  Validation now evaluates the ambient set in chunks. Built as one array, it was
  OOM-killed on this 14 GB machine. The patch only changes memory use; the metrics are
  accumulated the same way.
- **Licence limit:** the notebook states that the augmentation and negative datasets
  are for **non-commercial personal use**. These models are therefore research
  artifacts. A commercial build needs training data that is licensed for commercial use.

## Results (offline, synthetic)

The quantized streaming model is the one that runs on the device. Both models: 62,304 bytes.
Measured TFLite-Micro arena: 25,584 bytes. The manifests use 34,000 bytes, a 1.3× margin,
consistent with the stock manifests' own margins.

**microWakeWord test split**: augmented held-out positives, plus DiPCo ambient audio
for false accepts per hour (FA/h):

| Model | Cutoff | False reject | FA/h (DiPCo, 5.3 h) |
|---|---|---|---|
| Hey Naboo | **0.96 (shipped)** | 9.7% | 0.00 |
| Hey Naboo | 0.94 | 9.0% | 0.19 (1 FA) |
| Naboo | 0.82 | 31.3% | 0.00 |
| Naboo | **0.67 (shipped)** | 23.7% | 0.19 (1 FA) |

**Held-out voices**: six Piper VITS voices never used in training
(lessac, amy, ryan, joe, alan, cori). Clips are clean, with 1 s of leading silence.
- Positives: 270 per model.
- Opposite phrase: 270 per model (bare "Naboo" clips for the Hey Naboo model, "Hey Naboo" clips for the Naboo model).
- Sound-alikes: 696 clips. 17 phrases were never trained on (Danube, Malibu, Kazoo,
  "hey Mabel", "Winnie the Pooh", and others); 12 were trained-on phrases spoken in new voices.
- Detection rule: mean of 5 consecutive probabilities above the cutoff, as on the device.

| Model @ cutoff | True accept | Opposite phrase accepted | Sound-alike false accepts |
|---|---|---|---|
| Hey Naboo @ 0.96 | **263/270 (2.6% FR)** | bare "Naboo": 0/270 | 1/696 ("Danube", one voice) |
| Naboo @ 0.67 | 155/270 (42.6% FR) | "Hey Naboo": 76/270 | 27/696 (taboo, Nobu, Malibu…) |

**Reading the Naboo numbers.** Most of the Naboo misses are voices that say a respelling
differently. For example, ryan and joe read "Nahboo" with a different vowel, so those
clips partly test TTS pronunciation rather than the model. Even so, the bare word is
weak:
- It accepts many sound-alikes (taboo, Nobu, Malibu).
- It fires inside "Hey Naboo", which is expected: the word is contained in the phrase.

A two-syllable wake word has very little acoustic context, so this is the expected
trade-off.

**Recommendation:** use "Hey Naboo" as the device test candidate. Keep bare "Naboo"
selectable for comparison only. If "Hey Naboo" fails in the room, fall back to the
stock **Okay Nabu**, which is still in the firmware.

### Limits of these checks

- Everything is synthetic TTS. There are no real elderly voices and no real accents.
- Nothing was recorded through the Voice PE's own microphones or its XMOS front end.
- The false-accept rate covers 5.3 h of dinner-party audio. It does not cover TV,
  overnight room noise, or the target room.
- The held-out set is small: 6 voices.
- The "Wake word sensitivity" select in the stock firmware adjusts only the stock models.
  The custom models always use their manifest cutoffs.

## Build

```bash
python3 -m venv venv && venv/bin/pip install "esphome==2026.9.0"
venv/bin/esphome compile caoscare-voice-pe.yaml
```

Output (`.esphome/build/home-assistant-voice/build/`): `firmware.factory.bin`
(full image, USB) and `firmware.ota.bin` (app only, OTA).

Build evidence (2026-10-03, EliteDesk, ESPHome 2026.9.0, both compiled with exit 0):

| Build | factory.bin | ota.bin | Flash used | RAM used |
|---|---|---|---|---|
| Stock factory, tag 26.9.0 (reference) | 3,272,096 B | 3,206,560 B | 39.5% | 51.1% (174,591 B) |
| This config | 3,381,136 B | 3,315,600 B | 40.8% | 51.4% (175,831 B) |

SHA-256 of this build:
- `firmware.factory.bin`: `45c3189287b732b19f5722b22a249cf809ac40e4ae2062cc152705dfb7b267cf`
- `firmware.ota.bin`: `e9ffbc1b1d0c8be78049555a9a713e26045f9a257a04e7bd11afb439df8b1a48`

The image embeds project `CAOSCare.Voice PE Naboo spike 26.9.0-naboo.1`, and the
"Hey Naboo" and "Okay Nabu" wake-word names. It contains no
`firmware.esphome.io` update manifest URL, which confirms the update entity was removed.
The binaries are build outputs and are not committed. Rebuild them from this config.

To retrain:
1. Copy `training/*.py` into a work directory.
2. Run `fetch_data.py`, then `gen_samples.py`, then `train_model.py <naboo|hey_naboo>`.
3. Run `eval_model.py <run> [cutoffs]`.
4. From the work directory, run `make_manifest.py <run> <cutoff> <arena>`.

Steps 1–3 use a Python 3.10 venv with microWakeWord (with the patch applied),
piper-sample-generator and piper-tts.

## Flash / recovery (physical Voice PE) — not yet performed

**Before flashing:**
- Note the device's current firmware version in Home Assistant
  (Settings → Devices → Voice PE).
- Note its current wake word.

**Flash over USB (recommended for the first test):**
1. Connect the Voice PE to a computer with a USB-C data cable.
2. Run `venv/bin/esphome run caoscare-voice-pe.yaml --device /dev/ttyACM0`, or use
   ESPHome Web (`web.esphome.io`) → Connect → Install, and select `firmware.factory.bin`.
3. If the port does not appear, enter bootloader mode: unplug the device, hold the
   centre button, plug it in, keep holding briefly, then release.
4. The factory build keeps Improv provisioning. Wi-Fi credentials stored on the
   device are normally preserved. If they are not, re-provision over Bluetooth or USB
   (Improv), the same way as a new device.
5. In Home Assistant, the device should reappear. Its project/version should show
   `CAOSCare.Voice PE Naboo spike 26.9.0-naboo.1`.
   - Under the device's voice/wake-word settings, the wake word should be "Hey Naboo".
   - "Naboo", "Okay Nabu", "Hey Jarvis" and "Hey Mycroft" should also be listed.

**Over-the-air (OTA):** from an ESPHome dashboard that has adopted this device,
install `firmware.ota.bin`.

> "Taking control" with ESPHome changes how the device is managed. Prefer USB for
> a single test unit.

**Fallback, without reflashing:** in Home Assistant, set the wake word back to
**Okay Nabu**. The stock model is unchanged in this build.

**Full recovery to stock firmware:**
1. Open the official installer at <https://esphome.github.io/home-assistant-voice-pe/>
   over USB-C (Chrome or Edge).
2. Choose Connect, then Install. This writes the latest official firmware.
3. If the device is unresponsive, use bootloader mode (step 3 above).
4. Factory reset (wipes Wi-Fi and the encryption key): hold the centre button about
   30 s, until the red ring completes.

## Still requires testing on the actual device

1. **Boot and load:** the custom models load without a tensor-arena error.
   Check `esphome logs` at boot for `micro_wake_word` errors.
2. **Real speakers:** wake accuracy with the people who will actually say it. Test at
   1, 2 and 4 m, seated and lying down, quiet and with TV on, across "NAB-oo" and
   "NAH-boo" pronunciations.
3. **False wakes:** an overnight and full-day soak in the target room with TV and
   normal conversation. Record wake events from the HA logbook.
4. **Behaviour:**
   - LED, sound, mute switch, timers and stop word still work.
   - The Assist pipeline starts after a wake.
   - Switching between "Hey Naboo" and "Okay Nabu" in HA takes effect.
5. **Fallback:** reflashing stock firmware through the official installer, verified on
   this exact unit.
6. **Licence decision** on the training data before any non-personal use.

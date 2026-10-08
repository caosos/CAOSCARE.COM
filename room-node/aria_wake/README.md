# "Hey Aria" wake endpoint (EliteDesk home setup)

> **Additional Aria voice endpoint on the EliteDesk. Not standard apartment hardware.**
>
> The standard apartment design (Michael, 2026-10-03) is one central EliteDesk
> server running Home Assistant and CAOSCare, with a Home Assistant Voice PE in
> each apartment as the Aria room voice endpoint ("Hey Aria"). See
> `docs/ROOM_AUDIO_ARCHITECTURE.md`. This listener speaks the **same
> detector-to-page protocol** the Voice PE endpoint will use, so the room page,
> conversation, tools, memory and receipts are identical whichever endpoint woke
> Aria. It is used for:
> - Michael's home setup (always-listening Aria on this EliteDesk with the eMeet);
> - development before the Voice PE, synthetic and microphone testing;
> - emergency fallback if Voice PE acceptance fails, and comparison testing.
>
> **Disabled by default.** It does not start unless `ARIA_WAKE_ENABLE=1` is set
> (the earlier name `ARIA_WAKE_ENABLE_LEGACY=1` still works), and the room page
> only connects to it when its URL carries `?wake=1`. No standard provisioning
> (deploy script, demo setup) installs or starts it; the optional systemd units
> below are installed only by a person running `ctl.sh install`.
>
> **Retirement condition:** May only be considered for removal after Voice PE real-room acceptance proves wake accuracy, conversation continuity, response playback and deterministic session ending.

**Wake phrase: "Hey Aria"** (Aria is the assistant's name; the single word
"Aria" is **not** accepted - it sounds like "area"; `docs/WAKE_PHRASE_LAB.md`).
The listener refuses to start with a single-word `ARIA` keyword file unless
`ARIA_WAKE_ALLOW_SINGLE_WORD=1` (comparison testing only). At start it logs
the phrase, keywords file, threshold, score, model and allowed origins.

On-device wake trigger for a room endpoint. Implements the
trigger half of `docs/ARIA_WAKE_WORD_ARCHITECTURE.md`: it listens on the
room's existing audio capture endpoint (the eMeet, via the PulseAudio default
source, shared - never exclusive) and tells the room page, over a
**localhost-only** WebSocket, that the phrase was heard. The page starts the
existing Realtime conversation (`trigger_source: "wake_word"`, no resident
event, no new backend control surface).

No audio leaves the machine for wake detection, nothing is recorded, nothing
is transcribed.

## Engine

[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) open-vocabulary keyword
spotting (Apache-2.0), model `sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01`
(int8). Chosen over openWakeWord for the first proof only because no usable
pretrained openWakeWord "Aria" model exists (the one community "Aria" model is
Spanish-trained, published recall 0.01) and a custom openWakeWord model needs
a training run. sherpa-onnx also ships a native Android KWS library, so the
same model runs on an Android endpoint.

Keyword: `keywords.txt` = `▁HE Y ▁A RI A @HEY_ARIA` (BPE tokens from the
model's `bpe.model`, identical to the Wake Phrase Lab's encoding of "HEY ARIA").
`keywords_aria_single_word.txt` (`▁A RI A @ARIA`) is kept only so the offline
evaluation can compare the old single word on identical audio. Tunables (env):
`ARIA_WAKE_KEYWORDS_THRESHOLD` (default 0.15, the lab's setting; higher = fewer
wakes of both kinds), `ARIA_WAKE_KEYWORDS_SCORE` (1.0), `ARIA_WAKE_KEYWORDS`
(other keywords file).

Code: `detector.py` (spotter, silence reset, `StreamDetector` - no I/O, shared with
`eval_offline.py`), `aria_wake.py` (audio capture, state machine, WebSocket),
`wake_stats.py` (log tally + miss/false marks), `ctl.sh` + `systemd/` (always on).

## Setup (EliteDesk)

```bash
cd room-node/aria_wake
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
curl -LO https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2
tar xjf sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2
mkdir -p model && cp sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/{tokens.txt,*.int8.onnx} model/
ARIA_WAKE_ENABLE=1 .venv/bin/python aria_wake.py   # JSON-lines log on stdout
```

Env: `ARIA_WAKE_SOURCE` (PulseAudio source; default = system default source),
`ARIA_WAKE_PORT` (8765), `ARIA_WAKE_ORIGINS` (allowed page origins; default
`http://localhost:3000,http://127.0.0.1:3000`), `ARIA_WAKE_MODEL_DIR`.

Enable it on the room page per endpoint: `/kiosk/<kiosk_id>?wake=1`
(or `?wake=ws://127.0.0.1:<port>`). Without the parameter the page never
connects.

## Protocol (the portable part)

```
detector -> page  {"type":"hello", ...}
                  {"type":"wake", "wake_id", "keyword", "detected_at", "confidence", "audio_input_device", ...}
                  {"type":"listening", "at", "reason"}      # return-to-wake ack
page -> detector  {"type":"state", "state":"conversation"|"listening", "reason"}
```

Modes: `listening` → wake → `pending` → page reports `conversation` →
session ends → page reports `listening` → 1.5 s cooldown → `listening`.
Only `listening` may emit a wake, so Aria's own speech cannot re-trigger it.
A wake the page never confirms expires back to `listening` after 20 s.

An Android endpoint implements the same protocol from a native foreground
service (e.g. sherpa-onnx Android KWS, or an openWakeWord Android port) and
loads the same room page.

## Always on (systemd --user), evidence, offline evaluation

`./ctl.sh test-audio-access` (can this user open the eMeet; prints the one `sudo`
command if not), `./ctl.sh install` (venv, two user units, env file
`~/.config/aria-wake/aria-wake.env`), `status`, `logs [-f]`, `restart`, `uninstall`.
Units: `systemd/aria-wake.service.in` (listener, `Restart=on-failure`) and
`systemd/aria-wake-kiosk.service.in` (Room page in **headless Chrome**
`--headless=new` as the same user, `--use-fake-ui-for-media-stream`, autoplay
allowed, `PULSE_SOURCE`/`PULSE_SINK` from the env file, `Restart=always`, waits
for the frontend). Host check 2026-10-08: Chrome 155 present; `Xvfb`/`xvfb-run`
not installed and not needed. Nothing is installed by the repo itself.

`wake_stats.py summary --log FILE` tallies wakes, page-confirmed sessions,
unconfirmed wakes, detections suppressed during conversation, and Michael's own
marks (`wake_stats.py mark miss|false --note ...`). Physical procedure:
`docs/reports/2026-10-08-room214-wake-physical-runbook.md`.

`eval_offline.py --run <wakelab acoustic run>` rebuilds the lab's synthetic test
audio from its cache (never calls an API) and feeds it through the listener's own
`StreamDetector`.

## Proven vs unproven

PROVEN (physical, Room 214, 2026-09-23, single word "Aria", close range, Chrome
on the desktop session): wake with no touch started a conversation in under 1 s;
the real overhead light turned OFF then ON with Home Assistant read-back before
Aria confirmed; "goodbye" ended it; the next wake worked; return-to-wake logged.
At bed distance Michael had to speak louder.

PROVEN BAD (physical, 2026-09-24 02:06-02:46 UTC): the single word "Aria" woke
five times from background speech ("that area", "underneath her", "thirteen",
"Buna ziua"). "Aria" and "area" are the same sounds (CMUdict `EH R IY AH`), so no
threshold separates them; the single word was rejected as the product phrase.

OFFLINE (SYNTHETIC audio, below): "Hey Aria" removes the bare-"area" false wakes,
but it can still wake on "hey area" / "hay area" / "hey Ari", and far-field and
TV-over-speech recall is low.

NOT PROVEN: "Hey Aria" with a real voice on the real eMeet; far-field pickup; the
real false-wake rate with TV and normal talk; headless Chrome capturing and
playing through the eMeet; the always-on units; elderly or accented speech.
All of these need the microphone (runbook).

### Offline results (numbers only; audio is not committed)

Command (2026-10-08, threshold 0.15, model gigaspeech 3.3M int8, 1817 s):
`python eval_offline.py --run tools/wakelab/runs/20260924T053222_acoustic_hey-aria --out eval_results_2026-10-08.json`.
SYNTHETIC: gpt-4o-mini-tts voices x 6 speaking styles x simulated rooms; adversarial
lines (nearest sound-alikes, traps, Room 214 regression phrases); LibriSpeech
test-clean read speech for the soak. Same audio for both detectors, run through the
listener's own `StreamDetector`. Result file: `eval_results_2026-10-08.json`.

| | **"Hey Aria"** (default) | "Aria" (old single word) |
|---|---|---|
| true wakes (924 clips) | **629 (68%)** | 675 (73%) |
| clean / quiet / noise / fast / slow | 93% / 64% / 81% / 92% / 79% | 89% / 70% / 92% / 94% / 86% |
| **far (reverb)** | **39%** | 30% |
| **TV speech at 5 dB** | **28%** | 50% |
| adversarial false wakes (952 lines) | **8 (1%)** | 63 (7%) |
| what woke it | "hey area" x4, "hay area" x3, "hey Ari" x1 | "bay/gray/home area" sentences, "ari are you awake", "gray area", "beneficiary of", "hey area", ... |
| bare "area" phrases | 0 woke | woke repeatedly |
| soak false wakes (5.62 h) | **0** (0.0/h) | 0 (0.0/h) |

Reading it: "Hey Aria" is about 8x fewer adversarial false wakes and removes every bare-"area"
wake, at the cost of slightly lower recall and **weak far-field (39%) and TV-over-speech
(28%) recall**; the remaining false wakes are all "hey" + a sound-alike. The "Hey Aria" and
adversarial counts equal the lab's own report for the same run (629/924, 8/952, 63/952),
confirming the listener path and the lab's mirror agree. The old single word's soak showed
2 false wakes (0.36/h) in the lab's 10-minute-block run but 0 here, where the stream is
continuous with different chunk alignment: a 0-2 events in 5.6 h difference caused by stream
framing, not a real gap between the phrases. Read speech is calmer than a room with TV and
conversation, so 0/h on the soak is NOT a prediction of the real false-wake rate; the
2026-09-24 single-word wakes came from live background speech. The physical soak decides.

## Tests

`.venv/bin/python -m pytest test_aria_wake.py` (state machine + silence reset;
no model or audio device needed).

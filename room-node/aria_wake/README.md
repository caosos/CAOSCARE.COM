# Aria wake-word listener (room node)

> **Legacy development/fallback Aria voice endpoint. Not standard apartment hardware.**
>
> The standard apartment design (Michael, 2026-10-03) is one central EliteDesk
> server running Home Assistant and CAOSCare, with a Home Assistant Voice PE in
> each apartment as the Aria room voice endpoint ("Hey Aria"). See
> `docs/ROOM_AUDIO_ARCHITECTURE.md`. This listener is kept only for:
> - development before the Voice PE arrives;
> - synthetic and microphone testing;
> - emergency fallback if Voice PE acceptance fails;
> - comparison testing between this room-node path and the Voice PE.
>
> **Disabled by default.** It does not start unless `ARIA_WAKE_ENABLE_LEGACY=1`
> is set, and the room page only connects to it when its URL carries `?wake=1`.
> No standard provisioning (deploy script, demo setup, services) installs or
> starts it.
>
> **Retirement condition:** May only be considered for removal after Voice PE real-room acceptance proves wake accuracy, conversation continuity, response playback and deterministic session ending.

Local, on-device "Aria" trigger for a resident room endpoint. Implements the
trigger half of `docs/ARIA_WAKE_WORD_ARCHITECTURE.md`: it listens on the
room's existing audio capture endpoint (the eMeet, via the PulseAudio default
source, shared - never exclusive) and tells the room page, over a
**localhost-only** WebSocket, that "Aria" was heard. The page starts the
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

Keyword: `keywords.txt` (`▁A RI A @ARIA`, BPE tokens from the model's
`bpe.model`). Tunables (env): `ARIA_WAKE_KEYWORDS_THRESHOLD` (default 0.15),
`ARIA_WAKE_KEYWORDS_SCORE` (1.0).

## Setup (EliteDesk)

```bash
cd room-node/aria_wake
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
curl -LO https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2
tar xjf sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2
mkdir -p model && cp sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/{tokens.txt,*.int8.onnx} model/
ARIA_WAKE_ENABLE_LEGACY=1 .venv/bin/python aria_wake.py   # JSON-lines log on stdout
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

## Tests

`.venv/bin/python -m pytest test_aria_wake.py` (state machine + silence reset;
no model or audio device needed).

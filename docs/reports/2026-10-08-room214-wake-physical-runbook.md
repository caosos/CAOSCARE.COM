# Room 214 "Hey Aria" wake endpoint - physical runbook (EliteDesk home setup)

Date: 2026-10-08. Task: RQ-036. For Michael, at the EliteDesk with the eMeet
OfficeCore Luna Plus plugged in. Everything below is **prepared, not run**: the
engineer's session could not open the eMeet (see step 0), so no microphone test
has happened. Offline results (synthetic audio) are in
`room-node/aria_wake/README.md`; they do not replace this test.

Scope: this is an additional EliteDesk endpoint for the home setup. The Voice PE
will later be another endpoint speaking the same detector-to-page protocol; the
conversation, tools, memory and receipts are the same Aria either way.

**Phrase: "Hey Aria"** (three syllables in "Aria": AIR-ee-uh). Not "Aria" alone.
Speak at normal conversation volume from your usual seat.

## 0. One-time audio access fix (the only sudo)

The eMeet's ALSA devices are only open to user `michaelos` and group `audio`;
`caoscare-1` is in neither, so it sees only a null sink.

```
sudo usermod -aG audio caoscare-1
```

Then log out of `caoscare-1` and back in (or reboot) so the group applies.

## 1. Check access (no changes made)

```
cd ~/CAOSCARE-BOUNDED/rq-036-home-wake-endpoint/room-node/aria_wake   # or wherever this branch is checked out
./ctl.sh test-audio-access
```

Pass: `RESULT: eMeet source AND sink are visible to this user.` Note the two
names printed (`pactl list short sources` / `sinks`); you need them in step 3.
If it says NOT visible, repeat step 0 and re-login; do not continue.

## 2. Prerequisites

- CAOSCare backend and frontend running for Room 214 (`localhost:3000` serving the
  frontend; backend that frontend talks to, normally `:8092`). Check:
  `curl -fsS http://localhost:3000 >/dev/null && echo frontend ok`.
- The Room 214 kiosk id used below is `kio_dc8c06a19608`. Confirm it is yours:
  `curl -s http://127.0.0.1:8092/api/kiosks | python3 -m json.tool | grep -B1 -A1 214`.
- The sherpa model files. On this machine they already exist in the integration
  checkout; copy at install time with
  `ARIA_WAKE_MODEL_SRC=/home/caoscare-1/CAOSCARE-INTEGRATION/room-node/aria_wake/model`.
- Host check done by the engineer: Chrome 155 present; `Xvfb`/`xvfb-run` NOT installed.
  Not needed: the page unit uses headless Chrome (`--headless=new`), which needs no X server.

## 3. Install and start

```
ARIA_WAKE_MODEL_SRC=/home/caoscare-1/CAOSCARE-INTEGRATION/room-node/aria_wake/model ./ctl.sh install
$EDITOR ~/.config/aria-wake/aria-wake.env     # set the eMeet names from step 1:
#   PULSE_SOURCE=<eMeet source>   ARIA_WAKE_SOURCE=<same>   PULSE_SINK=<eMeet sink>
./ctl.sh restart
./ctl.sh status
./ctl.sh logs -f          # in a second terminal; leave it open
```

Expected in the log within ~10 s: `starting` (phrase `Hey Aria`, threshold 0.15),
`capture_started` (device = your eMeet source), `serving`, then `client_connected`
(the headless page connected). If you see `refused_to_start` the keyword file is
wrong. If you see `capture_ended`, the source name is wrong or unreadable.

## 4. Spoken test script (record the time you start)

Set a marker so the tally ignores earlier noise: `START=$(date -u +%FT%TZ)`.

Repeat this block **5 times**. Wait ~10 s between rounds.

1. Say **"Hey Aria."** Expect the greeting within ~2 s (log: `wake_detected`, then `mode_conversation`).
2. Say **"Turn the desk lamp off."** Expect the real desk lamp (`dev_f8be14de18e3`) to go off, then Aria confirms.
3. Say **"Turn it on."** Expect the lamp on (and a confirmation).
4. Repeat 2-3 once for the overhead light (`dev_facc6dbc7e13`: "turn the overhead light off / on").
5. Say **"Goodbye."** Expect Aria to end; log shows `mode_listening` and the page is idle again.

Two lights share a room: Aria may ask which one if you only say "the light". That is
correct behaviour, not a miss.

Mark what goes wrong **at the moment it happens** (separate terminal):

```
./wake_stats.py mark miss  --note "said Hey Aria from the bed, nothing"
./wake_stats.py mark false --note "woke during TV"
```

`miss` = you said the phrase and nothing started. `false` = Aria woke and you did not say it.

## 5. False-wake soak: 10 minutes of normal life

Leave the listener running. For 10 minutes: TV on at a normal volume, ordinary
talking nearby (including the words "area", "hey", "Maria"), moving about. Do **not**
say "Hey Aria". Mark every wake with `mark false`. Note the length in hours
(10 min = 0.17).

## 6. Tally

```
./wake_stats.py summary --log <(./ctl.sh logs --since "$START") --hours 0.17 --backend http://127.0.0.1:8092 --room 214
```

(or save the log: `journalctl --user -u aria-wake.service -o cat --since "$START" > /tmp/wake.log` and use `--log /tmp/wake.log`).
It prints wakes, page-confirmed sessions, unconfirmed wakes, wakes heard during a conversation
(suppressed), your marked misses and false wakes. Which Realtime session each wake became is in the
admin activation timeline (`wake_word_session_bound`), not in this tally.

## 7. Pass thresholds (starting values - Michael may change them)

- Recognition: at least 4 of 5 rounds start a conversation on the first "Hey Aria" from the usual seat
  (marked misses at most 1 in 5). The offline synthetic far-field rate is about 39%, so expect to
  speak up from the bed; record distance for each miss.
- Control: lamp/overhead commands change the real light each time, and Aria confirms only after
  the change (existing read-back behaviour). Zero wrong-light or false-confirmation events.
- End and re-wake: after "Goodbye", the next "Hey Aria" works every round (5/5).
- False wakes: at most 1 in the 10-minute soak; zero is the target. More than 2 = fail, change the
  phrase or threshold, do not ship.
- Reliability: both services stay up for the whole session (`./ctl.sh status`), no `capture_ended`.

## 8. If it fails

- No wake, `capture_started` shows the wrong device: fix `ARIA_WAKE_SOURCE` and `PULSE_SOURCE`.
- Wake logged but nothing happens: look for `detection_no_client` (page not connected: check the
  kiosk unit log and that `?wake=1` is in `ARIA_WAKE_PAGE_URL`) or `pending_wake_expired` (page
  connected but did not start a session: check mic permission and the page URL in a normal Chrome).
- Aria is silent after waking: headless audio output is the unverified part of this setup. Try the
  page in a normal desktop Chrome window with the same URL to separate "audio device" from "headless".
- To stop everything: `./ctl.sh uninstall`.

## What the engineer could not verify

Headless Chrome opening the eMeet through PulseAudio, Aria's voice being audible from it, real
far-field pickup of "Hey Aria", real false-wake rate with TV audio, and the whole loop with real
lights. These are exactly what steps 3-6 measure.

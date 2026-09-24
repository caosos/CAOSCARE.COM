# Wake Phrase Lab (research tooling)

Finds and tests candidate CAOSCare wake phrases, with **minimal phonetic
collision with ordinary speech** as the primary objective. Why it exists,
methodology, gates and limitations: [`docs/WAKE_PHRASE_LAB.md`](../../docs/WAKE_PHRASE_LAB.md).

Isolated from runtime: nothing in `room-node/`, `backend/` or `frontend/`
imports this package, and it never touches a running listener.

## Step 1 status
Built: corpus registry + provenance, authored domain corpus, lexicon (CMUdict +
g2p_en + pinned overrides), pronunciation variants, confusability model,
collision search, frequency/domain risk, rejection gates, `inspect`, reports,
Aria regression. Not built yet: candidate generation, acoustic synthesis,
detector training, soak testing.

## Reproduce a run
```bash
cd tools/wakelab
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m wakelab fetch --optional    # downloads + ~/.cache/caoscare-wakelab/manifest.json
.venv/bin/python -m wakelab build               # ~1 min, ~1.2 GB peak RAM, 834k phonetic items
.venv/bin/python -m wakelab inspect aria "okay nabu" hello
.venv/bin/python -m pytest tests
```
- Cache: `~/.cache/caoscare-wakelab` (override `WAKELAB_CACHE`). Never committed.
- Reports: `runs/<utc-stamp>_<candidate>/report.{json,md}` (gitignored). The
  JSON records config, corpus stats and the provenance manifest for the run.
- `inspect TEXT --phonemes "EH1 R IY0 AH0"` evaluates an explicit pronunciation.
- `python -m wakelab sources` prints licenses and attribution.

## Private facility names
Optional: one name per line in `local/facility_names.txt` (gitignored) or the
file named by `WAKELAB_FACILITY_NAMES`. They are used for collision checks
only; reports show `[private facility name]`, and the manifest records
presence, never contents. Never commit them.

## Layout
```
config/sources.yaml        corpus sources: url, pinned version/sha256, license, attribution
config/default.yaml        thresholds, gate switches, pronunciation overrides (Aria)
wakelab/corpus/            registry.py (fetch + manifest), build.py, generated.py, domain/*.yaml (authored)
wakelab/phonetics/         arpabet.py, lexicon.py, features.py (confusability model), variants.py
wakelab/collision/         index.py (pre-filter), align.py, analyze.py (separate metrics), gates.py
wakelab/speakability.py    separate from collision; never offsets a gate
wakelab/inspect.py         pronunciation policy + orchestration; report.py; cli.py
tests/                     fixture corpus (no network) + real-corpus integration test
```

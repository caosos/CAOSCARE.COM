# EliteDesk storage audit, Phase 1 cleanup, Phase 2 proposal (RQ-008)

**Host:** the development / central EliteDesk. **Date:** 2026-10-04. **By:** Claude Code (Opus 5.5), Agent Five.
**Scope:** the audit was read-only. Phase 1 removed caches only. No lab data, datasets, firmware runs, worktrees, VM images, evidence or logs were touched, and no running job was stopped.

## Before state (2026-10-04 20:42 UTC)

| Measure | Value |
|---|---|
| Root filesystem `/` (ext4, single disk; `/home` and `/tmp` are on it) | 234G size, 162G used, **61G free**, 73% |
| Bytes free | 64,524,374,016 |
| Inodes | 6% used |
| `~/.npm` | 6.4G |
| `~/.cache` | 9.4G (uv 3.8G, esphome 1.9G, wakelab 969M, huggingface 677M, google-chrome 670M, puppeteer 652M, yarn 485M, pip 284M) |
| Main repo git objects | 76M loose, 0.9M packed (not a consumer) |

## Top consumers (audit)

| Size | Path | Class |
|---|---|---|
| 45G | `~/caoscare-firmware-work/runs/lab` (wake-lab per-candidate features) | ACTIVE-DO-NOT-TOUCH |
| 30G | `~/caoscare-firmware-work/data/negative_datasets` (extracted) | ACTIVE-DO-NOT-TOUCH |
| 15G | `~/caoscare-firmware-work/runs/{aria,naboo,hey_aria,hey_naboo}` | EVIDENCE-PROTECT |
| 8.5G | Home Assistant VM disk image (crashed 2026-10-03) | EVIDENCE-PROTECT |
| 6.3G | `~/.npm/_cacache` | SAFE-LATER → Phase 1 |
| 6.3G | Agent session scratch under `/tmp` (includes the live RF bridge log, ~1.7G and growing) | UNKNOWN / do not touch yet |
| 5.6G | Dataset zips in `firmware-work/data/negative_datasets` (already extracted; only the download script reads them) | SAFE-LATER after the lab batch, with the lab owner's OK |
| 4.3G | Chrome on-device AI model (`OptGuideOnDeviceModel`) | SAFE-LATER via a Chrome setting |
| 4.3G | `/var/lib/snapd` (1.0G of it in disabled old revisions) | 1.0G SAFE-LATER → Phase 1 |
| 3.8G | `~/.cache/uv` | SAFE-LATER (`uv cache prune`) → Phase 1 |
| 3.7G | `firmware-work/venv-mww` | ACTIVE-DO-NOT-TOUCH |
| 3.0G | `firmware-work/samples` | ACTIVE / EVIDENCE |
| 2.7G | Four firmware build outputs (`.esphome/build`) | UNKNOWN (rebuildable; firmware lane decides) |
| 2.1G | Swap file | keep |
| 2.0G | `firmware-work/eval_data` | ACTIVE |
| 1.9G | `~/.cache/esphome` | UNKNOWN (firmware lane) |
| 1.6G | `CAOSCARE.COM/frontend/node_modules` (other worktrees link to it) | ACTIVE-DO-NOT-TOUCH |
| 1.3G | `~/Downloads` (includes an echo-cancellation debug capture) | EVIDENCE-PROTECT |
| 1.2G | `firmware-work/voices` | ACTIVE |
| 0.8G | `~/.cache/yarn` + `~/.cache/pip` | SAFE-LATER → Phase 1 |

## Worktree inventory (audit)

26 worktrees, about 4.3G in total. Only the integration checkout had unpushed commits at audit time.

| Worktree | Branch | Merged to integration | State at audit | Class |
|---|---|---|---|---|
| CAOSCARE.COM | aria/conversation-substrate | yes | clean, processes running (old lane backends, RF bridge) | ACTIVE |
| CAOSCARE-INTEGRATION | integration/2026-09-27 | — | clean, 3 unpushed commits, processes running | ACTIVE |
| CAOSCARE-JARVIS | test/okay-nabu-voice | no | dirty, processes running | ACTIVE |
| CAOSCARE-LANE-DEVICE-TRUTH | pilot/shared-core-device-truth | no | dirty, processes running | ACTIVE |
| CAOSCARE-LANE-FRONTDESK | pilot/frontdesk-transport | yes | processes running | ACTIVE |
| CAOSCARE-WAKE-FUNNEL | research/wake-phrase-funnel | no | processes running | ACTIVE |
| CAOSCARE-VOICEBRIDGE | spike/voice-bridge | no | process running | ACTIVE |
| CAOSCARE-ADMIN | claude/admin-operations | yes | process running | ACTIVE |
| CAOSCARE-LEVEL1-INTEGRATION | claude/level1-integration | yes | process running | ACTIVE |
| CAOSCARE-FIRMWARE | firmware/voice-pe-naboo | no | clean, 868M | UNMERGED-PROTECT |
| CAOSCARE-FIRMWARE-ARIA | firmware/voice-pe-aria | no | clean, 1.7G | UNMERGED-PROTECT |
| CAOSCARE-LANE-BOM | pilot/rq-004-room1-bom | no at audit | clean | UNMERGED-PROTECT |
| CAOSCARE-LANE-COMMS | pilot/communications | no | clean | UNMERGED-PROTECT |
| CAOSCARE-LANE-REREQUEST | pilot/shared-core-rerequest | no | clean | UNMERGED-PROTECT |
| CAOSCARE-LANE-SERVICES | pilot/community-services | no | clean | UNMERGED-PROTECT |
| CAOSCARE-SIM1 | pilot/sim-1-scheduler | no at audit | clean | UNMERGED-PROTECT |
| CAOSCARE-SIM-INVESTIGATE | agent/pilot-room1-hardware-inventory | no (superseded by PR #47) | clean | UNMERGED-PROTECT until #47 is settled |
| CAOSCARE-WEBSITE | feature/interactive-capability-cards | no | clean | UNMERGED-PROTECT |
| CAOSCARE-LANE-SHARED | pilot/shared-core | yes | clean, idle | SAFE-LATER if Agent 2 is done |
| ARIA-WAKE-FALLBACK, CLAUDE, DOCS-ARIA, LANE-DEMO-KIOSK, LANE-MAINTENANCE, LEVEL1, WIP-PANELS | various | yes | clean, idle (~165M together) | SAFE-LATER (clutter, not space) |

## Estimated reclaimable (audit)

| Tier | Approx. | Contents |
|---|---|---|
| Phase 1 (safe now) | ~11G | npm, uv (unused entries), yarn, pip caches; disabled snap revisions |
| With sign-off | +~10G | dataset zips (lab owner), Chrome on-device AI model (setting change) |
| Later, lab owner only | up to ~75G | `runs/lab` features and extracted datasets once the wake lab is finished |

## Open risks at audit time

- The RF bridge log in `/tmp` was still growing on the root filesystem. It needs a rotation decision.
- The integration checkout had 3 unpushed commits.
- A wake-lab batch was running throughout the audit and Phase 1.

## Phase 1 result (2026-10-04, ~20:43 UTC)

Run while the wake-lab batch kept running. Nothing in `~/caoscare-firmware-work`, no dataset or zip, no worktree, no Chrome model, no VM image and no log was touched.

| Step | Command | Result |
|---|---|---|
| npm cache | `npm cache clean --force` | `~/.npm` 6.4G → 109M |
| yarn cache | `yarn cache clean` | `~/.cache/yarn` 485M → 8K |
| pip cache | `pip cache purge` (backend venv pip; shared `~/.cache/pip`) | 946 files, 288 MB removed |
| uv unused cache | `uv cache prune` (`firmware-work/bin/uv`) | 0 bytes; every entry still referenced, so `~/.cache/uv` stays 3.8G |
| Disabled snap revisions | `sudo snap remove <name> --revision=<rev>` ×7 | `/var/lib/snapd` 4.3G → 3.1G; 0 disabled revisions left |

| Measure | Before | After |
|---|---|---|
| `/` used / free | 162G / 61G (73%) | 154G / 68G (70%) |
| Bytes free | 64,524,374,016 | 72,551,915,520 |
| **Net reclaimed** | | **8.03 GB (7.48 GiB)** |

The audit estimated ~11G for Phase 1. The shortfall is the uv cache: nothing in it was unused. The net figure is measured while the lab batch was writing, so it may slightly understate what the cleanup freed.

## Summary

| | Value |
|---|---|
| Original state (audit, 2026-10-04 20:42 UTC) | 64,524,374,016 bytes free (61G, 73% used) |
| Phase 1 (caches only, done) | **8.03 GB reclaimed** (64,524,374,016 → 72,551,915,520 bytes free) |
| Now (2026-10-05 01:52 UTC) | 51,035,262,976 bytes free (79% used) |
| Used since Phase 1 | ~21.5 GB, almost all wake-lab work (below) |

Phase 2 below is a **proposal only**. Nothing in it has been run. Each item says who must approve it and what has to be true first. Sizes are `du -sh` (GiB-based "G") unless given in bytes.

## What grew after Phase 1 (re-measured 2026-10-05 01:50 UTC)

| Path | At audit | Now | Why |
|---|---|---|---|
| `~/caoscare-firmware-work/runs/lab` | 45G | 58G | more wake candidates trained; a method-test run active now |
| `~/caoscare-firmware-work/data/hardneg_peoples_speech` | — | 5.6G | new hard-negative set for the A/B (features 3.2G, wavs 1.5G, clean 952M) |
| RF bridge log (agent scratch under `/tmp`) | ~1.7G | 2.6G (2,596,551,063 B) | ~0.9 GB in ~5 h ≈ **4 GB/day** if the rate holds |
| `/tmp/claude-1000` (all agent scratch, incl. the RF log) | 6.3G | 7.5G | agent sessions |

## Current major consumers

| Size | Path | Bucket |
|---|---|---|
| 58G | `firmware-work/runs/lab` — 35 candidate dirs (34 finished + the active one), each ~1.52G `positive_features` + ~12M `trained/` + eval JSON; 3 shared negative-feature dirs 2.7G + 2.67G + 2.67G | see Phase 2 A, B and DO NOT TOUCH |
| 30G | `firmware-work/data/negative_datasets` (extracted) | DO NOT TOUCH |
| 14.8G | `firmware-work/runs/{aria,naboo,hey_aria,hey_naboo}` (firmware proof runs) | DO NOT TOUCH |
| 8.5G | Home Assistant VM disk (`/var/lib/libvirt/images/caoscare-homeassistant.qcow2`; size from audit, not readable without root now) | DO NOT TOUCH |
| 5.71 GB | four dataset zips in `data/negative_datasets` (5,709,958,106 B) | Phase 2 D |
| 5.6G | `data/hardneg_peoples_speech` | Phase 2 C (intermediates) + DO NOT TOUCH (features) |
| 4.0G | Chrome on-device AI model `~/.config/google-chrome/OptGuideOnDeviceModel` | Phase 2 G |
| 3.8G | `~/.cache/uv` | not proposed (prune found 0 unused; venvs hard-link into it on this filesystem, so cleaning frees little) |
| 3.7G | `firmware-work/venv-mww` | DO NOT TOUCH |
| 3.2G | `firmware-work/samples` | DO NOT TOUCH |
| 2.7G | four ESPHome build dirs (~680M each) | Phase 2 E, J |
| 2.6G | RF bridge log | Phase 2 H |
| 2.0G | `firmware-work/eval_data` | DO NOT TOUCH |
| 2.0G | swap file | keep |
| 1.9G | `~/.cache/esphome` | Phase 2 E |
| ~4.9G | other agent scratch in `/tmp/claude-1000` (one session alone 3.7G: wake-verifier backup, a speech model, a venv, a Chrome profile) | Phase 2 I |
| 1.3G | `~/Downloads` (incl. an echo-cancellation debug capture) | Phase 2 L |
| 1.2G | `firmware-work/voices` | DO NOT TOUCH |
| 969M / 679M | `~/.cache/caoscare-wakelab` / `~/.cache/huggingface` | Phase 2 F |
| 670M / 652M / 619M | `~/.cache/google-chrome`, `~/.cache/puppeteer`, 12 `/tmp/cdp-*` dirs | SAFE AFTER WAKE TEST |

## Active / protected wake-lab data (right now)

A training job is running (Claude Two's method-test A/B, candidate `okay_sequoia_tvneg`, since ~01:46 UTC). It reads and writes:
- `runs/lab/okay_sequoia_tvneg/` (its features and `trained/` logs);
- the shared negative features (`runs/lab/_shared_negative_features*`);
- `data/negative_datasets/{speech,dinner_party,no_speech}` (extracted);
- the hard-negative features in `data/hardneg_peoples_speech/features`;
- augmentation inputs `data/{mit_rirs,fma_16k,audioset_16k}`;
- `samples/train/*`;
- `venv-mww`.

None of these may be touched while it runs. How features are made (`firmware/voice-pe-aria/lab/train_lab.py`): each candidate's `positive_features` is generated from `samples/train/positives/<slug>` with a fixed seed and is reused if present. The evaluation script (`eval_lab.py`) does not read training features.

## Evidence-protected files

- `firmware-work/runs/{aria,naboo,hey_aria,hey_naboo}` (14.8G): the firmware wake-word proof runs. Naboo is superseded but preserved.
- Every candidate's `trained/` model and `lab_eval*.json` (~12M each): the wake models and their evaluations.
- The HA VM disk (crashed 2026-10-03, under recovery by Agent Four).
- `~/Downloads` (echo-cancellation debug capture).
- The Naboo firmware build (`CAOSCARE-FIRMWARE/firmware/voice-pe-naboo/.esphome/build`).

## Worktrees (2026-10-05)

35 worktrees, ~6.5G in total. 2.6G of that is the two firmware worktrees; the rest are small. Worktrees are clutter more than space. **None are proposed for removal without Michael's approval** (Phase 2 K).

| Class | Worktrees |
|---|---|
| ACTIVE (processes running, or dirty) | CAOSCARE.COM, INTEGRATION, JARVIS, LANE-FRONTDESK, ADMIN, LEVEL1-INTEGRATION, VOICEBRIDGE, WAKE-FUNNEL, SIM3, SC8-SC9, HEARING-AUDIO, a detached `gate-base` |
| ACTIVE LANE (assigned now) | OPS-HA (Agent Four, HA VM recovery) |
| UNMERGED — protect | FIRMWARE (868M), FIRMWARE-ARIA (1.7G), LANE-COMMS, LANE-REREQUEST, LANE-SERVICES, SIM-INVESTIGATE, WEBSITE, DOCS-STORAGE (this branch) |
| MERGED, clean, idle — removable later with approval | ARIA-WAKE-FALLBACK, CLAUDE, DEMO-CONTINUITY, DOCS-ARIA, LANE-BOM, LANE-DEMO-KIOSK, LANE-DEVICE-TRUTH, LANE-MAINTENANCE, LANE-SHARED, LANE-SIM-PROVENANCE, LEVEL1, SIM1, SIM2, WIP-PANELS (~0.45G together) |

## Phase 2 proposal

Totals if every item were approved: SAFE ~1.9G; Claude Two ~71G; Michael ~12.6G (L not counted). Commands are exact. Run them **only** after the approval and the prerequisites listed.

### SAFE AFTER WAKE TEST (~1.9G)

Nothing here holds data anyone needs. "After the wake test" simply keeps disk activity quiet during the running job.

| # | Candidate | Est. | Command | Risk | Prerequisites |
|---|---|---|---|---|---|
| S1 | 12 stale Chrome DevTools temp profiles (all dated 2026-09-27) | 0.62G | `rm -rf /tmp/cdp-*` | none; scratch profiles | `ls -l /proc/[0-9]*/fd 2>/dev/null \| grep -c /tmp/cdp-` prints 0 (it did on 2026-10-05) |
| S2 | Puppeteer browser download | 0.65G | `rm -rf ~/.cache/puppeteer` | the next Puppeteer use re-downloads (~650 MB) | no Puppeteer/headless browser running |
| S3 | Chrome HTTP cache | 0.67G | `rm -rf ~/.cache/google-chrome/Default` | sites reload slower once; no data loss | Chrome fully closed |

### NEEDS CLAUDE TWO APPROVAL (~71G)

All of these are wake-lab or firmware lane data. Claude Two decides; Michael's directive also requires explicit approval before any negative dataset or wake-feature data is removed.

| # | Candidate | Est. | Command | Risk | Prerequisites |
|---|---|---|---|---|---|
| A | `positive_features` of the 34 finished candidates (keeps each `trained/` model and eval JSON) | ~52G (34 × 1.52G) | `cd ~/caoscare-firmware-work/runs/lab && for s in $(cat APPROVED_SLUGS.txt); do [ -d "$s/trained" ] && [ -f "$s/lab_eval.json" ] && rm -rf "$s/positive_features"; done` | retraining a candidate regenerates its features (seeded, minutes each; byte-identity of the regenerated features not verified) | A/B job finished; Claude Two writes the approved slug list (excluding anything that may be retrained); no `train_lab.py` running |
| B | variant shared negatives `_shared_negative_features__minus_krista`, `__minus_calista` | 5.3G | `rm -rf ~/caoscare-firmware-work/runs/lab/_shared_negative_features__minus_krista ~/caoscare-firmware-work/runs/lab/_shared_negative_features__minus_calista` | retraining a candidate that excludes those names regenerates them (the slowest regeneration) | no training running; no candidate with that exclusion planned |
| C | hard-negative intermediates (`wavs`, `clean`) | 2.5G | `rm -rf ~/caoscare-firmware-work/data/hardneg_peoples_speech/wavs ~/caoscare-firmware-work/data/hardneg_peoples_speech/clean` | rebuilding the features needs a re-fetch (`fetch.py`) and `prep.py` | A/B finished; features confirmed final |
| D | dataset zips (already extracted) | 5.71 GB | `rm -f ~/caoscare-firmware-work/data/negative_datasets/{speech,no_speech,dinner_party,dinner_party_eval}.zip` | re-extracting needs a ~5.7 GB re-download | extracted dirs verified complete; the download script will not be re-run; **also Michael's explicit approval** (negative datasets) |
| E | ESPHome build outputs (stock, Aria, Aria device test) + ESPHome cache | 3.9G | `rm -rf ~/caoscare-firmware-work/build-stock/.esphome/build ~/CAOSCARE-FIRMWARE-ARIA/firmware/voice-pe-aria/.esphome/build ~/CAOSCARE-FIRMWARE-ARIA/firmware/voice-pe-aria/lab/device_test/.esphome/build ~/.cache/esphome` | the next compile is slower and re-downloads the toolchain | no ESPHome build or flash running; firmware lane confirms no flashed binary is needed as evidence from these dirs |
| F | wakelab corpus cache, Hugging Face cache | 1.6G | `rm -rf ~/.cache/caoscare-wakelab ~/.cache/huggingface` | re-fetch on next use | no wakelab/HF fetch running |

### NEEDS MICHAEL APPROVAL (~12.6G)

| # | Candidate | Est. | Command | Risk | Prerequisites |
|---|---|---|---|---|---|
| G | Chrome on-device AI model | 4.0G | in Chrome: `chrome://flags/#optimization-guide-on-device-model` → Disabled, quit Chrome, then `rm -rf ~/.config/google-chrome/OptGuideOnDeviceModel` | Chrome's built-in AI features stop; it re-downloads if re-enabled | Michael agrees to lose the feature; Chrome closed |
| H | RF bridge log | 2.6G now, ~4 GB/day | archive: `mkdir -p ~/rf_log_archive && gzip -c <log> > ~/rf_log_archive/rf_bridge2-$(date +%F).log.gz`; then restart the bridge writing in append mode with rotation (e.g. `>>` into a logrotate-managed file) | the bridge holds the log open **without append mode**: `truncate` alone would free the blocks but leave a sparse file that keeps growing from its old offset. Restarting the bridge interrupts pendant reception for seconds | owner of the RF path agrees; restart window agreed; archive verified (`gzip -t`) before the old log is removed |
| I | other agent scratch in `/tmp/claude-1000` (~4.9G excl. the RF log) | ~4.9G | per session dir, after its owner confirms: `rm -rf /tmp/claude-1000/<project>/<session-id>` | a live session could lose working files (one 3.7G session holds a wake-verifier backup and a speech model) | the owning session has finished; the wake-verifier backup confirmed preserved elsewhere if still needed; `/tmp` is also cleared on reboot |
| J | Naboo firmware build (superseded proof) | 0.68G | `rm -rf ~/CAOSCARE-FIRMWARE/firmware/voice-pe-naboo/.esphome/build` | loses the exact build tree of the flashed Naboo proof | Michael accepts the GitHub branch (`firmware/voice-pe-naboo`) as sufficient evidence |
| K | 14 merged, clean, idle worktrees | ~0.45G | `git worktree remove <path>` for each (refuses if dirty) | none to code (all merged); removes clutter | each owner confirms done; list rechecked for dirt/processes on the day |
| L | `~/Downloads` | 1.3G | none proposed; review by Michael | contains an echo-cancellation debug capture | Michael reviews contents |

### DO NOT TOUCH (this phase)

- `runs/lab` while any training runs, including the active candidate, the shared negative features and every `trained/` model + eval JSON.
- Extracted negative datasets (`data/negative_datasets/*/`), hard-negative `features`, `samples`, `eval_data`, `voices`, augmentation inputs (`mit_rirs`, `fma*`, `audioset*`), `venv-mww`.
- Firmware proof runs `runs/{aria,naboo,hey_aria,hey_naboo}`.
- Wake models anywhere.
- All worktrees (until K is approved).
- RF logs (until H is approved).
- The HA VM disk.
- The Chrome model (until G is approved).
- `CAOSCARE.COM/frontend/node_modules` (other worktrees link to it).
- Swap; `~/.cache/uv`.

## Risks to watch

- Free space fell ~21.5 GB in ~5 h after Phase 1. Each wake candidate adds ~1.5G, and the RF log adds ~4 GB/day. At 51 GB free, roughly 30 more candidates or ~12 days of RF log would use it up.
- If the disk fills, the backend, MongoDB and the running training would fail together.
- Item A alone (Claude Two) recovers more than everything else combined.

# EliteDesk storage audit and Phase 1 cleanup (RQ-008)

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

## Not done (later phases, each needs sign-off)

- Dataset zips (5.6G): after the lab batch, with the lab owner's OK.
- Chrome on-device AI model (4.3G): after turning the setting off.
- The RF bridge log in `/tmp`: rotation decision pending.
- Merged idle worktrees: coordinator confirms each.
- Wake-lab feature data / extracted datasets: lab owner only.

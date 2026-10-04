# Voice prompt and context budget audit (2026-10-04)

Branch `spike/voice-bridge`, from `ef5f4f8`. Static analysis and measurement
only: no model call, no behaviour change. Tokens are **estimates**
(characters ÷ 4). tiktoken is not installed, so these figures are not billing
counts.

## 1. How it was measured

`backend/scripts/measure_voice_prompt.py` builds the first model request of a
bridge turn the same way `routes/voice_bridge.py::_converse` builds it:

- system message = `build_resident_instructions()` + `CHANNEL_NOTE`;
- history = `_history(session_id)`;
- tools = `bridge_tool_schemas()`.

It splits the system message on `## ` headings and reports the size of each
section and of each tool.

Two profiles, each run on a throwaway `caos_prompt_measure_*` database that is
dropped afterwards:

- **new**: a resident with nothing on file. This matches the load-test
  residents.
- **representative**: profile, intake notes, low vision, 25 facts, 8 events,
  an acknowledged alert, two open requests, two prior sessions, three
  interpretation patterns and 8 history turns.

`--db-resident ID` measures a real resident, read-only, and prints sizes only.

Raw output:

- `docs/reports/2026-10-04-voice-prompt-inventory-new-resident.json`
- `docs/reports/2026-10-04-voice-prompt-inventory-representative.json`

## 2. Exact current size (first model call of a turn)

| Profile | System | History | Tools (11) | **Total** | ~Tokens (est.) |
|---|---|---|---|---|---|
| New resident | 18,325 | 0 | 14,424 | **32,749** | ~8,190 |
| Representative | 24,435 | 572 (8 msgs) | 14,424 | **39,431** | ~9,860 |

- The new-resident figure matches the load report (33,083 average, measured
  by the mock provider over all calls).
- A turn that uses a tool makes a **second** model call. That call carries the
  same system message, history and tools again, plus the tool call and its
  result, so a tool turn costs roughly twice the table figure. Tool-result
  sizes were not measured.
- Upper bound at the caps (40 facts, 20 events, 20 history turns, 2,200-char
  continuity): estimated at about 44,000 characters. This is not measured.

## 3. Breakdown by component

Characters, representative profile. Where the new-resident figure differs, it
is in brackets.

| Section | Source | Chars | Included | Needed this turn? | Duplicated? | On demand? | Class |
|---|---|---|---|---|---|---|---|
| About yourself / What you run on / Kiosk screen | `realtime_self_knowledge._system_self_knowledge` | 3,037 | always | only for "how do you work" questions | partly (screen tiles are irrelevant on a voice-only Voice PE) | yes | retrievable on demand |
| What you can DO right now + NEVER over-promise | same | 1,483 | always | capability truth: yes | **yes**: restates the tool list and Truth discipline | replace with one generated line | unnecessary duplication |
| Right now (time anchor) | `realtime_companion_prompt` / `_facility_now` | 488 | always | yes | no | — | always required |
| Who you are, How you sound, Language, What never to say, What to do, Visually impaired | persona | 2,706 | always | yes | small overlaps with self-knowledge | — | always required |
| Truth, Memory-is-reference, Attribution, Mistakes | governance | 3,497 | always | yes | Truth vs NEVER over-promise | — | always required (never truncate) |
| Safety | persona | 292 | always | yes | no | — | always required |
| Tools you can actually use | persona tool guidance | 2,998 | always | only the part for tools in use | **yes**: restates the tool schemas | by intent | required by intent |
| More than Alexa, Sensitive adult-life topics | persona | 2,309 | always | ordinary conversation only | no | yes | required by intent |
| About this person (+ intake notes) | `realtime_companion_memory` | 1,782 [817] | per resident | identity: yes; intake notes: often no | name/provenance rule restated in the TSB-001 paragraph | intake notes yes | always (identity) / on demand (notes) |
| Durable facts (≤40) | memory facts bin | 2,072 [231] | per resident | rarely all of them | no | **yes**: subject-triggered (Layer D) | retrievable on demand |
| Recent moments (≤20) | memory events bin | 444 [223] | per resident | sometimes | no | yes | retrievable on demand |
| Interpretation patterns | `aria_interpretation_patterns` | 858 | when present | yes (understanding speech) | no | — | always required (AGENTS.md non-negotiable) |
| Where you and X were (continuity) | Layer B | 1,533 | when present, cap 2,200 | follow-ups | no | — | conversation summary |
| This call so far | Layer C | — | when present | yes | no | — | always required when present |
| What's actually happening right now | Layer E | 692 | when present | requests, status, help | no | — | always required when present |
| Channel note | `voice_bridge.CHANNEL_NOTE` | 244 | always | yes | no | — | always required |
| History (last 20 turns) | `voice_bridge._history` | 572 | always | follow-ups | partly overlaps continuity | — | conversation summary |
| Tool schemas (11) | `voice_bridge_tools.bridge_tool_schemas` | 14,424 | always | 1–3 tools per turn | descriptions overlap "Tools you can actually use" | **yes**: by intent | required by intent |

Per-tool schema size (characters):

| Tool | Chars | Tool | Chars |
|---|---|---|---|
| request_staff_help | 2,458 | adjust_room_temperature | 1,325 |
| check_request_status | 2,210 | call_for_help | 1,313 |
| request_transportation | 1,800 | check_request_history | 959 |
| toggle_light | 1,538 | end_call | 644 |
| get_menu | 1,127 | get_todays_schedule | 600 |
| get_current_time | 428 | | |

Totals by class (representative profile, system message only):

| Class | Chars | Share of system message |
|---|---|---|
| Always required | 10,559 | 43% |
| By intent | 5,307 | 22% |
| On demand | 5,553 | 23% |
| Conversation summary | 1,533 | 6% |
| Duplication | 1,483 | 6% |

The tool schemas are the largest single block: 37% of every call for a new
resident.

## 4. Context not in the prompt (already correct)

These are already fetched by tools or kept server-side, not placed in the
prompt:

- menu items;
- activities;
- request records;
- device state;
- receipts and provenance;
- the department list.

The canonical state already lives outside the prompt. The prompt carries only
derived snapshots (Layer E, Layer C). No change is needed here.

## 5. Findings

1. **The bridge prompt names tools the bridge does not have.** The prompt
   comes from the realtime (26-tool) build and tells the model to call these
   tools:
   - `get_room_status`
   - `mark_resting`
   - `request_live_staff`
   - `set_timer`
   - `get_weather`
   - `research_topic`
   - `update_preferred_name`

   The bridge exposes 11 tools and none of these. Self-knowledge also
   advertises reminders, weather and research. This conflicts with the
   requirement to keep capability boundaries truthful. It was found by
   comparing the tool names in the prompt with `BRIDGE_TOOLS`. It has **not**
   been observed in a live turn.
2. **Duplication.** The capability list (1,483 chars) restates the tool list
   and the truth rules. The persona "Tools you can actually use" section
   (2,998 chars) restates the routing rules that are also in the tool
   descriptions.
3. **Channel-irrelevant text.** The kiosk-screen description (775 chars) and
   the "describe buttons by location" guidance do not apply to a voice-only
   Voice PE.
4. **Prompt-cache ordering.** `_facility_now` ("Right now", which changes
   every minute) is the second block, after about 4,500 static characters.
   Provider prefix caching (OpenAI caches identical prefixes of at least 1,024
   tokens) therefore cannot reuse the ~13,000 static persona and governance
   characters that follow it. Moving all dynamic blocks after all static
   blocks is a no-behaviour-change ordering fix.

   The cost and latency effect has not been measured. It depends on the
   provider.
5. **The second call doubles the cost of tool turns.** This is inherent to
   tool calling. Smaller per-call context halves both calls.

## 6. Proposed budgets (PROPOSALS, not measured outcomes)

The fixed floor is included in every budget.

- **Core**: identity, persona, governance, safety, time, channel and profile
  identity lines. About 8,000 chars.
- **Safety tools**: `call_for_help`, `request_staff_help` and `end_call`.
  About 4,400 chars.

Safety, authority and governance rules are never truncated. If a budget is
exceeded, the system drops on-demand context first and then summary context.
It never drops floor context.

| Turn type | Adds to the floor | Proposed budget (chars / ~tokens) |
|---|---|---|
| Emergency / help words | nothing: no model call (`_emergency_turn`, already built) | 0 / 0 |
| Device command | toggle_light, adjust_room_temperature, room/device line, Layer E | ≤ 16,000 / ~4,000 |
| Menu / activity | get_menu, get_todays_schedule, time | ≤ 15,000 / ~3,750 |
| Request status | check_request_status, check_request_history, Layer E + C | ≤ 17,000 / ~4,250 |
| Operational request (staff help, transport) | request_transportation, Layer E, continuity | ≤ 18,000 / ~4,500 |
| Ordinary conversation | conversation persona sections, top-N retrieved facts, continuity | ≤ 18,000 / ~4,500 |
| Follow-up turn | previous turn's tool set + last 4–6 turns + Layer C | previous budget + 2,000 |
| Maximum exceptional | everything (all tools, full memory, full history) | ≤ 45,000 / ~11,250 (cap; log when used) |

Common informational turn target: **about 15,000 chars (~3,750 tokens)**,
compared with 32,749 to 39,431 today. This is a proposal.

## 7. Expected reduction (estimates, unverified until implemented)

| Phase | Change | Estimated saving per call |
|---|---|---|
| A | remove the capability duplicate, generate the tool guidance from the actual tool set, drop kiosk-screen text on the voice channel, put static blocks first | ~3,000–5,000 chars, plus cacheable prefix |
| B | tools and conversation-only persona sections by intent | ~7,000–10,000 chars |
| C | top-N memory retrieval; history replaced by summary + last 4–6 turns | ~2,000–5,000 chars (representative), more at caps |
| **A+B+C** | | **~50–60% of today's per-call size** |

## 8. Phased plan (bounded)

**Phase A: remove duplication, no behaviour change.**

1. Put all static blocks before all dynamic blocks (time, profile, Layers B,
   C and E).
2. Generate the capability line and the tool-guidance text from the tools
   actually passed to the model, for each channel. This also fixes Finding 1.
3. On the voice channel, omit the kiosk-screen section.
4. Keep the truth, attribution and safety text verbatim.

Exit test: these checks pass, and the harness shows the reduction.

- Snapshot test: every governance and safety rule string is present on every
  channel.
- Every tool named in the prompt exists in that call's tool list.

**Phase B: tools and department context by intent.**

1. Use `voice_bridge_admission.classify` and a small intent classifier, with
   no model call (keywords and the last turn's tools), to choose the tool
   subset.
2. Always include `call_for_help`, `request_staff_help` and `end_call`.
3. If the classifier is unsure, fall back to the full set. An uncertain turn
   must never lose a capability.

**Phase C: conversation summaries and targeted memory.**

1. Use the Layer D design: subject-triggered retrieval of facts and events
   instead of dumping the bins.
2. Replace history with a Layer C summary plus the last 4–6 turns.

**Phase D: verify against the existing scenarios.**

1. Re-run `tests/test_voice_bridge_flow.py`, `tests/test_voice_bridge.py` and
   the substrate tests.
2. Re-run the load harness (`python -m loadtest.run`) and compare prompt size
   and p95.
3. Do a live Voice PE acceptance pass when the hardware lane allows it.

Do not start Phase B or C before Phase A is merged and measured.

## 9. Verification performed

- Harness run on both profiles; the outputs are in the JSON files above.
- New-resident total (32,749) agrees with the load report (33,083 average).
- Tool-name cross-check: the prompt's tool references against `BRIDGE_TOOLS`.
- No paid calls (`OPENAI_API_KEY` blanked in synthetic mode). No tests were
  run, as instructed (no suites during the Wake Word Lab).

## 10. Phase A result (implemented 2026-10-04)

Same harness, same fixtures. "Before" is `01a5f33`, measured by the new
harness. Tokens are estimates (characters ÷ 4).

### Before and after

| Profile | Before | After | Reduction | System message before → after |
|---|---|---|---|---|
| Representative | 39,431 (~9,858 tok) | 36,734 (~9,184 tok) | −2,697 (−6.8%) | 24,435 → 21,738 (−11.0%) |
| New resident | 32,749 (~8,187 tok) | 30,052 (~7,513 tok) | −2,697 (−8.2%) | 18,325 → 15,628 (−14.7%) |

### Section changes (representative profile, characters)

| Section | Before | After | Change |
|---|---|---|---|
| Kiosk screen | 775 | 0 | dropped on the voice channel |
| What you can DO right now + NEVER over-promise | 1,483 | 0 | replaced by the generated list below |
| What you can do (the whole list) | 0 | 1,643 | new, generated from the tools actually provided |
| Tools you can actually use | 2,998 | 1,327 | generated; describes only tools the bridge provides |
| What you actually run on | 1,228 | 941 | no WebRTC/Realtime claim on the voice channel |
| About yourself | 1,034 | 924 | name rule kept once, in persona |
| Safety | 292 | 417 | now the single home of the emergency rule and the rest rule |
| About this person | 1,782 | 1,683 | name-correction tool mentioned only if provided |

All other sections are unchanged.

### Contract checks (`routes/companion_prompt_contract.py`)

| Check | Before | After |
|---|---|---|
| Tools exposed | 11 | 11 (unchanged) |
| Unsupported tool claims | 7 | 0 |
| Unsupported capability/channel claims | 4 | 0 |
| Duplicated mandatory instructions | 4 | 0 |
| Required sections missing | 0 | 0 |

- **Unsupported tool claims before:** get_room_status, get_weather,
  mark_resting, request_live_staff, research_topic, set_timer,
  update_preferred_name.
- **Unsupported capability/channel claims before:** live web lookup,
  kiosk-screen section, "The kiosk will hang up", "OpenAI Realtime API
  (WebRTC)".
- **Duplicated mandatory instructions before:** emergency, name not
  negotiable, rest/quiet, name-correction tool.
- **Required sections:** the "Before" harness reported "## What you can do"
  as missing, but the same content existed under the old heading "What you
  can DO right now". This is a naming difference, not a real gap.

### Why the reduction is smaller than estimated

The estimate in §7 was 3,000–5,000 characters; the result is 2,697.

- **Tool schemas are unchanged** (14,424 characters). They are shared with
  the realtime room session. Trimming their descriptions would change both
  channels and the tool contract, so it is left to Phase B.
- **The time anchor now follows all static text.** Characters before the
  first per-call block are identical across calls: 13,723 on the voice
  channel. Any cost or latency benefit from provider prefix caching is not
  measured.

### Kiosk (realtime room) channel

It is built from the same code, with its own 26-tool set:

- it still names all its tools and keeps the kiosk-screen section;
- its capability list now also covers its menu, schedule, request and
  transport tools;
- it no longer claims live web lookup unless a search key is configured.

### Not changed

- The following text remains as before; changing it was outside Phase A:
  - "What to do" still says "reassure them help is already on the way".
  - "Safety" still says "gently confirm a caregiver is on the way".
  - Both are arrival claims, which the bridge's `arrival_claim_guard`
    rewrites in replies.
- "Who you are" still says "You live in the wall of this resident's room".

These are flagged for a later decision.

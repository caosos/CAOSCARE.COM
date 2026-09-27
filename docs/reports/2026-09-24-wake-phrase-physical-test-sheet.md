# Wake phrase — Room 214 physical test sheet (PREPARED, NOT RUN)

Status: prepared 2026-09-24. **Do not run until Michael explicitly asks.**
The Room 214 listener stays OFF until then; running this sheet means
starting the listener with ONE finalist keyword at a time.

Candidates: the finalists listed in §0 (from `python -m wakelab rank` +
`python -m wakelab acoustic`). Record real observations only. Leave a cell
blank rather than estimate. Wake score is available from the listener log if
the engine exposes it (sherpa-onnx KWS currently reports detection only).

## 0. Finalists for this sheet

From `tools/wakelab/runs/20260924T004956_rank` (text stage) and
`runs/*_acoustic_hey-aria` (SYNTHETIC). None has passed every stage yet.

| candidate | text stage | acoustic (synthetic) | nearest dangerous neighbours to say in §2 |
|---|---|---|---|
| hey aria | REJECT (G2,G3,G4,G6,G7) | screened: 0 false wakes on bare "area" phrases; fired on "hey area", "hay area", "hey Ari"; recall 68% (far 39%, TV 28%) at 0.15 | hey area, hay area, hey Ari, bay area, the area, my area, hey Mary |
| okay nabu | PASS (control) | not screened | ontario canada, a cocaine addict, attainable |
| hey mycroft | PASS (control) | not screened | him across, my trust, I crossed, minecraft |
| natividad | PASS | not screened | not evidence, not evident, wasn't even on |
| pasquale | PASS | not screened | wallow, disqualified, disqualify |

"hey aria" is on this sheet only because it has acoustic evidence; its text
stage REJECT stands and is Michael's decision to override or not.

## 1. Setup (per finalist)

- keyword line: `python -c` from `tools/wakelab` `keyword_line()` (BPE
  tokens) → `room-node/aria_wake/keywords.txt`; threshold as tested
  acoustically; listener started by hand; page `?wake=1`.
- Record: date/time, keyword line, threshold, eMeet position, TV model/volume.

## 2. Collision (no intentional wake) — say each line 3× at normal voice, 3 ft

| phrase | tries | false wakes | session opened? | notes |
|---|---|---|---|---|
| finalist's nearest neighbours from the rank report (list here) | 3 | | | |
| hostile set if Aria-containing: area / the area / this area / that area / their area / your area / our area / dining area / common area / gray area / hey area | 3 each | | | |
| ordinary room phrases: "turn on the light", "what time is it", "thank you", "I'm fine" | 3 each | | | |

## 3. Intentional wake — 5 attempts per cell

| distance | facing | voice | TV | attempts | wakes | session opened | latency (s, if measurable) |
|---|---|---|---|---|---|---|---|
| 3 ft | toward eMeet | normal | off | 5 | | | |
| 3 ft | toward | soft | off | 5 | | | |
| 8 ft | toward | normal | off | 5 | | | |
| 8 ft | away | normal | off | 5 | | | |
| 8 ft | toward | soft | off | 5 | | | |
| 3 ft | toward | normal | on | 5 | | | |
| 8 ft | toward | normal | on | 5 | | | |
| bed | toward | normal | off | 5 | | | |

## 4. Soak — no intentional wake attempts

| condition | duration | false wakes | what was playing/said at each |
|---|---|---|---|
| live TV, normal volume | ≥ 1 h | | |
| ordinary conversation in the room | ≥ 30 min | | |

## 5. Result entry

For each finalist: intentional attempts, successful wakes, false wakes,
wake score (if available), sessions opened, latency. Then compare to the
SYNTHETIC acoustic report for the same finalist. The physical result wins
where they disagree.

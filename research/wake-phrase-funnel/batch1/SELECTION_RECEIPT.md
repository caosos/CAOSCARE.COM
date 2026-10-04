# Acoustic batch 1 — selection receipt (Round 5, 2026-10-04)

**Research only. Aria remains the assistant's identity; testing another activation phrase does not
rename Aria.** Every model trained here inherits the lab's licensing gate: RESEARCH ONLY — NOT
COMMERCIALLY RELEASABLE. No hardware is flashed.

Source evidence: the wake-phrase funnel (`24ceaff`), `results/TOP100_REVIEW.md`. The text score
is a screen, not acoustic truth; the batch is chosen to answer different questions, not by rank.

## The 8 phrases

| # | Phrase | Funnel rank | Category | New identity? | Why it is in the batch |
|---|---|---|---|---|---|
| 1 | okay verona | 1 | word name | yes (flagged) | #1 overall; perfect text collision, TV and name safety; a 3-syllable name after "okay" |
| 2 | okay evergreen | 4 | word name | yes (flagged) | strong consonants (V-G-R) and a long final vowel; tests a 4-syllable compound word |
| 3 | okay juniper | 14 | word name | yes (flagged) | JH and P plosives give hard acoustic edges; easy for older speakers |
| 4 | okay sequoia | 11 | word name | yes (flagged) | rare OY vowel; near-zero text collisions (9.9); tests an unusual sound pattern |
| 5 | hey thomasina | 31 | first name | yes (flagged) | a real 4-syllable first name with "hey" — directly comparable to the lab's Hey Callista |
| 6 | hello home helper | 5 | role phrase | **no** | no new identity; highest predicted catch among role phrases; tests the "hello" launcher |
| 7 | hey care companion | 76 | role phrase | **no** | no new identity; highest predicted distinctiveness in the top 100 (6.3); the longest phrase — does length buy catch rate or cost speakability? |
| 8 | hey nevina | 60 | invented name | yes (flagged) | the best invented name to pass the name-likeness rule |

Coverage of the directive's rules: ≥ 3 high-ranked word/name phrases (verona, evergreen,
juniper, sequoia, thomasina); ≥ 2 phrases with no new identity (home helper, care companion);
≥ 1 invented phrase (nevina). Launchers covered: okay ×4, hey ×3, hello ×1.

Pronunciation correction: CMUdict gives "TH-" for Thomasina; it is said tom-uh-SEE-nuh (T as in
Thomas). The batch uses `T AA2 M AH0 S IY1 N AH0`; recorded in `batch1_candidates.json`.

## Benchmarks (existing evidence, not retrained)

From the corrected 26-model lab (`772e216`, deterministic evaluation), at each model's matched
cutoff (simulated ambient ≤ 0.5 false wakes/h):

| Benchmark | Catch (all) | Catch, TV on | Catch, low volume | Wrong-word wakes | Sim. false wakes/h |
|---|---|---|---|---|---|
| hey kookaburra (acoustic benchmark only) | 75.0% | 50.7% | 90.6% | 0.16% | 0.355 |
| hey callista (best natural name) | 58.0% | 42.4% | 68.4% | 0.22% | 0.355 |
| okay velora | 54.8% | 26.4% | 70.5% | 0.49% | 0.355 |
| hey aria | 44.5% | 13.9% | 57.3% | 1.63% | 0.355 |

## Decision rule (fixed before results)

A new phrase **clearly outperforms the useful benchmark tradeoff** if, at its matched cutoff, it:
1. reaches the simulated ambient limit (≤ 0.5 false wakes/h);
2. catches ≥ 63% overall (Hey Callista + 5 points);
3. catches ≥ 42% with the TV on (≥ Hey Callista);
4. has a wrong-word wake rate ≤ 0.5% (≤ Okay Velora, the worst finalist);
5. is not an acoustic benchmark.

- If **2 or more** pass: stop and report them for physical-test consideration.
- Otherwise, if the results are informative: recommend a second batch of at most 8. It is **not**
  started automatically.

## Method

Identical to the corrected lab: the same Piper generator settings and seeds scheme, 1,800
training positives per phrase (3 forms × 600), the shared negative feature set, the microWakeWord
recipe (mixednet, 10,000 steps), the same 18 evaluation conditions, the same held-out negatives,
sentences and extra confusion list, the same ambient streams, and the deterministic per-clip noise
seed. Each batch model is also tested against every other candidate's phrase (all 26 + batch) for
cross-triggers. One retry with the identical configuration on failure; no model is dropped.

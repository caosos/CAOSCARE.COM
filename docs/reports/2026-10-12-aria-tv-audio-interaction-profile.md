# CAOSCare checkpoint — Aria TV audio and interaction profile

**REPORT DATE: Monday, October 12, 2026 — 9:22 PM America/Chicago**

## Position in the build

CAOSCare remains in **Phase 3 — Care Operations workspaces (active)** with **Phase 6 — pilot operation, reliability, room integration, and accessibility (partial and concurrent)**. This bounded item improves the Phase 6 room experience; it does not advance the overall product to Phase 7 release or live acceptance.

Status of this item: **CODE COMPLETE / FRONTEND TESTED / BUILD COMPILED / NOT LOADED / NOT LIVE-ACCEPTED**.

## Work completed in this checkpoint

1. Kept the wake phrase **“Hey Aria.”** Wake no longer has any automatic TV-power action. Conversation start may lower TV/speaker volume; conversation close restores it.
2. Preserved the corrected ending: a clear “goodbye,” “that’ll be all,” or “end the call” ends once with **“Okay, bye for now.”**
3. Added a default-on, room-scoped `tv_audio_duck` setting with admin control, opt-out warning, and Resident Aria’s two-turn confirmation-gated write path.
4. Added append-only authorization and completion receipts for preference writes, including exact request wording, exact confirmation wording, before/after state, actor, session, room, authority, and parent receipt.
5. Bound voice preference writes to the exact live kiosk, not merely another kiosk in the same room.
6. Added a **Natural** room interaction profile. Natural wake answers are one short sentence and cannot mention “back again,” “didn’t I just talk to you,” offer to linger, or append another question. Guided remains the more explanatory room default.
7. Added verified numeric TV-volume control for Home Assistant `media_player` entities. One-way infrared remains best-effort and unverified; it may dip/restore by matched steps but cannot claim an exact volume.
8. Kept the temporary conversation dip active while a resident asks for louder/quieter audio: the resident’s desired normal target is stored separately, the active physical level remains 15 points lower during conversation, and close restores the chosen target.
9. Grounded exact and relative volume changes in the resident’s transcript. A model-supplied number that the resident did not say is not applied.
10. Added the installer/setup manual, capability matrix, placement/power guidance, troubleshooting layers, profile rules, and physical acceptance procedure.
11. Split new profile and TV-power logic out of the existing large modules instead of adding more logic to them.

## Exact evidence and provenance

- Branch: `fix/aria-goodbye-grounding`
- Base at checkpoint start: `d7554f4`
- Earlier published corrected-ending implementation: `23265b7a330082c68466d21125dc6f93a98dcb19`
- Focused frontend gate after this extension: 6 suites / 69 tests passed.
- Ambiguity/state-reporting regression rerun: 1 suite / 13 tests passed.
- Full frontend attempt before the final fixture correction: 93 suites / 646 tests passed; one product assertion failed and was corrected, then its full 13-test suite passed. Five other suites did not load because the local install is missing `@radix-ui/primitive/is-development`; this is an environment/dependency failure, not a passed gate.
- Optimized frontend build: compiled successfully, `main.b2ab2337.js`.
- Changed Python modules: syntax compiled successfully.
- Backend pytest: **NOT RUN** — this scratch runtime lacks `pytest`, `fastapi`, and the repository's backend test environment. New backend tests are present but unexecuted here.
- Browser/Claude Chrome evidence: **NONE for this checkpoint**.
- Tested implementation revision: `7186d52` (`7186d521aea21a40409c4a8487b3361f98b29117`).
- Published review-branch implementation: `e7bcbde9e8b2e7725ab0604b0afe14e8e5b1cc73` on `fix/aria-goodbye-grounding`.
- Loaded revision: **UNKNOWN / unchanged from this environment**.
- Latest timestamped host observation: **UNKNOWN**. This environment did not inspect or control the EliteDesk, Room 214, Home Assistant, IR Mate, or production.

## ONE current bounded task

`careops-aria-tv-audio-profile-001` — responsible worker: Codex — stage: **published for review; not merged or loaded**.

## Remaining steps for this milestone

1. Finish diff/repository checks and commit this bounded slice.
2. Publish the review branch without merging or deploying.
3. Through the existing controlled coordinator, load the reviewed revision in Room 214.
4. Set Room 214/Michael's kiosk to `aria_interaction_profile=natural`; existing kiosk records default to Guided until explicitly changed.
5. Run ten labeled normal-voice “Hey Aria” attempts from Michael's normal seat with the TV at normal volume; record detection/miss, input source, speech/noise levels, and timestamps.
6. Run physical wake → dip → conversation → volume adjustment → “Is that good?” → goodbye → restore acceptance.
7. Run voice opt-out proposal/no/yes/expiry/wrong-room/wrong-kiosk tests and confirm the receipt chain in the real backend test environment.
8. Re-run the complete backend and frontend gates in a clean dependency environment.

## Upcoming milestones

1. Finish the current Phase 6 Room 214 acceptance item.
2. Reconcile remaining Phase 3 department-workspace owner decisions and acceptance.
3. Complete Phase 4 scheduling/records/resources.
4. Complete Phase 5 communications integrations.
5. Finish Phase 6 repeatable pilot provisioning, reliability, accessibility, hardware acceptance, and cost measurement.
6. Enter Phase 7 release/deployment/live acceptance only after the above evidence exists.

## Honest product assessment

The product is credible and useful, but the claim cannot be “nobody has voice, senior care, and smart-home controls together.” Products already cover parts of that combination. CAOSCare's strongest defensible position is the operating layer that joins configurable resident conversation, accessible home control, staff/family routing, and receipt-backed accountability for who heard a request, what changed, and whether the physical device verified it.

The suggested **$40/month** subscription is plausible as a starting hypothesis, not validated pricing. Unit cost, support burden, hardware financing, installation labor, retention, and willingness-to-pay have not been measured. The practical sales path is to prove one repeatable, state-reporting accessibility package locally; certify a small installer group; show physical verification and request receipts; then approach shade, lighting, thermostat/HVAC, and home-improvement financing partners with evidence rather than a broad concept pitch.

## ETA, blocker, and Michael action

- Engineering ETA for this code slice: commit/publication expected during this closeout.
- ETA for loaded Room 214 acceptance: **UNKNOWN** because this environment has no host/load authority or live room access.
- ETA for overall product completion: the prior planning range remains **2–4 focused engineering weeks plus hardware/provider calendar time**, not a promise; it must be recalculated after current milestone inventory and pilot evidence.
- `next_check_at`: **MISSING** in this execution environment; no new monitor or duplicate automation was created.
- Blocker: live host access, Room 214 load, clean backend test environment, and labeled physical acceptance evidence.
- Michael must do: **NOTHING for code closeout.** For physical acceptance later, Michael supplies the ten normal-voice attempts when the reviewed build is actually loaded.

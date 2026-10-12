# Handoff — 2026-10-12 ~12:25 CDT (coordinator session caoscare-1-ee restarting at Michael's request)

HANDOFF CAPSULE
- Objective: `careops-room214-wake-recall-001` — Room 214 "Hey Aria" is missed often (Michael: ~7 tries; logs 11:29–11:43 CDT: ~12 loud speech bursts, 2 detections; both conversations then worked). Michael's direct order: "find it and fix it". Then resume `careops-dining-dietary-allergen-truth-001` (paused, no code written).
- Branch: `integration/2026-09-27` in `~/CAOSCARE-INTEGRATION` (git worktree). Head after this handoff: see `git log -1`.
- Lane / ownership: wake listener `room-node/aria_wake/` (Michael lifted the "no Hey Aria work" limit for this fix). Do NOT change the conversation model, Aria prompts, production (`ff87c22`), or merge PR #41/#42/#131. Do NOT restart the dev backend without telling Michael first (he asked).
- Last proven state:
  - Cause = on-device detector recall (sherpa-onnx KWS, `keywords.txt` "HEY ARIA"), not backend, not the gpt-realtime-2.1 model (wake fires before any OpenAI connection; only 3 suppressed detections in 5 days, all mid-conversation).
  - Synthetic sweep (`eval_sweep.py`, 924 positives / 952 adversarial, no soak) — results in `docs/reports/2026-10-12-room214-wake-recall/`:
    | thr / score | all | quiet | far | TV | adversarial false |
    |---|---|---|---|---|---|
    | 0.05 / 1.5 (live) | 75% | 67% | 56% | 39% | 12 |
    | 0.01 / 2.5 | 80% | 73% | 67% | 44% | 16 |
    | 0.01 / 3.5 | 83% | 73% | 71% | 50% | 24 |
    Threshold ≤ 0.03 barely matters; score is the lever. Alternate BPE segmentations: no gain. Pronunciation variants (hay/arya/ariya/arria): worse (72%). Rejected.
  - Shadow detector (`room-node/aria_wake/shadow.py`, commit `01d3833`) is LIVE since 2026-10-12 12:20 CDT at 0.01 / 3.5 next to the unchanged live 0.05 / 1.5 detector. It logs `shadow_only` (shadow heard it, live did not) and `live_only`; never wakes, keeps no audio. Enabled by two lines appended to `~/.config/aria-wake/aria-wake.env` (`ARIA_WAKE_SHADOW_THRESHOLD=0.01`, `ARIA_WAKE_SHADOW_SCORE=3.5`; backup in the old session scratchpad). Listener PID at handoff: 1661030.
- Runtime: wake listener `aria-wake.service` (user unit) PID 1661030; room page services `aria-wake-page`, `aria-wake-kiosk` unchanged; dev backend `214523f` PID 1640124 on :8092; production `ff87c22` unchanged.
- Unresolved proven defect: wake recall too low for Michael's real voice in Room 214.
- Next safe action:
  1. `journalctl --user -u aria-wake --since "2026-10-12 12:20" | grep -E '"shadow_only"|"live_only"|"wake_detected"'` — count real misses the 0.01/3.5 shadow would catch, and any shadow_only during normal talk/TV (false-wake risk).
  2. Ask Michael for ~10 labelled "Hey Aria" tries (normal distance, then across the room, then with TV) and read the shadow log for each.
  3. If the shadow catches the misses without firing on normal talk: set the live `ARIA_WAKE_KEYWORDS_SCORE` (probably 2.5–3.5, threshold 0.01) in `~/.config/aria-wake/aria-wake.env`, restart `aria-wake` only when no call is active, re-test with Michael, record hits/misses + false wakes, update `room-node/aria_wake/README.md` sweep table, PROJECT_STATE, issue #129 (DONE `careops-room214-wake-recall-001`).
  4. Then resume `careops-dining-dietary-allergen-truth-001` (plan in issue #129 comment ACK da-e716a7ae10).
- Owner decisions still pending (do not invent): Alerts acknowledge/close roles (B recommended); who clears review flags; family re-notify on repeat presses; Front Desk message scope.
- Intake: DA-INTAKE peer messages from the Desktop-Agent control plane on issue #129 (ACK/WORKING/DONE receipts with exact America/Chicago next_check_at).

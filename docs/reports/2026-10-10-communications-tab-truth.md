# CommunicationsTab loading/failure truth (da-c90537f56a)

Fixed at `27b410e` (base `0e05e92`). `frontend/src/pages/CommunicationsTab.jsx`.

## Defect (reproduced by mounted fixtures against the old file)
- One `Promise.all` for `/notifications/status` and `/notifications`: either failing discarded both and only toasted.
- Initial state `status=null`, `notifs=[]`: a failed/unresolved status rendered "Resend/Twilio - not configured"; a failed/unresolved log rendered "No notifications."
- A failed filter change left the previous filter's rows on screen as if current.

## Change
Each read settles on its own (`Promise.allSettled`): loading, error (never loaded), ok, or ok+stale (a later refresh failed). The log result carries the filter it belongs to: a failure for a different filter shows an error (never the old rows); a failed refresh of the same filter keeps the rows, marked stale. Empty is asserted only from a successful read ("as of the last successful load" when stale). Retry on both. `latestOnly` and unmount protection unchanged; API calls and permissions unchanged.

## Evidence
- `frontend/src/lib/__tests__/communicationsTab.test.js`: 10 mounted tests (loading; each GET failing alone; both failing; genuine empty; retry; status stale; failed filter change then recovery; same-filter stale empty; old/new reply order). On the old component 9 of 10 fail (the reply-order test passes, as `latestOnly` already existed). New code: 10/10.
- Frontend 64 suites / 543 pass; production build compiles.
- Isolated browser check (scratch DB `caoscare_cm_truth`, backend 8133 with no provider keys, built frontend on 3133, headless Chrome, synthetic rows, CDP injected GET failures, Send test never used, no provider contacted): loaded; status 500 alone; log 403 alone; both failing; retry recovery; failed filter change (old rows gone, error shown) and recovery; status stale banner; 390 px width, 0 px horizontal overflow. Screenshots in `docs/reports/assets/2026-10-10-communications-tab/` (1_loaded … 9_narrow_both_fail).

## Not covered
Same-filter stale rows in a real browser (needs a refresh trigger; the only UI one is Send test, which was not used) - covered by the mounted test. Real provider/delivery behaviour unchanged and unproven.

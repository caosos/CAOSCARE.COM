# DeviceStatusCard: missing kiosk status is unknown, not online (da-11a4781440)

**Defect:** the Kiosks tile counted `status !== "offline"` as in service. RQ-035 deliberately strips `status` for non-admin staff, so a nurse saw every kiosk as green "in service" with no basis.
**Fix (frontend only, API boundary unchanged):** `frontend/src/lib/deviceCounts.js` counts only `online` / `offline` as known; anything else is unknown. Non-admin stripped rows show "—  / N kiosks, status not available to your role" (neutral, never green); mixed shows "1 / 2 in service, 1 status unknown" (amber); a failed request shows "status unavailable", not 0 / 0; loading shows "…".
**Tests:** `deviceStatusCard.test.js` (7: admin known, one offline, non-admin stripped, mixed, empty, failed request, helpers); old `!== "offline"` logic fails 3 of 7. Frontend 62 suites / 519 tests; `CI=true yarn build` compiled.
**Browser (isolated scratch DB, built UI, real role-shaped API rows):** `assets/DSC_known_admin.png` (2 / 3, 1 offline), `assets/DSC_known_nurse.png` (stripped rows: "—", not green), `assets/DSC_mixed_admin.png` (1 status unknown), `assets/DSC_empty_nurse.png` (0 / 0). Staging stopped and the scratch DB dropped.
**Not done:** no live role session on the running :3000/:8092; Room 214 untouched.

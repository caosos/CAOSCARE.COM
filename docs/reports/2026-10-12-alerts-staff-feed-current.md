# Nurse Live alerts: current vs older — careops-alerts-staff-feed-current-001 (2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED. Alerts section not owner-accepted.

**Defect (full-acceptance finding 1):** `/alerts/feed` (only consumer: nurse `/staff` Live alerts) returned every open alert. On development all 322 open alerts are > 72 h old (device-test debris), so the phone page listed 200 cards, ~87,112 px tall, 200 Acknowledge buttons.

**Failing before:** `backend/tests/test_alert_feed_current.py` (feed returned 72 h+ alerts as live), `frontend/src/pages/StaffDashboardOlder.test.jsx` (no split).

**Repair:** `06a51da` + `16af7b3`
- `/alerts/feed` default `scope=current` = opened within `STALE_ALERT_HOURS` (72 h, the owner board's `alert_is_stale` bound), newest first; `scope=older` returns the rest (newest 200). `/alerts/stats` adds `older_open`. Nothing is closed or changed.
- Nurse dashboard: "N older open alerts are hidden (opened more than 3 days ago, mostly device tests). Nothing was closed." + Show older; shown older alerts carry an "older" badge; while shown: "Showing 200 of 322 … The full list is on the Alerts board." Empty state reads "No current alerts".
- Unchanged: acknowledgement, authorization (anonymous 401 on both scopes), receipts, owner `/alerts` board.
- File sizes: `backend/routes/alerts.py` 387 (+9, pre-existing > 300), `frontend/src/pages/StaffDashboard.jsx` 401 (+11, pre-existing > 300). Not split in this bounded task.

**Gates:** backend 612 passed / 0 failed / 31 skipped; frontend 92 suites / 645; build compiled.

**Dev browser (headless Chrome) 11/11, 0 failed API calls:** current 0 + older 322 = 322 open; nurse 390 px: 1 card (the new synthetic alert, first), height 5,538 px (was ~87,112), no overflow, banner "322 older … Nothing was closed"; acknowledged (receipt recorded); Show older → 200 cards marked older, "Showing 200 of 322"; Hide older returns; owner `/alerts` "1 current open · 322 older needing review" unchanged; owner `/staff` desktop OK.
**Cleanup:** synthetic alert + 2 receipts removed; 0 notifications/dispatches; 322 open (unchanged).

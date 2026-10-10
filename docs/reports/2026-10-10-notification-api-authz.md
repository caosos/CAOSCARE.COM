# Notification API authorization (da-b969d9cb87)

## Policy / callers (inventory at d5de81f)
`GET /notifications`, `GET /notifications/status`, `POST /notifications/test` required only `get_current_user`. The only caller of all three is `CommunicationsTab` (Admin > Email & notifications), mounted under `/admin`, which `App.js` restricts to owner/admin. Sibling endpoints on the same surface (`/notifications/readiness`, `/email/allowlist`, inbound messages) use `require_admin`. No non-admin caller exists (RequestHistoryDialog uses `/tasks/{id}/detail`; no mobile/script caller found). Policy is therefore unambiguous: owner/admin only; no new role grant, no owner choice needed.

## Root cause
The UI restriction was the only barrier. Any signed-in user (staff of any department, front desk) could read every recipient and body in `db.notifications`, filter by any department or task id, and use test-send to push a message through the real provider path (ENGINEERING_CONTRACT decision 12: backend must enforce).

## Fix
`backend/routes/notifications.py`: the three endpoints use `require_admin` (owner/admin). Dependency resolves before the body runs, so a denied test-send reaches no provider function, no network and writes no notification. Family-contact and task-detail routes untouched.

## Evidence
- `backend/tests/test_notification_api_authz.py` (in-process, scratch DB, local-owner bypass off, both provider functions and the HTTP client mocked): roles owner, admin, nursing staff, maintenance staff, front desk, anonymous; seeded rows across departments/tasks plus an unscoped test row. Unfiltered, department-filtered, other-task-id and status-filtered queries return 403/401 with no row data for non-admins; owner/admin still read and filter correctly; denied test-sends (email, sms, in-app) leave the provider mocks uncalled and the notification count unchanged; owner/admin test-send reaches the (mock) provider with a fake destination. At d5de81f 6 of 12 fail (non-admin roles served); anonymous cases already passed. After: 12/12.
- Focused (authz + notification_delivery + rq027 + email_readiness): 32 passed.
- Full gate (port 8127, scratch DB, providers blank): 504 passed, 0 failed, 31 skipped.
- Isolated browser (scratch DB, built frontend unchanged, synthetic users/rows): admin sees the delivery log, provider status and Send test; same-origin fetches as admin 200/200; as nursing staff and as front desk: log, department-filtered log and status 403 with no data, test-send 403; no token 401; the nurse opening `/admin?tab=communications` ends on `/staff`. Screenshots `assets/2026-10-10-communications-tab/13_admin_authz_ok.png`, `14_nurse_denied.png`. Scratch DB and servers removed.

## Limits
Frontend unchanged (no frontend tests needed). Browser calls for denied roles are direct fetches with their token; the UI never offers them. Not deployed; the live :8092 backend still has the old behaviour until restarted. No provider was contacted.

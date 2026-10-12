# Front desk: alert messages that did not go out (careops-frontdesk-failed-deliveries-001, 2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED. Unified inbox as a whole not complete.

## Gap
Escalation texts/calls (`notify_alert_phone`) and family alert updates (`notify_family_for_alert`) that were not sent or failed were visible only in the admin delivery log (`GET /notifications`, admin-only). Request-linked deliveries were already covered by Needs attention (routing exceptions).

## Scope / redaction / action contract (`2278dcf`)
- `GET /ops/delivery-exceptions` (`backend/routes/delivery_exceptions.py`), **front desk + owner/admin**; other staff 403, anonymous 401.
- Source: `db.notifications` with `alert_id`, no `task_id`, `related_object_type` none/alert, status logged/failed/bounced/complained, created within 72 h, newest first (200 max).
- Returned: channel, masked recipient labelled by role (`Family: <name> (<relationship>)`, `Supervisor|On-call phone ending 1234`, else masked phone/email), plain status (`Not sent - no message provider is set up`, `Failed - the provider did not accept it`, `Bounced …`), resident name/room, alert severity/status, alert id, delivery receipt id. **Never** subject, message text, full address/number or provider error text.
- Action: **Open alert** (`/staff?alert=…`). Nothing is re-sent: no canonical retry path exists for family/escalation messages and re-sending an emergency update is a care decision. Admin log unchanged and still admin-only.
- UI: `DeliveryExceptionsCard` under the request exceptions in the front desk Needs attention tab.

## Tests and gates
Failing before: `backend/tests/test_delivery_exceptions.py` (404 — no desk view); `FrontDeskAttention.test.jsx` extended (no delivery rows). Backend 615 passed / 0 failed / 31 skipped; frontend 93 suites / 646; build compiled.

## Dev browser 11/11, 0 failed API calls
Temporary policy with a fictional supervisor phone (dev has no SMS/email provider), one synthetic emergency for demo resident 3W03 through the real kiosk path: family email + supervisor SMS both `logged`. Desk API lists both, redacted; labels "Family: Betty's daughter (daughter)" and "Supervisor phone ending 1234", "Not sent - no message provider is set up"; SMS row links `alert_sms_attempt` receipt; owner sees the same rows and the full log still has raw detail; nurse 403, anonymous 401, desk full log 403; desk 1280 rows = API rows; Open alert opens the real alert; 390 px no overflow/no errors. Cleanup: alert, 4 receipts, 2 notifications, temporary policy removed; no stored rule.

## Finding (not fixed)
Family alert updates (`notify_family_for_alert` → `send_email`/`send_sms`) write **no receipt** (row's `receipt_id` is null), unlike escalation SMS (`alert_sms_attempt`). Receipt-law gap; recommended next item.

# Family alert update receipts — careops-alerts-family-update-receipt-001 (2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED (backend).

**Defect:** `notify_family_for_alert` (kiosk/manual alerts, geofence, wearable) sent family email/SMS with no receipt; the notification had no `receipt_id` and no alert link fields.
**Failing before:** `backend/tests/test_family_update_receipt.py` — notification `receipt_id` None.
**Repair (`2079206`):** each attempt writes one `family_alert_update_attempt` receipt — actor `system:family_notify` (system), authority `family_contact:<contact_id>:notify_on:<pref>`, channel, parent = the alert's origin receipt, after_state `{notification_id, notification_status}`, `result_label` logged/sent → unverified, failed → failed (status failed + provider reason), no address/number in the result text. The notification stores the receipt id and `related_object_type/id = alert`. Sending behaviour unchanged; no retry, no new store.
**Gates:** backend 616 passed / 0 failed / 31 skipped; frontend untouched (93 / 646).
**Dev proof (loaded `2079206`):** synthetic emergency for demo resident 3W03 via the real kiosk path → family email `logged`, 1 receipt `rcpt_62c0bdeb7bcd`, stored on the notification, parent = origin, authority `family_contact:fam_9f4a9be2a5f9:notify_on:emergency`, `unverified`; 0 sent/delivered claims; desk "Needs attention" row now carries the receipt; anonymous receipts list 401, desk 403. Cleanup: alert, 2 receipts, 1 notification removed.
**Finding (not fixed):** `POST /alerts` (room screen) calls `notify_family_for_alert` on every press, including coalesced repeat presses, so a repeat press re-sends the family update; geofence and wearable notify only for a new event. Needs a decision whether repeat presses should notify family again.

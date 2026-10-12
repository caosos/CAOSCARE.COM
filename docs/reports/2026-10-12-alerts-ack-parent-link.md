# Acknowledgement receipt parent link — careops-alerts-ack-parent-link-001 (2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED (backend). Alerts section not owner-accepted.

**Defect (full-acceptance finding 2):** `alert_acknowledged` had no `parent_receipt_id`; `alert_completed` already names the alert's origin `resident_assistance_event` receipt.
**Failing before:** `backend/tests/test_alert_ack_parent_link.py` (real creation path → acknowledge): parent `None`.
**Repair (`d0642ec`):** `_record_acknowledgement` sets `parent_receipt_id` = the alert's stored origin `receipt_id`. Nothing else changed.
**Proven:** test — parent = origin, history entry carries the acknowledgement receipt, repeat refused with no second receipt, completion still parents the origin, no sent notification. Dev API (loaded `d0642ec`): origin `rcpt_e2b849e31cda` (resident_assistance_event) → ack `rcpt_0f844d2bee77` parent match; history receipt match; anonymous ack 401 with 0 receipts; repeat ack 404, still 1; 0 SMS/call receipts. Cleanup: alert + 2 receipts removed.
**Gates:** backend 613 passed / 0 failed / 31 skipped; frontend untouched (92 / 645); no UI change.

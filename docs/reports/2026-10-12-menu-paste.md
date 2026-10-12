# Whole-menu paste — careops-menu-paste-001 — 2026-10-12

## First concrete failure
"Paste a menu" took one day at a time: it always used the date picked on screen. A kitchen pasting a week's menu had to pick each date and paste each day separately. Nothing said so.

## Repair
- `POST /menu/ingest/paste` (`backend/routes/menu_ingest.py`): if the text has dated day headers ("Monday 2026-10-12:", the same format the activities calendar paste already uses), each dated section becomes its own draft upload for that day through the existing `create_menu_upload`. Each draft has its own receipt, and up to 31 days can be pasted at once. Impossible dates are refused (400). Without headers it is one day's menu for the picked date, as before. Kitchen/Administration editors only (nursing 403, unchanged rule). PR #110 was not used.
- `MenuUploadsPanel.jsx`: the dialog explains the dated format and shows an example. After a week paste it says "Drafts added for N days (first to last). Pick each date above to review and publish it."

## Trace (dev backend `7e854ce`, temporary Kitchen QA user, labeled menu)
1. One paste covering today and tomorrow produced one draft upload per day.
2. Drafts were not public: Aria's supper lookup returned nothing labeled.
3. Today's parsed breakfast, lunch and dinner were shown for review.
4. Publishing today made Aria's lookup return the pasted dinner. Tomorrow stayed a draft until its own publish.
5. Replacement: a corrected dinner for today was pasted and published. Aria then returned only the corrected dinner. The earlier dinner was kept in the record, marked superseded, and shown as "Replaced" on the operator menu.
6. The resident room screen showed the corrected dinner and not the replaced one, at 1280 and 390 px.

**Result: 12/12. 0 failed API calls.** Every labeled upload, item and receipt and the QA user were removed (0 labeled items left). Screenshots: `docs/reports/assets/2026-10-12-menu-paste/`.

Load failure versus empty for the menu was fixed in `6d80cad`.

## Tests
- Backend gate **570 passed, 0 failed, 31 skipped**. New `test_menu_paste_multiday.py`: week paste gives per-day drafts with receipts; a bad date is refused; a single-day paste still needs a date; nursing gets 403.
- Frontend **86 suites / 621 tests**. Build compiled.

## Limits
- Each day is still reviewed and published on its own date; there is no "publish whole week" button.
- Not deployed.

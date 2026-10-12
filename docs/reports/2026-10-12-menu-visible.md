# Menu visible end to end — careops-menu-visible-001 — 2026-10-12

## What was wrong
The owner saw no menu. Cause: the published menu ends on **2026-10-03** (dev; production was last refreshed through 2026-10-02 on 2026-09-19). Nothing is published for today, and the Menu screen said only "No menu items for this date yet". There was no indication why, or what to do.

## What changed
- `GET /menu/coverage` and `GET /schedule/coverage` (`backend/routes/content_coverage.py`, staff only). Each returns whether today has anything residents and Aria can see, the last published day, how many days ago that was, and how many days ahead are covered. They use the same rules as the public reads: approved menu items; schedule rows that are not draft/superseded and not staff-only.
- `frontend/src/components/ContentCoverageNote.jsx` on the Menu and Daily schedule screens. Example: "Residents and Aria have no menu for today. The last published day is 2026-10-03 (9 days ago). Paste or email the next menu, then publish it." When coverage runs out within 2 days: "Published through … only."

## Trace (dev backend `4b270ef`, labeled menu, temporary Kitchen QA user)
1. Before: the exact request Aria's `get_menu` tool makes for "what's for supper tonight?" (`GET /menu/public/today?meal_period=dinner`) returned nothing. The Kitchen Menu screen said nothing is published today.
2. Kitchen staff pasted a labeled breakfast/lunch/dinner. It was saved as a draft upload, and Aria's lookup still returned nothing (drafts are not live).
3. Publish menu: Aria's dinner lookup returned the labeled salmon and rice. Receipts recorded: `menu_content_uploaded`, `menu_content_published`. The coverage warning cleared.
4. The resident room screen (`/kiosk/demo`) showed today's published breakfast and dinner at 1280 and 390 px.
5. With no menu, Aria's tool text (`menuToolMessage`) already says no approved menu is on file and nothing was asked of the kitchen; unit-tested in `communityServices.test.js`.

**Result: 10/10. 0 failed API calls.** The labeled items, upload, receipts and QA user were removed afterwards; the dev menu for today is empty again. Screenshots: `docs/reports/assets/2026-10-12-menu-visible/`.

Note: the dev site at localhost:3000 reads the resident menu from the live caoscare.com (a local dev-only override in `frontend/.env`). The resident-screen proof therefore used a separate build without that override, served on a temporary port against the dev backend.

## Tests
- Backend gate **567 passed, 0 failed, 31 skipped**. New `test_content_coverage.py`.
- Frontend **85 suites / 617 tests**. New `contentCoverageNote.test.js`. Build compiled.
- Not verified: a spoken Aria question (no voice run); the tool's request and wording are covered above.

## Limits
- Production still has no menu after 2026-10-02 or schedule after its last refresh. Publishing current menus there is a data action this session cannot do: production access was refused. Kitchen staff, or Michael, paste and publish them.
- Not deployed; production `ff87c22`.

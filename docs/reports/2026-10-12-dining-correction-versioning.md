# Dining: menu corrections are versioned replacements (careops-dining-correction-versioning-001, 2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED. Dining not owner-accepted.

## Inventory (one store: `db.menu_items`; receipts via `content_receipts.record_content_change`)
| Path | Before | After |
|---|---|---|
| Staff add (`POST /menu`) → draft → publish (`/approve`) | receipted | unchanged |
| Email/paste upload (`menu_ingest`) for the same date+meal | supersedes older published items (`status: superseded`, receipted) | unchanged |
| **Correct a published item** (`PATCH /menu/{id}`) | **edited in place** — published version lost (receipt summary only); "save as draft" **took the dish off the residents' menu** | new item with `replaces`; published version stays live until the correction is published; then original `superseded`/`superseded_by`, kept and labelled **Replaced**; `menu_content_corrected` + `menu_content_superseded` receipts |
| Edit a draft | in place | unchanged (drafts were never public) |
| Re-publish / edit a superseded item | 409 | 409; a competing correction published second → 409 |
| Residents / Aria (`/menu/public/today`) | approved only | approved only → always the current corrected item |
| Who may change the menu | kitchen, administration, owner/admin (`require_content_editor`) | unchanged; nurse 403, anonymous 401 |

## Tests
Failing before: `backend/tests/test_menu_correction_versioning.py` (correction kept the same id). Updated (intentional behaviour change): `test_community_services.py` expected in-place edit and "draft correction removes the dish". Frontend: `MenuItemDialog.test.jsx` (wording + draft toast). Backend 618 passed / 0 failed / 31 skipped; frontend 95 suites / 649; build compiled.

## Dev browser 8/8 (demo kitchen staff Iris Kwan, synthetic date 2031-03-04 so no real screen is affected), 0 failed API calls
Published "Baked cod" visible to residents/Aria → Correct dialog explains versioning → "Save as draft" makes a new draft "Grilled salmon" with a Correction note while cod stays live → Publish → cod labelled Replaced, residents/Aria read salmon → 390 px readable, no overflow → receipts created, published, corrected, superseded, published → superseded re-publish/edit 409, nurse 403, anonymous 401. Cleanup: 2 items, 5 receipts removed.

Not in scope (not changed): dietary/allergen semantics, live provider email, resident Home UI.

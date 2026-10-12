# Dining: staff-entered dietary labels and allergens (careops-dining-dietary-allergen-truth-001, 2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED (2026-10-12 15:25 CDT). Not owner-accepted.

## What changed (product commit `b2faae1`)
| Surface | Before | After |
|---|---|---|
| `MenuItem` (one store, `db.menu_items`) | no dietary/allergen fields | `dietary_labels`, `allergens` ("contains") lists, staff-entered |
| Create / edit (`MenuItemCreate`/`MenuItemUpdate`) | — | `models.normalize_menu_labels`: trim, collapse spaces, drop blanks, case-insensitive de-dup (first spelling kept); >12 labels, >40 chars, or characters outside letters/digits/space/`' & ( ) / . -` → 422. On edit, absent = unchanged, `[]` clears |
| Correction of a published item | — | labels carried forward unless changed; the superseded version keeps what it said |
| Content receipts | — | before/after include both lists |
| `/menu/public/today` (residents, Aria) | name, description, availability | + both lists, verbatim; nothing added or inferred |
| Aria `get_menu` text (`communityServices.menuToolMessage`) | — | `[Vegetarian; contains: Milk, Wheat]` per item, plus a rule only when labels exist: repeat exactly, never "safe"/"suitable", an unlisted allergen is not a statement it is absent. No Aria prompt change |
| Staff Menu dialog / list | — | two comma-separated inputs + the fixed note; list shows labels |
| Resident Today panel | — | labels under each dish + `MENU_LABELS_NOTE` |

`MENU_LABELS_NOTE`, `menuLabelsText`, `parseMenuLabels` live once in `frontend/src/lib/communityServices.js`.

## Tests
- Failing before: `backend/tests/test_menu_dietary_labels.py` (ImportError — no field/normalizer); two new cases in `communityServices.test.js`; one in `MenuItemDialog.test.jsx`.
- Backend gate (`run_backend_tests.sh`): 640 passed / 2 failed / 13 skipped. The 2 failures (`iter10_test::test_session_default` expects voice "shimmer", Room 214 is "marin" by owner decision; `iter8_test::test_cross_session_memory_recall`, live OpenAI) fail identically on clean HEAD `9aaf9d5` (634 / 2 / 13): `backend/.env` now carries an OpenAI key so these no longer skip. Unrelated to the menu.
- Frontend 95 suites / 652 tests; production build compiled.
- Scratch databases dropped.

## Dev browser acceptance 11/11 (`2026-10-12-dining-dietary-allergen-truth/acceptance_script.py`)
Dev backend `042ef84` (PID 1828430, restarted with Michael's permission while Room 214 was idle), dev frontend :3000, demo kitchen login, synthetic date 2031-03-05. Dialog shows label inputs + note → " Vegetarian ,vegetarian, " / "Milk,  Wheat" saved as `["Vegetarian"]` / `["Milk","Wheat"]` → staff list shows "Vegetarian; contains: Milk, Wheat" → `/menu/public/today` repeats them verbatim, nothing added → correction dialog prefilled; adding Egg publishes a new version, superseded keeps Milk, Wheat → `<b>milk</b>` refused with a readable message (the one 422 from the page, expected), nothing saved → 1280 no page errors; 390 px no overflow → corrected receipt before/after carry the labels → nurse 403, anonymous 401, 13 labels 422. Cleanup: 2 items, 4 receipts. Screenshots 01–03.

## Not done
- Resident Today panel visual: it reads today's menu from production (`REACT_APP_FACILITY_CONTENT_URL`), so it shows labels once production carries this change and staff enter them; covered here by the public endpoint and unit tests.
- Note: the resident Today panel reads menus from `REACT_APP_FACILITY_CONTENT_URL` (production), so residents see labels only after production carries this change.

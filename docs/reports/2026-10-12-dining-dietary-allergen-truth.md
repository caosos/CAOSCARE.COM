# Dining: staff-entered dietary labels and allergens (careops-dining-dietary-allergen-truth-001, 2026-10-12)

Status: IMPLEMENTED / TESTED. Browser acceptance (desktop / 390 px) NOT yet run — needs the dev backend on :8092 restarted onto `b2faae1` (Michael's OK and an idle Room 214). Not DEV_ACCEPTED, not owner-accepted.

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

## Not done
- Desktop and 390 px browser proof, role refusal in the browser (API 403 for nursing is covered in the test).
- Note: the resident Today panel reads menus from `REACT_APP_FACILITY_CONTENT_URL` (production), so residents see labels only after production carries this change.

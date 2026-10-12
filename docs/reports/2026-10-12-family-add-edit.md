# Family contacts: add and edit — careops-family-add-001 / careops-family-edit-001 — 2026-10-12

## What was wrong
- **Add:** the "Add family contact" button existed, but at phone width (390 px) its header row did not wrap and the button sat partly off-screen (right edge at 475 px). That matches the owner not finding an add path. At desktop width it was visible.
- **Edit:** there was no edit at all — no route and no control. Only copy portal link and delete.
- **Receipts:** creating, approving for calls and deleting a contact wrote no receipt.

## What changed
- `PATCH /api/family-contacts/{id}` (`backend/routes/notifications.py`, `FamilyContactUpdate` in `models.py`): edits name, relationship, email, phone and alert choices. It cannot change the resident, call approval (still the admin-only `PATCH .../calls`) or the portal link (422). A blank name is refused. Unchanged values are not a change.
- Safety rule: an **approved** contact's phone is the number Aria dials, so changing it is owner/admin only (403 otherwise, nothing written). Same rule as approving the contact. An unapproved contact's phone can be changed by staff.
- Receipts: every contact change (created, updated, call approval changed, deleted) writes one receipt, chained per contact, with actor, authority and before/after state.
- UI: `frontend/src/components/FamilyContactForm.jsx` is the one form for add and edit (edit keeps the resident fixed and explains the approved-phone rule). `FamilyTab.jsx` gets an Edit (pencil) button per row, and its header buttons wrap at narrow widths.

## Tests
- Backend gate **557 passed, 0 failed, 31 skipped** (new `backend/tests/test_family_contact_edit.py`, 7 tests: edit with chained before/after receipt; no-change and blank-name; allow_calls/resident not editable; approved phone owner/admin only; unapproved phone staff OK; 404/401; call approval and delete receipts). `test_family_contact_call_approval.py` still passes.
- Frontend **81 suites / 603 tests** (new `familyContactForm.test.jsx`: edit PATCHes without resident or allow_calls; add refuses with no resident and POSTs without allow_calls). Production build compiled.
- Browser (dev site on `f4f210f`, headless Chrome, temporary labelled "Demo - QA Admin", removed afterwards): **11/11** — add a contact for a Demo resident, edit relationship and email, row shows the new values, receipts created → updated, edit dialog at 390 px, no page overflow at 1280 or 390 after the wrap fix, 0 failed API calls. The test contact and its receipts were deleted. Screenshots: `docs/reports/assets/2026-10-12-family-edit/`.

## Limits
- Any signed-in user can still add or delete a contact (existing rule, unchanged).
- Not deployed; production `ff87c22`.

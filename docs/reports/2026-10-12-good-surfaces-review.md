# Review of the surfaces the owner liked — careops-good-surfaces-review-001 — 2026-10-12

Requests, Devices, Reports/Audit, Facility setup and the Live board were each used for one normal task with the intended role. The runs used headless Chrome (Playwright) on the dev site with temporary labelled QA users, removed afterwards, at 1280 and 390 px. The Claude-in-Chrome extension was not used.

| Surface | Role | Normal task | Result |
|---|---|---|---|
| Requests | admin | open a request | detail with its timeline |
| Devices | admin | demo-room light On, then Off | two simulated, executed commands; state follows; **each now has a receipt** |
| Reports / Audit | admin | daily exceptions, CSV download, audit page | report shown; CSV has a header row; audit loads |
| Facility setup | owner | view the facility | the facility record shown |
| Live board | nursing | open an alert | alert detail opens |

There was no page overflow and 0 failed API calls on every surface at both widths. Room 214's real device commands were unchanged.

## First concrete gap, repaired
`POST /devices/{id}/command` (the Admin Devices On/Off/brightness buttons) accepted **any signed-in login**, so a staff login could switch any room's real devices. It also wrote **no receipt**: the command log held only the display name.
- Now owner/admin only (others 403, nothing sent). The only caller is the admin Devices screen.
- Every command, success or failure, writes a `staff_device_command` receipt. It records the actor id, name and role; authority `admin_override:<role>`; before and after state with the requested value; the command id; and the result label (simulated / verified / unverified / failed).
- Test `backend/tests/test_admin_device_command.py` (6): nurse and front desk get 403 with nothing written, anonymous gets 401, admin and owner get a receipt naming them, a failed command gets a failed receipt.

## Evidence
Backend gate **576 passed, 0 failed, 31 skipped**. Browser and API sweep **30/30** on dev backend `198fee4`. Screenshots: `docs/reports/assets/2026-10-12-good-surfaces/`.

## Note
A first sweep reported two false failures. My script sorted commands by `created_at`, a field command records do not have; they use `issued_at`. Re-checked: the commands were correctly labelled simulated all along.

Not deployed; production `ff87c22`.

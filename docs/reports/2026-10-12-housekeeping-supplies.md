# Housekeeping supply/linen requests (careops-housekeeping-supplies-linen-001), 2026-10-12

## Inspected first
- No inventory or stock source exists anywhere (no model, collection or route). Stock levels can't be stated
  truthfully, so nothing here claims stock; this is recorded as a gap, not invented.
- A typed Aria call "two extra towels and a warm blanket" created a housekeeping request whose items lived only in
  free text (summary/resident words). That is the first proven gap.

## Built (`5600475`)
- `request_staff_help` gains an optional `items` list (item + quantity), described as "only what the resident
  asked for; 1 if no number". Validation: name 1-60 chars, quantity 1-20, at most 10 items.
- Stored on the request (`StaffTask.items`); in the resident-safe view; Aria's spoken status adds
  "Asked for: 2 × towel, 1 × warm blanket." in every state.
- Shown as "Items: …" on the department queue card and the resident's request card.
- Fulfilment uses the normal lifecycle (claim → start → complete with a note).
- Also: the tool description no longer tells Aria to say the request was "sent".

## Evidence
- `backend/tests/test_housekeeping_supplies.py`: tool schema; bad items refused (quantity 0, empty name, 11 items);
  items stored and in the resident view; nurse completing → 403; Aria status names the items and never mentions
  stock; three chained receipts. Frontend `requestItems.test.js`.
- Live (dev backend `5600475`, demo room): typed Aria rt_qynuzxo4_1791796989926 → `request_staff_help` with
  items [2 × towel, 1 × warm blanket] → task_346a767999a8; owner in Claude Chrome saw "Items: 2 × towel, 1 × warm
  blanket" on the Housekeeping card (`01`); nurse and maintenance completing → 403; housekeeper at 390 px saw the
  items and claimed it, no overflow, no failed API calls (`02`); Aria rt_hksl8rj0_1791797058299 ("is it on its
  way?") said it was taken on, not started, no promise of arrival — her tool result included the items;
  housekeeper started and completed with "Delivered 2 towels and a warm blanket".
  Receipts (one workflow): resident_request_created → task_assigned → task_in_progress → task_completed.

## Gates
Backend 599 passed / 0 failed / 31 skipped at `5600475`; frontend 90 suites / 638; build compiled. Production
unchanged (`ff87c22`).

## Not built
Any inventory/stock record, the front-desk form's item entry, purchasing.

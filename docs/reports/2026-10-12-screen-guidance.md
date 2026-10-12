# Screen guidance — careops-screen-guidance-001 — 2026-10-12

The owner said several screens do not explain their purpose or use. Status of the screens named in the checklist:

| Screen | Purpose and next step now | Where |
|---|---|---|
| Departments | Who requests route to; click a department to see who works there, open work by person, and what was finished | `DepartmentsTab.jsx` (this change) |
| Activities | Admin → Community → Activities: how work arrives, who works there (or that nobody does), and the activities calendar with its coverage note | `a0f7773`, `4b270ef` |
| Menu | Only published items reach residents and Aria; a note says when nothing is published for today and what to do; whole-week paste explained | `4b270ef`, `7e854ce` |
| Transportation | Daily screen: New ride, Book, Unresolved explained (this change); Transport resources has a setup guide and "can rides be booked" line | `TransportationTab.jsx`, `11fe3f2` |
| Family | Who each contact is for, alerts, resident calling (owner/admin approves), portal link, how to add and edit, where deliveries are listed | `FamilyTab.jsx` (this change) |

Tests: frontend **86 suites / 621 tests**; build compiled. Browser (dev site, temporary QA admin, removed afterwards), 1280 and 390 px: **16/16** — the text is shown on Departments, Family and Transportation, no page overflow, 0 failed API calls. Screenshots: `docs/reports/assets/2026-10-12-screen-guidance/`.

Not a novice usability test: whether a new staff member can follow these screens unaided still needs the owner's review. Not deployed.

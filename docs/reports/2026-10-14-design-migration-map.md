# CAOSCare authenticated app — design migration map (2026-10-14)

Owner direction (Michael, 2026-10-14): the `/operations` workspace is the permanent
visual standard (white backgrounds, dark type, blue navigation/primary actions,
one sidebar + header, minimalist cards). Every authenticated page moves into the
shared shell (`frontend/src/components/workspace/WorkspaceShell.jsx`) in bounded
stages. **Changing appearance never removes a feature**: until a page is migrated
it stays reachable from the new sidebar exactly as it is today
(`frontend/src/lib/workspaceNav.js`; `workspaceNav.test.js` fails if any
command-centre tab is unreachable).

Status: **NEW** = in the new shell and design · **SHELL** = inside the shared shell
(sidebar, header, breadcrumbs, palette via the scoped theme bridge in `index.css`),
page body not yet redesigned · **LINKED** = reachable from the new sidebar, still
old design · **OUT** = not part of the staff/admin app (public, resident room
screen, family portal).

**Update (stage 1b, owner correction 2026-10-14):** owners/admins now land on
`/operations` after sign-in; the whole `/admin` command centre (all 41 tabs),
`/admin/help`, `/admin/install`, `/admin/blueprint` and `/aria` render inside the
shared shell (status SHELL); the old top bar and its Blueprint button are gone;
Blueprint lives in Settings > Documents (`/documents`, NEW).

## Pages (routes)

| Route | Who | Status | Next stage |
|---|---|---|---|
| `/operations` workspace | owner, admin | NEW | — |
| `/residents` | owner, admin | NEW (list); resident hub + add/edit dialogs still old style | Stage 2: resident hub and resident form dialogs |
| `/admin` command centre (41 tabs, below) | owner, admin | SHELL | per stage below; kept as "Classic command centre" until every tab is migrated |
| `/staff` live board | all staff | LINKED (Dashboard ▸ Live board) | Stage 6 (staff surfaces) |
| `/workspace` department workspace, Work-as target | staff; admin via Work-as | LINKED (Staff ▸ Department workspace; Work-as in header) | Stage 6 |
| `/alerts` | all staff | LINKED (Dashboard ▸ Alerts screen) | Stage 3 |
| `/front-desk` | owner, admin, front desk | LINKED (Staff ▸ Front desk) | Stage 6 |
| `/admin/blueprint` | owner | SHELL (Settings ▸ Documents ▸ Interactive blueprint) | Stage 7 |
| `/documents` | owner, admin (owner-only entries for owner) | NEW | — |
| `/admin/install`, `/admin/install/:kioskId` | owner, admin | SHELL (Devices ▸ Install a room screen) | Stage 5 |
| `/admin/help` | owner, admin | SHELL (Settings ▸ Tutorials) | Stage 7 |
| `/aria` voice | owner | SHELL (Ask Aria ▸ Talk to Aria) | Stage 7 |
| `/`, `/experience`, `/for-communities`, `/for-residents`, `/login`, `/admin-login` | public | OUT | separate public-site decision |
| `/kiosk/:kioskId` room screen, `/family/:token` | resident / family | OUT | not staff UI; own design rules (low-intimidation, senior UX) |

## Command-centre tabs → new sidebar → migration stage

| Sidebar | Tabs (`/admin?tab=`) | Stage |
|---|---|---|
| Dashboard | overview, live-operations, alerts, routing-exceptions | 3 |
| Residents | residents (**NEW at /residents**), clinician, family, meds | 2 |
| Staff | staff (Users & access) | 6 |
| Tasks | tasks, requests | 3 |
| Schedules | schedule, menu, transport-calendar, transport-log, transport-resources | 4 |
| Departments | departments, nursing, maintenance, housekeeping, kitchen, therapy, activities, transportation | 4 |
| Reports | reports, activity, insights, audit | 5 |
| Devices | devices, rf, wearables, kiosks, tokens, hardware, phones, zones, map | 5 |
| Settings | facilities (owner), communications, escalation, roadmap | 7 |
| Ask Aria | Admin Aria panel (`/admin-assistant/chat`) + owner voice `/aria` | done (reuses existing) |

## Stages (one bounded PR each)

1. **Done in this PR** — shared shell (sidebar with submenus, active page, breadcrumbs,
   mobile menu, Work-as, account menu, Ask Aria under Settings); dashboard drag fix;
   Residents list page.
2. Residents follow-up — resident hub dialog (overview, conversations, assistance
   events, requests, memory, movement, device), resident form, clinician, family,
   medications.
3. Operations — overview, alerts, routing exceptions, tasks, resident requests,
   live operations/simulator panels.
4. Departments and schedules — department queues, maintenance workspace, schedule,
   menu, transportation (calendar, log, resources).
5. Devices and reports — devices, pendants, wearables, kiosks, tokens, hardware,
   phones, zones, map, install wizard; reports, activity, insights, audit.
6. Staff surfaces — users & access, `/staff` live board, `/workspace`,
   `/front-desk` (staff-role shell: only the destinations their role may open).
7. Settings and owner tools — facilities, communications, escalation, roadmap,
   blueprint, tutorials, voice Aria.

## Findings recorded while migrating

- Resident hub "Resident requests" introduces scheduled simulator routines as
  "Things this resident … asked staff to do" — the #153 mix-up in another place;
  fix in Stage 2 using `routes/task_origin.py`.
- Admin used to strip `?tab=` from the URL (reload/Back/shared links lost the
  section) — fixed in this PR (tab kept in the URL).
- Dashboard: cards could not be dragged by most mouse grabs (16 px handle, drop
  lost over gaps) and a change made <0.6 s before leaving the page was not saved —
  fixed in this PR.

# Dot Aria → CAOSCare bounded channel

**State:** implemented and tested with synthetic fixtures; default off; not installed in Home Assistant; no credential generated; no live CAOSCare profile selected.

This is one integration with two layers. The reusable CAOSCare HTTP layer owns authentication, one-profile authorization, filtering, routing, deduplication and receipts. The first adapter is six Home Assistant scripts, because Dot Aria already has an owner-approved Home Assistant MCP connection. A future direct MCP adapter can call the same HTTP contracts; it must not create a second business-logic path.

It does not change or restart the wake listener, Playwright browser relay, call Start/retry logic, EMEET routing, or `input_button.end_call`. The existing `caoscare-dot-export.service` remains owned by the `caoscare-1` account and is not duplicated.

## Six tools and exact results

| Home Assistant entity | HTTP contract | Inputs | Evidence returned |
|---|---|---|---|
| `script.caoscare_get_my_profile` | `GET /api/dot-aria/profile` | none | Only the server-configured approved profile: ID, name, preferred name and room. No search. |
| `script.caoscare_get_departments` | `GET /api/dot-aria/departments` | none | Active department labels and stable routing slugs. |
| `script.caoscare_get_menu` | `POST /api/dot-aria/menu` | optional ISO date; optional breakfast/lunch/dinner | Staff-approved menu rows only. Drafts are filtered by CAOSCare. |
| `script.caoscare_get_schedule` | `POST /api/dot-aria/schedule` | optional ISO date | Published resident-facing activities/community services only. Draft and staff-only rows are filtered. |
| `script.caoscare_make_request` | `POST /api/dot-aria/requests` | stable operation ID, department slug, concrete summary, priority | `accepted`, `outcome`, exact `request_id`/`task_id`, `receipt_id`, lifecycle status, duplicate/replay flags and delivery evidence. Acceptance never claims service started or completed. |
| `script.caoscare_check_request_status` | `POST /api/dot-aria/requests/status` | exact returned `request_id` | Resident-safe state for that same request, open or closed, or `found:false`. |

Every Home Assistant response has `transport_ok`, `http_status`, and CAOSCare's response body. The adapter has a 10-second timeout. A transport error or timeout becomes `transport_ok:false` with an unavailable result. Home Assistant accepting a script action is therefore not used as proof of a CAOSCare read or write.

## Authorization and privacy boundary

The route is disabled unless the CAOSCare backend has all four settings:

```text
CAOSCARE_DOT_ARIA_TOKEN_SHA256=<SHA-256 of a dedicated random channel token>
CAOSCARE_DOT_ARIA_OWNER_USER_ID=<Michael's existing owner user_id>
CAOSCARE_DOT_ARIA_PROFILE_RESIDENT_ID=<one owner-approved test resident_id>
CAOSCARE_DOT_ARIA_ALLOWED_HOSTS=192.168.122.137
```

CAOSCare verifies the exact Home Assistant VM source IP, bearer-token hash, existing owner role and exact configured Room 214 profile on every request. Tool inputs contain no name, room or resident ID. A spoken claim cannot choose or change the profile. Tests use synthetic Room 214 data only; activation binds to Michael's specifically approved development/test profile.

`caoscare_make_request` also requires a stable operation ID. Home Assistant reuses that ID only for a transport retry of the same tool invocation. The backend atomically returns the original task, receipt, lifecycle and delivery result without another task, repeat count or notification. A changed payload with the same ID is rejected; a genuine repeat ask uses a new ID and follows the existing re-request policy.

The raw token belongs only in Home Assistant `secrets.yaml` as `caoscare_dot_aria_authorization: "Bearer …"`. CAOSCare stores only its SHA-256 hash. This service credential is not an owner JWT and routes only under `/api/dot-aria/*`. Code-level routing does not narrow Home Assistant's own MCP OAuth grant; only the six script entities must be exposed to Assist.

Returned profile details, menus, services and request state can pass from Home Assistant to the connected assistant. That is the privacy expansion Michael must review before activation. Administrative configuration, clinical data, arbitrary resident browsing, staff-private notes, task assignment/completion, emergency judgment, credentials and raw receipt records are absent.

## Request semantics

`caoscare_make_request` reuses the canonical resident-request bus. A new request creates one staff task plus an origin receipt. A repeated delivery for the same open issue updates the existing task and produces a different receipt rather than adding queue clutter. Its `request_id` is stable. The exact-ID status tool can retrieve that same task after it closes.

`accepted:true` means CAOSCare persisted or safely deduplicated the request. `delivery` reports notification evidence separately, limited to state, label, reached and attempt count; staff email addresses and notification routes do not leave this channel. Neither means a worker arrived, started or completed the service. Arya must speak the returned state.

The canonical request bus retains its existing string-valued `delivery` field for existing clients, adding `delivery_evidence` for this adapter. The old frontend's repeat-request phrase ("I've let them know again") is not reused: the channel returns notification evidence for this operation instead.

A timeout after the operation result is durably committed can recover the exact original result by retrying the same operation ID. An in-progress or failed/uncertain operation remains blocked rather than repeating a potentially completed write. This is fail-closed duplicate prevention, not proof of automatic recovery from a server crash between task creation and result commit.

## Package contents

- `caoscare_dot_aria_package.yaml.example` — six REST commands and six response-returning scripts; review-only.
- `caoscare-dot-aria.env.example` — variable names only; no values or secret.
- `health_check.sh` — read-only authenticated checks; prompts without echo and never writes.
- `START_HERE.md` — activation, supervised acceptance, rollback and resume checkpoint.

## Voice path is separate

The current owner-selected target is regular ChatGPT Voice. Its natural goodbye and same-tab post-call cleanup are separate from this channel. Earlier Home Assistant hang-up failures included confirmed assistant invocations followed by connector errors; absence of a helper receipt alone does not establish that the assistant failed to invoke a tool. Do not replay old End events. This channel does not alter wake detection, add a microphone listener, or trigger from background speech.

## October 20 connection preparation

The recovered original six-tool channel is imported into `/home/caoscare-1/CAOSCARE-DOT-ARIA-CONNECT`, branch `feature/dot-aria-caoscare-connect`, from the original Michael-owned local commit `a33bf22`. The original checkout remains intact. This branch adds server-bound Room 214 validation on every route, atomic same-operation replay protection and safe delivery evidence.

Focused canonical gate on October 20: **30 passed, 1,505 deselected, one deprecation warning, 13.14 seconds**, using scratch database `caoscare_dot_aria_connect_gate5`, port 8074, stubbed channel notifications. These are isolated tests, not live request acceptance or a full-suite pass.

Read-only runtime checks: existing Care app health HTTP 200; its channel capabilities path HTTP 404 (not loaded). Home Assistant 2026.10.2 has MCP loaded but no `rest_command` component and none of these script services. The existing ChatGPT-to-Home-Assistant connector successfully returned light discovery; no device was actuated. The dedicated channel credential hash and exact approved-profile/owner binding are absent. No credential, live config, exposure, service, tunnel or resident record was changed.

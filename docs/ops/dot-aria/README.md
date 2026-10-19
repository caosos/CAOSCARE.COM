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
| `script.caoscare_make_request` | `POST /api/dot-aria/requests` | department slug, concrete summary, priority | `accepted`, `outcome`, exact `request_id`, `receipt_id`, pending state, duplicate flag and delivery evidence. Acceptance never claims service started or completed. |
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

CAOSCare verifies the exact Home Assistant VM source IP, bearer-token hash, existing owner role and exact configured profile on every request. Tool inputs contain no name, room or resident ID. A spoken claim cannot choose or change the profile. Tests use synthetic residents only; activation must bind to Michael's specifically approved test profile.

The raw token belongs only in Home Assistant `secrets.yaml` as `caoscare_dot_aria_authorization: "Bearer …"`. CAOSCare stores only its SHA-256 hash. This service credential is not an owner JWT and routes only under `/api/dot-aria/*`. Code-level routing does not narrow Home Assistant's own MCP OAuth grant; only the six script entities must be exposed to Assist.

Returned profile details, menus, services and request state can pass from Home Assistant to the connected assistant. That is the privacy expansion Michael must review before activation. Administrative configuration, clinical data, arbitrary resident browsing, staff-private notes, task assignment/completion, emergency judgment, credentials and raw receipt records are absent.

## Request semantics

`caoscare_make_request` reuses the canonical resident-request bus. A new request creates one staff task plus an origin receipt. A repeated delivery for the same open issue updates the existing task and produces a different receipt rather than adding queue clutter. Its `request_id` is stable. The exact-ID status tool can retrieve that same task after it closes.

`accepted:true` means CAOSCare persisted or safely deduplicated the request. `delivery` reports notification evidence separately. Neither means a worker arrived, started or completed the service. Arya must speak the returned state.

## Package contents

- `caoscare_dot_aria_package.yaml.example` — six REST commands and six response-returning scripts; review-only.
- `caoscare-dot-aria.env.example` — variable names only; no values or secret.
- `health_check.sh` — read-only authenticated checks; prompts without echo and never writes.
- `START_HERE.md` — activation, supervised acceptance, rollback and resume checkpoint.

## Existing hang-up observation

The local Hang-up helper has succeeded in supervised calls. In some calls Arya speaks a goodbye but does not invoke the exposed tool. With no Home Assistant input event or local receipt, that is an assistant tool-selection/delivery miss, not evidence that the helper failed. This CAOSCare channel does not alter wake detection, add another microphone listener, or trigger from background speech.

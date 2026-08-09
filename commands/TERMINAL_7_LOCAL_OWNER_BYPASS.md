# Terminal 7 — Local Owner Bypass for EliteDesk Development

## Goal

Minimize login friction on the local EliteDesk CAOSCare build while preserving normal authentication on public deployments such as `caoscare.com`.

Michael is the owner/operator of this local development node. The local build should allow him to open owner/admin-only pages such as `/admin` and `/aria` without repeatedly entering credentials.

## Required behavior

Implement a **local-development-only owner bypass** with these constraints:

1. Add an explicit environment flag, for example:
   - `CAOSCARE_LOCAL_OWNER_BYPASS=true`
2. The bypass must be **disabled by default**.
3. It may only activate when the request/frontend host is clearly local or LAN development, such as:
   - `localhost`
   - `127.0.0.1`
   - the EliteDesk LAN host `192.168.1.151`
4. It must never activate on `caoscare.com`, `www.caoscare.com`, or any other public hostname.
5. When active, resolve Michael's existing owner account from the database and authenticate him as that existing `role=owner` user. Do not create a second owner account.
6. Owner/admin route guards should transparently treat the local session as authenticated.
7. Normal password and Google sign-in paths must remain intact for production/public use.
8. Do not weaken API authorization globally. The bypass should be explicit, bounded, and easy to remove later.
9. Add a visible small development-only indicator such as `LOCAL OWNER MODE` in the admin/Aria UI so it is obvious when bypass mode is active.
10. Do not commit secrets or `.env` values.

## Current known auth architecture

- `frontend/src/pages/AdminLogin.jsx` renders password login plus `GoogleSignIn portal="admin"`.
- `frontend/src/components/GoogleSignIn.jsx` requires `REACT_APP_GOOGLE_CLIENT_ID` or the Google button is hidden.
- `backend/routes/auth.py` supports `/auth/google/verify` and allowlists administrator Google accounts through `GOOGLE_ADMIN_EMAILS`.
- Michael already has one owner account in MongoDB.
- Google sign-in is not currently configured on the EliteDesk local environment.

## Also investigate the visual mismatch

Michael observed that the local EliteDesk site and public `caoscare.com` look different. Determine exactly why by comparing:

- the current local git commit;
- current `origin/main`;
- the version/build actually deployed to `caoscare.com`;
- frontend build/deployment configuration;
- whether the public site is stale, built from another commit/branch, or hosted from a different deployment source.

Do not change the public site yet unless the cause is conclusively identified and the existing deployment path is understood.

## Verification

Before declaring complete, verify:

- Opening `http://localhost:3000/aria` on the EliteDesk reaches Aria without a login prompt when bypass is enabled.
- Opening `http://localhost:3000/admin` reaches the owner/admin interface as Michael's existing owner account.
- `/api/auth/me` or the equivalent current-user path returns Michael with `role=owner` under the local bypass.
- Setting the bypass flag false restores normal authentication.
- Requests whose host is `caoscare.com` cannot use the bypass.
- Existing password login still works.

## Google sign-in follow-up

After the local bypass works, document the exact remaining steps to make Michael's Google account the permanent owner/admin login for both local and public deployments. Do not block the immediate local workflow on Google OAuth.

## Handoff

Update `docs/CURRENT_NODE_STATUS.md` with what was implemented and the exact reason for the local/public visual mismatch if determined. Commit and push completed code and documentation to `origin/main` once tests pass and no secrets are included.

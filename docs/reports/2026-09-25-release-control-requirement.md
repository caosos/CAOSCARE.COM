# Release control requirement — no unreviewed changes ride along a deploy

Status: **OPEN requirement, not implemented** (2026-09-25). The deploy
system is unchanged; do not change it without Michael's approval.

## What happened (evidence)

Michael authorised one bounded change: robots.txt, sitemap.xml, canonical
link and title (`348d164`). `scripts/deploy_caoscare.sh 348d164` deployed
it, but production was still on `7bad624` (2026-09-19). Because the script
deploys a `main` SHA, **everything merged to main since the last deploy
shipped with it**:

```
348d164 Search indexing: robots.txt, sitemap.xml, canonical + title   <- authorised
fb216d4 Lane 4: front-desk requests reuse create_resident_request's dedup
c0668e5 Lane 3: wire DepartmentWorkspaceDialog to existing task actions
1179a62 Lane 2: Tasks "Today" actually filters to today
9b2f1c4 Lane 1: age-bound current-state alert counters
e092e36 Add real inbound-email adapter (Resend) for menu/activities ingestion
1f44536, 85c2c52, ec7b3c5, 95bb5e4  (documentation)
36 files changed, +2301 / -260 (7bad624..348d164)
```

Deploy result: success, health verified by the script; backup
`/opt/caoscare/backups/mongo/20260926-020924-pre-deploy-7bad62440aa5`;
code rollback `./scripts/deploy_caoscare.sh 7bad62440aa5c0694ffd301a1756904160b98bd8`
(not executed — Michael: do not roll back).

Root cause: nothing in the process compared the requested change with the
full production→target diff. `main` ≠ production is normal here (work is
merged and deployed later), so any deploy can carry unreviewed work.

## Requirement

Before any production deployment, the process must show:

1. current production SHA (read from the server, not assumed);
2. proposed deployment SHA;
3. the commit range `production..proposed` and a diff summary (files, +/-);
4. whether the requested change is the entire diff;
5. every additional merged-but-not-deployed commit that would ship.

If anything beyond the requested change would ship: **STOP BEFORE
DEPLOYMENT** and require explicit approval of the full range (or deploy a
narrower target, e.g. a release branch containing only the approved change).

## Notes for whoever implements it (later, with approval)

- Natural home: a pre-flight step in `scripts/deploy_caoscare.sh` (it already
  verifies the target is on `origin/main` and records the previous SHA) that
  prints items 1-5 and refuses without an explicit acknowledgement flag
  naming the approved range.
- Agents must report items 1-5 to Michael before asking for deploy approval,
  even before the script enforces it.
- A deploy that ships only the approved change when main is ahead needs a
  release branch/tag strategy; that is a separate design decision.

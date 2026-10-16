# Living-community direct Mongo acceptance

This operator tool closes the simulator's direct-database evidence gap without
touching a shared community by default. It has no route, startup hook,
deployment action, provider call, or automatic cleanup.

## Safe default: read-only

From `backend/`, with the normal trusted environment loaded:

```bash
python scripts/check_community_mongo_acceptance.py
```

The default command performs only:

1. MongoDB `hello`, classified as `standalone`, `replica_set`, or `sharded`;
2. a real transactional read of a sentinel that is always aborted.

The tool never prints `MONGO_URL`, credentials, or raw connection errors. A
standalone server is expected to fail the transaction gate and must not be used
for living-community mutation controls.

To probe a named database without changing it:

```bash
python scripts/check_community_mongo_acceptance.py --database caoscare
```

## Explicit isolated scratch acceptance

Choose a brand-new disposable database. Its name must match
`caoscare_sim_acceptance_<8-32 lowercase letters/digits>`. The tool refuses the
configured production database, common production names, a non-empty scratch
database, or a command missing either confirmation or actor provenance.

```bash
python scripts/check_community_mongo_acceptance.py \
  --scratch-db caoscare_sim_acceptance_20261013a \
  --production-db caoscare \
  --confirm-scratch-mutations \
  --operator-id user:michael \
  --operator-name Michael
```

The acceptance run uses that scratch database only. It prepares the required
indexes with receipts, creates a paused burn-in run, provisions ten synthetic
residents atomically, resumes, executes one canonical event, pauses, reopens a
fresh database client, reloads persisted state, resumes, executes a second
canonical event, stops, and runs the exact scoped reset. The reset deletes the
scratch run/residents/tasks/notifications and preserves receipts as evidence.

Every mutation goes through an existing receipt-backed simulator service. The
output contains database name, topology classification, run/event IDs, receipt
IDs and post-reset counts only. It does not prove an EliteDesk service restart,
browser behavior, or production readiness; those remain separate gates.

If an attempt fails after creating anything, do not reuse that database name.
Keep it for evidence and choose a new unique scratch database for the next run.
Database deletion is intentionally outside this tool.

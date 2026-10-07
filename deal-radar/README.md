# Deal Radar

Local-first repair-arbitrage opportunity engine for Michael.

**Current status:** bootstrap.

Read [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md) before changing anything.

## Development rule

Deal Radar is isolated from CAOSCare runtime. Do not import CAOSCare code or modify CAOSCare services from this project.

## First run target

The first useful build must ingest real listings, calculate Conway travel and full landed cost, preserve evidence, and return BUY / WATCH / PASS with a reconstructable valuation receipt.

## Project paths

- `backend/deal_radar/` — Python package
- `frontend/` — operator UI after backend is useful
- `tests/` — deterministic tests
- `fixtures/` — captured listing/source fixtures
- `docs/` — source/access and operator documentation
- `deploy/` — systemd/runtime packaging
- `scripts/` — local operator scripts

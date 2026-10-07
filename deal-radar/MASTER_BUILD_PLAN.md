# Deal Radar — Master Build Plan

**Status:** ACTIVE PRIORITY  
**Date:** 2026-10-06  
**Owner:** Michael  
**Bootstrap branch:** `deal-radar/bootstrap-2026-10-06`

## Priority reset

Until Michael changes this directive, all discretionary project attention is focused on Deal Radar.

CAOSCare runtime work is paused. Do not deploy, merge, or start unrelated CAOSCare feature work from this branch.

This branch is only a temporary coordination/bootstrap location because no separate Deal Radar repository exists yet. Keep Deal Radar code and docs isolated under `deal-radar/` so they can be split into a standalone repo later without entangling CAOSCare runtime.

## Mission

Build a local-first system that continuously discovers underpriced, repairable, resellable assets; estimates their true landed cost to Conway, Arkansas; estimates realistic local resale value; calculates downside/risk; and surfaces only actionable deals with evidence.

The system is not a generic shopping scraper. It is a **repair-arbitrage engine** built around Michael's mechanical skills.

## Primary outcome

Michael should be able to open one screen and see ranked opportunities such as:

- BUY — E-Z-GO gas cart — ask $175 — 19 miles — est. $550 profit
- WATCH — Mercury 20 HP — ask $150 — missing compression evidence
- PASS — inverter generator — ask $100 — electronics downside destroys margin

Every recommendation must show the arithmetic and provenance.

## Non-negotiable rules

1. No recommendation without a valuation receipt.
2. No valuation receipt without source provenance.
3. Separate asking prices from verified sold comps.
4. Separate known facts from inferred repair risk.
5. All costs are landed-cost costs:
   purchase + buyer premium + tax + freight/shipping + travel + expected parts + cleanup + disposal + contingency.
6. Distance is not a hard cutoff. Higher-profit deals may justify 100+ mile drives.
7. The system must be configurable for:
   - minimum expected gross profit
   - minimum cash multiple
   - travel cost per mile
   - maximum practical distance
   - category-specific risk
8. Avoid sources/access methods that violate explicit robots/terms/access controls. Prefer official APIs/feeds, public pages, saved-search/email ingestion, or user-operated browser flows.
9. The system must remember listings already seen and detect price/status changes.
10. Never silently turn an unverified machine into a working-machine valuation.

## Initial economic rules

Defaults, configurable:

- Substantial flip target: >= $300 expected gross profit.
- Preferred cash multiple: >= 2.0x total cash invested.
- Small quick-flip exception: allowed when cash exposure is tiny, repair time is short, and resale confidence is high.
- Travel is round-trip and must be included in landed cost.
- Use low / median / high resale estimates, not one magic number.
- A deal can rank highly even at 100+ miles when expected profit and confidence justify travel.

## Architecture

```
Sources
  -> source adapters
  -> raw snapshots
  -> normalizer/deduper
  -> category classifier
  -> comp/valuation engine
  -> repair-risk engine
  -> geo/travel-cost engine
  -> landed-cost calculator
  -> deal scorer
  -> alert engine
  -> dashboard/API
  -> receipts/audit log
```

### MVP stack

- Python 3.12
- FastAPI
- SQLite for MVP, schema compatible with later Postgres
- SQLAlchemy
- Pydantic models
- async source workers
- simple scheduler with per-source cadence
- HTML/API/email adapters behind a common interface
- local dashboard; React optional only after backend proves useful
- systemd service on Michael's Linux machine
- structured JSON logs
- pytest fixtures with captured listing snapshots

## Core entities

### Listing
- listing_id
- source
- source_listing_id
- canonical_url
- title
- description
- asking_price
- location_text
- lat/lon if known
- seller/type metadata where public
- category
- condition claims
- fetched_at
- first_seen_at
- last_seen_at
- raw_snapshot_hash
- status

### Comp
- source
- URL
- sold_or_ask
- price
- date
- item/model/category
- location
- condition
- confidence

### ValuationReceipt
- listing_id
- model/category
- comp_ids
- resale_low
- resale_median
- resale_high
- purchase_cost
- premiums
- taxes
- travel_cost
- shipping
- repair_low/median/high
- cleanup
- contingency
- landed_cost
- profit_low/median/high
- cash_multiple
- confidence
- reasons
- created_at
- valuation_version

### DealDecision
- BUY / WATCH / PASS
- score
- blockers
- questions_to_ask_seller
- max_offer
- max_bid
- max_distance_at_current_profit
- receipt_id

## Source tiers

### Tier A — automate first
Public/official/structured sources where collection is stable:
- GovDeals
- Public Surplus
- HiBid public catalogs
- Purple Wave
- Craigslist/public classifieds where permitted
- municipal/state surplus pages
- auctioneer public catalogs

### Tier B — automate through permitted account/email mechanisms
- storage auction platforms
- Copart/IAA watchlists/search alerts
- retailer liquidation portals
- estate-sale alerts
- saved searches delivered by email

### Tier C — assisted/manual ingestion
- Facebook Marketplace where automated access is restricted/unreliable
- screenshots
- pasted listing URLs
- seller messages
- photos/model tags

Tier C must still run through the same valuation/scoring pipeline.

## Category priority

### Highest priority
- golf carts / utility carts
- outboards
- generators and welders
- commercial pressure washers
- air compressors
- contractor equipment
- trailers
- commercial cleaning equipment
- walk-behind / zero-turn / specialty lawn equipment
- shop equipment
- selected mobility equipment
- selected vehicles later

### Lower priority / higher caution
- inverter electronics-heavy equipment
- proprietary battery systems
- fiberglass boats with hidden structural wood
- anything whose repair depends on unobtainable boards/software
- commodity consumer goods with thin margins

## Dynamic travel policy

Do not use a single radius.

Initial configurable policy:
- < $150 expected profit: local only
- $150-$299: short radius
- $300-$499: moderate radius
- $500-$999: up to ~100 miles one way may be justified
- $1,000+: wider radius can be rational if confidence is high

Final decision uses:
```
travel_cost = round_trip_miles * configured_cost_per_mile
net_profit = expected_sale - all_other_costs - travel_cost
```

The dashboard should show both fuel-only and full-vehicle-cost scenarios.

## Parallel agent lanes

All lanes may work simultaneously because ownership boundaries are explicit.

### DR-01 Core schema + persistence
Own: `deal-radar/backend/models/`, `deal-radar/backend/db/`
Deliver: Listing, Comp, ValuationReceipt, DealDecision, SourceRun, immutable raw snapshot metadata.

### DR-02 Source registry + adapter contract
Own: `deal-radar/backend/sources/base.py`, `source_registry.py`
Deliver: adapter interface, cadence, auth mode, source capability matrix, rate/backoff contract.

### DR-03 Government/surplus collectors
Own: `deal-radar/backend/sources/gov/`
Start: GovDeals, Public Surplus, Arkansas/local public auction sources.

### DR-04 Auction/storage collectors
Own: `deal-radar/backend/sources/auctions/`
Start: HiBid, Purple Wave, public storage-auction catalogs where permitted.

### DR-05 Classified/manual ingestion
Own: `deal-radar/backend/sources/classifieds/`, import endpoint
Start: public classifieds; URL/text/screenshot/manual listing intake contract for restricted sources.

### DR-06 Deduplication + normalization
Own: `deal-radar/backend/normalize/`
Deliver: canonical listing shape, duplicate fingerprinting, price/status change detection.

### DR-07 Valuation/comp engine
Own: `deal-radar/backend/valuation/`
Deliver: sold-vs-ask separation, low/median/high resale estimates, comp confidence, versioned receipts.

### DR-08 Repair-risk engine
Own: `deal-radar/backend/repair/`
Deliver: category-specific failure modes, parts exposure, skill-adjusted repair estimates, seller-question generator.

### DR-09 Geo/travel/landed-cost engine
Own: `deal-radar/backend/geo/`, `costs/`
Deliver: distance, round-trip travel cost, dynamic profitable-radius calculation, freight/manual cost fields.

### DR-10 Ranking + alert engine
Own: `deal-radar/backend/scoring/`, `alerts/`
Deliver: BUY/WATCH/PASS, max offer/bid, confidence, thresholds, alert suppression/dedup.

### DR-11 API/dashboard
Own: `deal-radar/backend/api/`, `deal-radar/frontend/`
Deliver: ranked feed, listing detail, receipt view, filters, source/status controls.

### DR-12 Runtime/deployment/watchdog
Own: `deal-radar/deploy/`, `scripts/`
Deliver: systemd units, scheduler lifecycle, health endpoint, restart policy, logs, backup/export.

### DR-13 Test/simulator/fixtures
Own: `deal-radar/tests/`, `fixtures/`
Deliver: captured listing fixtures, duplicate tests, price-change tests, valuation arithmetic, failure/retry simulation.

### DR-14 Source-policy/access audit
Own: `deal-radar/docs/SOURCE_ACCESS_MATRIX.md`
Deliver: for each source: public/API/email/login/browser/manual, automation allowed/unknown/restricted, cadence, attribution requirements.

## Interface contracts

Source adapter returns:
```python
SourceResult(
    source=...,
    source_listing_id=...,
    canonical_url=...,
    fetched_at=...,
    raw=...,
    parsed={...},
)
```

Normalizer outputs one canonical Listing.

Valuation engine cannot fetch source pages directly. It consumes Listing + Comp records.

Scoring engine cannot invent repair costs. It consumes a repair estimate with confidence.

Every BUY/WATCH/PASS must point to one ValuationReceipt.

## MVP acceptance

MVP is real when all are true:

1. At least 4 source adapters ingest real current listings.
2. Manual listing import works for restricted/non-automated sources.
3. Duplicate listings are collapsed.
4. Price changes are detected.
5. Conway distance and round-trip travel cost are calculated.
6. Every candidate has landed-cost arithmetic.
7. At least 5 priority categories have repair-risk rules.
8. Valuation distinguishes sold comps from asking comps.
9. Dashboard ranks BUY/WATCH/PASS.
10. Alert fires only once per material listing state unless price/score changes.
11. Service survives reboot.
12. Every decision can be reconstructed from stored evidence.

## Phase order

### Phase 0 — today
- persist plan/contracts
- create parallel work issues
- scaffold isolated project tree
- no unrelated CAOSCare work

### Phase 1 — spine
DR-01, 02, 06, 09, 10, 13 in parallel.

### Phase 2 — first live sources
DR-03, 04, 05 in parallel against the adapter contract.

### Phase 3 — intelligence
DR-07 and DR-08 using real ingested listings and stored comps.

### Phase 4 — operator surface
DR-11; show evidence before polish.

### Phase 5 — unattended operation
DR-12; systemd, scheduler, alerts, health, recovery.

## Coordinator rule

Agents do not edit outside their owned paths unless the coordinator explicitly approves it.

Cross-lane changes are proposed as interface changes, not silently implemented.

No agent may claim success solely from its own output. Tests and receipts are required.

## Immediate next action

Create the lane issues from this plan, then scaffold the project tree and interfaces so multiple coding agents can begin independently.

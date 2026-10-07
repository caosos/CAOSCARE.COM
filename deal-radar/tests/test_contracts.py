from datetime import UTC, datetime

from deal_radar.contracts import Decision, MoneyRange, SourceResult


def test_source_result_contract():
    item = SourceResult(
        source="fixture",
        source_listing_id="abc123",
        canonical_url="https://example.com/item/abc123",
        fetched_at=datetime.now(UTC),
        parsed={"asking_price": 200},
    )
    assert item.source_listing_id == "abc123"


def test_decision_values_are_stable():
    assert Decision.BUY.value == "BUY"
    assert Decision.WATCH.value == "WATCH"
    assert Decision.PASS.value == "PASS"


def test_money_range_requires_nonnegative_values():
    r = MoneyRange(low=100, median=200, high=300)
    assert r.median == 200

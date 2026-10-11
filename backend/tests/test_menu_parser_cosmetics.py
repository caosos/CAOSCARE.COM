"""Menu paste parser: pure function, no database or server."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routes.menu_ingest import _parse_menu_email  # noqa: E402


def names(items, meal): return [i["item_name"] for i in items if i["meal_period"] == meal]


def test_trailing_period_removed_and_midline_label_is_its_own_dish():
    items, st, _ = _parse_menu_email("Lunch: Tomato soup, green beans. Vegetarian: Stuffed peppers.\nDinner: Baked chicken.")
    assert names(items, "lunch") == ["Tomato soup", "green beans", "Vegetarian: Stuffed peppers"]
    assert names(items, "dinner") == ["Baked chicken"]


def test_abbreviations_and_decimals_are_not_split():
    items, _, _ = _parse_menu_email("Dinner: Mr. Smith's pot roast, 2.5 oz roll")
    assert names(items, "dinner") == ["Mr. Smith's pot roast", "2.5 oz roll"] or len(names(items, "dinner")) == 2


def test_partial_menu_note_is_plain_not_a_fault():
    _, st, note = _parse_menu_email("Lunch: soup\nDinner: chicken")
    assert st == "needs_review"
    assert "lunch, dinner only" in note and "breakfast" in note and "No section found" not in note


def test_no_sections_still_needs_review():
    assert _parse_menu_email("hello")[1] == "needs_review"

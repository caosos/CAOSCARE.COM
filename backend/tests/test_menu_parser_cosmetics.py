"""Parser cosmetics for _parse_menu_email (docs/reports/2026-10-08-lane-d-f-browser-acceptance.md item 3)."""
from routes.menu_ingest import _parse_menu_email


def _names(items, meal):
    return [i["item_name"] for i in items if i["meal_period"] == meal]


def test_menu_parser_cosmetics_1_trailing_period():
    items, status, notes = _parse_menu_email("Lunch: soup, grilled cheese.\nDinner: baked chicken, green beans.")
    assert _names(items, "lunch") == ["soup", "grilled cheese"]
    assert _names(items, "dinner") == ["baked chicken", "green beans"]
    assert status == "parsed" and notes is None


def test_menu_parser_cosmetics_2_vegetarian_separator():
    items, _, _ = _parse_menu_email("Dinner: baked chicken, green beans. Vegetarian: Stuffed peppers.")
    assert _names(items, "dinner") == ["baked chicken", "green beans", "Stuffed peppers"]
    veg = [i for i in items if i["item_name"] == "Stuffed peppers"][0]
    assert veg["description"] == "Vegetarian"
    assert not any(i.get("description") for i in items if i["item_name"] != "Stuffed peppers")


def test_menu_parser_cosmetics_3_no_warning_for_absent_breakfast():
    items, status, notes = _parse_menu_email("Lunch: soup\nDinner: chicken")
    assert status == "parsed" and notes is None
    assert _names(items, "lunch") == ["soup"] and _names(items, "dinner") == ["chicken"]

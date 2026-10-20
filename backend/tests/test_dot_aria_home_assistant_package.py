"""Static contract checks for the review-only Home Assistant package."""
from pathlib import Path
import re


PACKAGE = Path(__file__).parents[2] / "docs/ops/dot-aria/caoscare_dot_aria_package.yaml.example"
TEXT = PACKAGE.read_text()


def _top_level_keys(section: str) -> list[str]:
    body = TEXT.split(f"{section}:\n", 1)[1]
    if section == "rest_command":
        body = body.split("\nscript:\n", 1)[0]
    return re.findall(r"^  ([a-z0-9_]+):$", body, flags=re.MULTILINE)


def test_package_exposes_exactly_six_bounded_scripts_and_six_rest_commands():
    assert _top_level_keys("rest_command") == [
        "caoscare_dot_aria_profile", "caoscare_dot_aria_departments", "caoscare_dot_aria_menu",
        "caoscare_dot_aria_schedule", "caoscare_dot_aria_request", "caoscare_dot_aria_request_status",
    ]
    assert _top_level_keys("script") == [
        "caoscare_get_my_profile", "caoscare_get_departments", "caoscare_get_menu",
        "caoscare_get_schedule", "caoscare_make_request", "caoscare_check_request_status",
    ]


def test_package_has_bounded_timeouts_and_explicit_transport_failure_results():
    assert TEXT.count("timeout: 10") == 6
    assert TEXT.count("continue_on_error: true") == 6
    assert len(re.findall(r"^\s+transport_ok:", TEXT, flags=re.MULTILINE)) == 6
    assert TEXT.count("CAOSCare unavailable or timed out") == 6
    assert TEXT.count("http_status:") == 6


def test_package_uses_secret_reference_and_cannot_target_spoken_person_or_room():
    assert TEXT.count("!secret caoscare_dot_aria_authorization") == 6
    assert "person_or_room" not in TEXT
    assert "resident_id" not in TEXT
    assert "Bearer " not in TEXT
    assert '{"request_id": request_id}' in TEXT
    assert '"operation_id": operation_id' in TEXT
    assert 'operation_id: "{{ operation_id }}"' in TEXT

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


def test_package_preserves_six_tools_and_adds_one_read_only_lookup():
    assert _top_level_keys("rest_command") == [
        "caoscare_dot_aria_profile", "caoscare_dot_aria_departments", "caoscare_dot_aria_menu",
        "caoscare_dot_aria_schedule", "caoscare_dot_aria_request", "caoscare_dot_aria_request_status",
        "caoscare_dot_aria_find_requests",
    ]
    assert _top_level_keys("script") == [
        "caoscare_get_my_profile", "caoscare_get_departments", "caoscare_get_menu",
        "caoscare_get_schedule", "caoscare_make_request", "caoscare_check_request_status",
        "caoscare_find_my_requests",
    ]


def test_package_has_bounded_timeouts_and_explicit_transport_failure_results():
    assert TEXT.count("timeout: 10") == 7
    assert TEXT.count("continue_on_error: true") == 7
    assert len(re.findall(r"^\s+transport_ok:", TEXT, flags=re.MULTILINE)) == 7
    assert TEXT.count("CAOSCare unavailable or timed out") == 7
    assert TEXT.count("http_status:") == 7


def test_package_uses_secret_reference_and_cannot_target_spoken_person_or_room():
    assert TEXT.count("!secret caoscare_dot_aria_authorization") == 7
    assert "person_or_room" not in TEXT
    assert "resident_id" not in TEXT
    assert "Bearer " not in TEXT
    assert '{"request_id": request_id}' in TEXT
    assert '"operation_id": operation_id' in TEXT
    assert 'operation_id: "{{ operation_id }}"' in TEXT


def test_text_selectors_survive_home_assistant_package_merge():
    # HA 2026.10.2 loaded the two fieldless scripts but stripped text: {}
    # during package processing, disabling the other four at runtime.
    # An explicit supported option keeps each selector mapping nonempty.
    assert not re.search(r"text:\s*\{\s*\}", TEXT)
    assert TEXT.count("selector: {text: {multiline: false}}") == 7
    assert TEXT.count("selector: {text: {multiline: true}}") == 1


def test_find_tool_never_requires_an_id_or_dispatches_the_creation_action():
    script = TEXT.split("\n  caoscare_find_my_requests:\n", 1)[1]
    assert "required: true" not in script
    assert "action: rest_command.caoscare_dot_aria_find_requests\n" in script
    assert "action: rest_command.caoscare_dot_aria_request\n" not in script
    assert "empty result is not proof" in script
    assert "next_offset" in script

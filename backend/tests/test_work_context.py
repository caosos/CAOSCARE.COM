"""Pure tests for the signed owner/admin work-context foundation."""
from datetime import datetime, timedelta, timezone
import os
import sys

import jwt
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation import work_context as wc  # noqa: E402


SECRET = "work-context-test-secret"
DEPARTMENTS = {"administration", "maintenance", "nursing"}
NOW = datetime.now(timezone.utc).replace(microsecond=0)
OWNER = {"user_id": "user_michael", "name": "Michael", "role": "owner", "department": None}


def issued(**overrides):
    args = {"acting_role": "staff", "acting_department": "maintenance",
            "known_departments": DEPARTMENTS, "secret": SECRET, "now": NOW}
    args.update(overrides)
    return wc.issue(OWNER, **args)


def test_signed_context_keeps_principal_separate_from_effective_scope():
    token, context = issued()
    resolved = wc.resolve(token, OWNER, known_departments=DEPARTMENTS, secret=SECRET)
    effective = wc.effective_user(OWNER, resolved)
    receipt = wc.receipt_metadata(OWNER, resolved)

    assert resolved == context
    assert effective["user_id"] == OWNER["user_id"]
    assert effective["role"] == "staff" and effective["department"] == "maintenance"
    assert effective["_principal_role"] == "owner"
    assert receipt["actor_id"] == OWNER["user_id"] and receipt["actor_role"] == "owner"
    assert receipt["acting_role"] == "staff" and receipt["acting_department"] == "maintenance"
    assert receipt["work_context_id"] == context.context_id and receipt["simulated"] is False
    assert OWNER == {"user_id": "user_michael", "name": "Michael", "role": "owner", "department": None}
    assert wc.scoped_authority("acts_for:maintenance", context).endswith(":acts_for:maintenance")


def test_tamper_and_different_principal_fail_closed():
    token, _ = issued()
    head, body, signature = token.split(".")
    tampered = ".".join((head, ("A" if body[0] != "A" else "B") + body[1:], signature))
    with pytest.raises(wc.WorkContextError) as error:
        wc.resolve(tampered, OWNER, known_departments=DEPARTMENTS, secret=SECRET)
    assert error.value.code == "invalid_token"

    other = {**OWNER, "user_id": "user_someone_else"}
    with pytest.raises(wc.WorkContextError) as error:
        wc.resolve(token, other, known_departments=DEPARTMENTS, secret=SECRET)
    assert error.value.code == "principal_mismatch"


def test_expired_token_fails_closed():
    _, context = issued()
    claims = context.claims()
    claims["iat"] = int((NOW - timedelta(hours=2)).timestamp())
    claims["exp"] = int((NOW - timedelta(hours=1)).timestamp())
    expired = jwt.encode(claims, SECRET, algorithm=wc.ALGORITHM)
    with pytest.raises(wc.WorkContextError) as error:
        wc.resolve(expired, OWNER, known_departments=DEPARTMENTS, secret=SECRET)
    assert error.value.code == "expired_context"


def test_unknown_or_forged_role_fails_closed():
    with pytest.raises(wc.WorkContextError) as error:
        issued(acting_role="superuser")
    assert error.value.code == "unknown_role"

    _, context = issued()
    claims = {**context.claims(), "acting_role": "owner"}
    forged = jwt.encode(claims, SECRET, algorithm=wc.ALGORITHM)
    with pytest.raises(wc.WorkContextError) as error:
        wc.resolve(forged, OWNER, known_departments=DEPARTMENTS, secret=SECRET)
    assert error.value.code == "unknown_role"


def test_department_is_revalidated_and_front_desk_is_administration_only():
    token, _ = issued()
    with pytest.raises(wc.WorkContextError) as error:
        wc.resolve(token, OWNER, known_departments={"nursing"}, secret=SECRET)
    assert error.value.code == "unknown_department"

    with pytest.raises(wc.WorkContextError) as error:
        issued(acting_role="front_desk", acting_department="maintenance")
    assert error.value.code == "invalid_scope"

    _, front_desk = issued(acting_role="front_desk", acting_department="administration")
    assert front_desk.acting_role == "front_desk" and front_desk.acting_department == "administration"


def test_only_current_admin_principals_and_short_ttls_are_accepted():
    with pytest.raises(wc.WorkContextError) as error:
        wc.issue({**OWNER, "role": "staff"}, acting_role="staff", acting_department="nursing",
                 known_departments=DEPARTMENTS, secret=SECRET)
    assert error.value.code == "principal_not_admin"

    for ttl in (59, wc.MAX_TTL_SECONDS + 1):
        with pytest.raises(wc.WorkContextError) as error:
            issued(ttl_seconds=ttl)
        assert error.value.code == "invalid_ttl"

    token, _ = issued()
    with pytest.raises(wc.WorkContextError) as error:
        wc.resolve(token, {**OWNER, "role": "admin"}, known_departments=DEPARTMENTS, secret=SECRET)
    assert error.value.code == "principal_mismatch"

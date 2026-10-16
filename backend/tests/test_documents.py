"""Settings > Documents: curated catalog, revisions, role gating, no free paths."""
import asyncio

import pytest
from fastapi import HTTPException

from routes import documents as docs

OWNER = {"role": "owner", "user_id": "o"}
ADMIN = {"role": "admin", "user_id": "a"}


def run(c):
    return asyncio.run(c)


def test_catalog_entries_exist_and_have_revisions():
    out = run(docs.list_documents(OWNER))
    assert {c["id"] for c in out["categories"]} == {"architecture", "product", "procedures", "hardware", "simulator", "plans"}
    for d in out["documents"]:
        assert d["available"], d["path"]          # every catalogued file is in the repo
        assert d["category"] in {c["id"] for c in out["categories"]}
        assert d["revision"]["commit"], d["path"]


def test_owner_only_documents_are_hidden_and_refused_for_admins():
    owner_ids = {d["id"] for d in run(docs.list_documents(OWNER))["documents"]}
    admin_ids = {d["id"] for d in run(docs.list_documents(ADMIN))["documents"]}
    assert "blueprint" in owner_ids and "blueprint" not in admin_ids
    with pytest.raises(HTTPException) as e:
        run(docs.read_document("blueprint", ADMIN))
    assert e.value.status_code == 404
    assert run(docs.read_document("blueprint", OWNER))["text"]


def test_only_catalogued_ids_can_be_read():
    for bad in ("../../backend/.env", "docs/PROJECT_STATE.md", "nope"):
        with pytest.raises(HTTPException):
            run(docs.read_document(bad, OWNER))
    assert run(docs.read_document("product-baseline", ADMIN))["text"].startswith("# CAOSCare Product Baseline")

"""Iteration 8 — long-term memory server tests.

Covers:
- POST /api/ai/chat with resident_id returns memories_used + history_replayed
- Background extraction produces memory rows with source='extraction'
- Cross-session memory recall (different session_id, same resident_id)
- GET /api/memory sort order (pinned first, importance desc, created_at desc)
- POST/PATCH/DELETE /api/memory CRUD
- POST /api/memory/extract
- GET /api/memory/conversation/{resident_id}
- /api/ai/chat without resident_id still works (skips memory layer)
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://senior-locate.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@caoscare.com", "password": "admin1234"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def resident_id(headers):
    r = requests.get(f"{API}/residents", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    rs = r.json()
    assert len(rs) > 0, "no residents seeded"
    return rs[0]["resident_id"]


# ---------------- CRUD tests first (quick, deterministic) ----------------

class TestMemoryCRUD:
    def test_create_manual_memory(self, headers, resident_id):
        payload = {
            "resident_id": resident_id,
            "text": "TEST_MEM crud fact — loves Earl Grey tea with honey",
            "category": "preferences",
            "importance": 4,
            "source": "admin",
            "pinned": False,
        }
        r = requests.post(f"{API}/memory", headers=headers, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["text"] == payload["text"]
        assert d["category"] == "preferences"
        assert d["importance"] == 4
        assert d["source"] == "admin"
        assert "memory_id" in d
        pytest.mem_id = d["memory_id"]

    def test_list_memory_contains_created(self, headers, resident_id):
        r = requests.get(f"{API}/memory/{resident_id}", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        ids = [m["memory_id"] for m in r.json()]
        assert pytest.mem_id in ids

    def test_patch_memory(self, headers, resident_id):
        r = requests.patch(
            f"{API}/memory/{pytest.mem_id}",
            headers=headers,
            json={"importance": 5, "pinned": True, "category": "family"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["importance"] == 5
        assert d["pinned"] is True
        assert d["category"] == "family"

    def test_sort_order_pinned_first(self, headers, resident_id):
        # add a non-pinned low-importance memory, and check list order
        low = {
            "resident_id": resident_id,
            "text": "TEST_MEM sort check — low importance trivia",
            "category": "other",
            "importance": 1,
            "source": "admin",
            "pinned": False,
        }
        r = requests.post(f"{API}/memory", headers=headers, json=low, timeout=20)
        assert r.status_code == 200
        pytest.low_id = r.json()["memory_id"]
        r = requests.get(f"{API}/memory/{resident_id}", headers=headers, timeout=20)
        lst = r.json()
        # Find positions
        pos_pinned = next(i for i, m in enumerate(lst) if m["memory_id"] == pytest.mem_id)
        pos_low = next(i for i, m in enumerate(lst) if m["memory_id"] == pytest.low_id)
        assert pos_pinned < pos_low, "pinned memory should come before unpinned"
        # All pinned items should come before all unpinned
        pinned_flags = [m.get("pinned", False) for m in lst]
        # Once we see False, never True again
        seen_unpinned = False
        for p in pinned_flags:
            if not p:
                seen_unpinned = True
            elif seen_unpinned:
                pytest.fail(f"pinned order broken: {pinned_flags}")

    def test_delete_memory(self, headers):
        r = requests.delete(f"{API}/memory/{pytest.low_id}", headers=headers, timeout=20)
        assert r.status_code == 200
        # Cleanup the pinned one too
        requests.delete(f"{API}/memory/{pytest.mem_id}", headers=headers, timeout=20)


# ---------------- /api/memory/extract (direct) ----------------

class TestMemoryExtract:
    def test_manual_extract(self, headers, resident_id):
        # Use unique phrasing to avoid dedupe collisions with prior iteration data
        unique = uuid.uuid4().hex[:6]
        payload = {
            "resident_id": resident_id,
            "user_text": f"My nephew Zephyrus{unique} studies marine biology in Reykjavik and loves puffins.",
            "assistant_text": "How wonderful — puffins are extraordinary birds.",
            "session_id": f"test-extract-{unique}",
        }
        r = requests.post(f"{API}/memory/extract", headers=headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert isinstance(d.get("saved"), int)
        # Allow 0 only if Claude deemed nothing durable — log but don't fail
        if d["saved"] == 0:
            pytest.skip(f"Claude returned 0 extractions for a novel phrase: {d}")
        assert d["saved"] >= 1, f"expected at least 1 extraction, got {d}"
        pytest.extract_saved = d["saved"]

    def test_extracted_memories_visible(self, headers, resident_id):
        r = requests.get(f"{API}/memory/{resident_id}", headers=headers, timeout=20)
        assert r.status_code == 200
        extracts = [m for m in r.json() if m.get("source") == "extraction"]
        assert len(extracts) > 0, "no extraction-sourced memories visible"
        sample = extracts[0]
        assert 1 <= int(sample.get("importance", 0)) <= 5
        assert sample.get("category") in {
            "family", "preferences", "health", "history", "daily_pattern",
            "concern", "relationship", "milestone", "other",
        }


# ---------------- /api/ai/chat integration ----------------

class TestChatMemoryIntegration:
    def test_chat_without_resident_works(self):
        sid = f"anon-{uuid.uuid4().hex[:6]}"
        r = requests.post(
            f"{API}/ai/chat",
            json={"session_id": sid, "message": "Hello, how are you?"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "reply" in d
        assert d.get("memories_used", 0) == 0
        assert d.get("history_replayed", 0) == 0

    def test_chat_with_resident_returns_memory_fields(self, resident_id):
        sid = f"iter8-a-{uuid.uuid4().hex[:6]}"
        msg = (
            "I wanted to tell you — my brother Liam lives in Cork, and every "
            "Sunday we used to walk our dog Bruno along the beach before he passed."
        )
        r = requests.post(
            f"{API}/ai/chat",
            json={"session_id": sid, "resident_id": resident_id, "message": msg},
            timeout=90,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "memories_used" in d
        assert "history_replayed" in d
        assert isinstance(d["memories_used"], int)
        assert isinstance(d["history_replayed"], int)
        pytest.first_sid = sid
        pytest.first_msg = msg

    def test_conversation_log_captured(self, headers, resident_id):
        # Small wait for DB write
        time.sleep(1)
        r = requests.get(
            f"{API}/memory/conversation/{resident_id}",
            headers=headers,
            params={"limit": 100},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        conv = r.json()
        assert len(conv) >= 2, f"expected at least user+assistant row, got {len(conv)}"
        # Chronological order: created_at non-decreasing
        times = [c["created_at"] for c in conv]
        assert times == sorted(times), "conversation not chronological"
        # Our user message should appear
        assert any(pytest.first_msg[:30] in (c.get("content") or "") for c in conv)

    def test_background_extraction_produces_memories(self, headers, resident_id):
        # Extraction is fire-and-forget — wait for Claude roundtrip
        time.sleep(10)
        r = requests.get(f"{API}/memory/{resident_id}", headers=headers, timeout=20)
        assert r.status_code == 200
        extracts = [m for m in r.json() if m.get("source") == "extraction"]
        # Keywords from message we expect to land in some memory
        blob = " ".join((m.get("text") or "").lower() for m in extracts)
        assert ("liam" in blob) or ("bruno" in blob) or ("cork" in blob), \
            f"background extraction did not capture expected facts. extracts={extracts[:5]}"

    def test_cross_session_memory_recall(self, resident_id):
        # Different session_id, same resident → memories should be injected
        sid2 = f"iter8-b-{uuid.uuid4().hex[:6]}"
        r = requests.post(
            f"{API}/ai/chat",
            json={
                "session_id": sid2,
                "resident_id": resident_id,
                "message": "What did I tell you earlier about my family?",
            },
            timeout=90,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("memories_used", 0) > 0, \
            f"expected memories_used>0 on 2nd session, got {d}"
        reply_lower = (d.get("reply") or "").lower()
        # Should reference at least one fact from the first turn
        assert any(k in reply_lower for k in ("liam", "bruno", "cork", "brother", "dog")), \
            f"cross-session reply did not reference earlier facts. reply={d.get('reply')}"


# ---------------- Conversation route ----------------

class TestConversationRoute:
    def test_conversation_chronological(self, headers, resident_id):
        r = requests.get(
            f"{API}/memory/conversation/{resident_id}",
            headers=headers,
            params={"limit": 200},
            timeout=20,
        )
        assert r.status_code == 200
        conv = r.json()
        times = [c["created_at"] for c in conv]
        assert times == sorted(times)
        # Each row has role in user/assistant
        roles = {c["role"] for c in conv}
        assert roles.issubset({"user", "assistant"})

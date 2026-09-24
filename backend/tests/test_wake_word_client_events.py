"""Wake-word breadcrumbs from the room page land in activation_events under
their own layer; unrelated names are still dropped. In-process, no DB."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes import activation_client_events as ace  # noqa: E402


def test_wake_word_events_are_accepted_under_wake_word_layer(monkeypatch):
    logged = []

    async def fake_alog(layer, event, **kw):
        logged.append((layer, event, kw.get("session_id"), kw.get("data")))

    monkeypatch.setattr(ace, "alog", fake_alog)
    batch = ace.ClientEventBatch(events=[
        ace.ClientEvent(event="wake_word_detected", client_instance_id="c1", room="214",
                        data={"wake_id": "wake_1", "keyword": "ARIA"}),
        ace.ClientEvent(event="wake_word_session_bound", client_instance_id="c1", room="214",
                        session_id="rt_x", data={"wake_id": "wake_1"}),
        ace.ClientEvent(event="wake_listening_resumed", client_instance_id="c1", room="214"),
        ace.ClientEvent(event="mic_acquired", client_instance_id="c1", room="214"),
        ace.ClientEvent(event="arbitrary_noise", client_instance_id="c1"),
    ])
    out = asyncio.run(ace.client_events(batch))
    assert out == {"ok": True, "accepted": 4, "dropped": 1}
    assert [(layer, event) for layer, event, _, _ in logged] == [
        ("wake_word", "wake_word_detected"),
        ("wake_word", "wake_word_session_bound"),
        ("wake_word", "wake_listening_resumed"),
        ("realtime", "mic_acquired"),
    ]
    assert logged[1][2] == "rt_x"

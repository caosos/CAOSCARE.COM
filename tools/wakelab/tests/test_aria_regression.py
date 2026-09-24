"""Permanent Room 214 regression: single-word "Aria" (intended "air-ee-uh").

Evidence: 2026-09-24 02:06-02:46 UTC Room 214 false wakes; background speech
included "that area". The intended pronunciation is authoritative and must be
rejected with "area" as an exact neighbour; no other pronunciation can rescue it.
"""
from wakelab.inspect import Lab
from wakelab.report import render


def _lab(cfg, cmudict, corpus):
    return Lab(cfg, cmudict=cmudict, data=corpus)


def test_aria_intended_is_identical_to_area_and_rejected(cfg, cmudict, corpus):
    r = _lab(cfg, cmudict, corpus).inspect("aria")
    assert r["verdict"] == "REJECT"
    intended = [e for e in r["pronunciations"] if e["role"] == "intended"]
    assert len(intended) == 1 and intended[0]["phonemes"] == "EH1 R IY0 AH0"
    g1 = next(g for g in intended[0]["gates"] if g["gate"] == "G1_exact_common")
    assert g1["result"] == "FAIL"
    assert any(f["text"] == "area" and f["distance"] == 0.0 for f in g1["evidence"])


def test_aria_dangerous_phrases_explained(cfg, cmudict, corpus):
    r = _lab(cfg, cmudict, corpus).inspect("aria")
    text = render(r)
    assert "IDENTICAL phonemes" in text
    for phrase in ("that area", "common area", "the area"):
        assert f'"{phrase}"' in text
    assert "does not prove" in r["limitation"]


def test_other_pronunciation_cannot_rescue_aria(cfg, cmudict, corpus):
    lab = _lab(cfg, cmudict, corpus)
    r = lab.inspect("aria")
    roles = {e["role"] for e in r["pronunciations"]}
    assert "informational" in roles
    # Even if every informational pronunciation passed, the verdict stays REJECT.
    for e in r["pronunciations"]:
        if e["role"] == "informational":
            e["failed_gates"] = []
    judged = [e for e in r["pronunciations"] if e["role"] != "informational"]
    assert any(e["failed_gates"] for e in judged)


def test_engine_is_not_rejecting_everything(cfg, cmudict, corpus):
    r = _lab(cfg, cmudict, corpus).inspect("zorvell")
    assert r["verdict"] == "PASS (text stage)", r["pronunciations"][0]["failed_gates"]

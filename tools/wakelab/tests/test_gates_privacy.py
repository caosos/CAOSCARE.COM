import copy

from wakelab.inspect import Lab
from wakelab.report import render


def _gates(r, idx=0):
    return {g["gate"]: g for g in r["pronunciations"][idx]["gates"]}


def test_hidden_word_inside_candidate_never_gates(cfg, cmudict, corpus):
    # "okay" (command) and "pine" (drug) sit INSIDE the candidates; hearing them
    # cannot sound like the whole candidate, so G4 must not fail on them.
    r = Lab(cfg, cmudict=cmudict, data=corpus).inspect("okay nabu")
    g = _gates(r)
    assert g["G4_domain_names_commands"]["result"] == "PASS"
    assert r["pronunciations"][0]["metric_counts"]["contains"] >= 1   # still reported


def test_distress_collision_gates(cfg, cmudict, corpus):
    r = Lab(cfg, cmudict=cmudict, data=corpus).inspect("help")
    assert _gates(r)["G5_distress_vocabulary"]["result"] == "FAIL"


def test_speakability_cluster_boundary(cfg, cmudict, corpus):
    lab = Lab(cfg, cmudict=cmudict, data=corpus)
    ok = lab.inspect("x", phonemes="K AH0 M P Y UW1 T ER0")          # cluster of 3: allowed
    bad = lab.inspect("x", phonemes="EH1 K S T R AH0 L")               # cluster of 4: rejected
    assert _gates(ok)["G8_speakability"]["result"] == "PASS"
    assert _gates(bad)["G8_speakability"]["result"] == "FAIL"


def test_speakability_never_offsets_collision(cfg, cmudict, corpus):
    r = Lab(cfg, cmudict=cmudict, data=corpus).inspect("aria")
    intended = r["pronunciations"][0]
    assert _gates(r)["G8_speakability"]["result"] == "PASS"
    assert intended["verdict"] == "REJECT"


def test_drug_names_reported_not_gated_by_default(cfg, cmudict, corpus):
    r = Lab(cfg, cmudict=cmudict, data=corpus).inspect("x", phonemes="P AY1 N")
    assert any(f["metric"] == "drug" for f in r["pronunciations"][0]["metrics"]["domain"])
    assert all(f["metric"] != "drug" for f in _gates(r)["G4_domain_names_commands"]["evidence"])
    strict = copy.deepcopy(cfg)
    strict["gates"]["gate_drug_names"] = True
    r2 = Lab(strict, cmudict=cmudict, data=corpus).inspect("x", phonemes="P AY1 N")
    assert any(f["metric"] == "drug" for f in _gates(r2)["G4_domain_names_commands"]["evidence"])


def test_private_facility_names_never_appear(cfg, cmudict, corpus):
    r = Lab(cfg, cmudict=cmudict, data=corpus).inspect("x", phonemes="K EY1")
    text = render(r)
    import json
    blob = json.dumps(r, default=str)
    assert "[private facility name]" in blob
    assert '"kay"' not in text and '"kay"' not in blob

"""Step 2: pinned pronunciation inside phrases, self-match policy, Pareto, word-drop forms."""
from wakelab import rank
from wakelab.inspect import Lab


def _gates(r, idx=0):
    return {g["gate"]: g for g in r["pronunciations"][idx]["gates"]}


def test_phrase_with_pinned_word_uses_pinned_pronunciation(cfg, cmudict, corpus):
    r = Lab(cfg, cmudict=cmudict, data=corpus).inspect("okay aria")
    intended = [e for e in r["pronunciations"] if e["role"] == "intended"]
    assert intended and all("EH1 R IY0 AH0" in e["phonemes"] for e in intended)
    assert all(e["role"] != "dictionary" for e in r["pronunciations"])   # dictionary = information only


def test_candidate_is_not_its_own_collision_but_its_frequency_counts(cfg, cmudict, corpus):
    # "area" is itself common speech (288/M): G0 must fail, and the self-match
    # must NOT also be counted as a collision with another word under G1.
    r = Lab(cfg, cmudict=cmudict, data=corpus).inspect("area")
    g = _gates(r)
    assert g["G0_self_frequency"]["result"] == "FAIL"
    assert all(f["text"] != "area" for f in g["G1_exact_common"]["evidence"])


def test_distress_self_match_still_gates(cfg, cmudict, corpus):
    assert _gates(Lab(cfg, cmudict=cmudict, data=corpus).inspect("help"))["G5_distress_vocabulary"]["result"] == "FAIL"


def _row(name, margin, risk=0.0, zipf=0.0, cons=3, fric=0, onset="plosive", failed=()):
    return {"candidate": name, "collision_margin": margin, "risk_per_hour": risk, "self_zipf": zipf,
            "distinct_consonants": cons, "high_frequency_fricatives": fric, "onset": onset,
            "failed_gates": list(failed), "near_threshold": 0.25}


def test_pareto_excludes_rejected_and_dominated():
    rows = [_row("best", 0.2), _row("worse", 0.1, risk=0.5), _row("tradeoff", 0.05, cons=6),
            _row("vetoed", None, failed=["G1_exact_common"])]
    got = [r["candidate"] for r in rank.pareto(rows)]
    assert "vetoed" not in got           # collision veto: never a finalist
    assert "worse" not in got            # dominated on every dimension
    assert set(got) == {"best", "tradeoff"}


def test_word_dropped_forms(cfg, cmudict, corpus):
    lab = Lab(cfg, cmudict=cmudict, data=corpus)
    pron = lab.inspect("okay aria")["pronunciations"][0]["phonemes"].split()
    forms = dict((label, p) for p, label in rank.word_dropped(lab, "okay aria", tuple(pron)))
    assert " ".join(forms["'okay' lost"]) == "EH1 R IY0 AH0"
    assert rank.word_dropped(lab, "aria", tuple(pron)) == []

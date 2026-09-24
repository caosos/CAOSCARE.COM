"""Hard rejection gates.

Gates are independent and all are evaluated (a report lists every failure,
not just the first). Any failed collision gate rejects the candidate;
speakability can never compensate for one. Thresholds live in
config/default.yaml.
"""


def _common(f, fr, level):
    """Is this neighbour frequent enough to matter at this gate level?"""
    if f["metric"] == "common_word":
        return (f["zipf"] or 0) >= fr[f"{level}_min_zipf"]
    if f["metric"] == "phrase":
        return (f["per_million"] or 0) >= fr[f"phrase_{level}_min_per_million"]
    return False


def _dedupe(items):
    seen, out = set(), []
    for f in items:
        if f["text"] not in seen:
            seen.add(f["text"])
            out.append(f)
    return out


def _fail(gate, title, why, evidence):
    return {"gate": gate, "title": title, "result": "FAIL", "why": why, "evidence": evidence[:8]}


def _pass(gate, title):
    return {"gate": gate, "title": title, "result": "PASS", "why": "", "evidence": []}


def evaluate(analysis, speak, cfg):
    g, fr, dist = cfg["gates"], cfg["frequency"], cfg["distance"]
    m = analysis["metrics"]
    out = []
    # Only matches where ordinary speech SOUNDS LIKE the candidate can cause a
    # false wake; a common word hidden inside the candidate ("contains") cannot.
    wakes = ("whole", "embedded", "boundary")
    gated_domain = {"domain", "facility", "name"} | ({"drug"} if g.get("gate_drug_names") else set())

    def gate(key, title, evidence, why):
        if not g.get(key, True):
            return
        out.append(_fail(key, title, why, evidence) if evidence else _pass(key, title))

    gate("G1_exact_common", "Exact collision with common speech",
         [f for f in m["exact"] if _common(f, fr, "exact")],
         "the candidate has the SAME phonemes as a common word or phrase; every ordinary use of it is a potential false wake")
    gate("G2_near_high_frequency", "Near collision with high-frequency speech",
         [f for f in m["near"] if _common(f, fr, "near")],
         f"sounds within distance {dist['near']} of very common speech")
    gate("G3_embedded_or_contains", "Candidate sound occurs inside common words or across word boundaries",
         [f for f in m["boundary"] + m["phrase"]
          if (f["relation"] == "boundary" or f["metric"] == "common_word") and _common(f, fr, "near")],
         "ordinary speech produces this sound sequence inside longer words or straddling two words")
    gate("G4_domain_names_commands", "Collision with facility vocabulary, commands or names",
         _dedupe([f for f in m["domain"] + m["names"] if f["relation"] in wakes and f["metric"] in gated_domain]),
         "sounds like words the room already hears (care/building vocabulary, commands, names)")
    gate("G5_distress_vocabulary", "Confusable with distress / safety words",
         [f for f in m["distress"] if f["relation"] in wakes],
         "a wake phrase must never be confusable with a call for help")
    gate("G6_clipped_boundary", "Clipped start/end collides with common speech",
         [f for f in m["clipped"] if f["distance"] <= dist["clipped_max"] and
          (_common(f, fr, "near") or f["metric"] == "distress")],
         "if the detector misses the first/last sound, what remains is common speech")
    gate("G7_accent_casual_variant", "Accent or casual-speech variant collides",
         [f for f in m["variants"] if f["relation"] == "whole" and _common(f, fr, "near")],
         "a common accent or casual pronunciation turns the candidate into common speech")
    if g.get("G8_speakability", True):
        problems = []
        if not g["min_syllables"] <= speak["syllables"] <= g["max_syllables"]:
            problems.append(f"{speak['syllables']} syllables (allowed {g['min_syllables']}-{g['max_syllables']})")
        if speak["max_consonant_cluster"] > g["max_consonant_cluster"]:
            problems.append(f"consonant cluster of {speak['max_consonant_cluster']}")
        if speak["hard_phonemes"]:
            problems.append("hard phonemes " + ", ".join(speak["hard_phonemes"]))
        out.append(_fail("G8_speakability", "Speakability floor", "; ".join(problems), [])
                   if problems else _pass("G8_speakability", "Speakability floor"))
    return out

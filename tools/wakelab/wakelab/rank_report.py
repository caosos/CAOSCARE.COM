"""Human-readable Step 2 report: finalists, the four Aria phrases, names, controls."""


def _neigh(d, n=5):
    return "; ".join(f"{f['text']} ({f['distance']:.2f} {f['relation']}/{f['metric']})"
                     for f in d["nearest_neighbours"][:n]) or "nothing within the near radius"


def _line(d):
    margin = "none<=%.2f" % d["near_threshold"] if d["collision_margin"] is None else f"{d['collision_margin']:.3f}"
    verdict = "PASS" if not d["failed_gates"] else "REJECT " + ",".join(g.split("_")[0] for g in d["failed_gates"])
    return (f"  {d['candidate']:<16} {verdict:<24} margin {margin:<10} risk/h {d['risk_per_hour']:<8} "
            f"self zipf {d['self_zipf']:<5} syl {d['syllables']} onset {d['onset']:<11} "
            f"cons {d['distinct_consonants']} fric {d['high_frequency_fricatives']}")


def render(res):
    rows = {d["candidate"]: d for d in res["candidates"]}
    L = [f"WAKE PHRASE LAB - STEP 2 RANKING   [{res['label']}]",
         f"generated {res['generated_at']}; {len(rows)} candidates inspected", "",
         "Columns are SEPARATE dimensions; there is no combined score. Any failed gate = REJECT (veto).",
         "margin = distance to the nearest OTHER ordinary speech (higher is safer; 0 = identical).",
         "risk/h = rough look-alike events per hour of speech (includes the candidate's own use).",
         "self zipf = how often the candidate itself is said (wordfreq; 3.0 = once per ~million words).", ""]
    L.append(f"PARETO FINALISTS ({len(res['finalists'])}) - survived every gate, not dominated on any dimension:")
    for c in res["finalists"]:
        d = rows[c]
        L += [_line(d), f"      [{d['origin']}] nearest: {_neigh(d)}"]
    L += ["", "THE FOUR ARIA PHRASES (hostile 'area' test = distance from each phrase to the candidate or a clipped form):"]
    for c in ("hey aria", "okay aria", "aria please", "listen aria"):
        d = rows.get(c)
        if not d:
            continue
        L += [_line(d), f"      nearest: {_neigh(d)}"]
        worst = ", ".join(f"{h['phrase']} {h['distance']:.2f} ({h['form']}, {h['relation']})"
                          for h in d.get("hostile_area", [])[:6])
        L.append(f"      hostile area: {worst}")
    L += ["", "NAME EXAMPLES FROM THE DIRECTIVE:"]
    for c in ("samantha", "veronica", "penelope", "delilah", "matilda"):
        if c in rows:
            L += [_line(rows[c]), f"      nearest: {_neigh(rows[c], 3)}"]
    gen = [d for d in res["candidates"] if d["origin"] == "name (generated)"]
    ok = [d for d in gen if not d["failed_gates"]]
    L += ["", f"GENERATED CONVENTIONAL NAMES: {len(gen)} inspected, {len(ok)} passed every gate "
              f"(criteria: {res['criteria']['name_syllables']} syllables, census rank <= "
              f"{res['criteria']['names_max_census_rank']}, zipf < {res['criteria']['name_max_zipf']})"]
    fails = {}
    for d in gen:
        for g in d["failed_gates"]:
            fails[g] = fails.get(g, 0) + 1
    L.append("  rejections by gate: " + ", ".join(f"{g} {n}" for g, n in sorted(fails.items())))
    for d in sorted(ok, key=lambda d: -(d["collision_margin"] or 1))[:15]:
        L.append(_line(d))
    sens = [d for d in res["candidates"] if d.get("g4_names_only")]
    L += ["", f"GATE-POLICY SENSITIVE ({len(sens)}): rejected ONLY by G4 on sound-alike census names. "
              "Still REJECT under current doctrine (G4 has no name-frequency weighting); listed so the "
              "policy can be decided on evidence:"]
    for d in sens:
        ev = ", ".join(f"{e['name']} {e['distance']:.2f} ({e['census_percent'] if e['census_percent'] is not None else '?'}%)"
                       for e in d["g4_names_only"][:4])
        L.append(_line(d) + f"\n      names: {ev}")
    L += ["", "CONTROLS (not recommendations):"]
    for d in res["candidates"]:
        if d["origin"].startswith("control"):
            L += [_line(d) + f"   [{d['origin']}]", f"      nearest: {_neigh(d, 3)}"]
    L += ["", "LIMITATION: text/phoneme stage only. It predicts collision danger; it does not prove "
              "detection, far-field or false-wake performance. Finalists still need the acoustic "
              "stage and physical Room 214 testing."]
    return "\n".join(L)

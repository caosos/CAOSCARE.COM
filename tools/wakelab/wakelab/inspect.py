"""`inspect`: full text-stage analysis of one candidate wake phrase.

Pronunciation policy:
- a pinned override (config) is the candidate's authoritative pronunciation;
  dictionary pronunciations are then analysed as INFORMATION only and can
  never rescue the candidate (Aria regression: intended "air-ee-uh");
- otherwise every dictionary/G2P pronunciation is evaluated and the candidate
  is rejected if ANY of them fails, because people may say it either way.
"""
import datetime
import os
import time

from .collision.analyze import analyze
from .collision.gates import evaluate
from .collision.index import CorpusIndex
from .config import cache_dir
from .corpus.build import load
from .corpus.registry import load_manifest, local_path
from .phonetics.arpabet import parse
from .phonetics.lexicon import Lexicon, load_cmudict
from .speakability import metrics as speak_metrics

LIMITATION = ("Text/phoneme collision analysis PREDICTS acoustic danger from dictionary "
              "pronunciations and word/phrase frequencies; it does not prove real acoustic "
              "performance. Only later acoustic, adversarial and soak testing (and physical "
              "Room 214 testing) can do that.")
CAP = 25


class Lab:
    """Loads the cached corpus + index once; inspects many candidates."""

    def __init__(self, cfg, corpus_path=None, cmudict=None, data=None):
        t0 = time.time()
        self.cfg = cfg
        data = data if data is not None else load(corpus_path)
        self.stats = data["stats"]
        self.index = CorpusIndex(data["items"], cfg["distance"]["min_contained_phones"])
        cmu = cmudict if cmudict is not None else load_cmudict(local_path("cmudict"))
        self.lexicon = Lexicon(cmu, overrides=cfg.get("pronunciation_overrides"),
                               g2p_cache_path=os.path.join(cache_dir(), "g2p_cache.json"))
        self.dictionary = Lexicon(cmu, g2p_cache_path=os.path.join(cache_dir(), "g2p_cache.json"))
        self.load_seconds = round(time.time() - t0, 2)

    def pronunciations(self, text, phonemes=None):
        """[(pron, role, source)] - role: intended | dictionary | informational."""
        if phonemes:
            return [(parse(phonemes), "intended", "command line")]
        pinned = self.lexicon.overrides.get(text.lower())
        dict_prons = [(p, s) for p, _, s in self.dictionary.phrase(text, use_g2p=True, max_variants=4)]
        if pinned:
            out = [(p, "intended", "override (config/default.yaml pronunciation_overrides)") for p in pinned]
            pinned_b = {tuple(x.rstrip("012") for x in p) for p in pinned}
            return out + [(p, "informational", s) for p, s in dict_prons
                          if tuple(x.rstrip("012") for x in p) not in pinned_b]
        return [(p, "dictionary", s) for p, s in dict_prons]

    def inspect(self, text, phonemes=None):
        t0 = time.time()
        prons = self.pronunciations(text, phonemes)
        if not prons:
            raise ValueError(f"no pronunciation available for {text!r}")
        evaluated = []
        for pron, role, source in prons:
            a = analyze(self.index, pron, self.cfg, candidate_text=text)
            sp = speak_metrics(pron, self.cfg)
            gates = evaluate(a, sp, self.cfg)
            failed = [g["gate"] for g in gates if g["result"] == "FAIL"]
            evaluated.append({"phonemes": a["phonemes"], "role": role, "source": source,
                              "verdict": "REJECT" if failed else "PASS (text stage)",
                              "failed_gates": failed, "gates": _clean(gates),
                              "metric_counts": {k: len(v) for k, v in a["metrics"].items()},
                              "metrics": {k: _clean(v[:CAP]) for k, v in a["metrics"].items()},
                              "risk_per_hour": a["risk_per_hour"], "speakability": sp})
        judged = [e for e in evaluated if e["role"] != "informational"]
        verdict = "REJECT" if any(e["failed_gates"] for e in judged) else "PASS (text stage)"
        return {"candidate": text, "verdict": verdict, "pronunciations": evaluated,
                "limitation": LIMITATION, "config": self.cfg,
                "corpus": {"stats": self.stats, "manifest": _manifest_summary()},
                "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "timing_seconds": {"corpus_load": self.load_seconds,
                                   "inspect": round(time.time() - t0, 2)}}


def _clean(items):
    """Drop internal fields; private names are already redacted in findings."""
    out = []
    for it in items:
        it = {k: v for k, v in it.items() if not k.startswith("_")}
        if "evidence" in it:
            it["evidence"] = _clean(it["evidence"])
        out.append(it)
    return out


def _manifest_summary():
    return {k: {x: v.get(x) for x in ("version", "license", "sha256", "retrieved_at",
                                      "installed_version", "present") if v.get(x) is not None}
            for k, v in load_manifest().items()}

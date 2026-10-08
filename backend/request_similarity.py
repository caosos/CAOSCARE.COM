"""Deterministic, explainable "is this the same issue?" check for the
resident-request dedup (RQ-032 / D2). No model call: lower-case words,
drop filler, light suffix stemming, then compare the word sets.

Same issue only when clearly the same:
  - the word sets are equal, or
  - Jaccard similarity >= 0.5, or
  - at least 2 shared words and the overlap covers >= 75% of the smaller set.
Anything else (including no usable words on either side) is a different
issue and becomes its own request, so a second problem in the same
department is never silently folded into the first.
"""
import re
from typing import Iterable, Optional

_STOP = frozenset("""
a an the and or but of to in on at for with from by is are was were be been am it its this that these those
i me my mine we our you your he she they them their there here
do does did done can could would should will shall may might please
need needs needed want wants wanted would like have has had get gets got
help someone somebody anyone staff request issue problem thing things something
just really very also again still now today again keeps keep kept
""".split())


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    if len(w) > 3 and w.endswith("y"):
        w = w[:-1] + "i"
    return w


def content_words(*texts: Optional[str]) -> frozenset:
    words = set()
    for t in texts:
        for w in re.findall(r"[a-z0-9']+", (t or "").lower()):
            w = w.replace("'", "")
            if w and w not in _STOP and not w.isdigit():
                words.add(_stem(w))
    return frozenset(words)


def similarity(a: Iterable[str], b: Iterable[str]) -> dict:
    a, b = frozenset(a), frozenset(b)
    shared = a & b
    union = a | b
    jaccard = len(shared) / len(union) if union else 0.0
    overlap = len(shared) / min(len(a), len(b)) if a and b else 0.0
    same = bool(a and b) and (a == b or jaccard >= 0.5 or (len(shared) >= 2 and overlap >= 0.75))
    return {"same": same, "jaccard": round(jaccard, 3), "overlap": round(overlap, 3),
            "shared": sorted(shared)}


def best_match(new_words: frozenset, candidates: list[dict]) -> Optional[dict]:
    """The open task that is clearly the same issue, or None. Most similar
    wins; ties go to the earlier (more recent first) candidate."""
    best, best_score = None, -1.0
    for task in candidates:
        old = content_words(task.get("description"), task.get("resident_words"), task.get("title"))
        s = similarity(new_words, old)
        if s["same"] and s["jaccard"] > best_score:
            best, best_score = task, s["jaccard"]
    return best

"""Pairing-time collision guard for RF pendants.

Real finding, 2026-09-06: the two live pendants already in this deployment
(Helen Torres's Rm 214 pendant and the Rm 401 bring-up test pendant) are
0.893 similar to each other under hamming_similarity, while the pairing
match_threshold at the time was 0.85 - a 0.85 threshold that a *clean,
noise-free* cross-device read already clears on its own. Every live event
since has decoded at score 1.0 so the correct device always won the
best-match contest, but nothing stopped it from going the other way. This
guard runs at pairing time so the next similar pair gets caught before
it's live, instead of being discovered by re-deriving the same math later.
Split out of rf.py (already well over the 300-line cap) so pair() could
call this without growing that file further.
"""
from typing import Optional

from deps import db
from models import RFFingerprint

# How far a new pendant's similarity to any other enabled device on a
# nearby frequency must sit below the pairing's own match_threshold before
# we call it safe. Not just "different from" - different enough that
# real-world signal noise (weak battery, distance, interference) can't
# plausibly close the gap.
PAIRING_SAFETY_MARGIN = 0.10


def hamming_similarity(a_hex: str, b_hex: str) -> float:
    """Fingerprint similarity. Both inputs are hex of the decoded bit
    pattern. Returns 0..1 where 1.0 = identical. Mismatched length is
    handled by aligning to the shorter of the two."""
    if not a_hex or not b_hex:
        return 0.0
    try:
        a = bytes.fromhex(a_hex.replace(" ", ""))
        b = bytes.fromhex(b_hex.replace(" ", ""))
    except ValueError:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    bits = n * 8
    diff = 0
    for i in range(n):
        diff += bin(a[i] ^ b[i]).count("1")
    return 1.0 - (diff / bits)


async def find_pairing_conflict(
    fingerprint: RFFingerprint, match_threshold: float, freq_tolerance_hz: int,
) -> Optional[dict]:
    """Return the closest already-enabled device this new fingerprint could
    be confused with at live-match time, or None if none are too close."""
    candidates = await db.rf_devices.find(
        {
            "enabled": True,
            "fingerprint.frequency_hz": {
                "$gte": fingerprint.frequency_hz - freq_tolerance_hz,
                "$lte": fingerprint.frequency_hz + freq_tolerance_hz,
            },
        },
        {"_id": 0},
    ).to_list(500)

    worst = None
    worst_score = 0.0
    for c in candidates:
        score = hamming_similarity(fingerprint.bit_pattern_hex, c["fingerprint"]["bit_pattern_hex"])
        if score > worst_score:
            worst_score = score
            worst = c

    if worst is not None and worst_score >= match_threshold - PAIRING_SAFETY_MARGIN:
        return {"device": worst, "score": round(worst_score, 4)}
    return None

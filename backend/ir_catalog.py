"""Curated executable IR candidates; web results never become raw commands."""
from ir_codesets import CODESETS

CATALOG = {
    "sony_sirc12": {
        "candidate_id": "sony_sirc12",
        "vendors": {"sony", "sony bravia", "bravia"},
        "codeset": "sony_sirc12",
        "source": "Lucaslhm/Flipper-IRDB TVs/Sony; physically proven Room 214 2026-10-12",
        "source_url": "https://github.com/Lucaslhm/Flipper-IRDB/tree/main/TVs/Sony",
        "test_action": "volume_step",
        "test_value": -1,
        "restore_value": 1,
    },
}


def candidates(vendor: str, model: str = "") -> list[dict]:
    key = " ".join((vendor or "").lower().split())
    found = [v for v in CATALOG.values() if key in v["vendors"] and v["codeset"] in CODESETS]
    return [{k: v[k] for k in ("candidate_id", "codeset", "source", "source_url", "test_action")} for v in found]


def candidate(candidate_id: str) -> dict:
    if candidate_id not in CATALOG:
        raise KeyError(candidate_id)
    return CATALOG[candidate_id]

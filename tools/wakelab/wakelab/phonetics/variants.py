"""Rule-based pronunciation variants: casual speech and common US accents.

Applied to the candidate so a collision that only appears when someone says
it casually, or with a different accent, is caught and reported as its own
metric ("variant collision"). Each rule is named so the report can say WHY a
variant exists. Rules are deliberately few and conservative; they are a
model of variation, not a complete phonology.
"""
from .arpabet import base, is_vowel


def _with_stress(new_base, old):
    return new_base + (old[-1] if old[-1] in "012" else "")


def _mary(pron):
    """Before R, EH / AE / EY / AA collapse toward EH (Mary/marry/merry)."""
    out, changed = list(pron), False
    for i in range(len(pron) - 1):
        if base(pron[i]) in {"AE", "EY", "AA"} and base(pron[i + 1]) == "R":
            out[i], changed = _with_stress("EH", pron[i]), True
    return tuple(out) if changed else None


def _cot_caught(pron):
    out = tuple(_with_stress("AA", p) if base(p) == "AO" else p for p in pron)
    return out if out != pron else None


def _pin_pen(pron):
    out, changed = list(pron), False
    for i in range(len(pron) - 1):
        if base(pron[i]) == "EH" and base(pron[i + 1]) in {"M", "N", "NG"}:
            out[i], changed = _with_stress("IH", pron[i]), True
    return tuple(out) if changed else None


def _reduce_unstressed(pron):
    """Casual speech: unstressed full vowels drift to schwa (AH0)."""
    out = tuple("AH0" if is_vowel(p) and p.endswith("0") and base(p) not in {"AH", "IY", "ER"} else p
                for p in pron)
    return out if out != pron else None


def _non_rhotic(pron):
    """Non-rhotic accents drop R after a vowel when no vowel follows."""
    out = [p for i, p in enumerate(pron)
           if not (base(p) == "R" and i > 0 and is_vowel(pron[i - 1])
                   and (i + 1 == len(pron) or not is_vowel(pron[i + 1])))]
    return tuple(out) if len(out) != len(pron) else None


def _h_drop(pron):
    return pron[1:] if pron and base(pron[0]) == "HH" and len(pron) > 2 else None


RULES = (
    ("mary_merry_marry", "vowels before R merge (Mary/marry/merry)", _mary),
    ("cot_caught", "cot/caught merger", _cot_caught),
    ("pin_pen", "pin/pen merger before nasals", _pin_pen),
    ("reduce_unstressed", "casual speech: unstressed vowels reduce to schwa", _reduce_unstressed),
    ("non_rhotic", "non-rhotic accent drops post-vocalic R", _non_rhotic),
    ("h_drop", "initial H dropped", _h_drop),
)


def variants(pron):
    """[(variant_pron, rule_name, description)] distinct from pron and each other."""
    seen, out = {tuple(base(p) for p in pron)}, []
    for name, desc, fn in RULES:
        v = fn(pron)
        if v and tuple(base(p) for p in v) not in seen:
            seen.add(tuple(base(p) for p in v))
            out.append((v, name, desc))
    return out


def clipped(pron):
    """Onset/offset clipping a detector may suffer: [(pron, label)]."""
    out = []
    if len(pron) > 3:
        out.append((pron[1:], "first phoneme clipped"))
        out.append((pron[:-1], "last phoneme clipped"))
    first_vowel = next((i for i, p in enumerate(pron) if is_vowel(p)), None)
    if first_vowel is not None:
        nxt = next((i for i in range(first_vowel + 1, len(pron)) if is_vowel(pron[i])), None)
        if nxt is not None and len(pron) - nxt >= 2:
            cut = nxt - 1 if nxt - 1 > first_vowel else nxt
            out.append((pron[cut:], "first syllable clipped"))
    return out

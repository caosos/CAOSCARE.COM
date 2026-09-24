from wakelab.collision.align import best_substring, normalized_global
from wakelab.phonetics.arpabet import bases, parse, syllable_count, to_chars
from wakelab.phonetics.features import sub_cost
from wakelab.phonetics.lexicon import Lexicon
from wakelab.phonetics.variants import clipped, variants


def test_arpabet_parse_and_strings():
    p = parse("EH1 R IY0 AH0")
    assert bases(p) == ("EH", "R", "IY", "AH")
    assert syllable_count(p) == 3
    assert to_chars(p) == to_chars(parse("EH0 R IY1 AH2"))   # stress-free comparison


def test_calibration_anchors():
    # Place-only < voicing-only < unrelated (Miller & Nicely: place most confusable).
    assert sub_cost("P", "T") < sub_cost("P", "B") < sub_cost("P", "S") <= 1.0
    assert sub_cost("IH", "IY") < 0.2 and sub_cost("EH", "AE") <= 0.2
    assert sub_cost("AH", "IY") >= 0.5
    assert sub_cost("EH", "K") == 1.0
    assert sub_cost("Y", "IY") == 0.5


def test_alignment_area_inside_that_area():
    aria = bases(parse("EH1 R IY0 AH0"))
    that_area = bases(parse("DH AE1 T EH1 R IY0 AH0"))
    assert normalized_global(aria, bases(parse("EH1 R IY0 AH0"))) == 0.0
    d, s, e = best_substring(aria, that_area)
    assert d == 0.0 and (s, e) == (3, 7)


def test_variants_and_clipping():
    names = {n for _, n, _ in variants(parse("AA1 R IY0 AH0"))}
    assert "mary_merry_marry" in names          # AA before R -> EH ("ar-ee-uh" -> "air-ee-uh")
    merged = [v for v, n, _ in variants(parse("AA1 R IY0 AH0")) if n == "mary_merry_marry"][0]
    assert bases(merged) == ("EH", "R", "IY", "AH")
    assert any(n == "h_drop" for _, n, _ in variants(parse("HH EY1 JH AA1 R V AH0 S")))
    labels = [lbl for _, lbl in clipped(parse("EH1 R IY0 AH0"))]
    assert "first phoneme clipped" in labels and "last phoneme clipped" in labels


def test_lexicon_override_is_authoritative(cmudict):
    lex = Lexicon(cmudict, overrides={"aria": ["EH1 R IY0 AH0"]}, allow_g2p=False)
    assert lex.word("aria") == [(parse("EH1 R IY0 AH0"), "override")]
    plain = Lexicon(cmudict, allow_g2p=False)
    assert plain.word("aria") == [(parse("AA1 R IY0 AH0"), "cmudict")]
    assert plain.phrase("that area")[0][1] == (0, 3)      # word boundary offsets
    assert plain.word("nonexistentword") == []

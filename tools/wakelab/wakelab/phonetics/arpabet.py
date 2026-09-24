"""ARPAbet inventory (CMUdict's 39 phonemes) and small helpers.

Pronunciations are tuples of ARPAbet symbols; vowels carry a stress digit
(0 unstressed, 1 primary, 2 secondary) exactly as CMUdict writes them.
"Base" symbols drop the stress digit. Each base phoneme also maps to one
private-use character so fast string matchers (rapidfuzz) can compare whole
phoneme sequences as strings.
"""

VOWELS = ("AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY",
          "IH", "IY", "OW", "OY", "UH", "UW")
CONSONANTS = ("B", "CH", "D", "DH", "F", "G", "HH", "JH", "K", "L", "M", "N",
              "NG", "P", "R", "S", "SH", "T", "TH", "V", "W", "Y", "Z", "ZH")
PHONES = VOWELS + CONSONANTS

# Broad IPA for articulatory-feature distances (PanPhon).
IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "IH": "ɪ", "IY": "i", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h",
    "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p",
    "R": "ɹ", "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}

PLOSIVES = {"P", "B", "T", "D", "K", "G"}
FRICATIVES = {"F", "V", "TH", "DH", "S", "Z", "SH", "ZH", "HH"}
AFFRICATES = {"CH", "JH"}
NASALS = {"M", "N", "NG"}
APPROXIMANTS = {"L", "R", "W", "Y"}

_CHAR = {p: chr(0xE000 + i) for i, p in enumerate(PHONES)}
_FROM_CHAR = {c: p for p, c in _CHAR.items()}


def base(phone):
    """'EH1' -> 'EH'; consonants unchanged."""
    return phone.rstrip("012")


def is_vowel(phone):
    return base(phone) in VOWELS


def parse(text):
    """'EH1 R IY0 AH0' -> ('EH1', 'R', 'IY0', 'AH0'). Validates symbols."""
    phones = tuple(text.split())
    for p in phones:
        if base(p) not in _CHAR:
            raise ValueError(f"unknown ARPAbet symbol {p!r} in {text!r}")
    return phones


def bases(pron):
    return tuple(base(p) for p in pron)


def to_chars(pron):
    """Stress-free phoneme sequence as a compact string (one char per phoneme)."""
    return "".join(_CHAR[base(p)] for p in pron)


def from_chars(s):
    return tuple(_FROM_CHAR[c] for c in s)


def show(pron):
    return " ".join(pron)


def syllable_count(pron):
    return sum(1 for p in pron if is_vowel(p))

"""Shared configuration for the Wake Word Lab Phase 2 (identical conditions).

Every trained candidate uses exactly these counts, seeds, speakers, noise,
television audio, volumes, thresholds and evaluation clips. Nothing here is
candidate-specific except the candidate's own phonemes.
"""
import hashlib
import json
from pathlib import Path

LAB = Path(__file__).resolve().parent
WORK = Path.home() / "caoscare-firmware-work"          # research work dir (data, samples, runs; not committed)
GEN_PT = WORK / "piper-sample-generator/models/en_US-libritts_r-medium.pt"
VOICES = WORK / "voices"
SAMPLES = WORK / "samples/lab"
RUNS = WORK / "runs/lab"
EVAL_DATA = WORK / "eval_data"

SEED = 20261003
TRAIN_POSITIVES_PER_FORM = 600        # x 3 forms = 1800 positive clips per candidate
TRAIN_NEGATIVES_PER_PHRASE = 50
TRAIN_STEPS = 10000
LENGTH_SCALES = (0.8, 0.9, 1.0, 1.1, 1.25)
NOISE_SCALES = (0.5, 0.667, 0.8)
NOISE_WS = (0.6, 0.8, 1.0)
EVAL_LENGTH_SCALES = (0.85, 1.15)     # slower / faster talkers in the held-out set
CUTOFFS = [round(0.05 * i, 2) for i in range(4, 20)] + [0.97, 0.98, 0.99]
REPORT_CUTOFF = 0.90                  # one identical operating point for side-by-side tables

# --- ARPAbet -> espeak-style IPA (what Piper was trained on) ------------------
_V = {"AA": "ɑː", "AE": "æ", "AO": "ɔː", "AW": "aʊ", "AY": "aɪ", "EH": "ɛ", "ER": "ɜː",
      "EY": "eɪ", "IH": "ɪ", "IY": "iː", "OW": "oʊ", "OY": "ɔɪ", "UH": "ʊ", "UW": "uː"}
_C = {"B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ",
      "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
      "T": "t", "TH": "θ", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ"}


def _vowel(base, stress, form):
    if base == "AH":
        return "ʌ" if stress in "12" and form != "casual" else "ə"
    if base == "ER":
        return "ɜː" if stress in "12" else "ɚ"
    if stress == "0" and form == "casual":           # casual speech: unstressed vowels reduce
        return {"IY": "i", "UW": "ʊ", "OW": "ə", "AA": "ə", "EH": "ə", "IH": "ɪ"}.get(base, _V[base])
    if stress == "0" and form == "intended" and base == "IY":
        return "i"
    return _V[base]


def arpabet_to_ipa(arpa, form="intended"):
    """form: careful (full vowels, clear), intended, casual (reduced unstressed vowels,
    shortened final vowel). Word boundaries are not encoded in ARPAbet strings here, so
    launcher words are separated by the caller."""
    out = []
    toks = arpa.split()
    for i, t in enumerate(toks):
        base, stress = t.rstrip("012"), t[-1] if t[-1] in "012" else ""
        if base in _V or base in ("AH", "ER"):
            mark = {"1": "ˈ", "2": "ˌ"}.get(stress, "")
            if form == "careful" and stress == "0":
                mark = "ˌ"
            v = _vowel(base, stress or "0", form)
            if form == "casual" and i == len(toks) - 1:
                v = v.replace("ː", "")
            out.append(mark + v)
        else:
            out.append(_C[base])
    return "".join(out)


def ipa_phrase(arpa_words, form):
    return " ".join(arpabet_to_ipa(w, form) for w in arpa_words)


FORMS = ("careful", "intended", "casual")

# --- shared NEGATIVE vocabulary (identical for every model) --------------------
REQUIRED_NEGATIVES = [
    "area", "care", "caregiver", "Maria", "Daria", "Ari", "Ariel", "Victoria", "malaria",
    "hey Maria", "hey Ari", "family", "therapy", "dietary", "activities", "emergency",
    "maintenance", "transportation", "nurse", "light", "television", "call", "help",
    "Krista", "Crystal", "Chris", "Christian", "Christmas", "Clarissa", "Melissa", "Cassandra",
    "Calista", "Kestrel", "extra", "list", "listen", "very", "various",
]
LAUNCHER_ONLY = ["hey", "hi there", "hello", "okay", "hey you", "hello there", "okay then",
                 "hi honey", "okay sure", "hey there"]
GENERAL_NEGATIVES = [
    "the area", "that area", "common area", "hey area", "Siri", "Hey Siri", "Korea", "Ria",
    "Harry", "Carrie", "sorry", "sorry about that", "Gloria", "are you there", "Mario", "Aaron",
    "Bavaria", "barrier", "Arianna", "hurry up", "our ears", "Larry", "Mary", "dairy",
    "call the nurse", "turn on the light", "turn off the television", "physical therapy",
    "memory care", "medication", "wheelchair", "bathroom", "dinner", "breakfast", "the remote",
    "channel", "volume", "the news", "weather", "commercial", "partly cloudy", "breaking news",
    "doctor appointment", "pharmacy", "can you hear me", "talk to you later", "blood pressure",
    "the van", "work order", "air conditioner",
]


def training_negative_phrases(neighbour_phrases=()):
    seen, out = set(), []
    for p in REQUIRED_NEGATIVES + LAUNCHER_ONLY + GENERAL_NEGATIVES + list(neighbour_phrases):
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


# Extra held-out confusion set for the Sivia addendum (Michael, 2026-10-04). EVALUATION ONLY - the shared
# training negatives stay identical for every model. Every model (all 26) is scored on these clips; results
# are written to separate files so completed results are never altered.
EXTRA_CONFUSION = ["Sylvia", "Olivia", "Siri", "Syria", "severe", "trivia", "see via", "Siva", "Shiva",
                   "Civia", "Vivian", "hey Sylvia", "hey Olivia"]

# Held-out evaluation sentences: TV / news / room conversation lines (never trained on).
EVAL_SENTENCES = [
    "In tonight's news, the city council approved the new budget.",
    "Partly cloudy skies today with a high near seventy degrees.",
    "Back after these messages, stay with us.",
    "Maria said she would be here at noon.",
    "Is this area clean yet, or should I come back?",
    "Hey Siri, what time is it?",
    "Christmas is coming, and Krista bought extra lights.",
    "Melissa and Cassandra are on the activities list.",
    "Did you take your medication with breakfast?",
    "The van leaves for the pharmacy at two o'clock.",
    "Call maintenance about the air conditioner, please.",
    "The family visit is in the common area after lunch.",
    "Victoria, can you turn the television down a little?",
    "Hello, who is this? I can't hear you very well.",
    "We have chicken casserole and apple pie for dinner tonight.",
    "Bingo starts at two in the activity room.",
    "Clarissa listened to various songs on the radio.",
    "Ari and Daria went to physical therapy.",
    "The caregiver will help you to the bathroom.",
    "That was a very good game show tonight.",
]

# Held-out speakers: (voice file, speaker_id or None, label, sex as documented in model card)
EVAL_SPEAKERS = [
    ("en_US-lessac-medium", None, "lessac", "F"), ("en_US-amy-medium", None, "amy", "F"),
    ("en_US-kristin-medium", None, "kristin", "F"), ("en_US-hfc_female-medium", None, "hfc_female", "F"),
    ("en_GB-cori-high", None, "cori (GB)", "F"), ("en_GB-southern_english_female-low", None, "southern_english_female (GB)", "F"),
    ("en_US-ryan-high", None, "ryan", "M"), ("en_US-joe-medium", None, "joe", "M"),
    ("en_US-norman-medium", None, "norman", "M"), ("en_US-hfc_male-medium", None, "hfc_male", "M"),
    ("en_GB-alan-medium", None, "alan (GB)", "M"), ("en_GB-northern_english_male-medium", None, "northern_english_male (GB)", "M"),
    ("en_US-john-medium", None, "john", "M"), ("en_US-kusal-medium", None, "kusal", "M"),
    ("en_US-arctic-medium", "rms", "arctic rms", "M"), ("en_US-arctic-medium", "bdl", "arctic bdl", "M"),
    ("en_US-arctic-medium", "slt", "arctic slt", "F"), ("en_US-arctic-medium", "clb", "arctic clb", "F"),
    ("en_GB-semaine-medium", "obadiah", "semaine obadiah (gloomy)", "M"), ("en_GB-semaine-medium", "prudence", "semaine prudence", "F"),
    ("en_US-l2arctic-medium", "0", "l2arctic speaker 0 (accented)", "?"), ("en_US-l2arctic-medium", "5", "l2arctic speaker 5 (accented)", "?"),
    ("en_US-l2arctic-medium", "10", "l2arctic speaker 10 (accented)", "?"), ("en_US-l2arctic-medium", "17", "l2arctic speaker 17 (accented)", "?"),
]


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def load_trained_candidates():
    """The original 15 Phase 2 candidates (select_lab.py)."""
    return json.loads((LAB / "trained_candidates.json").read_text())


def load_supplemental_candidates():
    """Mandatory supplemental candidates (select_supplemental.py, Michael 2026-10-04)."""
    f = LAB / "supplemental_candidates.json"
    return json.loads(f.read_text()) if f.exists() else []


def load_all_candidates():
    return load_trained_candidates() + load_supplemental_candidates()


def load_phase1_rows():
    """Phase 1 text-screen rows for every candidate, keyed by id: results/discovery.json plus the
    supplemental screen (results/discovery_supplemental.json, Sivia addendum). Supplemental rows
    never replace an original row."""
    rows = {r["id"]: r for r in json.loads((LAB / "results/discovery.json").read_text())["rows"]}
    extra = LAB / "results/discovery_supplemental.json"
    if extra.exists():
        for r in json.loads(extra.read_text())["rows"]:
            rows.setdefault(r["id"], r)
    return rows


def load_batch_candidates(name="batch1"):
    """Follow-on acoustic batches selected from the wake-phrase funnel (batch1_candidates.json, Round 5).
    Kept separate from the 26 so the completed lab's results are never rewritten."""
    f = LAB / f"{name}_candidates.json"
    return json.loads(f.read_text()) if f.exists() else []


def candidate(slug):
    return next(c for c in load_all_candidates() + load_batch_candidates() + load_batch_candidates("methodtest")
                if c["slug"] == slug)

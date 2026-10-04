"""Generate synthetic wake-word clips with Piper (official microWakeWord path).

Training clips: the LibriTTS-R generator (900+ speakers, slerp-mixed).
Held-out evaluation clips: separate Piper VITS voices (different training
data/speakers), so evaluation is not on the generator that produced the
training data. Both are still synthetic speech.
"""
import subprocess
import sys
from pathlib import Path

W = Path(__file__).parent
PY = str(W / "venv-mww/bin/python")
GEN = str(W / "piper-sample-generator/models/en_US-libritts_r-medium.pt")
VOICES = W / "voices"
OUT = W / "samples"

# Target pronunciation (Michael): AR-ee-uh.  espeak reads the plain spelling
# "Aria" as /ˈɛɹiə/ (AIR-ee-uh) -- the same sound as "area" -- so the positives
# use respellings that produce /ˈɑːɹiə/:
#   Ahria -> ˈɑːɹiʲə    Ahreea -> ˈɑːɹiːʲə    Ahrya -> ˈɑːɹɪʲə
# The plain spelling is generated only as a separate diagnostic eval set
# ("Aria" as TTS reads it), never as a positive or a negative.
ARIA = ["Ahria", "Ahreea", "Ahrya"]
HEY_ARIA = ["Hey Ahria", "Hey Ahreea", "Hey Ahrya"]
AIR_EE_UH = ["Aria", "Hey Aria"]  # diagnostic only

# Required confusions + sound-alikes, used as training hard negatives.
ADVERSARIAL = [
    "area", "the area", "that area", "this area", "common area", "hey area",
    "Maria", "hey Maria", "Daria", "hey Daria", "Ari", "hey Ari", "Hey Siri", "Siri",
    "Korea", "Ria", "Rhea", "Ariel", "aerial", "Harry", "hey Harry", "Carrie",
    "sorry", "sorry about that", "malaria", "Gloria", "are you", "are you there",
    "Mario", "Aaron", "Erie", "Bavaria", "barrier", "Harriet", "Arianna",
    "carry a bag", "hurry up", "hey there", "hey you", "hey Rita", "hey Erin",
    "hey nurse", "our ears", "a real one", "Larry", "Mary", "dairy",
]
# Held-out sound-alikes (never trained on).
ADVERSARIAL_EVAL = [
    "Valeria", "Victoria", "cafeteria", "criteria", "Syria", "Austria", "Ariana",
    "hey Gloria", "hey Victoria", "hey Mario", "hey Siri, are you there", "Marie",
    "diary", "Laria", "hey Larry", "I'm sorry", "hurry", "Harry, are you here",
]
# Held-out ordinary sentences containing the same sounds (never trained on).
SENTENCES_EVAL = [
    "The common area is on the second floor.",
    "Maria said she would be here at noon.",
    "Hey Siri, what time is it?",
    "Daria and Ari went to the cafeteria.",
    "Is this area clean yet?",
    "Harry is waiting in the dining area.",
    "I'm sorry, are you awake?",
    "My daughter Gloria lives in Victoria.",
    "Hey Maria, can you hear me?",
    "We sat in the sunny area by the window.",
]
EVAL_VOICES = ["en_US-lessac-medium", "en_US-amy-medium", "en_US-ryan-high",
               "en_GB-alan-medium", "en_US-joe-medium", "en_GB-cori-high"]


def run(text, out, n, model=GEN, batch=50):
    out.mkdir(parents=True, exist_ok=True)
    have = len(list(out.glob("*.wav")))
    if have >= n:
        return
    cmd = [PY, "-m", "piper_sample_generator", text, "--model", str(model),
           "--max-samples", str(n), "--batch-size", str(batch), "--output-dir", str(out),
           "--length-scales", "0.8", "0.9", "1.0", "1.1", "1.25",
           "--noise-scales", "0.5", "0.667", "0.8", "--noise-scale-ws", "0.6", "0.8", "1.0"]
    subprocess.run(cmd, check=True, cwd=W / "piper-sample-generator",
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fetch_voices():
    VOICES.mkdir(exist_ok=True)
    base = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en"
    for v in EVAL_VOICES:
        lang, name, q = v.split("-")
        for ext in (".onnx", ".onnx.json"):
            f = VOICES / f"{v}{ext}"
            if not f.exists():
                subprocess.run(["wget", "-q", "-O", str(f),
                                f"{base}/{lang}/{name}/{q}/{v}{ext}?download=true"], check=True)


def slug(s):
    return "".join(c if c.isalnum() else "_" for c in s.lower())


def main(per_spelling=1000, per_adv=60):
    # training material (generator)
    for t in ARIA:
        run(t, OUT / "train/aria" / slug(t), per_spelling)
    for t in HEY_ARIA:
        run(t, OUT / "train/hey_aria" / slug(t), per_spelling)
    for t in ADVERSARIAL:
        run(t, OUT / "train/adversarial_aria" / slug(t), per_adv)
    for t in ARIA:  # bare name is a hard negative for the "Hey Aria" model only
        run(t, OUT / "train/bare_aria_negative" / slug(t), per_adv * 3)
    # held-out evaluation material (other Piper voices)
    fetch_voices()
    for v in EVAL_VOICES:
        m = VOICES / f"{v}.onnx"
        for t in ARIA:
            run(t, OUT / "eval/aria" / f"{slug(t)}__{v}", 15, model=m, batch=1)
        for t in HEY_ARIA:
            run(t, OUT / "eval/hey_aria" / f"{slug(t)}__{v}", 15, model=m, batch=1)
        for t in AIR_EE_UH:
            run(t, OUT / "eval/air_ee_uh" / f"{slug(t)}__{v}", 10, model=m, batch=1)
        for t in ADVERSARIAL_EVAL + ADVERSARIAL[:13]:
            run(t, OUT / "eval/adversarial_aria" / f"{slug(t)}__{v}", 4, model=m, batch=1)
        for t in SENTENCES_EVAL:
            run(t, OUT / "eval/sentences_aria" / f"{slug(t)[:40]}__{v}", 3, model=m, batch=1)
    print("SAMPLES READY")


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))

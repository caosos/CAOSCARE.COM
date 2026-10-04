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

# Spellings chosen so espeak gives the sounds people actually say:
#   Nahboo  -> nˈɑːbuː  (NAH-boo)     Nah-boo -> nˈɑːbˈuː (nah-BOO)
#   Naboo   -> nˈæbuː   (NAB-oo, how the written name is often read)
NABOO = ["Nahboo", "Nah-boo", "Naboo"]
HEY_NABOO = ["Hey Nahboo", "Hey Nah-boo", "Hey Naboo"]

# Sound-alike / partial-overlap phrases, used as hard negatives.
ADVERSARIAL = [
    "nah", "no", "boo", "taboo", "bamboo", "kaboom", "nab", "nabbed it", "about",
    "a boot", "nebula", "Nobu", "nobody", "noodle", "Nancy", "Nala", "nanny", "navy",
    "naval", "napping", "knob", "Bob", "Abu", "ah boo", "Mabel", "yahoo", "Kabul",
    "Nairobi", "neighbor", "number", "Nebraska", "I knew", "and who", "nurse",
    "Nabisco", "on the bus", "hey you", "hey Bob", "hey there", "hey nurse",
    "nap time", "not now", "nah, you", "hey, no", "Nadia", "nautical", "Pablo",
]
# Held-out sound-alikes (never trained on).
ADVERSARIAL_EVAL = [
    "Nabby", "nab you", "nah, boo hoo", "Kazoo", "shampoo", "Winnie the Pooh",
    "Malibu", "Danube", "nobody knew", "hey Lou", "hey Mabel", "hey Nancy",
    "hey neighbor", "a new boot", "Nick, boo", "knock knock", "nothing new",
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
    for t in NABOO:
        run(t, OUT / "train/naboo" / slug(t), per_spelling)
    for t in HEY_NABOO:
        run(t, OUT / "train/hey_naboo" / slug(t), per_spelling)
    for t in ADVERSARIAL:
        run(t, OUT / "train/adversarial" / slug(t), per_adv)
    for t in NABOO:  # bare name is a hard negative for the "Hey Naboo" model only
        run(t, OUT / "train/bare_naboo_negative" / slug(t), per_adv * 3)
    # held-out evaluation material (other Piper voices, one clip per voice per setting)
    fetch_voices()
    for v in EVAL_VOICES:
        m = VOICES / f"{v}.onnx"
        for t in NABOO:
            run(t, OUT / "eval/naboo" / f"{slug(t)}__{v}", 15, model=m, batch=1)
        for t in HEY_NABOO:
            run(t, OUT / "eval/hey_naboo" / f"{slug(t)}__{v}", 15, model=m, batch=1)
        for t in ADVERSARIAL_EVAL + ADVERSARIAL[:12]:
            run(t, OUT / "eval/adversarial" / f"{slug(t)}__{v}", 4, model=m, batch=1)
    print("SAMPLES READY")


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))

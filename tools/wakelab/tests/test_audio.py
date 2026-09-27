"""Acoustic-stage units that need no network, API key, model download or dataset."""
import numpy as np
import pytest

from wakelab.audio import augment, negatives, summary
from wakelab.audio.detector import SilenceReset
from wakelab.audio.evaluate import _seed


def test_speed_ratios_are_exact():
    x = np.ones(20_000, np.float32)
    assert len(augment.speed(x, 0.85)) == pytest.approx(20_000 * 20 / 17, abs=2)
    assert len(augment.speed(x, 1.15)) == pytest.approx(20_000 * 20 / 23, abs=2)


def test_mix_at_snr_hits_target():
    rng = np.random.default_rng(0)
    speech = rng.standard_normal(16_000).astype(np.float32)
    noise = rng.standard_normal(16_000).astype(np.float32)
    mixed = augment.mix_at_snr(speech, noise, 10)
    added = mixed - speech
    snr = 20 * np.log10(np.sqrt(np.mean(speech ** 2)) / np.sqrt(np.mean(added ** 2)))
    assert snr == pytest.approx(10, abs=0.1)


def test_conditions_are_deterministic_per_seed():
    clip = np.sin(np.linspace(0, 400, 16_000)).astype(np.float32)
    babble = np.random.default_rng(3).standard_normal(64_000).astype(np.float32)
    conds = augment.conditions(babble)
    for fn in conds.values():
        a = fn(clip, np.random.default_rng(_seed("t", "v", "s")))
        b = fn(clip, np.random.default_rng(_seed("t", "v", "s")))
        assert np.array_equal(a, b)


def test_seed_is_stable_across_processes():
    # crc32, not hash(): must never change between runs
    assert _seed("hey aria", "alloy", "neutral", "clean") == _seed("hey aria", "alloy", "neutral", "clean")
    assert _seed("a", "b") != _seed("a", "c")


def test_silence_reset_fires_once_after_speech_then_quiet():
    sr = SilenceReset()
    loud = np.full(1600, 0.2, np.float32)
    quiet = np.zeros(1600, np.float32)
    assert not any(sr.update(quiet) for _ in range(20))  # never heard speech: no reset
    assert not sr.update(loud)
    fired = [sr.update(quiet) for _ in range(SilenceReset.QUIET_CHUNKS + 5)]
    assert fired.count(True) == 1 and fired[SilenceReset.QUIET_CHUNKS - 1]


def test_negatives_dedupe_and_skip_private_and_self():
    report = {"candidate": "hey aria", "pronunciations": [{"role": "intended", "metrics": {
        "exact": [{"text": "hey area"}, {"text": "hey aria"}],
        "near": [{"text": "Hey Area"}, {"text": "secret name", "private": True}],
    }}]}
    got = [t for t, _ in negatives.neighbour_texts(report)]
    assert got == ["hey area", "Hey Area"]
    built = [t.lower() for t, _, _ in negatives.build(report)]
    assert len(built) == len(set(built))
    assert "secret name" not in built and "hey aria" not in built


def _fake_result():
    pos = [{"text": "Hey Aria.", "voice": "v", "style": s, "condition": c, "hits": {"d": ok}}
           for s, c, ok in [("neutral", "clean", True), ("neutral", "quiet_-20dB", False)]]
    neg = [{"text": "hey area", "origin": "neighbour:exact+sentence", "neighbour": "hey area",
            "voice": "v", "condition": "clean", "hits": {"d": True}},
           {"text": "they are here", "origin": "trap", "neighbour": "they are here",
            "voice": "v", "condition": "clean", "hits": {"d": False}}]
    soak = {"hours": 2.0, "utterances": 10, "events": [
        {"detector": "d", "utterance": "u1", "transcript": "the area was quiet"}]}
    return {"candidate": "hey aria", "label": "SYNTHETIC", "tts_model": "m", "spoken_texts": ["Hey Aria."],
            "pron_instruction": "", "detectors": [{"name": "d"}], "conditions": ["clean", "quiet_-20dB"],
            "styles": {"neutral": ""}, "positives": pos, "negatives": neg, "soak": soak}


def test_summary_rates_are_separate_and_correct():
    s = summary.summarize(_fake_result())["d"]
    assert s["positives"] == [1, 2] and s["true_wake_rate"] == 0.5
    assert s["by_condition"] == {"clean": [1, 1], "quiet_-20dB": [0, 1]}
    assert s["adversarial"] == [1, 2]
    assert s["adversarial_by_origin"]["neighbour"] == [1, 1]
    assert s["adversarial_by_origin"]["trap"] == [0, 1]
    assert s["soak_false_wakes_per_hour"] == 0.5
    text = summary.render(_fake_result(), summary.summarize(_fake_result()))
    assert "SYNTHETIC" in text and "the area was quiet" in text

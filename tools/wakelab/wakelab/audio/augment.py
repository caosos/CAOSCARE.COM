"""Deterministic degradations that approximate a real room (SYNTHETIC).

Conditions: quiet speaker, far away (reverb + level drop), steady noise,
TV/other-person speech in the background, faster/slower speech. Each is a
crude approximation of the physical effect and is labelled as such; none
replaces real-room testing. Seeds are fixed per clip for reproducibility.
"""
import numpy as np
from scipy.signal import fftconvolve, resample_poly

SR = 16000


def _rms(x):
    return float(np.sqrt(np.mean(x * x)) + 1e-9)


def gain_db(x, db):
    return (x * 10 ** (db / 20)).astype(np.float32)


def pad(x, lead=0.5, tail=0.8):
    return np.concatenate([np.zeros(int(lead * SR), np.float32), x, np.zeros(int(tail * SR), np.float32)])


def pink_noise(n, rng):
    white = rng.standard_normal(n)
    f = np.fft.rfft(white)
    f /= np.maximum(np.sqrt(np.arange(len(f))), 1.0)
    out = np.fft.irfft(f, n)
    return (out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def mix_at_snr(speech, noise, snr_db):
    noise = np.resize(noise, len(speech)).astype(np.float32)
    scale = _rms(speech) / (_rms(noise) * 10 ** (snr_db / 20))
    return (speech + noise * scale).astype(np.float32)


def reverb(x, rt60=0.6, rng=None):
    """Synthetic exponentially-decaying room impulse response."""
    rng = rng or np.random.default_rng(0)
    n = int(rt60 * SR)
    ir = rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)
    ir[0] = 1.0
    wet = fftconvolve(x, ir)[: len(x)]
    return (wet / (np.abs(wet).max() + 1e-9) * np.abs(x).max()).astype(np.float32)


def speed(x, factor):
    """Tempo change by resampling (also shifts pitch, like a tape speed change)."""
    up, down = 20, int(round(20 * factor))   # 0.85 -> 17/20, 1.15 -> 23/20 exactly
    return resample_poly(x, up, down).astype(np.float32)


def conditions(babble):
    """name -> function(clip, rng) -> degraded clip. `babble` = background speech."""
    return {
        "clean": lambda x, rng: x,
        "quiet_-20dB": lambda x, rng: gain_db(x, -20),
        "far_reverb": lambda x, rng: gain_db(reverb(x, 0.7, rng), -12),
        "noise_snr10": lambda x, rng: mix_at_snr(x, pink_noise(len(x), rng), 10),
        "tv_speech_snr5": lambda x, rng: mix_at_snr(x, babble[rng.integers(0, len(babble)):], 5),
        "slow_0.85x": lambda x, rng: speed(x, 0.85),
        "fast_1.15x": lambda x, rng: speed(x, 1.15),
    }

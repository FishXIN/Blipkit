"""Procedural game sound-effect presets and renderer."""

from __future__ import annotations

import math
import random
from dataclasses import replace

import numpy as np

from .dsp import band_limited_wave, limit_peak, one_pole_lowpass
from .models import SFXPatch


def _patch(name: str, category: str, **values) -> SFXPatch:
    return SFXPatch(name=name, category=category, **values)


PRESETS: dict[str, SFXPatch] = {
    "Click": _patch(
        "Click",
        "UI",
        waveform="Triangle",
        start_freq=900,
        end_freq=620,
        duration=0.08,
        decay=0.025,
        release=0.025,
        lowpass_cutoff=0.72,
        volume=0.62,
    ),
    "Confirm": _patch(
        "Confirm",
        "UI",
        waveform="Sine",
        start_freq=520,
        end_freq=920,
        duration=0.18,
        decay=0.04,
        release=0.08,
    ),
    "Cancel": _patch(
        "Cancel",
        "UI",
        waveform="Triangle",
        start_freq=520,
        end_freq=260,
        duration=0.2,
        release=0.08,
    ),
    "Notification": _patch(
        "Notification",
        "UI",
        waveform="Sine",
        start_freq=660,
        end_freq=990,
        duration=0.3,
        release=0.16,
    ),
    "Error": _patch(
        "Error",
        "UI",
        waveform="Triangle",
        start_freq=240,
        end_freq=145,
        duration=0.28,
        noise=0.04,
        release=0.1,
        lowpass_cutoff=0.58,
    ),
    "Laser": _patch(
        "Laser",
        "战斗",
        waveform="Sawtooth",
        start_freq=1200,
        end_freq=120,
        duration=0.34,
        bend=1.8,
        release=0.08,
        lowpass_cutoff=0.68,
        volume=0.7,
    ),
    "Explosion": _patch(
        "Explosion",
        "战斗",
        waveform="Noise",
        start_freq=150,
        end_freq=45,
        duration=0.7,
        noise=0.95,
        decay=0.24,
        release=0.34,
    ),
    "Impact": _patch(
        "Impact",
        "战斗",
        waveform="Noise",
        start_freq=180,
        end_freq=70,
        duration=0.24,
        noise=0.72,
        release=0.11,
    ),
    "Block": _patch(
        "Block",
        "战斗",
        waveform="Triangle",
        start_freq=380,
        end_freq=210,
        duration=0.22,
        noise=0.22,
        release=0.13,
    ),
    "Magic": _patch(
        "Magic",
        "战斗",
        waveform="Sine",
        start_freq=320,
        end_freq=1500,
        duration=0.75,
        bend=0.65,
        noise=0.08,
        release=0.3,
    ),
    "Footstep Wood": _patch(
        "Footstep Wood",
        "环境",
        waveform="Noise",
        start_freq=170,
        end_freq=95,
        duration=0.16,
        noise=0.75,
        release=0.08,
    ),
    "Footstep Stone": _patch(
        "Footstep Stone",
        "环境",
        waveform="Noise",
        start_freq=260,
        end_freq=120,
        duration=0.12,
        noise=0.62,
        release=0.04,
    ),
    "Door": _patch(
        "Door",
        "环境",
        waveform="Sawtooth",
        start_freq=110,
        end_freq=55,
        duration=0.8,
        noise=0.28,
        attack=0.04,
        release=0.25,
    ),
    "Wind": _patch(
        "Wind",
        "环境",
        waveform="Noise",
        start_freq=340,
        end_freq=180,
        duration=1.4,
        noise=0.9,
        attack=0.25,
        release=0.4,
    ),
    "Water Drop": _patch(
        "Water Drop",
        "自然",
        waveform="Sine",
        start_freq=980,
        end_freq=420,
        duration=0.3,
        bend=1.4,
        release=0.15,
    ),
    "Thunder": _patch(
        "Thunder",
        "自然",
        waveform="Noise",
        start_freq=95,
        end_freq=35,
        duration=1.5,
        noise=1.0,
        attack=0.02,
        decay=0.5,
        release=0.7,
    ),
    "Coin": _patch(
        "Coin",
        "Pickup",
        waveform="Triangle",
        start_freq=880,
        end_freq=1480,
        duration=0.22,
        bend=0.8,
        release=0.08,
        lowpass_cutoff=0.8,
    ),
    "Power Up": _patch(
        "Power Up",
        "Pickup",
        waveform="Square",
        start_freq=260,
        end_freq=1320,
        duration=0.65,
        bend=0.7,
        release=0.15,
        lowpass_cutoff=0.7,
        volume=0.7,
    ),
    "Unlock": _patch(
        "Unlock",
        "Pickup",
        waveform="Triangle",
        start_freq=420,
        end_freq=1080,
        duration=0.4,
        release=0.2,
    ),
    "Pixel Jump": _patch(
        "Pixel Jump",
        "像素风",
        waveform="Square",
        start_freq=260,
        end_freq=760,
        duration=0.24,
        bend=0.72,
        release=0.05,
    ),
    "Pixel Score": _patch(
        "Pixel Score",
        "像素风",
        waveform="Square",
        start_freq=740,
        end_freq=1320,
        duration=0.28,
        bend=0.8,
        release=0.08,
    ),
    "Pixel Fail": _patch(
        "Pixel Fail",
        "像素风",
        waveform="Square",
        start_freq=420,
        end_freq=90,
        duration=0.55,
        bend=1.3,
        release=0.2,
    ),
}


def categories() -> list[str]:
    result = []
    for patch in PRESETS.values():
        if patch.category not in result:
            result.append(patch.category)
    return result


def preset_names(category: str = "") -> list[str]:
    return [name for name, patch in PRESETS.items() if not category or patch.category == category]


def get_preset(name: str) -> SFXPatch:
    source = PRESETS.get(name, PRESETS["Click"])
    return SFXPatch.from_dict(source.to_dict())


def randomize_patch(patch: SFXPatch, seed: int = None) -> SFXPatch:
    actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)
    rng = random.Random(actual_seed)
    return replace(
        patch,
        start_freq=max(30.0, patch.start_freq * rng.uniform(0.82, 1.18)),
        end_freq=max(25.0, patch.end_freq * rng.uniform(0.82, 1.18)),
        bend=max(0.2, patch.bend * rng.uniform(0.78, 1.22)),
        duration=max(0.04, patch.duration * rng.uniform(0.85, 1.15)),
        noise=min(1.0, max(0.0, patch.noise + rng.uniform(-0.1, 0.1))),
        vibrato_depth=min(
            2.0,
            max(0.0, patch.vibrato_depth + rng.uniform(-0.16, 0.16)),
        ),
        vibrato_rate=min(
            24.0,
            max(0.1, patch.vibrato_rate * rng.uniform(0.82, 1.18)),
        ),
        lowpass_cutoff=min(
            1.0,
            max(0.05, patch.lowpass_cutoff + rng.uniform(-0.1, 0.1)),
        ),
        crush=min(1.0, max(0.0, patch.crush + rng.uniform(-0.08, 0.08))),
        seed=actual_seed,
    )


def mutate_patch(
    patch: SFXPatch,
    seed: int | None = None,
    amount: float = 0.06,
) -> SFXPatch:
    actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)
    rng = random.Random(actual_seed)
    spread = max(0.01, min(0.25, amount))

    def scale(value: float, minimum: float, maximum: float) -> float:
        return min(maximum, max(minimum, value * rng.uniform(1.0 - spread, 1.0 + spread)))

    def offset(value: float, minimum: float, maximum: float) -> float:
        return min(maximum, max(minimum, value + rng.uniform(-spread, spread)))

    return replace(
        patch,
        start_freq=scale(patch.start_freq, 30.0, 2400.0),
        end_freq=scale(patch.end_freq, 20.0, 2400.0),
        bend=scale(patch.bend, 0.2, 3.0),
        duration=scale(patch.duration, 0.04, 2.0),
        noise=offset(patch.noise, 0.0, 1.0),
        vibrato_depth=offset(patch.vibrato_depth, 0.0, 2.0),
        vibrato_rate=scale(patch.vibrato_rate, 0.1, 24.0),
        lowpass_cutoff=offset(patch.lowpass_cutoff, 0.05, 1.0),
        crush=offset(patch.crush, 0.0, 1.0),
        seed=actual_seed,
    )


def _adsr(patch: SFXPatch, frames: int, sample_rate: int) -> np.ndarray:
    attack = min(frames, max(1, int(patch.attack * sample_rate)))
    decay = min(max(0, frames - attack), max(1, int(patch.decay * sample_rate)))
    release = min(max(1, frames - attack - decay), max(1, int(patch.release * sample_rate)))
    sustain_start = min(frames, attack + decay)
    release_start = max(sustain_start, frames - release)
    env = np.full(frames, patch.sustain, dtype=np.float32)
    env[:attack] = np.linspace(0.0, 1.0, attack, dtype=np.float32)
    if decay:
        env[attack:sustain_start] = np.linspace(1.0, patch.sustain, decay, dtype=np.float32)
    env[release_start:] = np.linspace(patch.sustain, 0.0, frames - release_start, dtype=np.float32)
    return env


def synthesize(patch: SFXPatch, sample_rate: int = 44100) -> np.ndarray:
    frames = max(16, int(max(0.03, patch.duration) * sample_rate))
    t = np.linspace(0.0, 1.0, frames, endpoint=False, dtype=np.float64)
    curve = np.power(t, max(0.08, patch.bend))
    frequency = patch.start_freq + (patch.end_freq - patch.start_freq) * curve
    if patch.vibrato_depth > 0.0:
        seconds = np.arange(frames, dtype=np.float64) / float(sample_rate)
        vibrato = np.sin(2.0 * np.pi * max(0.1, patch.vibrato_rate) * seconds)
        frequency *= np.power(2.0, patch.vibrato_depth * vibrato / 12.0)
    phase_step = frequency / sample_rate
    cycle = np.cumsum(phase_step)
    waveform = patch.waveform.lower()
    if waveform == "noise":
        tone = np.zeros(frames, dtype=np.float64)
    else:
        tone = band_limited_wave(cycle, phase_step, waveform)

    rng = np.random.default_rng(patch.seed)
    noise = rng.uniform(-1.0, 1.0, frames)
    noise_amount = patch.noise if waveform != "noise" else 1.0
    signal = tone * (1.0 - noise_amount * 0.75) + noise * noise_amount

    if noise_amount > 0.2:
        noise_cutoff = max(500.0, min(9000.0, patch.start_freq * 5.0))
        signal = one_pole_lowpass(signal, noise_cutoff, sample_rate)

    if patch.lowpass_cutoff < 0.995:
        amount = max(0.05, min(1.0, patch.lowpass_cutoff))
        cutoff = 180.0 + amount**2 * (sample_rate * 0.42 - 180.0)
        signal = one_pole_lowpass(signal, cutoff, sample_rate)

    if patch.crush > 0.001:
        bits = max(3, int(round(16 - min(1.0, patch.crush) * 12)))
        levels = float(2 ** (bits - 1))
        signal = np.round(signal * levels) / levels

    signal *= _adsr(patch, frames, sample_rate)
    signal *= min(1.0, max(0.0, patch.volume))
    signal = limit_peak(signal, ceiling=0.92)
    if not np.all(np.isfinite(signal)):
        raise ValueError("SFX synthesis produced invalid samples")
    return signal.astype(np.float32)


def waveform_preview(samples: np.ndarray, points: int = 240) -> list[float]:
    data = np.asarray(samples, dtype=np.float32).reshape(-1)
    if not len(data):
        return [0.0] * points
    step = max(1, int(math.ceil(len(data) / float(points))))
    result = []
    for start in range(0, len(data), step):
        window = data[start : start + step]
        peak = float(window[np.argmax(np.abs(window))]) if len(window) else 0.0
        result.append(peak)
    if len(result) < points:
        result.extend([0.0] * (points - len(result)))
    return result[:points]

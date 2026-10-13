"""Procedural game sound-effect presets and renderer."""

from __future__ import annotations

import math
import random
from dataclasses import replace

import numpy as np

from .dsp import band_limited_wave, limit_peak, one_pole_lowpass
from .models import SFXPatch
from .sfx_graph import apply_graph_template, synthesize_graph, vary_graph_nodes

EXCITERS = ("Tone", "Impact", "Scrape", "Drop", "Flow")
MATERIALS = ("Synthetic", "Metal", "Glass", "Wood", "Water")
BODIES = ("Open", "Plate", "Tube", "Cavity", "Vessel")
SPACES = ("Dry", "Room", "Hall", "Underwater")


def _patch(name: str, category: str, **values) -> SFXPatch:
    graph_template = values.pop("graph_template", "")
    patch = SFXPatch(name=name, category=category, **values)
    if graph_template:
        apply_graph_template(patch, graph_template)
    return patch


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
        exciter="Drop",
        material="Water",
        body="Vessel",
        space="Room",
        graph_template="water_drop",
        hardness=0.48,
        body_size=0.34,
        damping=0.42,
        texture=0.28,
        space_amount=0.12,
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
    "Metal Plate": _patch(
        "Metal Plate",
        "材质",
        waveform="Sine",
        exciter="Impact",
        material="Metal",
        body="Plate",
        space="Room",
        graph_template="metal_plate",
        hardness=0.82,
        body_size=0.58,
        damping=0.18,
        texture=0.22,
        space_amount=0.16,
        start_freq=360,
        end_freq=270,
        duration=1.25,
        attack=0.001,
        decay=0.12,
        sustain=0.32,
        release=0.72,
        noise=0.05,
        lowpass_cutoff=0.92,
        volume=0.68,
    ),
    "Metal Tube": _patch(
        "Metal Tube",
        "材质",
        waveform="Sine",
        exciter="Impact",
        material="Metal",
        body="Tube",
        space="Room",
        graph_template="metal_tube",
        hardness=0.72,
        body_size=0.72,
        damping=0.24,
        texture=0.12,
        space_amount=0.2,
        start_freq=280,
        end_freq=210,
        duration=1.15,
        attack=0.001,
        decay=0.16,
        sustain=0.3,
        release=0.68,
        noise=0.04,
        volume=0.7,
    ),
    "Glass Hit": _patch(
        "Glass Hit",
        "材质",
        waveform="Sine",
        exciter="Impact",
        material="Glass",
        body="Vessel",
        space="Room",
        graph_template="glass_hit",
        hardness=0.9,
        body_size=0.42,
        damping=0.16,
        texture=0.08,
        space_amount=0.18,
        start_freq=620,
        end_freq=460,
        duration=1.0,
        attack=0.001,
        decay=0.1,
        sustain=0.26,
        release=0.62,
        volume=0.62,
    ),
    "Wood Knock": _patch(
        "Wood Knock",
        "材质",
        waveform="Triangle",
        exciter="Impact",
        material="Wood",
        body="Cavity",
        space="Dry",
        graph_template="wood_knock",
        hardness=0.42,
        body_size=0.64,
        damping=0.72,
        texture=0.34,
        start_freq=210,
        end_freq=125,
        duration=0.34,
        attack=0.001,
        decay=0.08,
        sustain=0.18,
        release=0.16,
        noise=0.12,
        lowpass_cutoff=0.58,
        volume=0.76,
    ),
    "Water Flow": _patch(
        "Water Flow",
        "材质",
        waveform="Noise",
        exciter="Flow",
        material="Water",
        body="Open",
        space="Room",
        graph_template="water_flow",
        hardness=0.28,
        body_size=0.62,
        damping=0.52,
        texture=0.76,
        space_amount=0.12,
        start_freq=760,
        end_freq=420,
        duration=1.8,
        attack=0.12,
        decay=0.2,
        sustain=0.78,
        release=0.32,
        noise=0.72,
        lowpass_cutoff=0.74,
        volume=0.64,
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
        hardness=min(1.0, max(0.0, patch.hardness + rng.uniform(-0.12, 0.12))),
        body_size=min(1.0, max(0.0, patch.body_size + rng.uniform(-0.12, 0.12))),
        damping=min(1.0, max(0.0, patch.damping + rng.uniform(-0.12, 0.12))),
        texture=min(1.0, max(0.0, patch.texture + rng.uniform(-0.12, 0.12))),
        space_amount=min(
            1.0,
            max(0.0, patch.space_amount + rng.uniform(-0.08, 0.08)),
        ),
        graph_nodes=(
            vary_graph_nodes(patch.graph_nodes, rng, 0.1)
            if patch.graph_nodes
            else []
        ),
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
        hardness=offset(patch.hardness, 0.0, 1.0),
        body_size=offset(patch.body_size, 0.0, 1.0),
        damping=offset(patch.damping, 0.0, 1.0),
        texture=offset(patch.texture, 0.0, 1.0),
        space_amount=offset(patch.space_amount, 0.0, 1.0),
        graph_nodes=(
            vary_graph_nodes(patch.graph_nodes, rng, spread)
            if patch.graph_nodes
            else []
        ),
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


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return min(maximum, max(minimum, float(value)))


def _oscillator_signal(
    patch: SFXPatch,
    frames: int,
    sample_rate: int,
    rng: np.random.Generator,
) -> np.ndarray:
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

    noise = rng.uniform(-1.0, 1.0, frames)
    noise_amount = patch.noise if waveform != "noise" else 1.0
    signal = tone * (1.0 - noise_amount * 0.75) + noise * noise_amount

    if noise_amount > 0.2:
        noise_cutoff = max(500.0, min(9000.0, patch.start_freq * 5.0))
        signal = one_pole_lowpass(signal, noise_cutoff, sample_rate)
    return signal


def _excitation_signal(
    patch: SFXPatch,
    frames: int,
    sample_rate: int,
    rng: np.random.Generator,
) -> np.ndarray:
    exciter = patch.exciter.lower()
    if exciter == "tone":
        return _oscillator_signal(patch, frames, sample_rate, rng)

    seconds = np.arange(frames, dtype=np.float64) / float(sample_rate)
    hardness = _clamp(patch.hardness)
    texture = _clamp(patch.texture)
    white = rng.uniform(-1.0, 1.0, frames)

    if exciter == "impact":
        burst_time = 0.004 + (1.0 - hardness) * 0.024
        burst = np.exp(-seconds / burst_time)
        thump_frequency = max(35.0, min(220.0, patch.start_freq * 0.24))
        thump = np.sin(2.0 * np.pi * thump_frequency * seconds)
        thump *= np.exp(-seconds / (0.035 + 0.08 * (1.0 - hardness)))
        return white * burst * (0.55 + hardness * 0.45) + thump * 0.35

    if exciter == "scrape":
        low = one_pole_lowpass(white, 260.0 + texture * 740.0, sample_rate)
        rough = white - low * (0.72 - texture * 0.28)
        grain_rate = 18.0 + texture * 72.0
        grains = 0.28 + 0.72 * np.maximum(
            0.0,
            np.sin(2.0 * np.pi * grain_rate * seconds),
        )
        return rough * grains

    if exciter == "drop":
        frequency = np.linspace(
            max(80.0, patch.start_freq),
            max(45.0, patch.end_freq),
            frames,
            dtype=np.float64,
        )
        phase = np.cumsum(frequency / sample_rate)
        ring = np.sin(2.0 * np.pi * phase)
        envelope = np.exp(-seconds / (0.045 + (1.0 - hardness) * 0.16))
        click = white * np.exp(-seconds / 0.006)
        return ring * envelope + click * (0.12 + hardness * 0.24)

    cutoff = 700.0 + hardness * 5200.0
    flow = one_pole_lowpass(white, cutoff, sample_rate)
    motion = (
        0.68
        + 0.18 * np.sin(2.0 * np.pi * (0.7 + texture * 1.4) * seconds)
        + 0.14 * np.sin(2.0 * np.pi * (2.3 + texture * 3.2) * seconds + 0.8)
    )
    return flow * motion


def _mode_ratios(material: str, body: str) -> tuple[float, ...]:
    ratios = {
        "metal": (1.0, 2.71, 5.18, 8.43, 12.1, 16.8),
        "glass": (1.0, 2.32, 4.25, 6.63, 9.38),
        "wood": (1.0, 1.47, 2.09, 2.93, 3.74),
        "synthetic": (1.0, 2.0, 3.0, 4.0, 5.0),
    }.get(material, (1.0, 2.0, 3.0, 4.0))
    if body == "tube":
        return (1.0, 2.02, 3.01, 4.03, 5.05, 6.08)
    if body == "cavity":
        return (0.54, *ratios[:4])
    if body == "vessel":
        return (0.78, 1.0, 2.32, 4.25, 6.63)
    if body == "plate":
        return tuple(ratio * factor for ratio, factor in zip(
            ratios,
            (1.0, 1.06, 0.94, 1.11, 0.91, 1.04),
            strict=False,
        ))
    return ratios


def _modal_material_signal(
    patch: SFXPatch,
    frames: int,
    sample_rate: int,
    rng: np.random.Generator,
) -> np.ndarray:
    seconds = np.arange(frames, dtype=np.float64) / float(sample_rate)
    source = _excitation_signal(patch, frames, sample_rate, rng)
    material = patch.material.lower()
    body = patch.body.lower()
    hardness = _clamp(patch.hardness)
    damping = _clamp(patch.damping)
    texture = _clamp(patch.texture)
    size_scale = 2.0 ** ((0.5 - _clamp(patch.body_size)) * 2.2)
    base_frequency = max(35.0, min(sample_rate * 0.18, patch.start_freq * size_scale))
    continuous = patch.exciter.lower() in {"tone", "scrape", "flow"}
    material_decay = {
        "metal": 1.5,
        "glass": 1.18,
        "wood": 0.38,
        "synthetic": 0.72,
    }.get(material, 0.72)
    base_decay = (0.08 + (1.0 - damping) ** 2 * 1.85) * material_decay

    modes = np.zeros(frames, dtype=np.float64)
    amplitude_total = 0.0
    for index, ratio in enumerate(_mode_ratios(material, body)):
        frequency = base_frequency * ratio
        if frequency >= sample_rate * 0.46:
            continue
        high_mode_gain = 0.62 - hardness * 0.3
        amplitude = 1.0 / (1.0 + index * high_mode_gain)
        phase = rng.uniform(0.0, 2.0 * np.pi)
        if continuous:
            mode_envelope = np.ones(frames, dtype=np.float64)
        else:
            decay_time = base_decay / (1.0 + index * (0.1 + damping * 0.2))
            mode_envelope = np.exp(-seconds / max(0.012, decay_time))
        modes += np.sin(2.0 * np.pi * frequency * seconds + phase) * mode_envelope * amplitude
        amplitude_total += amplitude
    if amplitude_total:
        modes /= amplitude_total

    source_gain = 0.16 + texture * 0.3
    signal = modes * (0.92 - source_gain * 0.35) + source * source_gain
    if material == "wood":
        cutoff = 900.0 + hardness * 3600.0
        signal = one_pole_lowpass(signal, cutoff, sample_rate)
    return signal


def _water_signal(
    patch: SFXPatch,
    frames: int,
    sample_rate: int,
    rng: np.random.Generator,
) -> np.ndarray:
    seconds = np.arange(frames, dtype=np.float64) / float(sample_rate)
    hardness = _clamp(patch.hardness)
    texture = _clamp(patch.texture)
    damping = _clamp(patch.damping)
    source = _excitation_signal(patch, frames, sample_rate, rng)
    exciter = patch.exciter.lower()
    signal = source * (0.5 if exciter == "flow" else 0.22)

    if exciter == "drop":
        event_count = 1 + int(round(texture * 3.0))
        starts = [0.0]
        starts.extend(
            sorted(rng.uniform(0.035, max(0.04, patch.duration * 0.72), event_count - 1))
        )
    elif exciter == "flow":
        event_count = 7 + int(round(texture * 18.0))
        starts = sorted(rng.uniform(0.0, max(0.02, patch.duration * 0.92), event_count))
    else:
        event_count = 3 + int(round(texture * 10.0))
        starts = sorted(rng.uniform(0.0, max(0.02, patch.duration * 0.7), event_count))

    size_scale = 2.0 ** ((0.5 - _clamp(patch.body_size)) * 1.5)
    base_frequency = max(90.0, patch.start_freq * size_scale)
    for index, start in enumerate(starts):
        start_frame = min(frames - 1, max(0, int(start * sample_rate)))
        local = seconds[start_frame:] - start
        frequency = base_frequency * rng.uniform(0.72, 1.36)
        sweep_time = 0.018 + rng.uniform(0.015, 0.08) + damping * 0.025
        phase = 2.0 * np.pi * frequency * sweep_time * (
            1.0 - np.exp(-local / sweep_time)
        )
        lifetime = 0.035 + rng.uniform(0.025, 0.13) + (1.0 - damping) * 0.08
        envelope = (1.0 - np.exp(-local * 240.0)) * np.exp(-local / lifetime)
        amplitude = rng.uniform(0.28, 0.72) / (1.0 + index * 0.035)
        signal[start_frame:] += np.sin(phase) * envelope * amplitude

    if exciter == "flow":
        background = rng.uniform(-1.0, 1.0, frames)
        cutoff = 900.0 + hardness * 4800.0
        background = one_pole_lowpass(background, cutoff, sample_rate)
        signal += background * (0.24 + texture * 0.22)
    if patch.body.lower() == "vessel":
        vessel_frequency = max(55.0, base_frequency * 0.42)
        vessel = np.sin(2.0 * np.pi * vessel_frequency * seconds)
        vessel *= np.exp(-seconds / (0.08 + (1.0 - damping) * 0.42))
        signal += vessel * 0.18
    return signal


def _apply_space(
    signal: np.ndarray,
    patch: SFXPatch,
    sample_rate: int,
) -> np.ndarray:
    amount = _clamp(patch.space_amount)
    space = patch.space.lower()
    if amount <= 0.001 or space == "dry":
        return signal
    source = signal
    if space == "underwater":
        source = one_pole_lowpass(source, 420.0 + 1200.0 * (1.0 - amount), sample_rate)
        taps = ((0.028, 0.42), (0.061, 0.26), (0.097, 0.16))
    elif space == "hall":
        taps = ((0.043, 0.5), (0.071, 0.37), (0.109, 0.28), (0.157, 0.2))
    else:
        taps = ((0.017, 0.45), (0.031, 0.3), (0.047, 0.18))

    wet = np.zeros_like(source, dtype=np.float64)
    for delay_seconds, gain in taps:
        delay = max(1, int(delay_seconds * sample_rate))
        if delay < len(source):
            wet[delay:] += source[:-delay] * gain
    return source * (1.0 - amount * 0.24) + wet * amount


def _finish_signal(
    signal: np.ndarray,
    patch: SFXPatch,
    frames: int,
    sample_rate: int,
) -> np.ndarray:

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
    signal = _apply_space(signal, patch, sample_rate)
    signal = limit_peak(signal, ceiling=0.92)
    if not np.all(np.isfinite(signal)):
        raise ValueError("SFX synthesis produced invalid samples")
    return signal.astype(np.float32)


def synthesize(patch: SFXPatch, sample_rate: int = 44100) -> np.ndarray:
    if patch.graph_enabled and patch.graph_nodes:
        return synthesize_graph(patch, sample_rate=sample_rate)
    frames = max(16, int(max(0.03, patch.duration) * sample_rate))
    rng = np.random.default_rng(patch.seed)
    legacy_chain = (
        patch.exciter == "Tone"
        and patch.material == "Synthetic"
        and patch.body == "Open"
        and patch.space == "Dry"
    )
    if legacy_chain:
        signal = _oscillator_signal(patch, frames, sample_rate, rng)
    elif patch.material.lower() == "water":
        signal = _water_signal(patch, frames, sample_rate, rng)
    else:
        signal = _modal_material_signal(patch, frames, sample_rate, rng)
    return _finish_signal(signal, patch, frames, sample_rate)


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

"""Small dependency-free DSP helpers shared by the procedural renderers."""

from __future__ import annotations

import numpy as np


def _poly_blep(cycle: np.ndarray, phase_step: np.ndarray | float) -> np.ndarray:
    """Smooth a discontinuity over one sample to reduce oscillator aliasing."""
    step = np.clip(np.asarray(phase_step, dtype=np.float64), 1e-9, 0.5)
    correction = np.zeros_like(cycle, dtype=np.float64)

    leading = cycle < step
    position = np.divide(cycle, step, out=np.zeros_like(cycle), where=leading)
    correction[leading] = (
        position[leading] + position[leading] - position[leading] ** 2 - 1.0
    )

    trailing = cycle > 1.0 - step
    position = np.divide(
        cycle - 1.0,
        step,
        out=np.zeros_like(cycle),
        where=trailing,
    )
    correction[trailing] = (
        position[trailing] ** 2 + position[trailing] + position[trailing] + 1.0
    )
    return correction


def band_limited_wave(
    cycle: np.ndarray,
    phase_step: np.ndarray | float,
    waveform: str,
    *,
    duty: float = 0.5,
) -> np.ndarray:
    """Render common oscillators without the hard edges of naive waveforms."""
    phase = np.mod(np.asarray(cycle, dtype=np.float64), 1.0)
    name = waveform.lower()
    if name in {"saw", "sawtooth"}:
        return 2.0 * phase - 1.0 - _poly_blep(phase, phase_step)
    if name == "square":
        duty = max(0.08, min(0.92, float(duty)))
        result = np.where(phase < duty, 1.0, -1.0)
        result += _poly_blep(phase, phase_step)
        result -= _poly_blep(np.mod(phase - duty, 1.0), phase_step)
        result -= 2.0 * duty - 1.0
        peak = float(np.max(np.abs(result)))
        return result / peak if peak > 1e-9 else result
    if name == "triangle":
        return (2.0 / np.pi) * np.arcsin(np.sin(2.0 * np.pi * phase))
    return np.sin(2.0 * np.pi * phase)


def one_pole_lowpass(
    samples: np.ndarray,
    cutoff_hz: float,
    sample_rate: int,
) -> np.ndarray:
    """Apply a stable one-pole low-pass without adding a heavy DSP dependency."""
    data = np.asarray(samples, dtype=np.float64)
    if not len(data):
        return data
    cutoff = max(20.0, min(float(cutoff_hz), sample_rate * 0.45))
    coefficient = 1.0 - np.exp(-2.0 * np.pi * cutoff / sample_rate)
    output = np.empty_like(data)
    output[0] = data[0]
    for index in range(1, len(data)):
        output[index] = output[index - 1] + coefficient * (
            data[index] - output[index - 1]
        )
    return output


def limit_peak(samples: np.ndarray, ceiling: float = 0.94) -> np.ndarray:
    """Apply transparent global gain reduction only when a signal would clip."""
    data = np.asarray(samples, dtype=np.float64)
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak > ceiling:
        data = data * (ceiling / peak)
    return data.astype(np.float32)

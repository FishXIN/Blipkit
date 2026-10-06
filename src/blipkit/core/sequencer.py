"""Offline renderer for Blipkit piano-roll songs."""

from __future__ import annotations

import math

import numpy as np

from .dsp import band_limited_wave, limit_peak, one_pole_lowpass
from .models import Note, Song, Track
from .soundbank import InstrumentPreset, get_preset


def midi_to_frequency(note: int) -> float:
    return 440.0 * (2.0 ** ((int(note) - 69) / 12.0))


def _oscillator(
    frequency: float,
    seconds: float,
    sample_rate: int,
    preset: InstrumentPreset,
    seed: int,
) -> np.ndarray:
    frames = max(1, int(seconds * sample_rate))
    t = np.arange(frames, dtype=np.float64) / float(sample_rate)
    instantaneous_frequency = np.full(frames, frequency, dtype=np.float64)
    if preset.vibrato_cents:
        vibrato = np.sin(2.0 * np.pi * preset.vibrato_rate * t)
        instantaneous_frequency *= np.power(
            2.0,
            preset.vibrato_cents * vibrato / 1200.0,
        )
    phase_step = instantaneous_frequency / float(sample_rate)
    cycle = np.cumsum(phase_step)
    waveform = preset.waveform
    duty = 0.25 if "25%" in preset.name else 0.125 if "12%" in preset.name else 0.5
    rng = np.random.default_rng(seed)
    if waveform == "noise":
        data = rng.uniform(-1.0, 1.0, frames)
        cutoff = (
            6200.0 + preset.brightness * 4200.0
            if "hi-hat" in preset.name.lower()
            else 2200.0 + preset.brightness * 5000.0
        )
        data = one_pole_lowpass(data, cutoff, sample_rate)
    else:
        colored = band_limited_wave(cycle, phase_step, waveform, duty=duty)
        sine = np.sin(2.0 * np.pi * cycle)
        color_mix = 0.16 + 0.72 * preset.brightness
        data = sine * (1.0 - color_mix) + colored * color_mix
        if preset.detune_cents:
            spread = []
            for cents in (-preset.detune_cents, preset.detune_cents):
                ratio = 2.0 ** (cents / 1200.0)
                detuned_step = phase_step * ratio
                detuned_cycle = np.cumsum(detuned_step)
                spread.append(
                    band_limited_wave(
                        detuned_cycle,
                        detuned_step,
                        waveform,
                        duty=duty,
                    )
                )
            data = data * 0.66 + spread[0] * 0.17 + spread[1] * 0.17

    lower = preset.name.lower()
    phase = 2.0 * np.pi * cycle
    if preset.name in ("Rhodes Electric Piano", "Wurlitzer"):
        bell = 0.1 + preset.brightness * 0.12
        data = (
            (0.88 - bell) * np.sin(phase)
            + bell * np.sin(phase * 2.0)
            + 0.06 * np.sin(phase * 4.0)
        )
        data *= np.exp(-t * (0.7 + preset.brightness * 0.45))
        data *= 1.0 + 0.025 * np.sin(2.0 * np.pi * 4.6 * t)
    elif "piano" in lower:
        upper = 0.12 + preset.brightness * 0.16
        data = (
            (0.84 - upper) * np.sin(phase)
            + upper * np.sin(phase * 2.0)
            + (0.06 + preset.brightness * 0.05) * np.sin(phase * 3.0)
            + (0.025 + preset.brightness * 0.035) * np.sin(phase * 4.05)
        )
        damping = (
            1.35 + preset.brightness * 0.5
            if "soft" in lower or "mellow" in lower
            else 1.7 + preset.brightness * 0.8
        )
        data *= np.exp(-t * damping)
        data += (
            rng.normal(0.0, 0.008 + preset.brightness * 0.018, frames)
            * np.exp(-t * 55.0)
        )
    elif preset.name in ("Celesta", "Music Box", "Glockenspiel"):
        upper = 0.14 + preset.brightness * 0.12
        data = (
            (0.86 - upper) * np.sin(phase)
            + upper * np.sin(phase * 2.01)
            + (0.06 + preset.brightness * 0.08) * np.sin(phase * 3.98)
        )
        data *= np.exp(-t * (2.4 + preset.brightness))
    elif preset.name in (
        "Clavinet",
        "Harpsichord",
        "Harp",
        "Mandolin",
        "Acoustic Guitar",
        "Pipa",
        "Guzheng",
        "Koto",
    ):
        upper = 0.12 + preset.brightness * 0.16
        data = (
            (0.9 - upper) * data
            + upper * np.sin(phase * 2.0)
            + (0.04 + preset.brightness * 0.08) * np.sin(phase * 3.0)
        )
        data *= np.exp(-t * (1.55 + preset.brightness * 0.8))
        data += rng.normal(0.0, 0.012, frames) * np.exp(-t * 70.0)
    elif preset.category == "Strings":
        data = 0.76 * data + 0.16 * np.sin(phase * 2.0) + 0.08 * np.sin(phase * 3.0)
    elif preset.category == "Woodwind" or preset.name in ("Dizi", "Shakuhachi"):
        breath = one_pole_lowpass(
            rng.normal(0.0, 1.0, frames),
            4800.0 + preset.brightness * 3200.0,
            sample_rate,
        )
        upper = 0.035 + preset.brightness * 0.14
        data = (
            (0.96 - upper) * np.sin(phase)
            + upper * np.sin(phase * 2.0)
            + (0.009 + preset.brightness * 0.025) * breath
        )
    elif preset.category == "Brass":
        data = 0.72 * data + 0.2 * np.sin(phase) + 0.08 * np.sin(phase * 2.0)
    elif "organ" in lower or preset.name in ("Accordion", "Harmonica"):
        upper = 0.12 + preset.brightness * 0.18
        data = (
            (0.86 - upper) * np.sin(phase)
            + upper * np.sin(phase * 2.0)
            + (0.06 + preset.brightness * 0.1) * np.sin(phase * 3.0)
        )
    rms = float(np.sqrt(np.mean(np.square(data)))) if len(data) else 0.0
    if rms > 1e-9:
        data *= min(1.8, 0.48 / rms)
    return limit_peak(data, ceiling=0.98)


def _envelope(
    frames: int,
    sample_rate: int,
    attack: float,
    decay: float,
    release: float,
    sustain_level: float,
) -> np.ndarray:
    env = np.full(frames, sustain_level, dtype=np.float64)
    attack_frames = min(frames, max(1, int(attack * sample_rate)))
    release_frames = min(max(1, frames - attack_frames), max(1, int(release * sample_rate)))
    release_start = max(attack_frames, frames - release_frames)
    decay_frames = min(
        max(0, release_start - attack_frames),
        max(1, int(decay * sample_rate)),
    )
    env[:attack_frames] = np.sin(
        np.linspace(0.0, np.pi / 2.0, attack_frames, dtype=np.float64)
    ) ** 2
    decay_end = attack_frames + decay_frames
    if decay_frames:
        env[attack_frames:decay_end] = np.linspace(
            1.0,
            sustain_level,
            decay_frames,
            dtype=np.float64,
        )
    if release_start > decay_end:
        env[decay_end:release_start] = sustain_level
    release_level = env[release_start - 1] if release_start else sustain_level
    env[release_start:] = release_level * np.cos(
        np.linspace(0.0, np.pi / 2.0, frames - release_start, dtype=np.float64)
    )
    return env.astype(np.float32)


def render_note(
    note: Note,
    bpm: int,
    preset: InstrumentPreset,
    sample_rate: int = 44100,
) -> np.ndarray:
    seconds_per_beat = 60.0 / max(20, int(bpm))
    body_seconds = max(0.02, note.duration * seconds_per_beat)
    total_seconds = body_seconds + preset.release
    data = _oscillator(
        midi_to_frequency(note.pitch),
        total_seconds,
        sample_rate,
        preset,
        seed=note.pitch * 1009 + int(note.start * 100),
    )
    env = _envelope(
        len(data),
        sample_rate,
        preset.attack,
        preset.decay,
        preset.release,
        sustain_level=preset.sustain,
    )
    velocity_gain = (max(1, min(127, note.velocity)) / 127.0) ** 0.75
    return data * env * velocity_gain * 0.82


def render_track(
    track: Track,
    bpm: int,
    total_beats: float,
    sample_rate: int = 44100,
) -> np.ndarray:
    total_seconds = total_beats * 60.0 / max(20, int(bpm))
    frames = max(1, int(total_seconds * sample_rate))
    output = np.zeros(frames, dtype=np.float32)
    if track.muted:
        return output
    preset = get_preset(track.instrument)
    for note in track.notes:
        start = int(note.start * 60.0 / bpm * sample_rate)
        if start >= frames:
            continue
        rendered = render_note(note, bpm, preset, sample_rate)
        end = min(frames, start + len(rendered))
        if end > start:
            output[start:end] += rendered[: end - start] * track.volume
    return output


def render_song(
    song: Song,
    sample_rate: int = 44100,
    loop_only: bool = False,
    stereo: bool = True,
) -> np.ndarray:
    total_beats = max(float(song.bars * 4), float(song.loop_end))
    frames = max(1, int(total_beats * 60.0 / song.bpm * sample_rate))
    solo_tracks = [track for track in song.tracks if track.soloed and not track.muted]
    active_tracks = solo_tracks or [track for track in song.tracks if not track.muted]
    layers = [
        render_track(track, song.bpm, total_beats, sample_rate)
        for track in active_tracks
    ]

    if stereo:
        mix = np.zeros((frames, 2), dtype=np.float32)
        pans = np.linspace(-0.24, 0.24, len(layers)) if len(layers) > 1 else [0.0]
        for layer, pan in zip(layers, pans, strict=True):
            left_gain = math.sqrt(1.0 - float(pan))
            right_gain = math.sqrt(1.0 + float(pan))
            mix[: len(layer), 0] += layer * left_gain
            mix[: len(layer), 1] += layer * right_gain
        mix = limit_peak(mix)
    else:
        mix = np.zeros(frames, dtype=np.float32)
        for layer in layers:
            mix[: len(layer)] += layer
        mix = limit_peak(mix)

    if loop_only:
        start = int(song.loop_start * 60.0 / song.bpm * sample_rate)
        end = int(song.loop_end * 60.0 / song.bpm * sample_rate)
        mix = mix[max(0, start) : max(start + 1, min(len(mix), end))]

    return mix


def song_duration(song: Song, loop_only: bool = False) -> float:
    beats = song.loop_end - song.loop_start if loop_only else max(song.bars * 4, song.loop_end)
    return max(0.0, beats) * 60.0 / max(20, song.bpm)


def preview_track(
    song: Song,
    track_id: str | None = None,
    sample_rate: int = 44100,
) -> np.ndarray:
    if not track_id:
        return render_song(song, sample_rate=sample_rate, loop_only=True)
    selected = [track for track in song.tracks if track.id == track_id]
    shadow = Song.from_dict(song.to_dict())
    shadow.tracks = selected
    return render_song(shadow, sample_rate=sample_rate, loop_only=True)

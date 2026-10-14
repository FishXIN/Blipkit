"""Offline renderer for Blipkit piano-roll songs."""

from __future__ import annotations

import math

import numpy as np

from .dsp import band_limited_wave, limit_peak, one_pole_lowpass
from .models import Note, Song, Track
from .sample_engine import (
    is_available as sample_engine_available,
)
from .sample_engine import (
    render_sampled_note,
    render_sampled_track_layers,
    render_sampled_tracks,
    uses_samples,
)
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
    if uses_samples(preset) and sample_engine_available():
        return render_sampled_note(note, bpm, preset, sample_rate)
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
    *,
    ignore_mute: bool = False,
) -> np.ndarray:
    total_seconds = total_beats * 60.0 / max(20, int(bpm))
    frames = max(1, int(total_seconds * sample_rate))
    output = np.zeros(frames, dtype=np.float32)
    if track.muted and not ignore_mute:
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


def _master_output(mix: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if 1e-9 < peak < 0.82:
        mix = mix * min(1.5, 0.82 / peak)
    return limit_peak(mix)


def render_song_stems(
    song: Song,
    sample_rate: int = 44100,
) -> tuple[np.ndarray, ...]:
    total_beats = max(song.total_beats, float(song.loop_end))
    frames = max(1, int(total_beats * 60.0 / song.bpm * sample_rate))
    stems = [
        np.zeros((frames, 2), dtype=np.float32)
        for _track in song.tracks
    ]
    sampled_entries: list[tuple[int, Track]] = []
    procedural_entries: list[tuple[int, Track]] = []
    sampled_enabled = sample_engine_available()
    for index, track in enumerate(song.tracks):
        preset = get_preset(track.instrument)
        if sampled_enabled and uses_samples(preset):
            sampled_entries.append((index, track))
        else:
            procedural_entries.append((index, track))

    sampled_layers = render_sampled_track_layers(
        [track for _index, track in sampled_entries],
        song.bpm,
        total_beats,
        sample_rate,
    )
    for (index, _track), layer in zip(
        sampled_entries,
        sampled_layers,
        strict=True,
    ):
        stems[index] = layer

    pans = (
        np.linspace(-0.24, 0.24, len(procedural_entries))
        if len(procedural_entries) > 1
        else [0.0] if procedural_entries else []
    )
    for (index, track), pan in zip(procedural_entries, pans, strict=True):
        mono = render_track(
            track,
            song.bpm,
            total_beats,
            sample_rate,
            ignore_mute=True,
        )
        left_gain = math.sqrt(1.0 - float(pan))
        right_gain = math.sqrt(1.0 + float(pan))
        stems[index][:, 0] = mono * left_gain
        stems[index][:, 1] = mono * right_gain
    return tuple(stems)


def mix_song_stems(
    song: Song,
    stems: tuple[np.ndarray, ...],
    *,
    stereo: bool = True,
    sample_rate: int = 44100,
) -> np.ndarray:
    if len(stems) != len(song.tracks):
        raise ValueError("Stem count does not match song tracks")
    solo_indices = [
        index
        for index, track in enumerate(song.tracks)
        if track.soloed and not track.muted
    ]
    active_indices = solo_indices or [
        index for index, track in enumerate(song.tracks) if not track.muted
    ]
    if stems:
        frames = len(stems[0])
    else:
        total_beats = max(song.total_beats, float(song.loop_end))
        frames = max(1, int(total_beats * 60.0 / song.bpm * sample_rate))
    mix = np.zeros((frames, 2), dtype=np.float32)
    for index in active_indices:
        mix += stems[index]
    if stereo:
        return _master_output(mix)
    return _master_output(mix.mean(axis=1))


def render_song(
    song: Song,
    sample_rate: int = 44100,
    loop_only: bool = False,
    stereo: bool = True,
) -> np.ndarray:
    total_beats = max(song.total_beats, float(song.loop_end))
    solo_tracks = [track for track in song.tracks if track.soloed and not track.muted]
    active_tracks = solo_tracks or [track for track in song.tracks if not track.muted]
    sampled_tracks = []
    procedural_tracks = []
    sampled_enabled = sample_engine_available()
    for track in active_tracks:
        preset = get_preset(track.instrument)
        if sampled_enabled and uses_samples(preset):
            sampled_tracks.append(track)
        else:
            procedural_tracks.append(track)
    layers = [
        render_track(track, song.bpm, total_beats, sample_rate)
        for track in procedural_tracks
    ]
    sampled_mix = render_sampled_tracks(
        sampled_tracks,
        song.bpm,
        total_beats,
        sample_rate,
    )

    if stereo:
        mix = sampled_mix
        pans = (
            np.linspace(-0.24, 0.24, len(layers))
            if len(layers) > 1
            else [0.0] if layers else []
        )
        for layer, pan in zip(layers, pans, strict=True):
            left_gain = math.sqrt(1.0 - float(pan))
            right_gain = math.sqrt(1.0 + float(pan))
            mix[: len(layer), 0] += layer * left_gain
            mix[: len(layer), 1] += layer * right_gain
        mix = _master_output(mix)
    else:
        mix = sampled_mix.mean(axis=1)
        for layer in layers:
            mix[: len(layer)] += layer
        mix = _master_output(mix)

    if loop_only:
        start = int(song.loop_start * 60.0 / song.bpm * sample_rate)
        end = int(song.loop_end * 60.0 / song.bpm * sample_rate)
        mix = mix[max(0, start) : max(start + 1, min(len(mix), end))]

    return mix


def song_duration(song: Song, loop_only: bool = False) -> float:
    beats = (
        song.loop_end - song.loop_start
        if loop_only
        else max(song.total_beats, song.loop_end)
    )
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

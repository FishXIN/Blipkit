"""Offline renderer for Blipkit piano-roll songs."""

from __future__ import annotations

import math

import numpy as np

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
    phase = 2.0 * np.pi * frequency * t
    waveform = preset.waveform
    if waveform == "square":
        duty = 0.25 if "25%" in preset.name else 0.125 if "12%" in preset.name else 0.5
        cycle = np.mod(frequency * t, 1.0)
        data = np.where(cycle < duty, 1.0, -1.0)
    elif waveform == "saw":
        data = 2.0 * np.mod(frequency * t, 1.0) - 1.0
    elif waveform == "triangle":
        data = 2.0 * np.abs(2.0 * np.mod(frequency * t, 1.0) - 1.0) - 1.0
    elif waveform == "noise":
        data = np.random.default_rng(seed).uniform(-1.0, 1.0, frames)
    else:
        data = np.sin(phase)

    lower = preset.name.lower()
    if "piano" in lower or preset.name in ("Celesta", "Music Box", "Glockenspiel"):
        data = 0.72 * np.sin(phase) + 0.2 * np.sin(phase * 2.0) + 0.08 * np.sin(phase * 3.0)
        data *= np.exp(-t * (2.6 if "soft" not in lower else 1.6))
    elif "strings" in lower or preset.name in ("Solo Violin", "Viola", "Cello"):
        data = 0.62 * data + 0.24 * np.sin(phase * 2.0) + 0.14 * np.sin(phase * 3.0)
    elif preset.name in ("Flute", "Pan Flute", "Dizi", "Shakuhachi", "Ocarina"):
        data = 0.88 * np.sin(phase) + 0.12 * np.sin(phase * 2.0)
    return np.asarray(data, dtype=np.float32)


def _envelope(
    frames: int,
    sample_rate: int,
    attack: float,
    release: float,
    sustain_level: float = 0.82,
) -> np.ndarray:
    env = np.full(frames, sustain_level, dtype=np.float32)
    attack_frames = min(frames, max(1, int(attack * sample_rate)))
    release_frames = min(frames, max(1, int(release * sample_rate)))
    env[:attack_frames] = np.linspace(0.0, 1.0, attack_frames, dtype=np.float32)
    env[-release_frames:] *= np.linspace(1.0, 0.0, release_frames, dtype=np.float32)
    return env


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
        preset.release,
        sustain_level=0.76,
    )
    return data * env * (max(1, min(127, note.velocity)) / 127.0)


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
    mix = np.zeros(max(1, int(total_beats * 60.0 / song.bpm * sample_rate)), dtype=np.float32)
    solo_tracks = [track for track in song.tracks if track.soloed and not track.muted]
    active_tracks = solo_tracks or [track for track in song.tracks if not track.muted]
    for index, track in enumerate(active_tracks):
        layer = render_track(track, song.bpm, total_beats, sample_rate)
        mix[: len(layer)] += layer
    if active_tracks:
        mix /= max(1.0, math.sqrt(len(active_tracks)))
    mix = np.tanh(mix * 1.1).astype(np.float32)

    if loop_only:
        start = int(song.loop_start * 60.0 / song.bpm * sample_rate)
        end = int(song.loop_end * 60.0 / song.bpm * sample_rate)
        mix = mix[max(0, start) : max(start + 1, min(len(mix), end))]

    if not stereo:
        return mix
    left = mix.copy()
    right = mix.copy()
    if len(mix) > 32:
        right[16:] = mix[:-16]
        right[:16] = mix[:16]
    return np.column_stack((left, right)).astype(np.float32)


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

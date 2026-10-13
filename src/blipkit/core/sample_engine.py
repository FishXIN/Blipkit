"""Offline sampled-instrument rendering backed by a bundled SoundFont."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import numpy as np

from .dsp import limit_peak
from .models import Note, Track
from .soundbank import InstrumentPreset, get_preset

SOUNDFONT_NAME = "MuseScore_General.sf3"
_LOCK = threading.RLock()
_SYNTH = None
_SFID: int | None = None
_SAMPLE_RATE = 0


def soundfont_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    return base / "assets" / "soundfonts" / SOUNDFONT_NAME


def uses_samples(preset: InstrumentPreset) -> bool:
    return preset.gm_program is not None or preset.is_drum_kit


def is_available() -> bool:
    if not soundfont_path().is_file():
        return False
    try:
        import tinysoundfont  # noqa: F401
    except ImportError:
        return False
    return True


def _get_synth(sample_rate: int):
    global _SAMPLE_RATE, _SFID, _SYNTH
    if _SYNTH is not None and _SAMPLE_RATE == sample_rate:
        return _SYNTH, _SFID
    _SYNTH = None
    _SFID = None
    try:
        import tinysoundfont
    except ImportError as exc:
        raise RuntimeError("tinysoundfont is not installed") from exc
    path = soundfont_path()
    if not path.is_file():
        raise RuntimeError(f"Bundled SoundFont is missing: {path}")
    synth = tinysoundfont.Synth(gain=24.0, samplerate=sample_rate)
    sfid = synth.sfload(str(path), max_voices=384)
    _SYNTH = synth
    _SFID = sfid
    _SAMPLE_RATE = sample_rate
    return synth, sfid


def _select_preset(synth, sfid: int, channel: int, preset: InstrumentPreset) -> None:
    synth.program_select(
        channel,
        sfid,
        0,
        preset.gm_program or 0,
        preset.is_drum_kit,
    )


def _stereo_buffer(synth, frames: int) -> np.ndarray:
    if frames <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    buffer = synth.generate_simple(frames)
    return np.frombuffer(buffer, dtype=np.float32).reshape(-1, 2).copy()


def _match_peak(samples: np.ndarray, target: float) -> np.ndarray:
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak <= 1e-9:
        return samples
    gain = min(24.0, target / peak)
    return samples * gain


def render_sampled_note(
    note: Note,
    bpm: int,
    preset: InstrumentPreset,
    sample_rate: int,
) -> np.ndarray:
    with _LOCK:
        synth, sfid = _get_synth(sample_rate)
        assert sfid is not None
        synth.sounds_off()
        _select_preset(synth, sfid, 0, preset)
        key = preset.drum_key if preset.drum_key is not None else note.pitch
        body_frames = max(1, int(note.duration * 60.0 / bpm * sample_rate))
        release_frames = max(1, int(0.7 * sample_rate))
        synth.noteon(0, key, max(1, min(127, note.velocity)))
        body = _stereo_buffer(synth, body_frames)
        synth.noteoff(0, key)
        release = _stereo_buffer(synth, release_frames)
        rendered = np.concatenate((body, release), axis=0)
        mono = _match_peak(rendered.mean(axis=1), 0.72)
        return limit_peak(mono, ceiling=0.8)


def _render_track(
    synth,
    sfid: int,
    track: Track,
    bpm: int,
    frames: int,
    sample_rate: int,
) -> np.ndarray:
    synth.sounds_off()
    preset = get_preset(track.instrument)
    _select_preset(synth, sfid, 0, preset)
    events: list[tuple[int, bool, int, int]] = []
    for note in track.notes:
        key = preset.drum_key if preset.drum_key is not None else note.pitch
        start = max(0, int(note.start * 60.0 / bpm * sample_rate))
        end = max(start + 1, int((note.start + note.duration) * 60.0 / bpm * sample_rate))
        if start >= frames:
            continue
        events.append((start, True, key, max(1, min(127, note.velocity))))
        events.append((min(end, frames), False, key, 0))

    output = np.zeros((frames, 2), dtype=np.float32)
    cursor = 0
    for position, is_on, key, velocity in sorted(
        events,
        key=lambda event: (event[0], event[1]),
    ):
        position = min(frames, position)
        if position > cursor:
            output[cursor:position] = _stereo_buffer(synth, position - cursor)
            cursor = position
        if is_on:
            synth.noteon(0, key, velocity)
        else:
            synth.noteoff(0, key)
    if cursor < frames:
        output[cursor:] = _stereo_buffer(synth, frames - cursor)
    synth.sounds_off()
    target = 0.55 if preset.category == "Percussion" else 0.48
    return _match_peak(output, target) * max(0.0, min(1.0, track.volume))


def render_sampled_track_layers(
    tracks: list[Track],
    bpm: int,
    total_beats: float,
    sample_rate: int,
) -> list[np.ndarray]:
    frames = max(1, int(total_beats * 60.0 / bpm * sample_rate))
    if not tracks:
        return []

    with _LOCK:
        synth, sfid = _get_synth(sample_rate)
        assert sfid is not None
        layers: list[np.ndarray] = []
        pans = np.linspace(-0.2, 0.2, len(tracks)) if len(tracks) > 1 else [0.0]
        for channel, (track, pan) in enumerate(zip(tracks, pans, strict=True)):
            layer = _render_track(synth, sfid, track, bpm, frames, sample_rate)
            left_gain = np.sqrt(1.0 - float(pan))
            right_gain = np.sqrt(1.0 + float(pan))
            layer[:, 0] *= left_gain
            layer[:, 1] *= right_gain
            layers.append(layer)
        fade_frames = min(frames, max(1, int(sample_rate * 0.02)))
        fade = np.linspace(1.0, 0.0, fade_frames)[:, None]
        silence_frames = min(frames, max(1, int(sample_rate * 0.01)))
        for layer in layers:
            layer[-fade_frames:] *= fade
            layer[-silence_frames:] = 0.0
        return layers


def render_sampled_tracks(
    tracks: list[Track],
    bpm: int,
    total_beats: float,
    sample_rate: int,
) -> np.ndarray:
    frames = max(1, int(total_beats * 60.0 / bpm * sample_rate))
    layers = render_sampled_track_layers(tracks, bpm, total_beats, sample_rate)
    if not layers:
        return np.zeros((frames, 2), dtype=np.float32)
    return np.sum(layers, axis=0, dtype=np.float32)

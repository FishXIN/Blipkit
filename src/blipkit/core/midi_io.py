"""MIDI import and export for Blipkit songs."""

from __future__ import annotations

import math
from pathlib import Path

import mido

from .models import Note, Song, Track

TICKS_PER_BEAT = 480
TRACK_COLORS = ("#006CFF", "#18A57A", "#B66B18", "#8B5CF6", "#D84A4A")
FLAT_KEYS = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
}


def export_song_midi(song: Song, path: Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    midi = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    conductor = mido.MidiTrack()
    midi.tracks.append(conductor)
    numerator, denominator = _time_signature(song.time_signature)
    conductor.append(mido.MetaMessage("track_name", name=song.name, time=0))
    conductor.append(
        mido.MetaMessage(
            "set_tempo",
            tempo=mido.bpm2tempo(song.bpm),
            time=0,
        )
    )
    conductor.append(
        mido.MetaMessage(
            "time_signature",
            numerator=numerator,
            denominator=denominator,
            time=0,
        )
    )
    key = song.key + ("m" if "Minor" in song.scale else "")
    conductor.append(mido.MetaMessage("key_signature", key=key, time=0))
    conductor.append(
        mido.MetaMessage(
            "end_of_track",
            time=max(1, round(song.bars * 4 * TICKS_PER_BEAT)),
        )
    )

    for source in song.tracks:
        track = mido.MidiTrack()
        midi.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=source.name, time=0))
        events: list[tuple[int, int, mido.Message]] = []
        for note in source.notes:
            start = max(0, round(note.start * TICKS_PER_BEAT))
            end = max(start + 1, round((note.start + note.duration) * TICKS_PER_BEAT))
            events.append(
                (
                    start,
                    1,
                    mido.Message(
                        "note_on",
                        note=max(0, min(127, note.pitch)),
                        velocity=max(1, min(127, note.velocity)),
                        time=0,
                    ),
                )
            )
            events.append(
                (
                    end,
                    0,
                    mido.Message(
                        "note_off",
                        note=max(0, min(127, note.pitch)),
                        velocity=0,
                        time=0,
                    ),
                )
            )
        previous = 0
        for tick, _priority, message in sorted(events, key=lambda item: (item[0], item[1])):
            message.time = tick - previous
            track.append(message)
            previous = tick
    midi.save(destination)
    return destination


def import_song_midi(path: Path, name: str | None = None) -> Song:
    source = Path(path)
    midi = mido.MidiFile(source)
    bpm = 120
    signature = "4/4"
    key = "C"
    scale = "Major"
    tracks: list[Track] = []
    max_end = 0.0
    max_tick_seen = 0

    for midi_track in midi.tracks:
        absolute = 0
        track_name = f"轨道 {len(tracks) + 1}"
        active: dict[tuple[int, int], list[tuple[int, int]]] = {}
        notes: list[Note] = []
        for message in midi_track:
            absolute += message.time
            max_tick_seen = max(max_tick_seen, absolute)
            if message.is_meta:
                if message.type == "track_name" and message.name.strip():
                    track_name = message.name.strip()
                elif message.type == "set_tempo":
                    bpm = max(20, min(300, round(mido.tempo2bpm(message.tempo))))
                elif message.type == "time_signature":
                    signature = f"{message.numerator}/{message.denominator}"
                elif message.type == "key_signature":
                    minor = message.key.endswith("m")
                    raw_key = message.key[:-1] if minor else message.key
                    key = FLAT_KEYS.get(raw_key, raw_key)
                    scale = "Natural Minor" if minor else "Major"
                continue
            channel = getattr(message, "channel", 0)
            note_key = (channel, getattr(message, "note", -1))
            if message.type == "note_on" and message.velocity > 0:
                active.setdefault(note_key, []).append((absolute, message.velocity))
            elif message.type in ("note_off", "note_on") and note_key in active:
                started, velocity = active[note_key].pop(0)
                if not active[note_key]:
                    del active[note_key]
                start = started / midi.ticks_per_beat
                duration = max(1 / 16, (absolute - started) / midi.ticks_per_beat)
                notes.append(
                    Note(
                        pitch=message.note,
                        start=start,
                        duration=duration,
                        velocity=velocity,
                    )
                )
                max_end = max(max_end, start + duration)
        if notes:
            tracks.append(
                Track(
                    name=track_name,
                    color=TRACK_COLORS[len(tracks) % len(TRACK_COLORS)],
                    notes=sorted(notes, key=lambda note: (note.start, note.pitch)),
                )
            )

    if not tracks:
        tracks = [Track(name="主旋律")]
    midi_end = max_tick_seen / midi.ticks_per_beat
    bars = max(1, math.ceil(max(max_end, midi_end) / 4.0))
    return Song(
        name=name or source.stem,
        bpm=bpm,
        time_signature=signature,
        key=key,
        scale=scale,
        bars=bars,
        loop_end=bars * 4.0,
        tracks=tracks,
    )


def _time_signature(value: str) -> tuple[int, int]:
    try:
        numerator, denominator = value.split("/", 1)
        return max(1, int(numerator)), max(1, int(denominator))
    except (AttributeError, ValueError):
        return 4, 4

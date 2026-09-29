"""Small, deterministic music-theory helpers for the editor."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT_TO_SHARP = {
    "DB": "C#",
    "EB": "D#",
    "GB": "F#",
    "AB": "G#",
    "BB": "A#",
}

SCALES: dict[str, Sequence[int]] = {
    "Major": (0, 2, 4, 5, 7, 9, 11),
    "Natural Minor": (0, 2, 3, 5, 7, 8, 10),
    "Harmonic Minor": (0, 2, 3, 5, 7, 8, 11),
    "Melodic Minor": (0, 2, 3, 5, 7, 9, 11),
    "Major Pentatonic": (0, 2, 4, 7, 9),
    "Minor Pentatonic": (0, 3, 5, 7, 10),
    "Blues": (0, 3, 5, 6, 7, 10),
    "Whole Tone": (0, 2, 4, 6, 8, 10),
    "Diminished": (0, 2, 3, 5, 6, 8, 9, 11),
    "Lydian": (0, 2, 4, 6, 7, 9, 11),
    "Mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "Dorian": (0, 2, 3, 5, 7, 9, 10),
    "Phrygian": (0, 1, 3, 5, 7, 8, 10),
    "Locrian": (0, 1, 3, 5, 6, 8, 10),
    "In Sen": (0, 1, 5, 7, 10),
    "Gong": (0, 2, 4, 7, 9),
}

PROGRESSIONS: dict[str, tuple[str, ...]] = {
    "冒险 / 出发": ("I", "V", "vi", "IV"),
    "悲伤 / 落幕": ("i", "VI", "III", "VII"),
    "神秘 / 探索": ("i", "bVII", "bVI", "bVII"),
    "胜利 / 高潮": ("IV", "V", "I", "I"),
    "日常 / 轻松": ("I", "IV", "V", "I"),
    "Boss 战 / 紧张": ("i", "bII", "i", "V"),
    "治愈 / 结局": ("I", "iii", "IV", "V"),
}

_CHORD_QUALITY = {
    "": (0, 4, 7),
    "M": (0, 4, 7),
    "MAJ": (0, 4, 7),
    "MIN": (0, 3, 7),
    "M7": (0, 3, 7, 10),
    "MIN7": (0, 3, 7, 10),
    "7": (0, 4, 7, 10),
    "MAJ7": (0, 4, 7, 11),
    "DIM": (0, 3, 6),
    "DIM7": (0, 3, 6, 9),
    "AUG": (0, 4, 8),
    "SUS2": (0, 2, 7),
    "SUS4": (0, 5, 7),
}


def note_index(name: str) -> int:
    normalized = name.strip().upper().replace("♭", "B").replace("♯", "#")
    normalized = FLAT_TO_SHARP.get(normalized, normalized)
    if normalized not in NOTE_NAMES:
        raise ValueError(f"Unknown note: {name}")
    return NOTE_NAMES.index(normalized)


def scale_pitch_classes(key: str, scale: str) -> list[int]:
    root = note_index(key)
    intervals = SCALES.get(scale, SCALES["Major"])
    return [(root + interval) % 12 for interval in intervals]


def is_in_scale(midi_note: int, key: str, scale: str) -> bool:
    return midi_note % 12 in scale_pitch_classes(key, scale)


def transpose(notes: Iterable[int], semitones: int) -> list[int]:
    return [max(0, min(127, int(note) + semitones)) for note in notes]


def chord_to_midi(symbol: str, octave: int = 4) -> list[int]:
    match = re.match(
        r"^([A-Ga-g])([#b]?)(maj7|min7|dim7|sus2|sus4|aug|dim|maj|min|m7|m|7)?(?:/([A-Ga-g][#b]?))?$",
        symbol.strip(),
    )
    if not match:
        raise ValueError(f"Unsupported chord: {symbol}")
    root_name = (match.group(1) + match.group(2)).upper()
    quality = (match.group(3) or "").upper()
    bass_name = match.group(4)
    root = 12 * (octave + 1) + note_index(root_name)
    notes = [root + interval for interval in _CHORD_QUALITY.get(quality, (0, 4, 7))]
    if bass_name:
        bass = 12 * octave + note_index(bass_name)
        notes = [bass] + [note for note in notes if note % 12 != bass % 12]
    return notes


def chord_function(symbol: str, key: str = "C") -> str:
    try:
        root_match = re.match(r"^([A-Ga-g][#b]?)", symbol.strip())
        if not root_match:
            return "?"
        delta = (note_index(root_match.group(1)) - note_index(key)) % 12
    except ValueError:
        return "?"
    if delta in (0, 3, 4):
        return "T"
    if delta in (2, 5, 9):
        return "S"
    if delta in (7, 10, 11):
        return "D"
    return "-"

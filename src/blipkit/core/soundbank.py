"""Metadata for the lightweight built-in procedural soundbank."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentPreset:
    name: str
    category: str
    waveform: str
    attack: float
    release: float
    brightness: float = 0.5


_GROUPS = {
    "Chiptune": [
        "Square Lead",
        "Square Bass",
        "Square Pad",
        "Square Arp",
        "Square Bright",
        "Square Warm",
        "Square Pulse 25%",
        "Square Pulse 12%",
        "Saw Lead",
        "Saw Bass",
        "Saw Brass",
        "Saw Strings",
        "Saw Supersaw",
        "Saw Aggressive",
        "Saw Soft",
        "Saw Sub",
        "Triangle Bell",
        "Triangle Bass",
        "Triangle Flute",
        "Triangle Pad",
        "Triangle Mellow",
        "Triangle Hollow",
        "Noise Snare",
        "Noise Hi-Hat",
        "NES Piano",
        "NES Organ",
        "NES Choir",
        "NES Lead",
        "GB Square",
        "GB Wave",
        "GB Noise",
        "GB Bass",
    ],
    "Keyboard": [
        "Grand Piano",
        "Grand Piano Mellow",
        "Upright Piano",
        "Soft Piano",
        "Honky Tonk Piano",
        "Rhodes Electric Piano",
        "Wurlitzer",
        "Clavinet",
        "Harpsichord",
        "Celesta",
        "Glockenspiel",
        "Music Box",
        "Pipe Organ",
        "Church Organ",
        "Accordion",
        "Harmonica",
    ],
    "Strings": [
        "Strings Ensemble",
        "Strings Slow Attack",
        "Strings Pizzicato",
        "Solo Violin",
        "Violin Tremolo",
        "Viola",
        "Cello",
        "Cello Pizzicato",
        "Double Bass",
        "Harp",
        "Mandolin",
        "Acoustic Guitar",
    ],
    "Woodwind": [
        "Flute",
        "Pan Flute",
        "Piccolo",
        "Oboe",
        "English Horn",
        "Clarinet",
        "Bassoon",
        "Ocarina",
    ],
    "Brass": [
        "Trumpet",
        "Trumpet Muted",
        "French Horn",
        "Trombone",
        "Tuba",
        "Brass Section",
    ],
    "World": [
        "Guzheng",
        "Erhu",
        "Pipa",
        "Dizi",
        "Shakuhachi",
        "Koto",
    ],
}


def _profile(name: str, category: str) -> InstrumentPreset:
    lower = name.lower()
    if "noise" in lower:
        return InstrumentPreset(name, category, "noise", 0.001, 0.06, 0.9)
    if "square" in lower or name.startswith(("NES", "GB")):
        return InstrumentPreset(name, category, "square", 0.003, 0.08, 0.8)
    if "saw" in lower or name in ("Brass Section", "Trumpet", "Trombone"):
        return InstrumentPreset(name, category, "saw", 0.02, 0.16, 0.75)
    if "triangle" in lower or name in ("Flute", "Ocarina", "Pan Flute"):
        return InstrumentPreset(name, category, "triangle", 0.02, 0.2, 0.4)
    if "pad" in lower or "strings" in lower or "organ" in lower:
        return InstrumentPreset(name, category, "sine", 0.18, 0.45, 0.35)
    if name in ("Grand Piano", "Upright Piano", "Soft Piano", "Harpsichord"):
        return InstrumentPreset(name, category, "triangle", 0.002, 0.25, 0.55)
    if name in ("Cello", "Double Bass", "Tuba", "Bassoon"):
        return InstrumentPreset(name, category, "saw", 0.04, 0.25, 0.35)
    return InstrumentPreset(name, category, "sine", 0.015, 0.22, 0.5)


BUILTIN_PRESETS: list[InstrumentPreset] = [
    _profile(name, category) for category, names in _GROUPS.items() for name in names
]
PRESETS_BY_NAME: dict[str, InstrumentPreset] = {preset.name: preset for preset in BUILTIN_PRESETS}


def categories() -> list[str]:
    return list(_GROUPS)


def list_presets(category: str = "") -> list[InstrumentPreset]:
    if not category:
        return list(BUILTIN_PRESETS)
    return [preset for preset in BUILTIN_PRESETS if preset.category == category]


def get_preset(name: str) -> InstrumentPreset:
    return PRESETS_BY_NAME.get(name, PRESETS_BY_NAME["Square Lead"])

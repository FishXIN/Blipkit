"""Metadata for the lightweight built-in procedural soundbank."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class InstrumentPreset:
    name: str
    category: str
    waveform: str
    attack: float
    release: float
    brightness: float = 0.5
    decay: float = 0.12
    sustain: float = 0.72
    detune_cents: float = 0.0
    vibrato_cents: float = 0.0
    vibrato_rate: float = 5.0


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
        release = 0.035 if "hi-hat" in lower else 0.1
        brightness = 0.82 if "hi-hat" in lower else 0.48
        return InstrumentPreset(
            name,
            category,
            "noise",
            0.001,
            release,
            brightness,
            decay=0.04,
            sustain=0.08,
        )
    if name in ("Rhodes Electric Piano", "Wurlitzer", "Celesta", "Glockenspiel", "Music Box"):
        bell = name in ("Celesta", "Glockenspiel", "Music Box")
        return InstrumentPreset(
            name,
            category,
            "sine",
            0.003 if bell else 0.012,
            0.42 if bell else 0.3,
            0.52 if bell else 0.38,
            decay=0.7 if bell else 0.34,
            sustain=0.14 if bell else 0.48,
        )
    if "piano" in lower:
        soft = "soft" in lower or "mellow" in lower
        return InstrumentPreset(
            name,
            category,
            "sine",
            0.004 if not soft else 0.012,
            0.34 if not soft else 0.48,
            0.5 if not soft else 0.3,
            decay=0.62 if not soft else 0.82,
            sustain=0.24 if not soft else 0.18,
        )
    if name in (
        "Clavinet",
        "Harpsichord",
        "Harp",
        "Mandolin",
        "Acoustic Guitar",
        "Pipa",
        "Guzheng",
        "Koto",
    ):
        return InstrumentPreset(
            name,
            category,
            "triangle",
            0.002,
            0.28,
            0.52,
            decay=0.48,
            sustain=0.18,
        )
    if "organ" in lower or "accordion" in lower or name == "Harmonica":
        return InstrumentPreset(
            name,
            category,
            "sine",
            0.025,
            0.24,
            0.42,
            decay=0.08,
            sustain=0.8,
            vibrato_cents=3.0,
            vibrato_rate=5.2,
        )
    if category == "Strings":
        pizzicato = "pizzicato" in lower
        return InstrumentPreset(
            name,
            category,
            "saw",
            0.003 if pizzicato else (0.16 if "slow" in lower else 0.07),
            0.24 if pizzicato else 0.42,
            0.3 if not pizzicato else 0.4,
            decay=0.34 if pizzicato else 0.16,
            sustain=0.16 if pizzicato else 0.7,
            detune_cents=5.5 if "ensemble" in lower or "strings" in lower else 1.8,
            vibrato_cents=7.0 if not pizzicato else 0.0,
            vibrato_rate=5.1,
        )
    if category == "Woodwind" or name in ("Dizi", "Shakuhachi"):
        return InstrumentPreset(
            name,
            category,
            "triangle",
            0.045,
            0.28,
            0.26,
            decay=0.16,
            sustain=0.72,
            vibrato_cents=8.0,
            vibrato_rate=5.4,
        )
    if category == "Brass":
        return InstrumentPreset(
            name,
            category,
            "saw",
            0.035,
            0.24,
            0.38,
            decay=0.14,
            sustain=0.68,
            detune_cents=2.5 if name == "Brass Section" else 0.0,
            vibrato_cents=3.0,
            vibrato_rate=4.8,
        )
    if "square" in lower or name.startswith(("NES", "GB")):
        attack = 0.06 if "pad" in lower or "choir" in lower else 0.004
        release = 0.3 if "pad" in lower or "choir" in lower else 0.1
        brightness = 0.65 if "bright" in lower or "lead" in lower else 0.45
        if "warm" in lower or "bass" in lower:
            brightness = 0.3
        return InstrumentPreset(
            name,
            category,
            "square",
            attack,
            release,
            brightness,
            decay=0.1,
            sustain=0.68,
        )
    if "saw" in lower:
        brightness = 0.62 if "aggressive" in lower else 0.38
        if "soft" in lower or "sub" in lower or "bass" in lower:
            brightness = 0.24
        return InstrumentPreset(
            name,
            category,
            "saw",
            0.025,
            0.2,
            brightness,
            decay=0.15,
            sustain=0.66,
            detune_cents=7.0 if "supersaw" in lower else 0.0,
        )
    if "triangle" in lower or name in ("Flute", "Ocarina", "Pan Flute"):
        return InstrumentPreset(
            name,
            category,
            "triangle",
            0.025,
            0.24,
            0.3,
            decay=0.12,
            sustain=0.72,
            vibrato_cents=4.0 if "flute" in lower else 0.0,
        )
    if "pad" in lower or "strings" in lower or "organ" in lower:
        return InstrumentPreset(
            name,
            category,
            "sine",
            0.18,
            0.45,
            0.3,
            decay=0.18,
            sustain=0.7,
            detune_cents=4.0,
        )
    if name in ("Cello", "Double Bass", "Tuba", "Bassoon"):
        return InstrumentPreset(
            name,
            category,
            "triangle",
            0.04,
            0.3,
            0.25,
            decay=0.16,
            sustain=0.7,
            vibrato_cents=3.0,
        )
    return InstrumentPreset(
        name,
        category,
        "sine",
        0.018,
        0.25,
        0.36,
        decay=0.16,
        sustain=0.68,
        vibrato_cents=2.0,
    )


def _personalize(preset: InstrumentPreset) -> InstrumentPreset:
    """Give similarly voiced presets stable, subtle differences."""
    signature = sum((index + 1) * ord(character) for index, character in enumerate(preset.name))
    color_offset = ((signature % 17) - 8) * 0.008
    timing_scale = 0.92 + ((signature // 17) % 9) * 0.02
    detune_offset = ((signature // 153) % 7) * 0.18
    return replace(
        preset,
        attack=max(0.001, preset.attack * timing_scale),
        release=max(0.02, preset.release * (2.0 - timing_scale)),
        brightness=max(0.08, min(0.9, preset.brightness + color_offset)),
        decay=max(0.03, preset.decay * (0.96 + (signature % 5) * 0.02)),
        detune_cents=preset.detune_cents + detune_offset,
        vibrato_rate=preset.vibrato_rate * (0.96 + (signature % 3) * 0.04),
    )


BUILTIN_PRESETS: list[InstrumentPreset] = [
    _personalize(_profile(name, category))
    for category, names in _GROUPS.items()
    for name in names
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

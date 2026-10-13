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
    gm_program: int | None = None
    drum_key: int | None = None
    is_drum_kit: bool = False


_GROUPS = {
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
        "Bagpipe",
        "Fiddle",
        "Whistle",
        "Sitar",
        "Banjo",
        "Shamisen",
    ],
    "Percussion": [
        "Standard Drum Kit",
        "Acoustic Snare",
        "Closed Hi-Hat",
        "Bass Drum",
        "Taiko Drum",
        "Tinkle Bell",
        "Woodblock",
        "Steel Drums",
    ],
    "Chiptune": [
        "Square Lead",
        "Square Bass",
        "Square Pad",
        "Square Arp",
        "Square Pulse 25%",
        "Saw Lead",
        "Saw Bass",
        "Saw Strings",
        "Saw Supersaw",
        "Triangle Bell",
        "Triangle Bass",
        "Triangle Pad",
        "Triangle Mellow",
        "NES Piano",
        "NES Lead",
        "GB Square",
        "GB Wave",
        "GB Noise",
    ],
}

_GM_PROGRAMS = {
    "Grand Piano": 0,
    "Grand Piano Mellow": 0,
    "Upright Piano": 1,
    "Soft Piano": 0,
    "Honky Tonk Piano": 3,
    "Rhodes Electric Piano": 4,
    "Wurlitzer": 4,
    "Clavinet": 7,
    "Harpsichord": 6,
    "Celesta": 8,
    "Glockenspiel": 9,
    "Music Box": 10,
    "Pipe Organ": 19,
    "Church Organ": 19,
    "Accordion": 21,
    "Harmonica": 22,
    "Strings Ensemble": 48,
    "Strings Slow Attack": 49,
    "Strings Pizzicato": 45,
    "Solo Violin": 40,
    "Violin Tremolo": 44,
    "Viola": 41,
    "Cello": 42,
    "Cello Pizzicato": 45,
    "Double Bass": 43,
    "Harp": 46,
    "Mandolin": 25,
    "Acoustic Guitar": 25,
    "Flute": 73,
    "Pan Flute": 75,
    "Piccolo": 72,
    "Oboe": 68,
    "English Horn": 69,
    "Clarinet": 71,
    "Bassoon": 70,
    "Ocarina": 79,
    "Trumpet": 56,
    "Trumpet Muted": 59,
    "French Horn": 60,
    "Trombone": 57,
    "Tuba": 58,
    "Brass Section": 61,
    "Guzheng": 107,
    "Erhu": 110,
    "Pipa": 106,
    "Dizi": 77,
    "Shakuhachi": 77,
    "Koto": 107,
    "Bagpipe": 109,
    "Fiddle": 110,
    "Whistle": 78,
    "Sitar": 104,
    "Banjo": 105,
    "Shamisen": 106,
    "Taiko Drum": 116,
    "Tinkle Bell": 112,
    "Woodblock": 115,
    "Steel Drums": 114,
}

_DRUM_KEYS = {
    "Acoustic Snare": 38,
    "Closed Hi-Hat": 42,
    "Bass Drum": 36,
}


def _profile(name: str, category: str) -> InstrumentPreset:
    lower = name.lower()
    if category == "Percussion":
        return InstrumentPreset(
            name,
            category,
            "noise" if name in _DRUM_KEYS or name == "Standard Drum Kit" else "triangle",
            0.001,
            0.12,
            0.5,
            decay=0.05,
            sustain=0.05,
        )
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
        gm_program=_GM_PROGRAMS.get(preset.name),
        drum_key=_DRUM_KEYS.get(preset.name),
        is_drum_kit=preset.name == "Standard Drum Kit" or preset.name in _DRUM_KEYS,
    )


BUILTIN_PRESETS: list[InstrumentPreset] = [
    _personalize(_profile(name, category))
    for category, names in _GROUPS.items()
    for name in names
]
PRESETS_BY_NAME: dict[str, InstrumentPreset] = {preset.name: preset for preset in BUILTIN_PRESETS}
_LEGACY_PRESET_ALIASES = {
    "Square Bright": "Square Lead",
    "Square Warm": "Square Pad",
    "Square Pulse 12%": "Square Pulse 25%",
    "Saw Brass": "Brass Section",
    "Saw Aggressive": "Saw Lead",
    "Saw Soft": "Saw Strings",
    "Saw Sub": "Saw Bass",
    "Triangle Flute": "Flute",
    "Triangle Hollow": "Double Bass",
    "Noise Snare": "Acoustic Snare",
    "Noise Hi-Hat": "Closed Hi-Hat",
    "NES Organ": "Pipe Organ",
    "NES Choir": "Strings Ensemble",
    "GB Bass": "Square Bass",
}


def categories() -> list[str]:
    return list(_GROUPS)


def list_presets(category: str = "") -> list[InstrumentPreset]:
    if not category:
        return list(BUILTIN_PRESETS)
    return [preset for preset in BUILTIN_PRESETS if preset.category == category]


def get_preset(name: str) -> InstrumentPreset:
    resolved = _LEGACY_PRESET_ALIASES.get(name, name)
    return PRESETS_BY_NAME.get(resolved, PRESETS_BY_NAME["Grand Piano"])

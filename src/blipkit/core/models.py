"""Serializable data models shared by the UI, CLI, and audio engine."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class Note:
    pitch: int
    start: float
    duration: float = 1.0
    velocity: int = 100
    id: str = field(default_factory=lambda: _id("note"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Note:
        return cls(
            pitch=int(data["pitch"]),
            start=float(data["start"]),
            duration=float(data.get("duration", 1.0)),
            velocity=int(data.get("velocity", 100)),
            id=str(data.get("id") or _id("note")),
        )


@dataclass
class Track:
    name: str
    instrument: str = "Square Lead"
    volume: float = 0.8
    muted: bool = False
    soloed: bool = False
    color: str = "#006CFF"
    notes: list[Note] = field(default_factory=list)
    id: str = field(default_factory=lambda: _id("track"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Track:
        return cls(
            name=str(data.get("name", "Track")),
            instrument=str(data.get("instrument", "Square Lead")),
            volume=float(data.get("volume", 0.8)),
            muted=bool(data.get("muted", False)),
            soloed=bool(data.get("soloed", False)),
            color=str(data.get("color", "#5B8DEF")),
            notes=[Note.from_dict(item) for item in data.get("notes", [])],
            id=str(data.get("id") or _id("track")),
        )


@dataclass
class MoodMarker:
    beat: float
    label: str
    bpm: int = 120
    key: str = "C"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MoodMarker:
        return cls(
            beat=float(data.get("beat", 0)),
            label=str(data.get("label", "Marker")),
            bpm=int(data.get("bpm", 120)),
            key=str(data.get("key", "C")),
        )


@dataclass
class Song:
    name: str
    bpm: int = 120
    time_signature: str = "4/4"
    key: str = "C"
    scale: str = "Major"
    bars: int = 4
    loop_start: float = 0.0
    loop_end: float = 16.0
    tracks: list[Track] = field(default_factory=list)
    mood_markers: list[MoodMarker] = field(default_factory=list)
    id: str = field(default_factory=lambda: _id("song"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Song:
        bars = int(data.get("bars", 4))
        return cls(
            name=str(data.get("name", "Untitled")),
            bpm=int(data.get("bpm", 120)),
            time_signature=str(data.get("time_signature", "4/4")),
            key=str(data.get("key", "C")),
            scale=str(data.get("scale", "Major")),
            bars=bars,
            loop_start=float(data.get("loop_start", 0.0)),
            loop_end=float(data.get("loop_end", bars * 4)),
            tracks=[Track.from_dict(item) for item in data.get("tracks", [])],
            mood_markers=[MoodMarker.from_dict(item) for item in data.get("mood_markers", [])],
            id=str(data.get("id") or _id("song")),
        )


@dataclass
class SFXPatch:
    name: str
    category: str = "UI"
    waveform: str = "Sine"
    attack: float = 0.005
    decay: float = 0.08
    sustain: float = 0.35
    release: float = 0.12
    start_freq: float = 700.0
    end_freq: float = 320.0
    bend: float = 1.0
    duration: float = 0.35
    noise: float = 0.0
    vibrato_depth: float = 0.0
    vibrato_rate: float = 6.0
    lowpass_cutoff: float = 1.0
    crush: float = 0.0
    volume: float = 0.8
    seed: int = 1
    id: str = field(default_factory=lambda: _id("sfx"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SFXPatch:
        fields = {
            "name": str(data.get("name", "Untitled SFX")),
            "category": str(data.get("category", "UI")),
            "waveform": str(data.get("waveform", "Sine")),
            "attack": float(data.get("attack", 0.005)),
            "decay": float(data.get("decay", 0.08)),
            "sustain": float(data.get("sustain", 0.35)),
            "release": float(data.get("release", 0.12)),
            "start_freq": float(data.get("start_freq", 700.0)),
            "end_freq": float(data.get("end_freq", 320.0)),
            "bend": float(data.get("bend", 1.0)),
            "duration": float(data.get("duration", 0.35)),
            "noise": float(data.get("noise", 0.0)),
            "vibrato_depth": float(data.get("vibrato_depth", 0.0)),
            "vibrato_rate": float(data.get("vibrato_rate", 6.0)),
            "lowpass_cutoff": float(data.get("lowpass_cutoff", 1.0)),
            "crush": float(data.get("crush", 0.0)),
            "volume": float(data.get("volume", 0.8)),
            "seed": int(data.get("seed", 1)),
            "id": str(data.get("id") or _id("sfx")),
        }
        return cls(**fields)


@dataclass
class ProjectMetadata:
    name: str
    template: str = "Blank"
    engine: str = "None"
    engine_path: str = ""
    sample_rate: int = 44100
    bit_depth: int = 16
    channels: str = "Stereo"
    export_format: str = "wav"
    normalize: bool = True
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectMetadata:
        return cls(
            name=str(data.get("name", "Untitled")),
            template=str(data.get("template", "Blank")),
            engine=str(data.get("engine", "None")),
            engine_path=str(data.get("engine_path", "")),
            sample_rate=int(data.get("sample_rate", 44100)),
            bit_depth=int(data.get("bit_depth", 16)),
            channels=str(data.get("channels", "Stereo")),
            export_format=str(data.get("export_format", "wav")),
            normalize=bool(data.get("normalize", True)),
            created_at=float(data.get("created_at", time.time())),
            modified_at=float(data.get("modified_at", time.time())),
            version=int(data.get("version", 1)),
        )


@dataclass
class AssetInfo:
    id: str
    name: str
    kind: str
    path: str
    duration: float = 0.0
    modified_at: float = 0.0
    synced: bool = False

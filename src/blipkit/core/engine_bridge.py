"""Resolve safe output locations for supported game engines."""

from __future__ import annotations

import json
from pathlib import Path

ENGINES = ("None", "Unity", "Godot 4", "Unreal Engine 5", "Web", "Custom")


def validate_engine_path(engine: str, root: Path) -> bool:
    root = Path(root)
    if engine in ("None", "Custom", "Web"):
        return root.exists() and root.is_dir()
    if engine == "Unity":
        return root.name == "Assets" or (root / "Assets").is_dir()
    if engine == "Godot 4":
        return (root / "project.godot").is_file()
    if engine == "Unreal Engine 5":
        return root.name == "Content" or (root / "Content").is_dir()
    return False


def output_root(engine: str, root: Path) -> Path:
    root = Path(root)
    if engine == "Unity":
        assets = root if root.name == "Assets" else root / "Assets"
        return assets / "Audio"
    if engine == "Godot 4":
        return root / "audio"
    if engine == "Unreal Engine 5":
        content = root if root.name == "Content" else root / "Content"
        return content / "Audio"
    if engine == "Web":
        return root / "audio"
    return root


def asset_output_dir(engine: str, root: Path, kind: str) -> Path:
    target = output_root(engine, root)
    child = (
        "Music"
        if kind == "music" and engine in ("Unity", "Unreal Engine 5")
        else ("SFX" if kind == "sfx" and engine in ("Unity", "Unreal Engine 5") else kind)
    )
    target = target / child
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_unreal_import_descriptor(audio_path: Path, kind: str) -> Path:
    descriptor = audio_path.with_suffix(audio_path.suffix + ".import.json")
    payload: dict[str, object] = {
        "source": audio_path.name,
        "destination": "/Game/Audio/%s" % ("Music" if kind == "music" else "SFX"),
        "asset_type": "SoundWave",
        "looping": kind == "music",
    }
    descriptor.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return descriptor

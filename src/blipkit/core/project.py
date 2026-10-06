"""`.bkproj` project storage, snapshots, and compact operation history."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Any

from .models import AssetInfo, Note, ProjectMetadata, SFXPatch, Song, Track
from .sfx_synth import get_preset
from .showcase import create_showcase_songs

PROJECT_SUFFIX = ".bkproj"


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value.strip())
    return cleaned.strip(". ") or "untitled"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(path)


def _template_song(name: str, template: str) -> Song:
    colors = ("#006CFF", "#18A57A", "#B66B18", "#8B5CF6")
    tracks = [
        Track(name="主旋律", instrument="Square Lead", color=colors[0]),
        Track(name="和声", instrument="Strings Ensemble", volume=0.58, color=colors[1]),
        Track(name="低音", instrument="Square Bass", volume=0.68, color=colors[2]),
        Track(name="节奏", instrument="Noise Snare", volume=0.42, color=colors[3]),
    ]
    song = Song(name=name, tracks=tracks)
    if template == "Blank":
        song.tracks = tracks[:1]
        return song

    roots = {
        "RPG": (60, 64, 67, 72, 69, 67, 64, 62),
        "Platformer": (72, 76, 79, 76, 74, 77, 81, 79),
        "Horror": (48, 49, 55, 50, 48, 56, 49, 47),
        "Puzzle": (60, 67, 64, 71, 69, 64, 62, 67),
        "Action": (52, 55, 59, 62, 59, 64, 62, 55),
    }
    melody = roots.get(template, roots["RPG"])
    for index, pitch in enumerate(melody):
        tracks[0].notes.append(Note(pitch=pitch, start=index * 2.0, duration=1.5))
    chord_roots = (48, 55, 45, 53)
    for index, root in enumerate(chord_roots):
        for interval in (0, 4, 7):
            tracks[1].notes.append(
                Note(pitch=root + interval, start=index * 4.0, duration=3.8, velocity=72)
            )
        tracks[2].notes.append(Note(pitch=root - 12, start=index * 4.0, duration=3.6, velocity=88))
    for beat in range(16):
        if beat % 2 == 1:
            tracks[3].notes.append(Note(pitch=38, start=float(beat), duration=0.18, velocity=72))
    return song


class BlipkitProject:
    def __init__(self, path: Path, metadata: ProjectMetadata):
        self.path = Path(path)
        self.metadata = metadata
        self._connection: sqlite3.Connection | None = None

    @classmethod
    def create(
        cls,
        path: Path,
        name: str,
        template: str = "RPG",
    ) -> BlipkitProject:
        path = Path(path).expanduser()
        if path.suffix != PROJECT_SUFFIX:
            path = path.with_name(path.name + PROJECT_SUFFIX)
        path.mkdir(parents=True, exist_ok=True)
        for child in ("music", "sfx", "exports", "snapshots"):
            (path / child).mkdir(exist_ok=True)
        project = cls(path, ProjectMetadata(name=name, template=template))
        project.save_metadata()
        project.save_song(_template_song("bgm_main", template), record=False)
        for preset_name in ("Click", "Coin", "Explosion"):
            project.save_sfx(get_preset(preset_name), record=False)
        project._init_history()
        project.record("project.create", "project", name, {"template": template})
        return project

    @classmethod
    def open(cls, path: Path) -> BlipkitProject:
        path = Path(path).expanduser().resolve()
        metadata_path = path / "project.json"
        if not metadata_path.is_file():
            raise FileNotFoundError(f"Not a Blipkit project: {path}")
        metadata = ProjectMetadata.from_dict(json.loads(metadata_path.read_text(encoding="utf-8")))
        project = cls(path, metadata)
        project._init_history()
        return project

    def _init_history(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path / "history.db"))
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                action TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def save_metadata(self) -> None:
        self.metadata.modified_at = time.time()
        _write_json(self.path / "project.json", self.metadata.to_dict())

    def record(
        self,
        action: str,
        asset_type: str,
        asset_id: str,
        payload: dict[str, Any],
    ) -> None:
        if self._connection is None:
            self._init_history()
        assert self._connection is not None
        self._connection.execute(
            "INSERT INTO history("
            "created_at, action, asset_type, asset_id, payload"
            ") VALUES (?, ?, ?, ?, ?)",
            (time.time(), action, asset_type, asset_id, json.dumps(payload, ensure_ascii=False)),
        )
        self._connection.execute(
            "DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT 50)"
        )
        self._connection.commit()

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        if self._connection is None:
            self._init_history()
        assert self._connection is not None
        rows = self._connection.execute(
            "SELECT id, created_at, action, asset_type, asset_id, payload "
            "FROM history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": row[0],
                "created_at": row[1],
                "action": row[2],
                "asset_type": row[3],
                "asset_id": row[4],
                "payload": json.loads(row[5]),
            }
            for row in rows
        ]

    def save_song(self, song: Song, record: bool = True) -> Path:
        path = self.path / "music" / (safe_filename(song.name) + ".bkm")
        _write_json(path, song.to_dict())
        if record:
            self.record("song.save", "music", song.id, song.to_dict())
        self.save_metadata()
        return path

    def save_sfx(self, patch: SFXPatch, record: bool = True) -> Path:
        path = self.path / "sfx" / (safe_filename(patch.name) + ".bkx")
        _write_json(path, patch.to_dict())
        if record:
            self.record("sfx.save", "sfx", patch.id, patch.to_dict())
        self.save_metadata()
        return path

    def ensure_showcase_song(self) -> Song | None:
        songs = self.ensure_showcase_songs()
        return songs[0] if songs else None

    def ensure_showcase_songs(self) -> list[Song]:
        if self.metadata.name != "Starter":
            return []
        existing = {song.name: song for _path, song in self.load_songs()}
        songs = []
        for bundled in create_showcase_songs():
            song = existing.get(bundled.name, bundled)
            if bundled.name not in existing:
                self.save_song(song, record=False)
            songs.append(song)
        return songs

    def load_songs(self) -> list[tuple[Path, Song]]:
        result = []
        for path in sorted((self.path / "music").glob("*.bkm")):
            try:
                result.append((path, Song.from_dict(json.loads(path.read_text(encoding="utf-8")))))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return result

    def load_sfx(self) -> list[tuple[Path, SFXPatch]]:
        result = []
        for path in sorted((self.path / "sfx").glob("*.bkx")):
            try:
                result.append(
                    (path, SFXPatch.from_dict(json.loads(path.read_text(encoding="utf-8"))))
                )
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return result

    def assets(self) -> list[AssetInfo]:
        assets: list[AssetInfo] = []

        def export_name(name: str) -> str:
            return safe_filename(name) + "." + self.metadata.export_format

        for path, song in self.load_songs():
            assets.append(
                AssetInfo(
                    id=song.id,
                    name=song.name,
                    kind="music",
                    path=str(path),
                    duration=max(song.bars * 4, song.loop_end) * 60.0 / song.bpm,
                    modified_at=path.stat().st_mtime,
                    synced=any((self.path / "exports").rglob(export_name(song.name))),
                )
            )
        for path, patch in self.load_sfx():
            assets.append(
                AssetInfo(
                    id=patch.id,
                    name=patch.name,
                    kind="sfx",
                    path=str(path),
                    duration=patch.duration,
                    modified_at=path.stat().st_mtime,
                    synced=any((self.path / "exports").rglob(export_name(patch.name))),
                )
            )
        return assets

    def snapshot_song(self, song: Song, label: str) -> Path:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = (
            self.path
            / "snapshots"
            / (f"{stamp}_{safe_filename(label)}_{safe_filename(song.name)}.bkm")
        )
        _write_json(path, song.to_dict())
        self.record("song.snapshot", "music", song.id, {"path": str(path), "label": label})
        return path

    def export_zip(self, destination: Path) -> Path:
        destination = Path(destination)
        if destination.suffix.lower() != ".zip":
            destination = destination.with_suffix(".zip")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(destination), "w", zipfile.ZIP_DEFLATED) as archive:
            for source in self.path.rglob("*"):
                if source.is_file() and source != destination:
                    archive.write(str(source), str(source.relative_to(self.path.parent)))
        return destination

    def delete_asset(self, asset_type: str, name: str) -> None:
        folder = "music" if asset_type == "music" else "sfx"
        extension = ".bkm" if asset_type == "music" else ".bkx"
        path = self.path / folder / (safe_filename(name) + extension)
        if path.exists():
            trash = self.path / "snapshots" / f"deleted_{int(time.time())}_{path.name}"
            shutil.move(str(path), str(trash))
            self.record("asset.delete", asset_type, name, {"backup": str(trash)})

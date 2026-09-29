"""Project audio export pipeline shared by the desktop UI and CLI."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .audio_io import export_audio
from .engine_bridge import asset_output_dir, write_unreal_import_descriptor
from .project import BlipkitProject, safe_filename
from .sequencer import render_song
from .sfx_synth import synthesize
from .web_export import write_audio_manifest


@dataclass
class ExportResult:
    files: list[Path] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


ProgressCallback = Callable[[int, int, str], None]


def _channels(project: BlipkitProject) -> int:
    return 1 if project.metadata.channels.lower() == "mono" else 2


def export_project(
    project: BlipkitProject,
    destination: Path | None = None,
    engine: str | None = None,
    audio_format: str | None = None,
    selected_ids: Sequence[str] | None = None,
    progress: ProgressCallback | None = None,
) -> ExportResult:
    target_root = Path(destination) if destination else project.path / "exports"
    active_engine = engine or project.metadata.engine or "None"
    fmt = (audio_format or project.metadata.export_format or "wav").lower()
    sample_rate = project.metadata.sample_rate
    bit_depth = project.metadata.bit_depth
    channels = _channels(project)
    selected = set(selected_ids or [])
    songs = [song for _, song in project.load_songs() if not selected or song.id in selected]
    patches = [patch for _, patch in project.load_sfx() if not selected or patch.id in selected]
    total = len(songs) + len(patches)
    current = 0
    result = ExportResult()
    web_music = []
    web_sfx = []

    for kind, assets in (("music", songs), ("sfx", patches)):
        for asset in assets:
            current += 1
            if progress:
                progress(current, total, asset.name)
            try:
                data = (
                    render_song(
                        asset, sample_rate=sample_rate, loop_only=True, stereo=channels == 2
                    )
                    if kind == "music"
                    else synthesize(asset, sample_rate=sample_rate)
                )
                output_dir = asset_output_dir(active_engine, target_root, kind)
                base = safe_filename(asset.name)
                formats = ("ogg", "mp3") if active_engine == "Web" else (fmt,)
                produced = []
                for current_format in formats:
                    path = output_dir / (f"{base}.{current_format}")
                    export_audio(
                        path,
                        data,
                        sample_rate=sample_rate,
                        bit_depth=bit_depth,
                        channels=channels,
                        normalize=project.metadata.normalize,
                    )
                    result.files.append(path)
                    produced.append(path.name)
                    if active_engine == "Unreal Engine 5":
                        result.files.append(write_unreal_import_descriptor(path, kind))
                if active_engine == "Web":
                    entry = (base, produced[0], produced[1])
                    (web_music if kind == "music" else web_sfx).append(entry)
            except Exception as exc:
                result.failed.append(f"{asset.name}: {exc}")

    if active_engine == "Web":
        manifest = write_audio_manifest(target_root, web_music, web_sfx)
        result.files.append(manifest)
    project.record(
        "project.export",
        "project",
        project.metadata.name,
        {
            "engine": active_engine,
            "destination": str(target_root),
            "files": [str(path) for path in result.files],
            "failed": result.failed,
        },
    )
    return result

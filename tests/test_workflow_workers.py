from __future__ import annotations

import threading
import time

import numpy as np

from blipkit.core.audition import NoteAuditioner
from blipkit.core.export import ExportSnapshot, export_project
from blipkit.core.models import Note
from blipkit.core.project import BlipkitProject


def test_audition_discards_stale_notes_and_uses_cache():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def render(note, *_args):
        calls.append(note.pitch)
        started.set()
        assert release.wait(3)
        return np.array([note.pitch], dtype=np.float32)

    worker = NoteAuditioner(render)
    try:
        worker.request(60, "Square Lead", 100, 120, 8000)
        assert started.wait(2)
        worker.request(64, "Square Lead", 100, 120, 8000)
        worker.request(67, "Square Lead", 100, 120, 8000)
        release.set()
        deadline = time.monotonic() + 3
        result = None
        while time.monotonic() < deadline and result is None:
            result = worker.take_latest()
            time.sleep(0.005)
        assert result is not None
        assert result[0].tolist() == [67]
        assert calls == [60, 67]
        worker.request(67, "Square Lead", 100, 120, 8000)
        deadline = time.monotonic() + 3
        result = None
        while time.monotonic() < deadline and result is None:
            result = worker.take_latest()
            time.sleep(0.005)
        assert result is not None
        assert calls == [60, 67]
    finally:
        release.set()
        worker.close()


def test_export_snapshot_isolated_from_edits_and_uses_worker_connection(tmp_path):
    project = BlipkitProject.create(tmp_path / "test.bkproj", "Test", "Blank")
    try:
        _, song = project.load_songs()[0]
        song.tracks[0].instrument = "Square Lead"
        song.tracks[0].notes = [Note(60, 0, 0.25)]
        project.metadata.sample_rate = 8000
        project.save_song(song)
        snapshot = ExportSnapshot(project)
        song.tracks[0].notes.clear()
        project.save_song(song)
        project.metadata.sample_rate = 44100
        assert len(snapshot.load_songs()[0][1].tracks[0].notes) == 1
        assert snapshot.metadata.sample_rate == 8000
        results = []
        worker = threading.Thread(
            target=lambda: results.append(
                export_project(
                    snapshot,
                    destination=tmp_path / "audio",
                    selected_ids=[song.id],
                )
            )
        )
        worker.start()
        worker.join(10)
        assert not worker.is_alive()
        assert not results[0].failed
        assert len(results[0].files) == 1
        assert results[0].files[0].stat().st_size > 100
    finally:
        project.close()

"""Core regression tests for synthesis, storage, and export."""

from __future__ import annotations

import json
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from blipkit.core.audio_io import export_audio
from blipkit.core.engine_bridge import output_root, validate_engine_path
from blipkit.core.export import export_project
from blipkit.core.models import Note, Song, Track
from blipkit.core.music_assistant import chord_to_midi, is_in_scale
from blipkit.core.project import BlipkitProject
from blipkit.core.sequencer import render_song
from blipkit.core.sfx_synth import get_preset, synthesize
from blipkit.core.soundbank import BUILTIN_PRESETS


class SoundbankTests(unittest.TestCase):
    def test_v1_soundbank_has_eighty_presets(self):
        self.assertEqual(len(BUILTIN_PRESETS), 80)
        self.assertEqual(len({preset.name for preset in BUILTIN_PRESETS}), 80)

    def test_music_assistant(self):
        self.assertEqual(chord_to_midi("Dm7/F"), [53, 62, 69, 72])
        self.assertTrue(is_in_scale(60, "C", "Major"))
        self.assertFalse(is_in_scale(61, "C", "Major"))


class SynthesisTests(unittest.TestCase):
    def test_sfx_is_deterministic_and_finite(self):
        patch = get_preset("Explosion")
        first = synthesize(patch, sample_rate=22050)
        second = synthesize(patch, sample_rate=22050)
        self.assertEqual(len(first), int(patch.duration * 22050))
        self.assertTrue(np.array_equal(first, second))
        self.assertTrue(np.all(np.isfinite(first)))
        self.assertLessEqual(float(np.max(np.abs(first))), 1.0)

    def test_song_loop_length_and_stereo(self):
        song = Song(
            name="loop",
            bpm=120,
            bars=1,
            loop_start=0,
            loop_end=4,
            tracks=[
                Track(
                    name="lead",
                    notes=[Note(pitch=60, start=0, duration=1)],
                )
            ],
        )
        rendered = render_song(song, sample_rate=8000, loop_only=True, stereo=True)
        self.assertEqual(rendered.shape, (16000, 2))
        self.assertGreater(float(np.max(np.abs(rendered))), 0.01)

    def test_wav_export(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tone.wav"
            data = synthesize(get_preset("Coin"), sample_rate=22050)
            export_audio(path, data, sample_rate=22050, channels=1)
            with wave.open(str(path), "rb") as source:
                self.assertEqual(source.getframerate(), 22050)
                self.assertEqual(source.getnchannels(), 1)
                self.assertGreater(source.getnframes(), 100)


class ProjectTests(unittest.TestCase):
    def test_project_round_trip_and_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            project = BlipkitProject.create(
                Path(folder) / "Demo",
                "Demo",
                template="Puzzle",
            )
            path = project.path
            songs = project.load_songs()
            patches = project.load_sfx()
            self.assertEqual(path.suffix, ".bkproj")
            self.assertEqual(len(songs), 1)
            self.assertEqual(len(patches), 3)
            snapshot = project.snapshot_song(songs[0][1], "v0.1")
            self.assertTrue(snapshot.is_file())
            self.assertTrue(project.history())
            project.close()

            reopened = BlipkitProject.open(path)
            self.assertEqual(reopened.metadata.name, "Demo")
            self.assertEqual(len(reopened.assets()), 4)
            reopened.close()

    def test_local_wav_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = BlipkitProject.create(root / "Demo", "Demo", template="Blank")
            destination = root / "out"
            result = export_project(
                project,
                destination=destination,
                engine="None",
                audio_format="wav",
            )
            self.assertFalse(result.failed)
            self.assertEqual(len(result.files), 4)
            self.assertTrue(all(path.is_file() for path in result.files))
            project.close()

    def test_web_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = BlipkitProject.create(root / "Demo", "Demo", template="Blank")
            destination = root / "web"
            result = export_project(project, destination=destination, engine="Web")
            self.assertFalse(result.failed, result.failed)
            manifest = destination / "AudioManifest.js"
            self.assertTrue(manifest.is_file())
            text = manifest.read_text(encoding="utf-8")
            body = text.split("=", 1)[1].strip().rstrip(";")
            parsed = json.loads(body)
            self.assertIn("bgm_main", parsed["music"])
            self.assertIn("Coin", parsed["sfx"])
            project.close()

    def test_engine_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Assets").mkdir()
            self.assertTrue(validate_engine_path("Unity", root))
            self.assertEqual(output_root("Unity", root), root / "Assets" / "Audio")
            (root / "project.godot").write_text("", encoding="utf-8")
            self.assertTrue(validate_engine_path("Godot 4", root))


if __name__ == "__main__":
    unittest.main(verbosity=2)

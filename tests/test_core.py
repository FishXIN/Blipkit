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
from blipkit.core.midi_io import export_song_midi, import_song_midi
from blipkit.core.models import Note, Song, Track
from blipkit.core.music_assistant import chord_to_midi, is_in_scale
from blipkit.core.project import BlipkitProject
from blipkit.core.sequencer import render_note, render_song
from blipkit.core.sfx_synth import get_preset, mutate_patch, preset_names, synthesize
from blipkit.core.showcase import SHOWCASE_SONG_NAMES, create_showcase_songs
from blipkit.core.soundbank import BUILTIN_PRESETS
from blipkit.core.soundbank import get_preset as get_instrument_preset


class SoundbankTests(unittest.TestCase):
    def test_v1_soundbank_has_eighty_presets(self):
        self.assertEqual(len(BUILTIN_PRESETS), 80)
        self.assertEqual(len({preset.name for preset in BUILTIN_PRESETS}), 80)

    def test_music_assistant(self):
        self.assertEqual(chord_to_midi("Dm7/F"), [53, 62, 69, 72])
        self.assertTrue(is_in_scale(60, "C", "Major"))
        self.assertFalse(is_in_scale(61, "C", "Major"))

    def test_all_instrument_presets_render_cleanly(self):
        note = Note(pitch=60, start=0, duration=0.25, velocity=100)
        rendered_voices = set()
        for preset in BUILTIN_PRESETS:
            rendered = render_note(note, 120, preset, sample_rate=8000)
            self.assertTrue(np.all(np.isfinite(rendered)), preset.name)
            self.assertLessEqual(float(np.max(np.abs(rendered))), 0.81, preset.name)
            rendered_voices.add(rendered.tobytes())
        self.assertEqual(len(rendered_voices), len(BUILTIN_PRESETS))

    def test_bright_presets_limit_harsh_high_frequency_energy(self):
        sample_rate = 44100
        note = Note(pitch=72, start=0, duration=2, velocity=100)
        for name in ("Square Lead", "Saw Lead", "Trumpet"):
            rendered = render_note(
                note,
                120,
                get_instrument_preset(name),
                sample_rate=sample_rate,
            )
            spectrum = np.abs(np.fft.rfft(rendered * np.hanning(len(rendered)))) ** 2
            frequencies = np.fft.rfftfreq(len(rendered), 1.0 / sample_rate)
            ratio = float(
                spectrum[frequencies > 10000].sum() / max(spectrum.sum(), 1e-12)
            )
            self.assertLess(ratio, 0.012, name)


class SynthesisTests(unittest.TestCase):
    def test_sfx_is_deterministic_and_finite(self):
        patch = get_preset("Explosion")
        first = synthesize(patch, sample_rate=22050)
        second = synthesize(patch, sample_rate=22050)
        self.assertEqual(len(first), int(patch.duration * 22050))
        self.assertTrue(np.array_equal(first, second))
        self.assertTrue(np.all(np.isfinite(first)))
        self.assertLessEqual(float(np.max(np.abs(first))), 1.0)

    def test_sfx_mutation_is_repeatable_and_changes_sound(self):
        patch = get_preset("Coin")
        first = mutate_patch(patch, seed=42)
        second = mutate_patch(patch, seed=42)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertNotEqual(first.start_freq, patch.start_freq)
        rendered = synthesize(first, sample_rate=8000)
        self.assertTrue(np.all(np.isfinite(rendered)))

    def test_all_sfx_presets_render_below_the_clean_ceiling(self):
        for name in preset_names():
            rendered = synthesize(get_preset(name), sample_rate=8000)
            self.assertTrue(np.all(np.isfinite(rendered)), name)
            self.assertLessEqual(float(np.max(np.abs(rendered))), 0.921, name)

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
        self.assertTrue(np.array_equal(rendered[:, 0], rendered[:, 1]))

    def test_solo_tracks_override_non_solo_tracks(self):
        song = Song(
            name="solo",
            bpm=120,
            bars=1,
            loop_end=4,
            tracks=[
                Track(name="solo", soloed=True, notes=[Note(pitch=60, start=0)]),
                Track(name="other", notes=[Note(pitch=72, start=1)]),
            ],
        )
        solo_mix = render_song(song, sample_rate=8000, loop_only=True, stereo=False)
        song.tracks[1].muted = True
        expected = render_song(song, sample_rate=8000, loop_only=True, stereo=False)
        self.assertTrue(np.array_equal(solo_mix, expected))

    def test_dense_chord_uses_clean_peak_management(self):
        notes = [
            Note(pitch=pitch, start=0, duration=2, velocity=115)
            for pitch in (48, 52, 55, 60, 64, 67, 72)
        ]
        song = Song(
            name="dense",
            bpm=120,
            bars=1,
            loop_end=4,
            tracks=[Track(name="lead", instrument="Saw Lead", notes=notes)],
        )
        rendered = render_song(song, stereo=False)
        self.assertLessEqual(float(np.max(np.abs(rendered))), 0.941)
        self.assertFalse(np.any(np.abs(rendered) >= 0.95))

    def test_showcase_songs_are_full_arrangements_with_clean_loops(self):
        songs = create_showcase_songs()
        self.assertEqual(tuple(song.name for song in songs), SHOWCASE_SONG_NAMES)
        for song in songs:
            notes = [note for track in song.tracks for note in track.notes]
            self.assertEqual(song.bars, 16, song.name)
            self.assertGreaterEqual(len(song.tracks), 6, song.name)
            self.assertGreaterEqual(len(notes), 150, song.name)
            self.assertGreaterEqual(min(note.pitch for note in notes), 36, song.name)
            self.assertLessEqual(max(note.pitch for note in notes), 84, song.name)
            rendered = render_song(song, sample_rate=8000, loop_only=True, stereo=True)
            self.assertGreater(float(np.sqrt(np.mean(rendered**2))), 0.07, song.name)
            self.assertLessEqual(float(np.max(np.abs(rendered))), 0.941, song.name)
            self.assertEqual(float(np.max(np.abs(rendered[-80:]))), 0.0, song.name)

    def test_wav_export(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tone.wav"
            data = synthesize(get_preset("Coin"), sample_rate=22050)
            export_audio(path, data, sample_rate=22050, channels=1)
            with wave.open(str(path), "rb") as source:
                self.assertEqual(source.getframerate(), 22050)
                self.assertEqual(source.getnchannels(), 1)
                self.assertGreater(source.getnframes(), 100)

    def test_midi_round_trip_preserves_notes_and_tempo(self):
        song = Song(
            name="midi",
            bpm=96,
            bars=2,
            loop_end=8,
            tracks=[
                Track(
                    name="lead",
                    notes=[
                        Note(pitch=60, start=0, duration=1, velocity=88),
                        Note(pitch=64, start=1.5, duration=0.5, velocity=72),
                    ],
                )
            ],
        )
        with tempfile.TemporaryDirectory() as folder:
            path = export_song_midi(song, Path(folder) / "loop.mid")
            imported = import_song_midi(path)
        self.assertEqual(imported.bpm, 96)
        self.assertEqual(imported.tracks[0].name, "lead")
        self.assertEqual(len(imported.tracks[0].notes), 2)
        self.assertEqual(imported.tracks[0].notes[1].start, 1.5)
        self.assertEqual(imported.tracks[0].notes[1].velocity, 72)


class ProjectTests(unittest.TestCase):
    def test_starter_project_installs_showcase_once(self):
        with tempfile.TemporaryDirectory() as folder:
            project = BlipkitProject.create(
                Path(folder) / "Starter",
                "Starter",
                template="Blank",
            )
            first = project.ensure_showcase_songs()
            second = project.ensure_showcase_songs()
            names = [song.name for _path, song in project.load_songs()]
            self.assertEqual([song.id for song in first], [song.id for song in second])
            for name in SHOWCASE_SONG_NAMES:
                self.assertEqual(names.count(name), 1)
            project.close()

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

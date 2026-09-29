"""Minimal cross-platform WAV preview without a bundled media framework."""

from __future__ import annotations

import atexit
import shutil
import subprocess
import sys
import threading

import numpy as np

from .audio_io import write_wav
from .config import data_dir


class AudioPlayer:
    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._generation = 0
        atexit.register(self.stop)

    def play(self, samples: np.ndarray, sample_rate: int = 44100) -> bool:
        with self._lock:
            self.stop()
            cache = data_dir() / "cache"
            cache.mkdir(parents=True, exist_ok=True)
            self._generation += 1
            path = cache / f"preview_{self._generation}.wav"
            write_wav(path, samples, sample_rate=sample_rate, bit_depth=16)

            if sys.platform == "darwin":
                command = ["/usr/bin/afplay", str(path)]
            elif sys.platform.startswith("win"):
                import winsound

                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
                return True
            else:
                player = shutil.which("aplay") or shutil.which("paplay")
                if not player:
                    return False
                command = [player, str(path)]
            try:
                self._process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except OSError:
                self._process = None
                return False

    def stop(self) -> None:
        if sys.platform.startswith("win"):
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except (ImportError, RuntimeError):
                pass
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=0.4)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

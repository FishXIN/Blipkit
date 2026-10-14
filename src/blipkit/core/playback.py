"""Minimal cross-platform WAV preview without a bundled media framework."""

from __future__ import annotations

import atexit
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

import numpy as np

from .audio_io import write_wav
from .config import data_dir


class AudioPlayer:
    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._generation = 0
        self._started_at: float | None = None
        self._native_module: Any = None
        self._native_engine: Any = None
        self._native_player: Any = None
        self._native_players: list[Any] = []
        self._native_buffer: Any = None
        self._native_buffers: list[Any | None] = []
        self._native_active_index = 0
        self._native_swap_generation = 0
        self._native_swap_timer: threading.Timer | None = None
        self._native_format: tuple[int, int] | None = None
        atexit.register(self.close)

    def prepare(self, sample_rate: int = 44100, channels: int = 2) -> None:
        if sys.platform != "darwin":
            return
        with self._lock:
            self._ensure_native_engine(sample_rate, channels)

    def play(self, samples: np.ndarray, sample_rate: int = 44100) -> bool:
        with self._lock:
            self.stop()
            data = np.asarray(samples, dtype=np.float32)
            if sys.platform == "darwin" and self._play_native(data, sample_rate):
                return True

            cache = data_dir() / "cache"
            cache.mkdir(parents=True, exist_ok=True)
            self._generation += 1
            path = cache / f"preview_{self._generation}.wav"
            write_wav(path, data, sample_rate=sample_rate, bit_depth=16)

            if sys.platform == "darwin":
                command = ["/usr/bin/afplay", str(path)]
            elif sys.platform.startswith("win"):
                import winsound

                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
                self._started_at = time.monotonic()
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
                self._started_at = time.monotonic()
                return True
            except OSError:
                self._process = None
                return False

    def replace(self, samples: np.ndarray, sample_rate: int = 44100) -> bool:
        with self._lock:
            data = np.asarray(samples, dtype=np.float32)
            if (
                sys.platform == "darwin"
                and self._native_player is not None
                and self._native_player.isPlaying()
                and self._play_native(data, sample_rate, seamless=True)
            ):
                return True
            return self.play(data, sample_rate)

    def _ensure_native_engine(self, sample_rate: int, channels: int) -> bool:
        native_format = (int(sample_rate), int(channels))
        if (
            self._native_engine is not None
            and len(self._native_players) == 2
            and self._native_format == native_format
            and self._native_engine.isRunning()
        ):
            return True
        self._close_native()
        try:
            import AVFoundation

            engine = AVFoundation.AVAudioEngine.alloc().init()
            players = [
                AVFoundation.AVAudioPlayerNode.alloc().init(),
                AVFoundation.AVAudioPlayerNode.alloc().init(),
            ]
            audio_format = (
                AVFoundation.AVAudioFormat.alloc()
                .initStandardFormatWithSampleRate_channels_(
                    float(sample_rate),
                    channels,
                )
            )
            if audio_format is None:
                return False
            for player in players:
                engine.attachNode_(player)
                engine.connect_to_format_(
                    player,
                    engine.mainMixerNode(),
                    audio_format,
                )
            result = engine.startAndReturnError_(None)
            started = bool(result[0]) if isinstance(result, tuple) else bool(result)
            if not started:
                engine.stop()
                return False
            self._native_module = AVFoundation
            self._native_engine = engine
            self._native_players = players
            self._native_buffers = [None, None]
            self._native_active_index = 0
            self._native_player = players[0]
            self._native_format = native_format
            return True
        except (ImportError, OSError, RuntimeError):
            self._close_native()
            return False

    def _play_native(
        self,
        samples: np.ndarray,
        sample_rate: int,
        *,
        seamless: bool = False,
    ) -> bool:
        if samples.ndim not in (1, 2) or not len(samples):
            return False
        channels = 2
        if not self._ensure_native_engine(sample_rate, channels):
            return False
        assert self._native_module is not None
        assert self._native_player is not None
        previous_index = self._native_active_index
        self._cancel_native_swap()
        player_index = (
            1 - previous_index
            if seamless and self._native_players[previous_index].isPlaying()
            else previous_index
        )
        player = self._native_players[player_index]
        player.stop()
        player.setVolume_(0.0 if player_index != previous_index else 1.0)
        audio_format = (
            self._native_module.AVAudioFormat.alloc()
            .initStandardFormatWithSampleRate_channels_(float(sample_rate), channels)
        )
        buffer = (
            self._native_module.AVAudioPCMBuffer.alloc()
            .initWithPCMFormat_frameCapacity_(audio_format, len(samples))
        )
        if buffer is None:
            return False
        buffer.setFrameLength_(len(samples))
        output_channels = buffer.floatChannelData()
        if output_channels is None:
            return False
        clipped = np.clip(samples, -1.0, 1.0)
        for channel in range(channels):
            destination = np.frombuffer(
                output_channels[channel].as_buffer(len(samples)),
                dtype=np.float32,
            )
            source = (
                clipped
                if clipped.ndim == 1
                else clipped[:, min(channel, clipped.shape[1] - 1)]
            )
            destination[:] = source
        self._generation += 1
        self._native_buffers[player_index] = buffer
        player.scheduleBuffer_completionHandler_(buffer, lambda: None)
        player.play()
        if player_index != previous_index:
            self._native_swap_generation += 1
            generation = self._native_swap_generation
            timer = threading.Timer(
                0.05,
                self._finish_native_swap,
                args=(generation, previous_index, player_index),
            )
            timer.daemon = True
            self._native_swap_timer = timer
            timer.start()
        self._native_active_index = player_index
        self._native_player = player
        self._native_buffer = buffer
        self._started_at = time.monotonic()
        return True

    def _cancel_native_swap(self) -> None:
        if self._native_swap_timer is not None:
            self._native_swap_timer.cancel()
            self._native_swap_timer = None
        if self._native_players:
            active = self._native_players[self._native_active_index]
            active.setVolume_(1.0)
            for index, player in enumerate(self._native_players):
                if index != self._native_active_index:
                    player.stop()
                    player.setVolume_(1.0)
                    self._native_buffers[index] = None

    def _finish_native_swap(
        self,
        generation: int,
        previous_index: int,
        player_index: int,
    ) -> None:
        with self._lock:
            if (
                generation != self._native_swap_generation
                or not self._native_players
                or self._native_active_index != player_index
            ):
                return
            active = self._native_players[player_index]
            previous = self._native_players[previous_index]
            active.setVolume_(1.0)
            previous.setVolume_(0.0)
            previous.stop()
            previous.setVolume_(1.0)
            self._native_buffers[previous_index] = None
            self._native_swap_timer = None

    def current_time(self) -> float:
        with self._lock:
            if self._native_player is not None and self._native_player.isPlaying():
                node_time = self._native_player.lastRenderTime()
                if node_time is not None:
                    player_time = self._native_player.playerTimeForNodeTime_(node_time)
                    if player_time is not None and player_time.sampleRate() > 0:
                        return max(0.0, player_time.sampleTime() / player_time.sampleRate())
            if self._started_at is None:
                return 0.0
            fallback_latency = 0.06 if sys.platform == "darwin" else 0.0
            return max(0.0, time.monotonic() - self._started_at - fallback_latency)

    def stop(self) -> None:
        with self._lock:
            self._cancel_native_swap()
            self._native_swap_generation += 1
            for player in self._native_players:
                player.stop()
            self._native_buffer = None
            self._native_buffers = [None for _player in self._native_players]
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
            self._started_at = None

    def _close_native(self) -> None:
        self._cancel_native_swap()
        self._native_swap_generation += 1
        for player in self._native_players:
            player.stop()
        if self._native_engine is not None:
            self._native_engine.stop()
        self._native_buffer = None
        self._native_buffers = []
        self._native_players = []
        self._native_player = None
        self._native_active_index = 0
        self._native_engine = None
        self._native_module = None
        self._native_format = None

    def close(self) -> None:
        with self._lock:
            self.stop()
            self._close_native()

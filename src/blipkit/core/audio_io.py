"""Audio encoding helpers with WAV guaranteed and optional compressed formats."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SUPPORTED_FORMATS = ("wav", "ogg", "mp3", "flac")


def normalize_audio(samples: np.ndarray, ceiling: float = 0.92) -> np.ndarray:
    data = np.asarray(samples, dtype=np.float32)
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak <= 0.000001:
        return data
    return data * min(1.0, ceiling / peak)


def ensure_channels(samples: np.ndarray, channels: int) -> np.ndarray:
    data = np.asarray(samples, dtype=np.float32)
    if channels == 1:
        if data.ndim == 2:
            return np.mean(data, axis=1).astype(np.float32)
        return data
    if data.ndim == 1:
        return np.column_stack((data, data)).astype(np.float32)
    if data.shape[1] == 1:
        return np.repeat(data, 2, axis=1).astype(np.float32)
    return data[:, :2]


def _pcm_bytes(samples: np.ndarray, bit_depth: int) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    if bit_depth == 16:
        return (clipped * 32767.0).astype("<i2").tobytes()
    if bit_depth == 24:
        values = (clipped * 8388607.0).astype(np.int32).reshape(-1)
        packed = np.empty((values.size, 3), dtype=np.uint8)
        packed[:, 0] = values & 0xFF
        packed[:, 1] = (values >> 8) & 0xFF
        packed[:, 2] = (values >> 16) & 0xFF
        return packed.tobytes()
    raise ValueError("bit_depth must be 16 or 24")


def write_wav(
    path: Path,
    samples: np.ndarray,
    sample_rate: int = 44100,
    bit_depth: int = 16,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(samples, dtype=np.float32)
    channels = 1 if data.ndim == 1 else int(data.shape[1])
    temp = path.with_name(path.name + ".tmp")
    with wave.open(str(temp), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(bit_depth // 8)
        output.setframerate(sample_rate)
        output.writeframes(_pcm_bytes(data, bit_depth))
    temp.replace(path)
    return path


def _write_with_soundfile(
    path: Path,
    samples: np.ndarray,
    sample_rate: int,
    bit_depth: int,
) -> Path:
    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError(f"{path.suffix.upper()} export requires the soundfile package") from exc
    subtype = "PCM_24" if bit_depth == 24 and path.suffix.lower() == ".flac" else None
    temp = path.with_name(path.stem + ".tmp" + path.suffix)
    sf.write(str(temp), samples, sample_rate, subtype=subtype)
    temp.replace(path)
    return path


def _write_mp3(
    path: Path,
    samples: np.ndarray,
    sample_rate: int,
) -> Path:
    data = np.asarray(samples, dtype=np.float32)
    channels = 1 if data.ndim == 1 else data.shape[1]
    pcm = _pcm_bytes(data, 16)
    try:
        import lameenc

        encoder = lameenc.Encoder()
        encoder.set_bit_rate(192)
        encoder.set_in_sample_rate(sample_rate)
        encoder.set_channels(channels)
        encoder.set_quality(2)
        encoded = encoder.encode(pcm) + encoder.flush()
        temp = path.with_name(path.name + ".tmp")
        temp.write_bytes(encoded)
        temp.replace(path)
        return path
    except ImportError:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("MP3 export requires lameenc or ffmpeg")
        with tempfile.TemporaryDirectory(prefix="blipkit_mp3_") as folder:
            wav_path = Path(folder) / "source.wav"
            write_wav(wav_path, data, sample_rate, 16)
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(wav_path),
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "192k",
                    str(path),
                ],
                check=True,
            )
        return path


def export_audio(
    path: Path,
    samples: np.ndarray,
    sample_rate: int = 44100,
    bit_depth: int = 16,
    channels: int = 2,
    normalize: bool = True,
) -> Path:
    path = Path(path)
    suffix = path.suffix.lower().lstrip(".")
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported audio format: {suffix}")
    data = ensure_channels(samples, channels)
    if normalize:
        data = normalize_audio(data)
    if suffix == "wav":
        return write_wav(path, data, sample_rate, bit_depth)
    if suffix == "mp3":
        return _write_mp3(path, data, sample_rate)
    return _write_with_soundfile(path, data, sample_rate, bit_depth)


def audio_info(path: Path) -> tuple[float, int, int]:
    path = Path(path)
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as source:
            rate = source.getframerate()
            channels = source.getnchannels()
            duration = source.getnframes() / float(rate)
            return duration, rate, channels
    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Reading compressed audio requires soundfile") from exc
    info = sf.info(str(path))
    return float(info.duration), int(info.samplerate), int(info.channels)

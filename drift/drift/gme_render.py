"""Render AY/EMUL files to wav using libgme (game-music-emu) via ctypes."""

from __future__ import annotations

import ctypes
import ctypes.util
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 22050
MAX_DURATION_S = 120
CHANNELS = 1


def _load_libgme() -> ctypes.CDLL:
    """Find and load the libgme shared library."""
    # Try brew location first, then system
    for candidate in [
        "/opt/homebrew/lib/libgme.dylib",
        "/usr/local/lib/libgme.dylib",
        ctypes.util.find_library("gme"),
    ]:
        if candidate:
            try:
                return ctypes.CDLL(candidate)
            except OSError:
                continue
    raise RuntimeError(
        "libgme not found. Install with: brew install game-music-emu"
    )


def render_emul_to_wav(
    src: Path,
    dst: Path,
    sample_rate: int = SAMPLE_RATE,
    max_duration_s: int = MAX_DURATION_S,
) -> bool:
    """Render a .emul (or any libgme-supported) file to a mono wav.

    Returns True on success, False on failure.
    """
    lib = _load_libgme()

    emu_ptr = ctypes.c_void_p()
    err = lib.gme_open_file(
        str(src).encode(), ctypes.byref(emu_ptr), sample_rate
    )
    if err:
        return False

    try:
        track_count = lib.gme_track_count(emu_ptr)
        if track_count < 1:
            return False

        err = lib.gme_start_track(emu_ptr, 0)
        if err:
            return False

        # Render in chunks — stereo interleaved s16
        chunk_frames = sample_rate
        total_frames = sample_rate * max_duration_s
        buf_type = ctypes.c_short * (chunk_frames * 2)
        buf = buf_type()

        all_samples: list[np.ndarray] = []
        rendered = 0

        while rendered < total_frames:
            if lib.gme_track_ended(emu_ptr):
                break
            n = min(chunk_frames, total_frames - rendered)
            err = lib.gme_play(emu_ptr, n * 2, buf)
            if err:
                break
            stereo = np.frombuffer(buf, dtype=np.int16, count=n * 2)
            mono = ((stereo[0::2].astype(np.float32) + stereo[1::2].astype(np.float32)) / 2.0) / 32768.0
            all_samples.append(mono)
            rendered += n

        if not all_samples:
            return False

        audio = np.concatenate(all_samples)
        dst.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(dst), audio, sample_rate)
        return True

    finally:
        lib.gme_delete(emu_ptr)

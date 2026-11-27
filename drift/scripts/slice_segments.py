#!/usr/bin/env python3
"""
Slice rendered wav files into fixed-length non-overlapping segments.

Reads wavs from _data/rendered_wav/{chip_type}/ and writes segments to
_data/segments/{chip_type}/. Silently skips mostly-silent chunks (RMS < threshold)
and drops the final short chunk rather than padding it.

Usage:
    python scripts/slice_segments.py
    python scripts/slice_segments.py --types sid vgm
    python scripts/slice_segments.py --durations 4
    python scripts/slice_segments.py --rms-threshold 0.01
"""
import argparse
from collections import defaultdict
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

SAMPLE_RATE = 22050
DEFAULT_DURATIONS = [4, 8]
DEFAULT_RMS_THRESHOLD = 0.005
RENDERED_WAV_ROOT = Path("_data/rendered_wav")
SEGMENTS_ROOT = Path("_data/segments")


def segment_lengths(durations: list[int]) -> dict[int, int]:
    """Map duration (seconds) → sample count at SAMPLE_RATE."""
    return {d: d * SAMPLE_RATE for d in durations}


def output_exists(out_dir: Path, stem: str) -> bool:
    """Return True if any segment for this source file already exists."""
    return any(out_dir.glob(f"{stem}_*"))


def slice_wav(
    wav_path: Path,
    out_dir: Path,
    duration_samples: dict[int, int],
    rms_threshold: float,
) -> dict[int, int]:
    """
    Slice one wav into segments for each requested duration.

    Returns a dict of {duration_seconds: segments_written}.
    """
    audio, _ = librosa.load(str(wav_path), sr=SAMPLE_RATE, mono=True)
    stem = wav_path.stem
    counts: dict[int, int] = defaultdict(int)

    for dur, n_samples in duration_samples.items():
        if output_exists(out_dir, f"{stem}") and any(
            out_dir.glob(f"{stem}_*_{dur}s.wav")
        ):
            continue

        idx = 0
        offset = 0
        while offset + n_samples <= len(audio):
            chunk = audio[offset : offset + n_samples]
            rms = np.sqrt(np.mean(chunk ** 2))
            if rms >= rms_threshold:
                fname = out_dir / f"{stem}_{idx:03d}_{dur}s.wav"
                sf.write(str(fname), chunk, SAMPLE_RATE)
                counts[dur] += 1
            idx += 1
            offset += n_samples

    return counts


def process_chip_type(
    chip_type: str,
    durations: list[int],
    rms_threshold: float,
) -> dict[int, int]:
    """Process all wavs for one chip type. Returns total segments per duration."""
    src_dir = RENDERED_WAV_ROOT / chip_type
    out_dir = SEGMENTS_ROOT / chip_type
    out_dir.mkdir(parents=True, exist_ok=True)

    wav_files = sorted(src_dir.glob("*.wav"))
    total = len(wav_files)
    if total == 0:
        print(f"  {chip_type}: no wav files found in {src_dir}")
        return {}

    dur_samples = segment_lengths(durations)
    totals: dict[int, int] = defaultdict(int)

    for i, wav_path in enumerate(wav_files, 1):
        stem = wav_path.stem
        already_done = all(
            any(out_dir.glob(f"{stem}_*_{d}s.wav")) for d in durations
        )
        if already_done:
            print(f"\r  {chip_type}: {i}/{total} (skipped {stem})", end="", flush=True)
            continue

        counts = slice_wav(wav_path, out_dir, dur_samples, rms_threshold)
        for dur, n in counts.items():
            totals[dur] += n
        print(f"\r  {chip_type}: {i}/{total} — {stem}", end="", flush=True)

    print()
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--durations",
        nargs="+",
        type=int,
        default=DEFAULT_DURATIONS,
        metavar="SECS",
        help="segment durations in seconds (default: 4 8)",
    )
    parser.add_argument(
        "--rms-threshold",
        type=float,
        default=DEFAULT_RMS_THRESHOLD,
        dest="rms_threshold",
        help="discard chunks with RMS below this value (default: 0.005)",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        metavar="CHIP",
        help="chip types to process (default: all found in _data/rendered_wav/)",
    )
    args = parser.parse_args()

    if not RENDERED_WAV_ROOT.exists():
        print(f"Rendered wav root not found: {RENDERED_WAV_ROOT}")
        return

    chip_types = args.types or [d.name for d in sorted(RENDERED_WAV_ROOT.iterdir()) if d.is_dir()]
    if not chip_types:
        print("No chip types found.")
        return

    print(f"Durations: {args.durations}s  |  RMS threshold: {args.rms_threshold}")
    print(f"Chip types: {', '.join(chip_types)}\n")

    summary: dict[str, dict[int, int]] = {}
    for chip in chip_types:
        print(f"{chip}:")
        totals = process_chip_type(chip, args.durations, args.rms_threshold)
        summary[chip] = totals

    print("\n--- Summary ---")
    for chip, totals in summary.items():
        if totals:
            parts = ", ".join(f"{d}s: {totals.get(d, 0)}" for d in sorted(args.durations))
            print(f"  {chip}: {parts}")
        else:
            print(f"  {chip}: 0 segments")


if __name__ == "__main__":
    main()

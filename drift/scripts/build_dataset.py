#!/usr/bin/env python3
"""Build the chip-tune spectrogram dataset end-to-end.

Pipeline:
  1. Render chip files to wav     (scripts/render_wav.py)
  2. Slice wav files into segments (scripts/slice_segments.py)
  3. Build dataset metadata        (drift.dataset.build_metadata)

Steps 1 and 2 can be skipped with --skip-render and --skip-slice.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build chip-tune spectrogram dataset end-to-end."
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Skip step 1: rendering chip files to wav.",
    )
    parser.add_argument(
        "--skip-slice",
        action="store_true",
        help="Skip step 2: slicing wav files into segments.",
    )
    parser.add_argument(
        "--segments-dir",
        type=Path,
        default=Path("_data/segments"),
        help="Root directory for segments (default: _data/segments).",
    )
    return parser.parse_args()


def run_script(script: str, label: str) -> None:
    """Run a Python script as a subprocess, streaming its output."""
    print(f"\n{'='*60}")
    print(f"Step: {label}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, script],
        check=False,
    )
    if result.returncode != 0:
        print(f"\nERROR: {label} failed (exit code {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)


def print_summary(segments_dir: Path, metadata: dict) -> None:
    """Print a human-readable summary of the built dataset."""
    print(f"\n{'='*60}")
    print("Dataset summary")
    print(f"{'='*60}")

    chip_types: list[str] = metadata["chip_types"]
    splits: dict[str, list[str]] = metadata["splits"]

    # Count segments per chip type across all splits.
    counts: dict[str, int] = {ct: 0 for ct in chip_types}
    for paths in splits.values():
        for p in paths:
            for ct in chip_types:
                if p.startswith(ct + "/"):
                    counts[ct] += 1
                    break

    print("\nTotal segments per chip type:")
    for ct, n in counts.items():
        print(f"  {ct:12s}: {n}")

    print("\nSplit sizes:")
    for split_name, paths in splits.items():
        print(f"  {split_name:5s}: {len(paths)}")

    # Infer spectrogram shape from a sample file.
    sample_path: Path | None = None
    for paths in splits.values():
        if paths:
            sample_path = segments_dir / paths[0]
            break

    if sample_path and sample_path.exists():
        try:
            import librosa
            import numpy as np
            from drift.dataset import HOP_LENGTH, N_FFT, N_MELS, SR

            y, _ = librosa.load(str(sample_path), sr=SR, mono=True)
            S = librosa.feature.melspectrogram(
                y=y, sr=SR, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
            )
            print(f"\nSpectrogram shape (sample): (1, {N_MELS}, {S.shape[1]})")
        except Exception as exc:  # noqa: BLE001
            print(f"\nCould not infer spectrogram shape: {exc}")


def main() -> None:
    args = parse_args()
    segments_dir: Path = args.segments_dir

    # Resolve script paths relative to this file's directory.
    scripts_dir = Path(__file__).parent

    # Step 1 — render chip files to wav.
    if args.skip_render:
        print("Skipping step 1: render.")
    else:
        run_script(str(scripts_dir / "render_wav.py"), "Render chip files → wav")

    # Step 2 — slice wav files into segments.
    if args.skip_slice:
        print("Skipping step 2: slice.")
    else:
        run_script(str(scripts_dir / "slice_segments.py"), "Slice wav → segments")

    # Step 3 — build metadata.
    print(f"\n{'='*60}")
    print("Step: Build dataset metadata")
    print(f"{'='*60}")

    if not segments_dir.exists():
        print(f"ERROR: segments_dir not found: {segments_dir}", file=sys.stderr)
        sys.exit(1)

    from drift.dataset import build_metadata

    metadata = build_metadata(segments_dir)
    print_summary(segments_dir, metadata)

    print("\nDone.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
spectrogram.py — Side-by-side spectrogram comparison of two WAV files.

Compares ZX Spectrum reference audio against the Rust beeper engine output.
Generates a PNG with:
  - Two spectrograms (top row, shared Y axis)
  - Per-note frequency analysis table (bottom)

Usage:
  python3 spectrogram.py zx-scale.wav rust-scale.wav
  python3 spectrogram.py zx-scale.wav rust-scale.wav --output my-compare.png
  python3 spectrogram.py --demo     # synthetic test, no real WAVs needed
"""

import argparse
import sys

# ---------------------------------------------------------------------------
# Dependency check — friendly error before numpy import fails
# ---------------------------------------------------------------------------
def _check_deps():
    missing = []
    for pkg in ("numpy", "matplotlib", "scipy"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("Missing packages:", ", ".join(missing))
        print("Install with:  pip3 install", " ".join(missing))
        sys.exit(1)

_check_deps()

import numpy as np
import matplotlib
matplotlib.use("Agg")          # non-interactive backend — saves to file
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.io import wavfile
from scipy.signal import spectrogram as sci_spectrogram

# ---------------------------------------------------------------------------
# WAV loading
# ---------------------------------------------------------------------------
def load_wav(path: str) -> tuple[int, np.ndarray]:
    """Read a WAV file. Returns (sample_rate, mono_float_array)."""
    rate, data = wavfile.read(path)

    # Convert to float in range [-1, 1]
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float32) - 128) / 128.0
    else:
        data = data.astype(np.float32)

    # Mix stereo to mono
    if data.ndim == 2:
        data = data.mean(axis=1)

    return rate, data


# ---------------------------------------------------------------------------
# Synthetic demo WAVs (square waves at two close frequencies)
# ---------------------------------------------------------------------------
def make_demo_wav(freq_hz: float, duration: float = 2.0, sample_rate: int = 44100) -> tuple[int, np.ndarray]:
    """Generate a square wave at freq_hz for demo mode."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Square wave: sign of a sine
    signal = np.sign(np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)
    return sample_rate, signal


# ---------------------------------------------------------------------------
# Spectrogram plot (one panel)
# ---------------------------------------------------------------------------
def plot_spectrogram(ax, signal: np.ndarray, sample_rate: int, title: str):
    """Draw a spectrogram on the given axes."""
    # nperseg: window size in samples. 1024 gives ~43 Hz resolution at 44.1 kHz.
    nperseg = 1024
    noverlap = 768          # 75% overlap — smoother time axis
    freqs, times, Sxx = sci_spectrogram(
        signal,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=noverlap,
        scaling="spectrum",
    )

    # Convert power to dB, clip floor at -80 dB
    Sxx_db = 10 * np.log10(Sxx + 1e-12)
    Sxx_db = np.clip(Sxx_db, -80, None)

    # Restrict display to 0–4000 Hz (all beeper content is below 2 kHz)
    freq_mask = freqs <= 4000
    freqs_cut = freqs[freq_mask]
    Sxx_cut = Sxx_db[freq_mask, :]

    mesh = ax.pcolormesh(
        times, freqs_cut, Sxx_cut,
        shading="gouraud",   # smooth interpolation
        cmap="inferno",
        vmin=-80, vmax=0,
    )
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel("Time (s)", fontsize=9)
    ax.set_ylabel("Frequency (Hz)", fontsize=9)
    ax.set_ylim(0, 4000)

    return mesh, freqs, times, Sxx


# ---------------------------------------------------------------------------
# Per-note frequency detection via zero-crossing rate
# ---------------------------------------------------------------------------
def detect_note_frequencies(signal: np.ndarray, sample_rate: int,
                             min_note_len_s: float = 0.08,
                             zcr_window_s: float = 0.02) -> list[dict]:
    """
    Segment the signal into notes by looking for consistent zero-crossing rate.

    Zero-crossing rate (ZCR) ≈ frequency for a square/triangle wave:
        freq ≈ ZCR / 2  (each cycle has two crossings)

    Returns a list of dicts: {start_s, end_s, freq_hz}
    """
    win = int(sample_rate * zcr_window_s)
    if win < 2:
        win = 2

    n_windows = len(signal) // win
    if n_windows == 0:
        return []

    # ZCR per window
    zcr = np.zeros(n_windows)
    for i in range(n_windows):
        chunk = signal[i * win : (i + 1) * win]
        # Count sign changes
        crossings = np.sum(np.diff(np.sign(chunk)) != 0)
        zcr[i] = crossings / (2 * zcr_window_s)   # → Hz

    # Merge consecutive windows with similar frequency (within 5%)
    min_note_windows = max(1, int(min_note_len_s / zcr_window_s))
    notes = []
    seg_start = 0
    seg_freq = zcr[0]

    for i in range(1, n_windows):
        # Relative difference — allow 5% variance
        if seg_freq > 1 and abs(zcr[i] - seg_freq) / seg_freq < 0.05:
            # Same note — update rolling mean
            seg_freq = seg_freq * 0.9 + zcr[i] * 0.1
        else:
            # New note — commit previous segment if long enough
            if (i - seg_start) >= min_note_windows:
                notes.append({
                    "start_s": seg_start * zcr_window_s,
                    "end_s": i * zcr_window_s,
                    "freq_hz": round(seg_freq, 1),
                })
            seg_start = i
            seg_freq = zcr[i]

    # Flush last segment
    if (n_windows - seg_start) >= min_note_windows:
        notes.append({
            "start_s": seg_start * zcr_window_s,
            "end_s": n_windows * zcr_window_s,
            "freq_hz": round(seg_freq, 1),
        })

    return notes


def align_notes(notes_a: list[dict], notes_b: list[dict]) -> list[tuple]:
    """
    Pair notes from A and B by temporal overlap.

    Returns list of (note_index, freq_a, freq_b, diff_hz).
    If counts differ, pairs up to the shorter list.
    """
    pairs = []
    for i, (a, b) in enumerate(zip(notes_a, notes_b)):
        diff = round(b["freq_hz"] - a["freq_hz"], 1)
        pairs.append((i + 1, a["freq_hz"], b["freq_hz"], diff))
    return pairs


# ---------------------------------------------------------------------------
# Per-note frequency analysis subplot
# ---------------------------------------------------------------------------
def plot_note_table(ax, pairs: list[tuple], label_a: str, label_b: str):
    """Draw a text table of per-note frequency comparison."""
    ax.axis("off")

    if not pairs:
        ax.text(0.5, 0.5, "No notes detected", ha="center", va="center",
                transform=ax.transAxes, fontsize=10, color="gray")
        return

    headers = ["Note", f"{label_a} (Hz)", f"{label_b} (Hz)", "Diff (Hz)"]
    rows = [[str(p[0]), str(p[1]), str(p[2]), f"{p[3]:+.1f}"] for p in pairs]

    table = ax.table(
        cellText=rows,
        colLabels=headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)

    # Header style
    for col in range(len(headers)):
        table[0, col].set_facecolor("#2c2c3e")
        table[0, col].set_text_props(color="white", fontweight="bold")

    # Colour diff column: green if close, orange if 10+ Hz, red if 50+ Hz
    for row_idx, pair in enumerate(pairs):
        diff = abs(pair[3])
        if diff < 10:
            colour = "#d4edda"   # light green
        elif diff < 50:
            colour = "#fff3cd"   # amber
        else:
            colour = "#f8d7da"   # red
        table[row_idx + 1, 3].set_facecolor(colour)

    ax.set_title("Per-Note Frequency Analysis", fontsize=10, fontweight="bold", pad=12)


# ---------------------------------------------------------------------------
# Main comparison figure
# ---------------------------------------------------------------------------
def generate_comparison(
    path_a: str,
    path_b: str,
    label_a: str = "ZX Spectrum",
    label_b: str = "Rust Engine",
    output: str = "spectrogram.png",
):
    """Build and save the comparison PNG."""
    print(f"Loading  {path_a}...")
    rate_a, sig_a = load_wav(path_a)

    print(f"Loading  {path_b}...")
    rate_b, sig_b = load_wav(path_b)

    print("Analysing notes...")
    notes_a = detect_note_frequencies(sig_a, rate_a)
    notes_b = detect_note_frequencies(sig_b, rate_b)
    pairs = align_notes(notes_a, notes_b)

    print(f"  {label_a}: {len(notes_a)} notes")
    print(f"  {label_b}: {len(notes_b)} notes")
    print(f"  Paired:  {len(pairs)}")

    # --- Layout ---
    fig = plt.figure(figsize=(14, 8), facecolor="#1a1a2e")
    fig.suptitle("Beeper Engine Comparison", fontsize=14, fontweight="bold",
                 color="white", y=0.98)

    gs = gridspec.GridSpec(
        2, 2,
        figure=fig,
        height_ratios=[2.5, 1],
        hspace=0.45,
        wspace=0.08,
    )

    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1], sharey=ax_a)   # shared Y = shared freq axis
    ax_table = fig.add_subplot(gs[1, :])             # table spans full width

    # Dark axes background
    for ax in (ax_a, ax_b, ax_table):
        ax.set_facecolor("#0d0d1a")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444466")

    # Spectrograms
    mesh_a, _, _, _ = plot_spectrogram(ax_a, sig_a, rate_a, label_a)
    mesh_b, _, _, _ = plot_spectrogram(ax_b, sig_b, rate_b, label_b)

    # Hide the Y axis label on the right panel (shared axis)
    ax_b.set_ylabel("")
    plt.setp(ax_b.get_yticklabels(), visible=False)

    # Shared colour bar
    cbar = fig.colorbar(mesh_a, ax=[ax_a, ax_b], orientation="vertical",
                        fraction=0.015, pad=0.02)
    cbar.set_label("Amplitude (dB)", color="white", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    # Note table
    plot_note_table(ax_table, pairs, label_a, label_b)
    ax_table.set_facecolor("#1a1a2e")

    plt.savefig(output, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved → {output}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate side-by-side spectrogram comparison of two WAV files.",
        epilog="Example: python3 spectrogram.py zx-scale.wav rust-scale.wav --output compare.png",
    )
    parser.add_argument("wav_a", nargs="?", help="First WAV (e.g. zx-scale.wav)")
    parser.add_argument("wav_b", nargs="?", help="Second WAV (e.g. rust-scale.wav)")
    parser.add_argument(
        "--output", "-o",
        default="spectrogram.png",
        help="Output PNG path (default: spectrogram.png)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with synthetic square waves (440 Hz vs 441 Hz) — no WAV files needed.",
    )
    args = parser.parse_args()

    if args.demo:
        # Write temp WAVs and compare them
        import tempfile, os
        from scipy.io import wavfile as wv

        print("Demo mode: generating synthetic square waves (440 Hz vs 441 Hz)...")
        with tempfile.TemporaryDirectory() as tmp:
            rate_a, sig_a = make_demo_wav(440.0, duration=2.0)
            rate_b, sig_b = make_demo_wav(441.0, duration=2.0)

            path_a = os.path.join(tmp, "demo-440.wav")
            path_b = os.path.join(tmp, "demo-441.wav")

            # scipy wavfile wants int16
            wv.write(path_a, rate_a, (sig_a * 32767).astype(np.int16))
            wv.write(path_b, rate_b, (sig_b * 32767).astype(np.int16))

            generate_comparison(
                path_a, path_b,
                label_a="440 Hz (demo)",
                label_b="441 Hz (demo)",
                output=args.output,
            )
        return

    if not args.wav_a or not args.wav_b:
        parser.error("Provide two WAV paths, or use --demo for a quick test.")

    generate_comparison(
        args.wav_a, args.wav_b,
        label_a="ZX Spectrum",
        label_b="Rust Engine",
        output=args.output,
    )


if __name__ == "__main__":
    main()

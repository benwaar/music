"""Extract melody from a generated spectrogram and re-render on a chip-tune voice.

Takes a generated wav, extracts pitch contour via pyin, quantises to a scale,
and synthesises on a square/triangle wave. Turns the model's "musical shape"
into actual notes.

Usage:
    python scripts/extract_melody.py _data/generated/m5_noise/two_pass/pass1_road/sample_000.wav
    python scripts/extract_melody.py input.wav --scale pentatonic --voice square --output melody.wav
"""

from __future__ import annotations

import argparse
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


SCALES = {
    "chromatic": list(range(12)),
    "pentatonic": [0, 2, 4, 7, 9],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}

SR = 22050


def extract_pitch(wav_path: Path) -> tuple[np.ndarray, np.ndarray, float]:
    """Extract pitch contour from audio using pyin."""
    y, sr = librosa.load(str(wav_path), sr=SR, mono=True)
    f0, voiced, _ = librosa.pyin(
        y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"),
        sr=sr, frame_length=2048, hop_length=512,
    )
    frame_duration = 512 / sr
    return f0, voiced, frame_duration


def quantise_to_scale(f0: np.ndarray, scale_name: str, root: str = "C") -> np.ndarray:
    """Quantise frequencies to nearest note in the given scale."""
    scale = SCALES[scale_name]
    root_midi = librosa.note_to_midi(f"{root}0")

    quantised = np.full_like(f0, np.nan)
    for i, freq in enumerate(f0):
        if np.isnan(freq) or freq <= 0:
            continue
        midi = librosa.hz_to_midi(freq)
        note_in_octave = round(midi - root_midi) % 12
        closest = min(scale, key=lambda s: min(abs(note_in_octave - s), 12 - abs(note_in_octave - s)))
        octave = int((midi - root_midi) // 12)
        quantised[i] = librosa.midi_to_hz(root_midi + octave * 12 + closest)

    return quantised


def square_wave(freq: float, duration: float, sr: int = SR, duty: float = 0.5) -> np.ndarray:
    """Generate a square wave at the given frequency."""
    t = np.arange(int(sr * duration)) / sr
    phase = (t * freq) % 1.0
    return np.where(phase < duty, 0.8, -0.8).astype(np.float32)


def triangle_wave(freq: float, duration: float, sr: int = SR) -> np.ndarray:
    """Generate a triangle wave at the given frequency."""
    t = np.arange(int(sr * duration)) / sr
    phase = (t * freq) % 1.0
    return (2.0 * np.abs(2.0 * phase - 1.0) - 1.0).astype(np.float32) * 0.8


def pulse_wave(freq: float, duration: float, sr: int = SR) -> np.ndarray:
    """Generate a 25% pulse wave (classic NES lead sound)."""
    return square_wave(freq, duration, sr, duty=0.25)


VOICES = {
    "square": square_wave,
    "triangle": triangle_wave,
    "pulse": pulse_wave,
}


def apply_envelope(samples: np.ndarray, attack: int = 100, release: int = 200) -> np.ndarray:
    """Simple AR envelope to avoid clicks."""
    n = len(samples)
    attack = min(attack, n // 2)
    release = min(release, n // 2)
    env = np.ones(n, dtype=np.float32)
    env[:attack] = np.linspace(0, 1, attack)
    env[-release:] = np.linspace(1, 0, release)
    return samples * env


def synthesise(
    freqs: np.ndarray, frame_duration: float, voice_name: str = "square",
) -> np.ndarray:
    """Synthesise audio from a quantised pitch contour."""
    voice_fn = VOICES[voice_name]
    audio = np.zeros(0, dtype=np.float32)

    i = 0
    while i < len(freqs):
        if np.isnan(freqs[i]):
            silence = np.zeros(int(SR * frame_duration), dtype=np.float32)
            audio = np.concatenate([audio, silence])
            i += 1
            continue

        freq = freqs[i]
        note_len = 1
        while i + note_len < len(freqs) and not np.isnan(freqs[i + note_len]) and abs(freqs[i + note_len] - freq) < 0.5:
            note_len += 1

        duration = note_len * frame_duration
        samples = voice_fn(freq, duration)
        samples = apply_envelope(samples)
        audio = np.concatenate([audio, samples])
        i += note_len

    return audio


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract melody from generated audio")
    parser.add_argument("input", help="Path to input wav file")
    parser.add_argument("--scale", default="pentatonic", choices=list(SCALES.keys()))
    parser.add_argument("--root", default="C", help="Root note for scale quantisation")
    parser.add_argument("--voice", default="square", choices=list(VOICES.keys()))
    parser.add_argument("--output", default="", help="Output wav path (default: input_melody.wav)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_name(input_path.stem + "_melody.wav")

    print(f"Extracting pitch from {input_path}...")
    f0, voiced, frame_duration = extract_pitch(input_path)

    voiced_pct = np.sum(~np.isnan(f0)) / len(f0) * 100
    print(f"  Voiced frames: {voiced_pct:.1f}%")
    valid = f0[~np.isnan(f0)]
    if len(valid) > 0:
        print(f"  Pitch range: {valid.min():.0f} Hz – {valid.max():.0f} Hz")
        print(f"  Median pitch: {np.median(valid):.0f} Hz ({librosa.hz_to_note(np.median(valid))})")

    print(f"Quantising to {args.scale} scale (root={args.root})...")
    quantised = quantise_to_scale(f0, args.scale, args.root)

    print(f"Synthesising on {args.voice} wave...")
    audio = synthesise(quantised, frame_duration, args.voice)

    # Normalise
    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio / peak * 0.9

    sf.write(str(output_path), audio, SR)
    print(f"Saved: {output_path} ({len(audio) / SR:.1f}s)")

    # Also save the raw pitch data for inspection
    pitch_path = output_path.with_suffix(".pitch.txt")
    with open(pitch_path, "w") as f:
        f.write("frame\tfreq_hz\tquantised_hz\tvoiced\n")
        for i in range(len(f0)):
            raw = f"{f0[i]:.1f}" if not np.isnan(f0[i]) else "NaN"
            q = f"{quantised[i]:.1f}" if not np.isnan(quantised[i]) else "NaN"
            f.write(f"{i}\t{raw}\t{q}\t{voiced[i]}\n")
    print(f"Pitch data: {pitch_path}")


if __name__ == "__main__":
    main()

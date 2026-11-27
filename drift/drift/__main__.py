"""drift CLI — generate chip-tunes from noise via diffusion.

Usage:
    python -m drift generate --chip ay --bars 8 --steps 50
    python -m drift generate --from-noise road.wav --steps 50
    python -m drift generate --from-noise road.wav --extract-melody --voice triangle
    python -m drift generate --chip sid --bars 16 --output my_samples/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

from drift.dataset import CHIP_TYPES, HOP_LENGTH, N_FFT, N_MELS, SR
from drift.vocoder import save_audio, spectrogram_to_audio

DEFAULT_CHECKPOINT = "_data/checkpoints_m4_conditional/epoch_0010.pt"
DEFAULT_BPM = 120


def bars_to_duration(bars: int, bpm: int = DEFAULT_BPM) -> int:
    """Convert bars (4/4 time) to seconds, rounded to nearest supported duration."""
    seconds = bars * 4 * 60 / bpm
    # Snap to 4 or 8 — these are the durations our checkpoints support
    if seconds <= 6:
        return 4
    return 8


def cmd_generate(args: argparse.Namespace) -> None:
    # Lazy imports — keep CLI startup fast
    from drift.sampler import generate_and_crop
    from drift.scheduler import DDIMScheduler, DDPMScheduler
    from drift.train import get_device, target_width_for_duration
    from drift.unet import UNet

    device = get_device() if args.device == "auto" else torch.device(args.device)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.seed is not None:
        torch.manual_seed(args.seed)

    # Load checkpoint
    ckpt_path = Path(args.checkpoint)
    if not ckpt_path.exists():
        print(f"Checkpoint not found: {ckpt_path}")
        print("Run 'bash scripts/setup.sh' to download data and train, or provide a checkpoint path.")
        sys.exit(1)

    ckpt = torch.load(str(ckpt_path), map_location=device, weights_only=False)
    config = ckpt.get("config", {})

    base_ch = config.get("base_ch", 32)
    num_classes = config.get("num_classes", 0)
    attn_str = config.get("attn_levels", "")
    attn_levels = {int(x.strip()) for x in attn_str.split(",") if x.strip()} if attn_str else set()

    model = UNet(base_ch=base_ch, attn_levels=attn_levels, num_classes=num_classes).to(device)

    if "ema_state" in ckpt and ckpt["ema_state"]:
        model.load_state_dict(ckpt["ema_state"], strict=False)
    else:
        model.load_state_dict(ckpt["model_state"])
    model.eval()

    # Duration handling
    duration = config.get("duration", 4)
    if args.bars:
        requested = bars_to_duration(args.bars)
        if requested != duration:
            print(f"Note: --bars {args.bars} maps to {requested}s, checkpoint trained on {duration}s. Using {duration}s.")
    tw = target_width_for_duration(duration)
    original_width = -(-duration * SR // HOP_LENGTH)

    # Scheduler
    if args.sampler == "ddim":
        scheduler = DDIMScheduler(num_inference_steps=args.steps, eta=args.eta).to(device)
    else:
        scheduler = DDPMScheduler(num_steps=1000).to(device)

    # Starting noise
    import librosa
    import numpy as np
    import torch.nn.functional as F

    start_noise = None
    noise_label = "gaussian"

    if args.from_noise:
        noise_path = Path(args.from_noise)
        if not noise_path.exists():
            print(f"Noise file not found: {noise_path}")
            sys.exit(1)
        noise_label = noise_path.stem
        duration_s = tw * HOP_LENGTH / SR
        y, _ = librosa.load(str(noise_path), sr=SR, mono=True, duration=duration_s)
        S = librosa.feature.melspectrogram(y=y, sr=SR, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS)
        S_db = librosa.power_to_db(S, ref=np.max)
        S_norm = 2.0 * (S_db - args.global_min) / (args.global_max - args.global_min) - 1.0
        tensor = torch.FloatTensor(S_norm).unsqueeze(0).unsqueeze(0)
        if tensor.shape[-1] < tw:
            tensor = F.pad(tensor, (0, tw - tensor.shape[-1]))
        else:
            tensor = tensor[:, :, :, :tw]
        start_noise = tensor.repeat(args.n, 1, 1, 1)

    # Class conditioning
    class_label = None
    if args.chip:
        if num_classes == 0:
            print("Warning: checkpoint is unconditional, --chip ignored.")
        else:
            chip_idx = CHIP_TYPES.index(args.chip)
            class_label = torch.full((args.n,), chip_idx, dtype=torch.long)

    # Generate
    info_parts = [f"n={args.n}", f"source={noise_label}", f"strength={args.strength}"]
    if args.chip:
        info_parts.append(f"chip={args.chip}")
    info_parts.append(f"duration={duration}s")
    print(f"Generating: {', '.join(info_parts)}")

    specs = generate_and_crop(
        model, scheduler, args.n, device,
        original_width=original_width,
        start_noise=start_noise, strength=args.strength,
        class_label=class_label, guidance_scale=args.guidance_scale,
    )

    # Save
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for i in range(args.n):
        spec = specs[i]
        wav_path = out_dir / f"sample_{i:03d}.wav"
        img_path = out_dir / f"sample_{i:03d}.png"

        audio = spectrogram_to_audio(spec, args.global_min, args.global_max)
        save_audio(audio, wav_path)

        fig, ax = plt.subplots(1, 1, figsize=(8, 4))
        ax.imshow(spec.squeeze().cpu().numpy(), aspect="auto", origin="lower", cmap="magma")
        ax.set_xlabel("Time frames")
        ax.set_ylabel("Mel bins")
        ax.set_title(f"{noise_label} → sample_{i:03d}")
        fig.tight_layout()
        fig.savefig(str(img_path), dpi=150)
        plt.close(fig)

        print(f"  {wav_path.name} ({len(audio) / SR:.1f}s)  +  {img_path.name}")

        # Melody extraction
        if args.extract_melody:
            melody_path = out_dir / f"sample_{i:03d}_melody.wav"
            _extract_melody(wav_path, melody_path, args.voice, args.scale, args.smoothing)
            print(f"  {melody_path.name} (melody: {args.voice}, {args.scale}, smoothing={args.smoothing})")

    print(f"\nDone. {args.n} samples → {out_dir}/")


def _extract_melody(
    wav_path: Path, output_path: Path, voice: str, scale: str, smoothing: int,
) -> None:
    """Inline melody extraction — same algorithm as scripts/extract_melody.py."""
    import librosa
    import numpy as np
    import soundfile as sf

    SCALES = {
        "pentatonic": [261.63, 293.66, 329.63, 392.00, 440.00],
        "minor_pentatonic": [261.63, 311.13, 349.23, 392.00, 466.16],
        "major": [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88],
    }

    y, sr = librosa.load(str(wav_path), sr=SR, mono=True)
    S = librosa.feature.melspectrogram(y=y, sr=SR, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS)
    S_db = librosa.power_to_db(S, ref=np.max)
    mel_freqs = librosa.mel_frequencies(n_mels=N_MELS, fmin=0, fmax=SR / 2)

    lo = np.searchsorted(mel_freqs, 130)
    hi = np.searchsorted(mel_freqs, 2100)
    S_band = S_db[lo:hi, :]
    mel_band = mel_freqs[lo:hi]

    base = SCALES.get(scale, SCALES["pentatonic"])
    scale_notes = sorted(set(
        f * (2 ** o) for f in base for o in [-2, -1, 0, 1, 2]
        if 130 <= f * (2 ** o) <= 2100
    ))

    frame_dur = HOP_LENGTH / SR
    n_frames = S_band.shape[1]
    threshold = S_band.max() - 20
    min_frames = max(1, int(0.4 / frame_dur))  # 400ms legato

    # Raw notes
    raw_notes = []
    for i in range(n_frames):
        frame = S_band[:, i]
        if frame.max() < threshold:
            raw_notes.append(None)
            continue
        top_k = 3
        indices = np.argsort(frame)[-top_k:]
        weights = np.power(10, (frame[indices] - frame[indices].max()) / 10)
        avg_freq = np.average(mel_band[indices], weights=weights)
        raw_notes.append(min(scale_notes, key=lambda s: abs(np.log2(avg_freq / s))))

    # Median filter
    filtered = list(raw_notes)
    for i in range(smoothing, len(filtered) - smoothing):
        window = [n for n in raw_notes[i - smoothing:i + smoothing + 1] if n is not None]
        if window:
            filtered[i] = min(scale_notes, key=lambda s: sum(abs(np.log2(w / s)) for w in window))

    # Min duration
    final: list[float | None] = []
    i = 0
    while i < len(filtered):
        if filtered[i] is None:
            final.append(None)
            i += 1
            continue
        note = filtered[i]
        run = 1
        while i + run < len(filtered) and filtered[i + run] == note:
            run += 1
        extend = max(run, min_frames)
        extend = min(extend, len(filtered) - i)
        for _ in range(extend):
            final.append(note)
        i += max(run, extend)

    # Synthesise
    audio = np.zeros(0, dtype=np.float32)
    i = 0
    while i < len(final):
        if final[i] is None:
            audio = np.concatenate([audio, np.zeros(int(SR * frame_dur), dtype=np.float32)])
            i += 1
            continue
        freq = final[i]
        run = 1
        while i + run < len(final) and final[i + run] == freq:
            run += 1
        duration = run * frame_dur
        n_samp = int(SR * duration)
        t = np.arange(n_samp) / SR
        if voice == "triangle":
            phase = (t * freq) % 1.0
            samples = (2.0 * np.abs(2.0 * phase - 1.0) - 1.0).astype(np.float32) * 0.7
        elif voice == "pulse":
            samples = np.where((t * freq) % 1.0 < 0.25, 0.7, -0.7).astype(np.float32)
        else:
            samples = np.where((t * freq) % 1.0 < 0.5, 0.7, -0.7).astype(np.float32)
        att = min(200, n_samp // 3)
        rel = min(300, n_samp // 3)
        env = np.ones(n_samp, dtype=np.float32)
        env[:att] = np.linspace(0, 1, att)
        env[-rel:] = np.linspace(1, 0, rel)
        audio = np.concatenate([audio, samples * env])
        i += run

    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio / peak * 0.85
    sf.write(str(output_path), audio, SR)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="drift", description="Chip-tune generation via diffusion")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate chip-tune samples")
    gen.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT, help="Path to .pt checkpoint")
    gen.add_argument("--n", type=int, default=5, help="Number of samples")
    gen.add_argument("--output", default="_data/generated", help="Output directory")
    gen.add_argument("--device", default="auto")
    gen.add_argument("--seed", type=int, default=None, help="Random seed")
    gen.add_argument("--chip", default="", choices=[""] + CHIP_TYPES, help="Chip type conditioning")
    gen.add_argument("--guidance-scale", type=float, default=3.0, dest="guidance_scale")
    gen.add_argument("--bars", type=int, default=None, help="Duration in bars (4/4 at 120 BPM). Maps to 4s or 8s.")
    gen.add_argument("--from-noise", default="", dest="from_noise", help="WAV file to use as starting noise")
    gen.add_argument("--strength", type=float, default=1.0, help="Denoising strength (0.0–1.0)")
    gen.add_argument("--sampler", choices=["ddpm", "ddim"], default="ddim")
    gen.add_argument("--steps", type=int, default=50, help="DDIM inference steps")
    gen.add_argument("--eta", type=float, default=1.0, help="DDIM stochasticity")
    gen.add_argument("--global-min", type=float, default=-80.0, dest="global_min")
    gen.add_argument("--global-max", type=float, default=0.0, dest="global_max")

    # Melody extraction
    gen.add_argument("--extract-melody", action="store_true", dest="extract_melody",
                     help="Extract melody from output and render on a chip voice")
    gen.add_argument("--voice", default="triangle", choices=["square", "triangle", "pulse"],
                     help="Chip voice for melody extraction")
    gen.add_argument("--scale", default="pentatonic", choices=["pentatonic", "minor_pentatonic", "major"],
                     help="Scale for melody quantisation")
    gen.add_argument("--smoothing", type=int, default=12, help="Median filter window for melody smoothing")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

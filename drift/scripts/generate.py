"""Generate chip-tune audio from a trained DDPM checkpoint.

Usage:
    python scripts/generate.py --checkpoint _data/checkpoints/epoch_0050.pt --n 5
    python scripts/generate.py --checkpoint _data/checkpoints/epoch_0050.pt --from-noise _data/noise/road.wav
    python scripts/generate.py --checkpoint _data/checkpoints/epoch_0050.pt --from-image art-natural-noise/code/img1.png --strength 0.5
"""

from __future__ import annotations

import argparse
from pathlib import Path

import librosa
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

from drift.dataset import CHIP_TYPES, HOP_LENGTH, N_FFT, N_MELS, SR
from drift.sampler import generate_and_crop
from drift.scheduler import DDIMScheduler, DDPMScheduler
from drift.train import TARGET_WIDTH, get_device, target_width_for_duration
from drift.unet import UNet
from drift.vocoder import save_audio, spectrogram_to_audio


def load_checkpoint(
    path: str | Path, device: torch.device
) -> tuple[UNet, DDPMScheduler, dict, int]:
    ckpt = torch.load(path, map_location=device, weights_only=False)
    config = ckpt.get("config", {})

    attn_levels: set[int] = set()
    attn_str = config.get("attn_levels", "")
    if attn_str:
        attn_levels = {int(x.strip()) for x in attn_str.split(",")}

    base_ch = config.get("base_ch", 32)
    num_classes = config.get("num_classes", 0)
    model = UNet(base_ch=base_ch, attn_levels=attn_levels, num_classes=num_classes).to(device)
    scheduler = DDPMScheduler(num_steps=1000).to(device)

    if "ema_state" in ckpt and ckpt["ema_state"]:
        model.load_state_dict(ckpt["ema_state"], strict=False)
        print("Loaded EMA weights")
    else:
        model.load_state_dict(ckpt["model_state"])
        print("Loaded model weights")

    duration = config.get("duration", 4)
    tw = target_width_for_duration(duration)

    model.eval()
    return model, scheduler, config, tw


def save_spectrogram_image(spec: torch.Tensor, path: Path, title: str | None = None) -> None:
    fig, ax = plt.subplots(1, 1, figsize=(8, 4))
    ax.imshow(
        spec.squeeze().cpu().numpy(),
        aspect="auto",
        origin="lower",
        cmap="magma",
    )
    ax.set_xlabel("Time frames")
    ax.set_ylabel("Mel bins")
    ax.set_title(title or path.stem)
    fig.tight_layout()
    fig.savefig(str(path), dpi=150)
    plt.close(fig)


def load_noise_as_spectrogram(
    wav_path: Path, global_min: float, global_max: float, tw: int = TARGET_WIDTH,
) -> torch.Tensor:
    """Load a wav file, convert to normalised Mel-spectrogram, pad to model width.

    Returns tensor of shape (1, 1, 128, tw).
    """
    duration_s = tw * HOP_LENGTH / SR
    y, _ = librosa.load(str(wav_path), sr=SR, mono=True, duration=duration_s)
    S = librosa.feature.melspectrogram(
        y=y, sr=SR, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
    )
    S_db = librosa.power_to_db(S, ref=np.max)
    S_norm = 2.0 * (S_db - global_min) / (global_max - global_min) - 1.0
    tensor = torch.FloatTensor(S_norm).unsqueeze(0).unsqueeze(0)
    current_w = tensor.shape[-1]
    if current_w < tw:
        tensor = F.pad(tensor, (0, tw - current_w))
    else:
        tensor = tensor[:, :, :, :tw]
    return tensor


def load_image_as_spectrogram(img_path: Path, tw: int = TARGET_WIDTH) -> torch.Tensor:
    """Load an image, convert to greyscale, resize to spectrogram dimensions, normalise to [-1,1].

    Dark areas → low values (silence/bass), bright areas → high values (treble/energy).

    Returns tensor of shape (1, 1, 128, tw).
    """
    img = Image.open(img_path).convert("L")  # greyscale
    img = img.resize((tw, 128), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32)
    # Flip vertically so bottom of image = low frequency (matches spectrogram convention)
    arr = arr[::-1].copy()
    # Normalise 0–255 → [-1, 1]
    arr = arr / 127.5 - 1.0
    return torch.FloatTensor(arr).unsqueeze(0).unsqueeze(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate chip-tunes from trained DDPM")
    parser.add_argument("--checkpoint", required=True, help="Path to .pt checkpoint")
    parser.add_argument("--n", type=int, default=5, help="Number of samples")
    parser.add_argument("--output", default="_data/generated", help="Output directory")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--global-min", type=float, default=-80.0, dest="global_min")
    parser.add_argument("--global-max", type=float, default=0.0, dest="global_max")
    parser.add_argument(
        "--from-noise", default="", dest="from_noise",
        help="Path to a wav file to use as starting noise instead of Gaussian"
    )
    parser.add_argument(
        "--strength", type=float, default=1.0,
        help="Denoising strength 0.0–1.0. 1.0=full denoise, 0.5=half input/half generated. Requires --from-noise or --from-image when < 1.0"
    )
    parser.add_argument(
        "--from-image", default="", dest="from_image",
        help="Path to an image file to use as starting spectrogram (greyscale, resized to 128×176)"
    )
    parser.add_argument(
        "--sampler", choices=["ddpm", "ddim"], default="ddpm",
        help="Sampling method: ddpm (1000 steps) or ddim (fewer steps)"
    )
    parser.add_argument(
        "--steps", type=int, default=50,
        help="Number of DDIM inference steps (ignored for DDPM)"
    )
    parser.add_argument(
        "--eta", type=float, default=1.0,
        help="DDIM stochasticity (0.0=deterministic, 1.0=full noise). Default 1.0"
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument(
        "--chip", default="", choices=[""] + CHIP_TYPES,
        help=f"Chip type for conditional generation: {CHIP_TYPES}. Requires a conditionally-trained checkpoint."
    )
    parser.add_argument(
        "--guidance-scale", type=float, default=3.0, dest="guidance_scale",
        help="Classifier-free guidance scale (default 3.0). Higher = more chip-type-specific."
    )
    args = parser.parse_args()

    if args.strength < 1.0 and not args.from_noise and not args.from_image:
        parser.error("--strength < 1.0 requires --from-noise or --from-image")

    device = get_device() if args.device == "auto" else torch.device(args.device)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.seed is not None:
        torch.manual_seed(args.seed)

    model, _, config, tw = load_checkpoint(args.checkpoint, device)

    if args.sampler == "ddim":
        scheduler = DDIMScheduler(
            num_inference_steps=args.steps, eta=args.eta
        ).to(device)
        print(f"Sampler: DDIM ({args.steps} steps, eta={args.eta})")
    else:
        scheduler = DDPMScheduler(num_steps=1000).to(device)
        print("Sampler: DDPM (1000 steps)")
    duration = config.get("duration", 4)
    original_width = -(-duration * SR // HOP_LENGTH)  # ceil division

    start_noise = None
    noise_label = "gaussian"
    if args.from_image:
        img_path = Path(args.from_image)
        noise_label = img_path.stem
        print(f"Loading image as spectrogram seed: {img_path}")
        single = load_image_as_spectrogram(img_path, tw=tw)

        save_spectrogram_image(
            single.squeeze(0), out_dir / f"input_{noise_label}.png",
            title=f"Input image: {noise_label}"
        )

        start_noise = single.repeat(args.n, 1, 1, 1)
        print(f"Start noise shape: {start_noise.shape}")
    elif args.from_noise:
        noise_path = Path(args.from_noise)
        noise_label = noise_path.stem
        print(f"Loading noise source: {noise_path}")
        single = load_noise_as_spectrogram(noise_path, args.global_min, args.global_max, tw=tw)

        # Save the input noise spectrogram for comparison.
        save_spectrogram_image(
            single.squeeze(0), out_dir / f"input_{noise_label}.png",
            title=f"Input noise: {noise_label}"
        )

        start_noise = single.repeat(args.n, 1, 1, 1)
        print(f"Start noise shape: {start_noise.shape}")

    print(f"Generating {args.n} samples (noise source: {noise_label}, strength: {args.strength}, duration: {duration}s)...")
    class_label = None
    if args.chip:
        chip_idx = CHIP_TYPES.index(args.chip)
        class_label = torch.full((args.n,), chip_idx, dtype=torch.long)
        print(f"Chip type: {args.chip} (index {chip_idx}), guidance scale: {args.guidance_scale}")
    specs = generate_and_crop(
        model, scheduler, args.n, device,
        original_width=original_width,
        start_noise=start_noise, strength=args.strength,
        class_label=class_label, guidance_scale=args.guidance_scale,
    )

    for i in range(args.n):
        spec = specs[i]

        wav_path = out_dir / f"sample_{i:03d}.wav"
        img_path = out_dir / f"sample_{i:03d}.png"

        audio = spectrogram_to_audio(spec, args.global_min, args.global_max)
        save_audio(audio, wav_path)
        save_spectrogram_image(spec, img_path, title=f"{noise_label} → sample_{i:03d}")

        print(f"  {wav_path.name} ({len(audio) / 22050:.1f}s)  +  {img_path.name}")

    print(f"\nDone. {args.n} samples saved to {out_dir}/")


if __name__ == "__main__":
    main()

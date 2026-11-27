"""DDPM training loop for chip-tune Mel-spectrogram diffusion.

Run as:
    python -m drift.train --data _data/segments --epochs 50 --batch-size 16
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from tqdm import tqdm

from drift.dataset import get_dataloader
from drift.scheduler import DDPMScheduler
from drift.unet import UNet

TARGET_WIDTH = 176


def target_width_for_duration(duration_s: int, sr: int = 22050, hop: int = 512) -> int:
    """Compute the padded target width for a given segment duration.

    Frames = ceil(samples / hop_length). Pad up to the next multiple of 8
    (3 U-Net downsampling stages → divide by 2^3 = 8).
    """
    n_samples = duration_s * sr
    n_frames = -(-n_samples // hop)  # ceil division
    return ((n_frames + 7) // 8) * 8


# ---------------------------------------------------------------------------
# Padding
# ---------------------------------------------------------------------------


def pad_to_target(x: torch.Tensor, target_width: int = TARGET_WIDTH) -> torch.Tensor:
    """Right-pad the time (last) dimension of x to target_width with zeros.

    Args:
        x: Tensor of shape (..., T).
        target_width: Desired width along the last dimension.

    Returns:
        Tensor of shape (..., target_width).  If T >= target_width, x is
        returned unchanged (no truncation).
    """
    current = x.shape[-1]
    if current >= target_width:
        return x
    pad_amount = target_width - current
    # F.pad pads from last dim backwards: (left, right) for last dim
    return F.pad(x, (0, pad_amount))


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------


class EMA:
    """Exponential moving average of a model's parameters.

    Usage::

        ema = EMA(model)
        # after each optimiser step:
        ema.update(model)
        # to save:
        torch.save(ema.state_dict(), path)
    """

    def __init__(self, model: torch.nn.Module, decay: float = 0.9999) -> None:
        self.decay = decay
        # Deep-copy initial parameters into a separate dict.
        self.shadow: dict[str, torch.Tensor] = {
            name: param.data.clone()
            for name, param in model.named_parameters()
        }

    @torch.no_grad()
    def update(self, model: torch.nn.Module) -> None:
        """Blend current model parameters into the shadow copy."""
        for name, param in model.named_parameters():
            self.shadow[name].mul_(self.decay).add_(
                param.data, alpha=1.0 - self.decay
            )

    def state_dict(self) -> dict[str, torch.Tensor]:
        return {k: v.clone() for k, v in self.shadow.items()}


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------


def get_device() -> torch.device:
    """Return the best available device: MPS > CUDA > CPU."""
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    print(f"Device: {device}")
    return device


# ---------------------------------------------------------------------------
# Training step
# ---------------------------------------------------------------------------


def train_step(
    model: torch.nn.Module,
    scheduler: DDPMScheduler,
    batch: tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    target_width: int = TARGET_WIDTH,
    num_classes: int = 0,
    cfg_dropout: float = 0.1,
) -> torch.Tensor:
    """One forward pass + loss computation (no backward, no optimiser step).

    Args:
        model: U-Net noise predictor.
        scheduler: DDPM noise scheduler.
        batch: (specs, labels).
        device: Target device.
        target_width: Pad spectrograms to this width for U-Net divisibility.
        num_classes: Number of chip-type classes (0 = unconditional).
        cfg_dropout: Probability of replacing a label with the unconditional token.

    Returns:
        Scalar MSE loss tensor.
    """
    specs, labels = batch
    specs = specs.to(device)
    specs = pad_to_target(specs, target_width)

    batch_size = specs.shape[0]
    t = scheduler.sample_timesteps(batch_size).to(device)
    noise = torch.randn_like(specs)
    noisy = scheduler.add_noise(specs, t, noise)

    if num_classes > 0:
        labels = labels.to(device)
        # CFG dropout: replace each label with unconditional token with prob cfg_dropout
        drop_mask = torch.rand(batch_size, device=device) < cfg_dropout
        labels = torch.where(drop_mask, torch.full_like(labels, num_classes), labels)
        noise_pred = model(noisy, t, class_label=labels)
    else:
        noise_pred = model(noisy, t)

    return F.mse_loss(noise_pred, noise)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class TrainConfig:
    data_dir: str = "_data/segments"
    epochs: int = 50
    batch_size: int = 16
    lr: float = 2e-4
    duration: int = 4
    base_ch: int = 32
    checkpoint_dir: str = "_data/checkpoints"
    save_every: int = 10
    device: str = "auto"
    resume: str = ""
    attn_levels: str = ""
    num_classes: int = 0
    cfg_dropout: float = 0.1


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------


def train(config: TrainConfig | dict[str, Any]) -> None:
    """Full training loop.

    Args:
        config: TrainConfig dataclass or equivalent dict.
    """
    if isinstance(config, dict):
        config = TrainConfig(**config)

    print("Training config:")
    for key, val in vars(config).items():
        print(f"  {key}: {val}")
    print()

    device = (
        get_device() if config.device == "auto" else torch.device(config.device)
    )

    # Dataset + dataloader.
    loader = get_dataloader(
        Path(config.data_dir),
        duration=config.duration,
        split="train",
        batch_size=config.batch_size,
        num_workers=4,
        shuffle=True,
    )

    # Model + scheduler.
    attn_levels: set[int] = set()
    if config.attn_levels:
        attn_levels = {int(x.strip()) for x in config.attn_levels.split(",")}
    model = UNet(base_ch=config.base_ch, attn_levels=attn_levels, num_classes=config.num_classes).to(device)
    scheduler = DDPMScheduler(num_steps=1000).to(device)
    tw = target_width_for_duration(config.duration)

    optimiser = torch.optim.Adam(model.parameters(), lr=config.lr)
    ema = EMA(model)

    start_epoch = 1

    # Resume from checkpoint if provided.
    if config.resume:
        ckpt = torch.load(config.resume, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state"])
        optimiser.load_state_dict(ckpt["optimiser_state"])
        if "ema_state" in ckpt:
            ema.shadow = {k: v.to(device) for k, v in ckpt["ema_state"].items()}
        start_epoch = ckpt["epoch"] + 1
        print(f"Resumed from {config.resume} (epoch {ckpt['epoch']})")

    ckpt_dir = Path(config.checkpoint_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(start_epoch, config.epochs + 1):
        model.train()
        epoch_loss = 0.0

        batch_bar = tqdm(loader, desc=f"Epoch {epoch}/{config.epochs}", leave=False)
        for batch in batch_bar:
            loss = train_step(model, scheduler, batch, device, target_width=tw,
                              num_classes=config.num_classes, cfg_dropout=config.cfg_dropout)

            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            ema.update(model)

            epoch_loss += loss.item()
            batch_bar.set_postfix(loss=f"{loss.item():.4f}")

        avg_loss = epoch_loss / max(len(loader), 1)
        print(f"Epoch {epoch:>4}/{config.epochs}  loss={avg_loss:.4f}")

        if epoch % config.save_every == 0 or epoch == config.epochs:
            ckpt_path = ckpt_dir / f"epoch_{epoch:04d}.pt"
            torch.save(
                {
                    "epoch": epoch,
                    "model_state": model.state_dict(),
                    "ema_state": ema.state_dict(),
                    "optimiser_state": optimiser.state_dict(),
                    "config": vars(config),
                },
                ckpt_path,
            )
            print(f"  Saved checkpoint: {ckpt_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train DDPM on chip-tune spectrograms")
    parser.add_argument("--data", default="_data/segments", help="Path to segments dir")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=16, dest="batch_size")
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--duration", type=int, default=4, help="Segment duration (s)")
    parser.add_argument("--base-ch", type=int, default=32, dest="base_ch",
                        help="U-Net base channel count (32=3M params, 64=12M params)")
    parser.add_argument("--checkpoint-dir", default="_data/checkpoints", dest="checkpoint_dir")
    parser.add_argument("--save-every", type=int, default=10, dest="save_every")
    parser.add_argument("--device", default="auto", help="auto | cpu | cuda | mps")
    parser.add_argument("--resume", default="", help="Path to checkpoint to resume from")
    parser.add_argument("--attn-levels", default="", dest="attn_levels",
                        help="Comma-separated U-Net levels for self-attention (e.g. '2' or '1,2')")
    parser.add_argument("--num-classes", type=int, default=0, dest="num_classes",
                        help="Number of chip-type classes for CFG (0=unconditional, 4=conditional)")
    parser.add_argument("--cfg-dropout", type=float, default=0.1, dest="cfg_dropout",
                        help="Probability of replacing class label with unconditional token during training")
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    cfg = TrainConfig(
        data_dir=args.data,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        duration=args.duration,
        base_ch=args.base_ch,
        checkpoint_dir=args.checkpoint_dir,
        save_every=args.save_every,
        device=args.device,
        resume=args.resume,
        attn_levels=args.attn_levels,
        num_classes=args.num_classes,
        cfg_dropout=args.cfg_dropout,
    )
    train(cfg)

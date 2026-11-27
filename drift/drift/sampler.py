"""Reverse-process sampler for chip-tune Mel-spectrogram generation.

Supports both DDPMScheduler (full 1000-step reverse process) and
DDIMScheduler (deterministic subsequence — typically 50 steps).
"""

from __future__ import annotations

import torch
import torch.nn as nn
from tqdm import tqdm

from drift.scheduler import DDIMScheduler, DDPMScheduler
from drift.unet import UNet


@torch.no_grad()
def generate(
    model: UNet,
    scheduler: nn.Module,
    n_samples: int,
    device: torch.device | str,
    shape: tuple[int, int, int] = (1, 128, 176),
    start_noise: torch.Tensor | None = None,
    strength: float = 1.0,
    class_label: torch.Tensor | None = None,
    guidance_scale: float = 1.0,
) -> torch.Tensor:
    """Run the reverse diffusion process, optionally starting partway through.

    Works with both DDPMScheduler and DDIMScheduler. DDIM uses the
    precomputed timestep subsequence stored in ``scheduler.timesteps``; DDPM
    iterates through every step in descending order.

    Args:
        model: Trained U-Net noise predictor.
        scheduler: DDPMScheduler or DDIMScheduler instance.
        n_samples: Number of samples to generate.
        device: Target device for tensors.
        shape: Per-sample shape (C, H, W). Defaults to (1, 128, 176).
        start_noise: Optional starting tensor instead of Gaussian noise.
                     Must be shape (n_samples, *shape) or broadcastable.
        strength: Controls how many denoising steps to run (0.0–1.0).
                  1.0 = full denoise from pure noise (default).
                  < 1.0 = add noise to an intermediate step, denoise from there.
                  Requires start_noise when < 1.0.
        class_label: Optional LongTensor of shape (n_samples,) with chip-type indices.
        guidance_scale: CFG scale. Values > 1.0 require class_label and perform
                        a dual forward pass. 1.0 = no guidance (single pass).

    Returns:
        Tensor of shape (n_samples, *shape) — padded spectrograms.
    """
    model.eval()

    start_step = int(strength * scheduler.num_steps)
    start_step = max(1, min(start_step, scheduler.num_steps))

    if strength >= 1.0:
        if start_noise is not None:
            x = start_noise.to(device)
        else:
            x = torch.randn(n_samples, *shape, device=device)
    else:
        if start_noise is None:
            raise ValueError("start_noise is required when strength < 1.0")
        x_0 = start_noise.to(device)
        t = torch.full((n_samples,), start_step - 1, device=device, dtype=torch.long)
        noise = torch.randn_like(x_0)
        x = scheduler.add_noise(x_0, t, noise)

    if class_label is not None:
        class_label = class_label.to(device)

    # Build the timestep sequence for the loop.
    is_ddim = hasattr(scheduler, "timesteps")
    if is_ddim:
        timesteps = scheduler.timesteps.tolist()
        if strength < 1.0:
            timesteps = [t for t in timesteps if t < start_step]
    else:
        timesteps = list(range(start_step - 1, -1, -1))

    use_cfg = class_label is not None and guidance_scale > 1.0

    for i, t in enumerate(tqdm(timesteps, desc="Sampling")):
        t_batch = torch.full((n_samples,), t, device=device, dtype=torch.long)

        if use_cfg:
            noise_pred_cond = model(x, t_batch, class_label=class_label)
            uncond_label = torch.full_like(class_label, model.num_classes)
            noise_pred_uncond = model(x, t_batch, class_label=uncond_label)
            noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_cond - noise_pred_uncond)
        else:
            noise_pred = model(x, t_batch, class_label=class_label)

        if is_ddim:
            t_prev = timesteps[i + 1] if i + 1 < len(timesteps) else -1
            if t_prev < 0:
                x = scheduler.step(x, t_batch, noise_pred, t_prev=-1)
            else:
                t_prev_batch = torch.full((n_samples,), t_prev, device=device, dtype=torch.long)
                x = scheduler.step(x, t_batch, noise_pred, t_prev=t_prev_batch)
        else:
            x = scheduler.step(x, t_batch, noise_pred)

    return x


def generate_and_crop(
    model: UNet,
    scheduler: nn.Module,
    n_samples: int,
    device: torch.device | str,
    original_width: int = 173,
    start_noise: torch.Tensor | None = None,
    strength: float = 1.0,
    class_label: torch.Tensor | None = None,
    guidance_scale: float = 1.0,
) -> torch.Tensor:
    """Generate spectrograms and crop padding back to original time dimension.

    Args:
        model: Trained U-Net noise predictor.
        scheduler: DDPMScheduler or DDIMScheduler instance.
        n_samples: Number of samples to generate.
        device: Target device for tensors.
        original_width: Time frames before padding (crop target). Default 173.
        start_noise: Optional starting tensor instead of Gaussian noise.
        strength: Denoising strength (0.0–1.0). See generate() docs.
        class_label: Optional LongTensor of shape (n_samples,) with chip-type indices.
        guidance_scale: CFG scale. Values > 1.0 perform dual forward pass.

    Returns:
        Tensor of shape (n_samples, 1, 128, original_width).
    """
    padded_width = ((original_width + 7) // 8) * 8
    x = generate(
        model, scheduler, n_samples, device,
        shape=(1, 128, padded_width),
        start_noise=start_noise, strength=strength,
        class_label=class_label, guidance_scale=guidance_scale,
    )
    return x[:, :, :, :original_width]

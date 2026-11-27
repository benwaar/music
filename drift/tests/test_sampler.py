"""Tests for the reverse-process sampler (DDPM and DDIM)."""

from __future__ import annotations

import pytest
import torch

from drift.sampler import generate, generate_and_crop
from drift.scheduler import DDIMScheduler, DDPMScheduler
from drift.unet import UNet

# Use tiny params so tests finish in under a second on CPU.
_N_STEPS = 5
_BASE_CH = 8
_DEVICE = "cpu"


@pytest.fixture
def tiny_scheduler() -> DDPMScheduler:
    return DDPMScheduler(num_steps=_N_STEPS)


@pytest.fixture
def tiny_model() -> UNet:
    model = UNet(base_ch=_BASE_CH)
    model.eval()
    return model


def test_generate_output_shape(tiny_model: UNet, tiny_scheduler: DDPMScheduler) -> None:
    n_samples = 2
    out = generate(tiny_model, tiny_scheduler, n_samples, _DEVICE)
    assert out.shape == (n_samples, 1, 128, 176)


def test_generate_and_crop_shape(tiny_model: UNet, tiny_scheduler: DDPMScheduler) -> None:
    n_samples = 2
    out = generate_and_crop(tiny_model, tiny_scheduler, n_samples, _DEVICE)
    assert out.shape == (n_samples, 1, 128, 173)


def test_no_nan(tiny_model: UNet, tiny_scheduler: DDPMScheduler) -> None:
    out = generate(tiny_model, tiny_scheduler, 1, _DEVICE)
    assert not torch.isnan(out).any(), "Output contains NaN values"


def test_deterministic_with_seed(tiny_model: UNet, tiny_scheduler: DDPMScheduler) -> None:
    torch.manual_seed(42)
    out_a = generate(tiny_model, tiny_scheduler, 1, _DEVICE)

    torch.manual_seed(42)
    out_b = generate(tiny_model, tiny_scheduler, 1, _DEVICE)

    assert torch.allclose(out_a, out_b), "Same seed should produce identical outputs"


def test_strength_partial_denoise(tiny_model: UNet, tiny_scheduler: DDPMScheduler) -> None:
    start = torch.randn(1, 1, 128, 176)
    out = generate(tiny_model, tiny_scheduler, 1, _DEVICE, start_noise=start, strength=0.5)
    assert out.shape == (1, 1, 128, 176)
    assert not torch.isnan(out).any()


def test_strength_requires_start_noise(tiny_model: UNet, tiny_scheduler: DDPMScheduler) -> None:
    with pytest.raises(ValueError, match="start_noise is required"):
        generate(tiny_model, tiny_scheduler, 1, _DEVICE, strength=0.5)


def test_strength_1_matches_full_denoise(tiny_model: UNet, tiny_scheduler: DDPMScheduler) -> None:
    start = torch.randn(1, 1, 128, 176)
    torch.manual_seed(99)
    out_full = generate(tiny_model, tiny_scheduler, 1, _DEVICE, start_noise=start, strength=1.0)
    torch.manual_seed(99)
    out_default = generate(tiny_model, tiny_scheduler, 1, _DEVICE, start_noise=start)
    assert torch.allclose(out_full, out_default)


def test_strength_fewer_steps(tiny_model: UNet, tiny_scheduler: DDPMScheduler) -> None:
    """Lower strength should run fewer denoising steps."""
    start = torch.randn(1, 1, 128, 176)
    out_low = generate_and_crop(tiny_model, tiny_scheduler, 1, _DEVICE, start_noise=start, strength=0.2)
    out_high = generate_and_crop(tiny_model, tiny_scheduler, 1, _DEVICE, start_noise=start, strength=0.8)
    # Both should produce valid output
    assert out_low.shape == (1, 1, 128, 173)
    assert out_high.shape == (1, 1, 128, 173)


def test_generate_with_ddim_shape(tiny_model: UNet) -> None:
    """generate() with DDIMScheduler produces the correct output shape."""
    scheduler = DDIMScheduler(num_train_steps=_N_STEPS, num_inference_steps=3)
    n_samples = 2
    out = generate(tiny_model, scheduler, n_samples, _DEVICE)
    assert out.shape == (n_samples, 1, 128, 176), f"Expected (2, 1, 128, 176), got {out.shape}"
    assert not torch.isnan(out).any(), "DDIM output contains NaN values"


def test_generate_with_class_label() -> None:
    model = UNet(base_ch=_BASE_CH, num_classes=4)
    model.eval()
    scheduler = DDPMScheduler(num_steps=_N_STEPS)
    class_label = torch.zeros(2, dtype=torch.long)
    out = generate(model, scheduler, 2, _DEVICE, class_label=class_label)
    assert out.shape == (2, 1, 128, 176)
    assert not torch.isnan(out).any()


def test_cfg_guidance_changes_output() -> None:
    torch.manual_seed(0)
    model = UNet(base_ch=_BASE_CH, num_classes=4)
    model.eval()
    scheduler = DDPMScheduler(num_steps=_N_STEPS)
    noise = torch.randn(1, 1, 128, 176)
    class_label = torch.tensor([1], dtype=torch.long)

    torch.manual_seed(42)
    out_no_cfg = generate(model, scheduler, 1, _DEVICE, start_noise=noise.clone(),
                           class_label=class_label, guidance_scale=1.0)

    torch.manual_seed(42)
    out_cfg = generate(model, scheduler, 1, _DEVICE, start_noise=noise.clone(),
                       class_label=class_label, guidance_scale=5.0)

    assert not torch.allclose(out_no_cfg, out_cfg), "CFG guidance_scale=5.0 should differ from 1.0"


def test_generate_no_label_backward_compat() -> None:
    model = UNet(base_ch=_BASE_CH, num_classes=4)
    model.eval()
    scheduler = DDPMScheduler(num_steps=_N_STEPS)
    out = generate(model, scheduler, 1, _DEVICE)
    assert out.shape == (1, 1, 128, 176)
    assert not torch.isnan(out).any()

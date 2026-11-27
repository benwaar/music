"""Tests for drift.train — training loop components."""

from __future__ import annotations

import torch

from drift.scheduler import DDPMScheduler
from drift.train import EMA, pad_to_target, target_width_for_duration, train_step
from drift.unet import UNet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_batch(batch_size: int = 2) -> tuple[torch.Tensor, torch.Tensor]:
    """Synthetic batch: (B, 1, 128, 173) specs + zero chip labels."""
    specs = torch.randn(batch_size, 1, 128, 173)
    labels = torch.zeros(batch_size, dtype=torch.long)
    return specs, labels


def _make_model_and_scheduler(device: torch.device) -> tuple[UNet, DDPMScheduler]:
    model = UNet(base_ch=32).to(device)
    scheduler = DDPMScheduler(num_steps=1000).to(device)
    return model, scheduler


# ---------------------------------------------------------------------------
# pad_to_target
# ---------------------------------------------------------------------------


def test_pad_to_target_shape() -> None:
    x = torch.randn(1, 1, 128, 173)
    out = pad_to_target(x, target_width=176)
    assert out.shape == (1, 1, 128, 176), f"Expected (1, 1, 128, 176), got {out.shape}"


def test_pad_to_target_values_preserved() -> None:
    x = torch.randn(1, 1, 128, 173)
    out = pad_to_target(x, target_width=176)
    # Original content must be identical.
    assert torch.allclose(out[..., :173], x), "Original values not preserved after padding"
    # Padding region should be zero.
    assert out[..., 173:].eq(0).all(), "Padding region should be zero"


def test_pad_to_target_already_wide() -> None:
    x = torch.randn(1, 1, 128, 176)
    out = pad_to_target(x, target_width=176)
    assert out is x, "Should return x unchanged when already at target width"


# ---------------------------------------------------------------------------
# train_step
# ---------------------------------------------------------------------------


def test_train_step_returns_finite_loss() -> None:
    device = torch.device("cpu")
    model, scheduler = _make_model_and_scheduler(device)
    batch = _make_batch()

    loss = train_step(model, scheduler, batch, device)

    assert loss.ndim == 0, "Loss should be a scalar"
    assert torch.isfinite(loss), f"Loss should be finite, got {loss.item()}"
    assert loss.item() > 0, f"Loss should be positive, got {loss.item()}"


def test_train_step_loss_decreases() -> None:
    """Five gradient steps on the same batch should drive loss down."""
    device = torch.device("cpu")
    model, scheduler = _make_model_and_scheduler(device)
    optimiser = torch.optim.Adam(model.parameters(), lr=1e-3)

    batch = _make_batch()
    losses: list[float] = []

    for _ in range(5):
        loss = train_step(model, scheduler, batch, device)
        optimiser.zero_grad()
        loss.backward()
        optimiser.step()
        losses.append(loss.item())

    # Loss should be lower at the end than at the start.
    assert losses[-1] < losses[0], (
        f"Loss did not decrease: first={losses[0]:.4f}, last={losses[-1]:.4f}"
    )


# ---------------------------------------------------------------------------
# target_width_for_duration
# ---------------------------------------------------------------------------


def test_target_width_4s():
    assert target_width_for_duration(4) == 176  # ceil(88200/512)=173, pad to 176


def test_target_width_8s():
    assert target_width_for_duration(8) == 352  # ceil(176400/512)=345, pad to 352


def test_target_width_divisible_by_8():
    for dur in [2, 4, 6, 8, 10, 16]:
        tw = target_width_for_duration(dur)
        assert tw % 8 == 0, f"duration={dur} → width={tw} not divisible by 8"


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------


def test_ema_update_diverges_from_model() -> None:
    """After one update, EMA shadow params should differ from the (perturbed) model."""
    model = UNet(base_ch=32)
    ema = EMA(model, decay=0.9)

    # Perturb model weights drastically.
    with torch.no_grad():
        for param in model.parameters():
            param.add_(torch.randn_like(param) * 10.0)

    ema.update(model)

    # At least one shadow parameter should differ from the current model param.
    any_different = False
    for name, param in model.named_parameters():
        if not torch.allclose(ema.shadow[name], param.data):
            any_different = True
            break

    assert any_different, "EMA shadow should differ from model after update with decay<1"


def test_ema_state_dict_is_copy() -> None:
    """state_dict() returns a copy — mutating it doesn't affect the shadow."""
    model = UNet(base_ch=32)
    ema = EMA(model, decay=0.9999)

    sd = ema.state_dict()
    first_key = next(iter(sd))
    original_val = sd[first_key].clone()

    # Mutate the returned state dict.
    sd[first_key].fill_(999.0)

    # Shadow should be unchanged.
    assert torch.allclose(ema.shadow[first_key], original_val), (
        "state_dict() should return a copy, not a reference to the shadow"
    )


def test_train_step_conditional() -> None:
    device = torch.device("cpu")
    model = UNet(base_ch=8, num_classes=4).to(device)
    scheduler = DDPMScheduler(num_steps=10).to(device)
    specs = torch.randn(2, 1, 128, 173)
    labels = torch.tensor([0, 2], dtype=torch.long)
    batch = (specs, labels)

    loss = train_step(model, scheduler, batch, device, num_classes=4)

    assert loss.ndim == 0
    assert torch.isfinite(loss)
    assert loss.item() > 0


def test_cfg_dropout_produces_unconditional_tokens() -> None:
    device = torch.device("cpu")
    model = UNet(base_ch=8, num_classes=4).to(device)
    scheduler = DDPMScheduler(num_steps=10).to(device)

    seen_uncond = False
    for _ in range(20):
        specs = torch.randn(4, 1, 128, 173)
        labels = torch.zeros(4, dtype=torch.long)  # all class 0
        batch = (specs, labels)
        # With cfg_dropout=1.0, every label becomes the unconditional token (4)
        loss = train_step(model, scheduler, batch, device, num_classes=4, cfg_dropout=1.0)
        assert torch.isfinite(loss)
        seen_uncond = True

    assert seen_uncond, "train_step with cfg_dropout=1.0 should always use unconditional tokens"

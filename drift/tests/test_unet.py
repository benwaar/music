"""Tests for UNet noise-prediction backbone."""

import pytest
import torch

from drift.unet import UNet


@pytest.fixture
def model() -> UNet:
    return UNet().eval()


@pytest.fixture
def inputs() -> tuple[torch.Tensor, torch.Tensor]:
    x = torch.randn(2, 1, 128, 176)
    t = torch.randint(0, 1000, (2,))
    return x, t


def test_output_shape(model: UNet, inputs: tuple[torch.Tensor, torch.Tensor]) -> None:
    x, t = inputs
    with torch.no_grad():
        out = model(x, t)
    assert out.shape == x.shape


def test_gradient_flow(inputs: tuple[torch.Tensor, torch.Tensor]) -> None:
    model = UNet().train()
    x, t = inputs
    out = model(x, t)
    loss = out.mean()
    loss.backward()
    params_without_grad = [
        name for name, p in model.named_parameters() if p.grad is None
    ]
    assert not params_without_grad, f"No grad: {params_without_grad}"


def test_time_conditioning(model: UNet, inputs: tuple[torch.Tensor, torch.Tensor]) -> None:
    x, _ = inputs
    t1 = torch.zeros(2, dtype=torch.long)
    t2 = torch.full((2,), 500, dtype=torch.long)
    with torch.no_grad():
        out1 = model(x, t1)
        out2 = model(x, t2)
    assert not torch.allclose(out1, out2), "Different timesteps should produce different outputs"


def test_parameter_count(model: UNet) -> None:
    n_params = sum(p.numel() for p in model.parameters())
    assert 1_000_000 <= n_params <= 5_000_000, f"Param count {n_params:,} outside [1M, 5M]"


def test_attn_levels_output_shape(inputs: tuple[torch.Tensor, torch.Tensor]) -> None:
    """UNet with extra attention at level 2 produces correct output shape."""
    model = UNet(attn_levels={2}).eval()
    x, t = inputs
    with torch.no_grad():
        out = model(x, t)
    assert out.shape == x.shape


def test_attn_levels_increases_params() -> None:
    """Extra attention layers should add parameters."""
    base = sum(p.numel() for p in UNet().parameters())
    with_attn = sum(p.numel() for p in UNet(attn_levels={2}).parameters())
    assert with_attn > base, f"Expected more params with attention, got {with_attn} vs {base}"


def test_conditional_output_shape(inputs: tuple[torch.Tensor, torch.Tensor]) -> None:
    model = UNet(num_classes=4).eval()
    x, t = inputs
    labels = torch.randint(0, 4, (x.shape[0],))
    with torch.no_grad():
        out = model(x, t, class_label=labels)
    assert out.shape == x.shape


def test_class_conditioning_changes_output(inputs: tuple[torch.Tensor, torch.Tensor]) -> None:
    model = UNet(num_classes=4).eval()
    x, t = inputs
    label_a = torch.zeros(x.shape[0], dtype=torch.long)
    label_b = torch.ones(x.shape[0], dtype=torch.long)
    with torch.no_grad():
        out_a = model(x, t, class_label=label_a)
        out_b = model(x, t, class_label=label_b)
    assert not torch.allclose(out_a, out_b), "Different class labels should produce different outputs"


def test_unconditional_token(inputs: tuple[torch.Tensor, torch.Tensor]) -> None:
    num_classes = 4
    model = UNet(num_classes=num_classes).eval()
    x, t = inputs
    uncond = torch.full((x.shape[0],), num_classes, dtype=torch.long)
    with torch.no_grad():
        out = model(x, t, class_label=uncond)
    assert out.shape == x.shape


def test_backward_compat_no_class_label(inputs: tuple[torch.Tensor, torch.Tensor]) -> None:
    model = UNet(num_classes=4).eval()
    x, t = inputs
    with torch.no_grad():
        out = model(x, t)
    assert out.shape == x.shape


def test_num_classes_zero_ignores_label(inputs: tuple[torch.Tensor, torch.Tensor]) -> None:
    model = UNet(num_classes=0).eval()
    x, t = inputs
    label = torch.zeros(x.shape[0], dtype=torch.long)
    with torch.no_grad():
        out = model(x, t, class_label=label)
    assert out.shape == x.shape

import torch
import pytest
from drift.scheduler import DDPMScheduler, DDIMScheduler


@pytest.fixture
def scheduler() -> DDPMScheduler:
    return DDPMScheduler()


def test_schedule_shapes(scheduler: DDPMScheduler) -> None:
    assert scheduler.betas.shape == (1000,)
    assert scheduler.alphas.shape == (1000,)
    assert scheduler.alpha_cumprod.shape == (1000,)
    assert scheduler.sqrt_alpha_cumprod.shape == (1000,)
    assert scheduler.sqrt_one_minus_alpha_cumprod.shape == (1000,)
    assert scheduler.sqrt_recip_alpha.shape == (1000,)
    assert scheduler.posterior_variance.shape == (1000,)


def test_alpha_cumprod_bounds(scheduler: DDPMScheduler) -> None:
    ac = scheduler.alpha_cumprod
    assert ac[0].item() > 0.99, "should start near 1"
    assert ac[-1].item() < 0.01, "should end near 0"
    diffs = ac[1:] - ac[:-1]
    assert (diffs < 0).all(), "should be monotonically decreasing"


def test_add_noise_at_t0(scheduler: DDPMScheduler) -> None:
    B = 2
    x_0 = torch.randn(B, 1, 128, 64)
    noise = torch.randn_like(x_0)
    t = torch.zeros(B, dtype=torch.long)
    x_t = scheduler.add_noise(x_0, t, noise)
    # At t=0 sqrt_one_minus_alpha_cumprod ≈ 0.01 — noise contribution is tiny.
    # Use MSE rather than element-wise allclose so a few extreme noise values don't fail.
    mse = ((x_t - x_0) ** 2).mean().item()
    assert mse < 1e-2, f"MSE at t=0 should be small, got {mse:.4f}"


def test_add_noise_at_t999(scheduler: DDPMScheduler) -> None:
    B = 2
    x_0 = torch.randn(B, 1, 128, 64)
    noise = torch.randn_like(x_0)
    t = torch.full((B,), 999, dtype=torch.long)
    x_t = scheduler.add_noise(x_0, t, noise)
    # At t=999 alpha_cumprod ≈ 0, x_0 contribution is negligible.
    mse = ((x_t - noise) ** 2).mean().item()
    assert mse < 1e-2, f"MSE at t=999 should be small, got {mse:.4f}"


def test_step_output_shape(scheduler: DDPMScheduler) -> None:
    B = 2
    x_t = torch.randn(B, 1, 128, 64)
    noise_pred = torch.randn_like(x_t)
    t = torch.ones(B, dtype=torch.long) * 500
    out = scheduler.step(x_t, t, noise_pred)
    assert out.shape == x_t.shape


def test_roundtrip_low_t(scheduler: DDPMScheduler) -> None:
    """add_noise then step with perfect prediction should ≈ recover x_0 at low t."""
    B = 2
    x_0 = torch.randn(B, 1, 128, 64)
    noise = torch.randn_like(x_0)
    t = torch.ones(B, dtype=torch.long)  # t=1

    x_t = scheduler.add_noise(x_0, t, noise)
    # Perfect noise prediction: pass the actual noise used
    x_prev = scheduler.step(x_t, t, noise)

    # At t=1 the step should bring us close to x_0; tolerance is loose
    # because posterior variance still adds a small amount of noise
    mse = ((x_prev - x_0) ** 2).mean().item()
    assert mse < 0.5, f"roundtrip MSE too high at low t: {mse:.4f}"


def test_sample_timesteps(scheduler: DDPMScheduler) -> None:
    t = scheduler.sample_timesteps(16)
    assert t.shape == (16,)
    assert t.min() >= 0
    assert t.max() < 1000


def test_step_scalar_t(scheduler: DDPMScheduler) -> None:
    x_t = torch.randn(1, 1, 128, 64)
    noise_pred = torch.randn_like(x_t)
    out = scheduler.step(x_t, 5, noise_pred)
    assert out.shape == x_t.shape


def test_step_t0_no_noise(scheduler: DDPMScheduler) -> None:
    """At t=0 the step should return the mean (no stochastic variance term)."""
    torch.manual_seed(42)
    x_t = torch.randn(2, 1, 128, 64)
    noise_pred = torch.randn_like(x_t)
    t = torch.zeros(2, dtype=torch.long)

    # Two calls at t=0 should give the same result (no randomness)
    out1 = scheduler.step(x_t, t, noise_pred)
    out2 = scheduler.step(x_t, t, noise_pred)
    assert torch.allclose(out1, out2), "t=0 step must be deterministic (no noise)"


# --- DDIMScheduler tests ---


@pytest.fixture
def ddim() -> DDIMScheduler:
    return DDIMScheduler(num_inference_steps=50)


def test_ddim_timesteps_length(ddim: DDIMScheduler) -> None:
    assert len(ddim.timesteps) == 50


def test_ddim_timesteps_descending(ddim: DDIMScheduler) -> None:
    ts = ddim.timesteps
    assert (ts[:-1] > ts[1:]).all(), "timesteps must be in descending order"


def test_ddim_step_output_shape(ddim: DDIMScheduler) -> None:
    B = 2
    x_t = torch.randn(B, 1, 128, 64)
    noise_pred = torch.randn_like(x_t)
    t = ddim.timesteps[5].item()
    out = ddim.step(x_t, t, noise_pred)
    assert out.shape == x_t.shape


def test_ddim_deterministic_eta0() -> None:
    sched = DDIMScheduler(num_inference_steps=50, eta=0.0)
    torch.manual_seed(0)
    x_t = torch.randn(1, 1, 128, 64)
    noise_pred = torch.randn_like(x_t)
    t = sched.timesteps[10].item()
    out1 = sched.step(x_t, t, noise_pred)
    out2 = sched.step(x_t, t, noise_pred)
    assert torch.allclose(out1, out2), "eta=0 must be fully deterministic"


def test_ddim_stochastic_eta1() -> None:
    sched = DDIMScheduler(num_inference_steps=50, eta=1.0)
    x_t = torch.randn(1, 1, 128, 64)
    noise_pred = torch.randn_like(x_t)
    t = sched.timesteps[10].item()
    out1 = sched.step(x_t, t, noise_pred)
    out2 = sched.step(x_t, t, noise_pred)
    assert not torch.allclose(out1, out2), "eta=1 must be stochastic"


def test_ddim_fewer_steps_same_shape() -> None:
    sched_50 = DDIMScheduler(num_inference_steps=50)
    sched_1000 = DDIMScheduler(num_inference_steps=1000)
    x_t = torch.randn(1, 1, 128, 64)
    noise_pred = torch.randn_like(x_t)
    t_50 = sched_50.timesteps[0].item()
    t_1000 = sched_1000.timesteps[0].item()
    out_50 = sched_50.step(x_t, t_50, noise_pred)
    out_1000 = sched_1000.step(x_t, t_1000, noise_pred)
    assert out_50.shape == out_1000.shape


def test_ddim_add_noise_matches_ddpm() -> None:
    ddpm = DDPMScheduler()
    ddim = DDIMScheduler()
    B = 2
    x_0 = torch.randn(B, 1, 128, 64)
    noise = torch.randn_like(x_0)
    t = torch.full((B,), 500, dtype=torch.long)
    assert torch.allclose(ddpm.add_noise(x_0, t, noise), ddim.add_noise(x_0, t, noise))

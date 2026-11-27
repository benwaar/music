from __future__ import annotations

import torch
import torch.nn as nn


class DDPMScheduler(nn.Module):
    def __init__(
        self,
        num_steps: int = 1000,
        beta_start: float = 1e-4,
        beta_end: float = 0.02,
    ) -> None:
        super().__init__()
        self.num_steps = num_steps

        betas = torch.linspace(beta_start, beta_end, num_steps, dtype=torch.float32)
        alphas = 1.0 - betas
        alpha_cumprod = torch.cumprod(alphas, dim=0)

        alpha_cumprod_prev = torch.cat(
            [torch.ones(1, dtype=torch.float32), alpha_cumprod[:-1]]
        )
        posterior_variance = betas * (1.0 - alpha_cumprod_prev) / (1.0 - alpha_cumprod)

        self.register_buffer("betas", betas)
        self.register_buffer("alphas", alphas)
        self.register_buffer("alpha_cumprod", alpha_cumprod)
        self.register_buffer("sqrt_alpha_cumprod", torch.sqrt(alpha_cumprod))
        self.register_buffer(
            "sqrt_one_minus_alpha_cumprod", torch.sqrt(1.0 - alpha_cumprod)
        )
        self.register_buffer("sqrt_recip_alpha", torch.sqrt(1.0 / alphas))
        self.register_buffer("posterior_variance", posterior_variance)

    def _gather(self, tensor: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        """Index tensor by t and reshape to (B, 1, 1, 1) for broadcasting."""
        return tensor[t].reshape(-1, 1, 1, 1)

    def add_noise(
        self, x_0: torch.Tensor, t: torch.Tensor, noise: torch.Tensor
    ) -> torch.Tensor:
        sqrt_ac = self._gather(self.sqrt_alpha_cumprod, t)
        sqrt_one_minus_ac = self._gather(self.sqrt_one_minus_alpha_cumprod, t)
        return sqrt_ac * x_0 + sqrt_one_minus_ac * noise

    def step(
        self,
        x_t: torch.Tensor,
        t: int | torch.Tensor,
        noise_pred: torch.Tensor,
    ) -> torch.Tensor:
        if isinstance(t, int):
            t_tensor = torch.tensor([t], device=x_t.device)
        else:
            t_tensor = t.to(x_t.device)

        sqrt_recip_alpha = self._gather(self.sqrt_recip_alpha, t_tensor)
        betas = self._gather(self.betas, t_tensor)
        sqrt_omc = self._gather(self.sqrt_one_minus_alpha_cumprod, t_tensor)

        mean = sqrt_recip_alpha * (x_t - betas / sqrt_omc * noise_pred)

        # t == 0 mask: no noise on final step
        is_final = (t_tensor == 0).reshape(-1, 1, 1, 1).float()
        var = self._gather(self.posterior_variance, t_tensor)
        noise = torch.randn_like(x_t)
        return mean + (1.0 - is_final) * torch.sqrt(var) * noise

    def sample_timesteps(self, batch_size: int) -> torch.Tensor:
        return torch.randint(0, self.num_steps, (batch_size,))


class DDIMScheduler(nn.Module):
    def __init__(
        self,
        num_train_steps: int = 1000,
        num_inference_steps: int = 50,
        beta_start: float = 1e-4,
        beta_end: float = 0.02,
        eta: float = 0.0,
    ) -> None:
        super().__init__()
        self.num_steps = num_inference_steps
        self.eta = eta

        betas = torch.linspace(beta_start, beta_end, num_train_steps, dtype=torch.float32)
        alphas = 1.0 - betas
        alpha_cumprod = torch.cumprod(alphas, dim=0)

        self.register_buffer("betas", betas)
        self.register_buffer("alphas", alphas)
        self.register_buffer("alpha_cumprod", alpha_cumprod)
        self.register_buffer("sqrt_alpha_cumprod", torch.sqrt(alpha_cumprod))
        self.register_buffer(
            "sqrt_one_minus_alpha_cumprod", torch.sqrt(1.0 - alpha_cumprod)
        )

        # Evenly-spaced subsequence of training timesteps, ascending then reversed.
        step_ratio = num_train_steps // num_inference_steps
        timesteps = (torch.arange(0, num_inference_steps) * step_ratio + step_ratio - 1).long()
        timesteps = timesteps.flip(0)
        self.register_buffer("timesteps", timesteps)

    def _gather(self, tensor: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        return tensor[t].reshape(-1, 1, 1, 1)

    def add_noise(
        self, x_0: torch.Tensor, t: torch.Tensor, noise: torch.Tensor
    ) -> torch.Tensor:
        sqrt_ac = self._gather(self.sqrt_alpha_cumprod, t)
        sqrt_one_minus_ac = self._gather(self.sqrt_one_minus_alpha_cumprod, t)
        return sqrt_ac * x_0 + sqrt_one_minus_ac * noise

    def step(
        self,
        x_t: torch.Tensor,
        t: int | torch.Tensor,
        noise_pred: torch.Tensor,
        t_prev: int | torch.Tensor | None = None,
    ) -> torch.Tensor:
        if isinstance(t, int):
            t_tensor = torch.tensor([t], device=x_t.device)
        else:
            t_tensor = t.to(x_t.device)

        # Look up t_prev from the subsequence when not provided.
        if t_prev is None:
            idx = (self.timesteps == t_tensor[0]).nonzero(as_tuple=True)[0]
            if idx.numel() > 0 and idx[0] + 1 < len(self.timesteps):
                t_prev = self.timesteps[idx[0] + 1].item()
            else:
                t_prev = -1

        alpha_bar_t = self._gather(self.alpha_cumprod, t_tensor)
        sqrt_one_minus_alpha_bar_t = self._gather(self.sqrt_one_minus_alpha_cumprod, t_tensor)

        if isinstance(t_prev, int) and t_prev < 0:
            # Final step — treat as though alpha_bar_{t-1} = 1.0 (clean signal).
            alpha_bar_prev = torch.ones_like(alpha_bar_t)
        else:
            if isinstance(t_prev, int):
                t_prev_tensor = torch.tensor([t_prev], device=x_t.device)
            else:
                t_prev_tensor = t_prev.to(x_t.device)
            alpha_bar_prev = self._gather(self.alpha_cumprod, t_prev_tensor)

        x_0_pred = (x_t - sqrt_one_minus_alpha_bar_t * noise_pred) / torch.sqrt(alpha_bar_t)
        x_0_pred = x_0_pred.clamp(-3.0, 3.0)

        sigma = self.eta * torch.sqrt(
            (1.0 - alpha_bar_prev) / (1.0 - alpha_bar_t) * (1.0 - alpha_bar_t / alpha_bar_prev)
        )

        dir_xt = torch.sqrt(1.0 - alpha_bar_prev - sigma ** 2) * noise_pred

        noise = torch.randn_like(x_t) if self.eta > 0.0 else torch.zeros_like(x_t)
        return torch.sqrt(alpha_bar_prev) * x_0_pred + dir_xt + sigma * noise

    @property
    def inference_timesteps(self) -> list[int]:
        """Return timesteps in reverse order for the sampling loop."""
        return self.timesteps.tolist()

    def sample_timesteps(self, batch_size: int) -> torch.Tensor:
        return torch.randint(0, len(self.alpha_cumprod), (batch_size,))

"""U-Net noise-prediction backbone for DDPM diffusion on Mel-spectrograms."""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def sinusoidal_embedding(t: torch.Tensor, dim: int) -> torch.Tensor:
    half = dim // 2
    freqs = torch.exp(
        -math.log(10000) * torch.arange(half, device=t.device) / (half - 1)
    )
    args = t[:, None].float() * freqs[None]
    return torch.cat([args.sin(), args.cos()], dim=-1)


class TimeEmbed(nn.Module):
    def __init__(self, model_dim: int) -> None:
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(model_dim, model_dim * 4),
            nn.SiLU(),
            nn.Linear(model_dim * 4, model_dim),
        )
        self.dim = model_dim

    def forward(self, t: torch.Tensor) -> torch.Tensor:
        emb = sinusoidal_embedding(t, self.dim)
        return self.mlp(emb)


class ResBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, time_dim: int) -> None:
        super().__init__()
        self.norm1 = nn.GroupNorm(8, in_ch)
        self.conv1 = nn.Conv2d(in_ch, out_ch, 3, padding=1)
        self.time_proj = nn.Linear(time_dim, out_ch)
        self.norm2 = nn.GroupNorm(8, out_ch)
        self.conv2 = nn.Conv2d(out_ch, out_ch, 3, padding=1)
        self.skip = nn.Conv2d(in_ch, out_ch, 1) if in_ch != out_ch else nn.Identity()

    def forward(self, x: torch.Tensor, t_emb: torch.Tensor) -> torch.Tensor:
        h = self.conv1(F.silu(self.norm1(x)))
        h = h + self.time_proj(F.silu(t_emb))[:, :, None, None]
        h = self.conv2(F.silu(self.norm2(h)))
        return h + self.skip(x)


class SelfAttention(nn.Module):
    def __init__(self, ch: int) -> None:
        super().__init__()
        self.norm = nn.GroupNorm(8, ch)
        self.q = nn.Conv1d(ch, ch, 1)
        self.k = nn.Conv1d(ch, ch, 1)
        self.v = nn.Conv1d(ch, ch, 1)
        self.proj = nn.Conv1d(ch, ch, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, C, H, W = x.shape
        h = self.norm(x).view(B, C, H * W)
        q, k, v = self.q(h), self.k(h), self.v(h)
        # (B, C, N) → (B, N, C) for sdp
        q, k, v = q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)
        if hasattr(F, "scaled_dot_product_attention"):
            out = F.scaled_dot_product_attention(q, k, v)
        else:
            scale = q.shape[-1] ** -0.5
            attn = torch.softmax((q @ k.transpose(-2, -1)) * scale, dim=-1)
            out = attn @ v
        out = self.proj(out.transpose(1, 2)).view(B, C, H, W)
        return x + out


class Downsample(nn.Module):
    def __init__(self, ch: int) -> None:
        super().__init__()
        self.conv = nn.Conv2d(ch, ch, 3, stride=2, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class Upsample(nn.Module):
    def __init__(self, ch: int) -> None:
        super().__init__()
        self.conv = nn.Conv2d(ch, ch, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(F.interpolate(x, scale_factor=2, mode="nearest"))


class UNet(nn.Module):
    """Small U-Net for DDPM noise prediction on (B, 1, 128, 176) spectrograms.

    Args:
        base_ch: Base channel count. Stages use [base_ch, 2×, 4×].
        attn_levels: Set of down-path levels (0-indexed) to add self-attention.
                     Default {-1} = bottleneck only (original behaviour).
                     Use {2, -1} to add attention at level 2 (32×44) + bottleneck.
    """

    def __init__(
        self,
        base_ch: int = 32,
        attn_levels: set[int] | None = None,
        num_classes: int = 0,
    ) -> None:
        super().__init__()
        if attn_levels is None:
            attn_levels = set()
        self.attn_levels = attn_levels
        self.num_classes = num_classes

        t_dim = base_ch
        ch = [base_ch, base_ch * 2, base_ch * 4]

        self.time_embed = TimeEmbed(t_dim)
        # +1 for the unconditional token (index num_classes) used in CFG
        if num_classes > 0:
            self.class_emb = nn.Embedding(num_classes + 1, t_dim)
        self.input_conv = nn.Conv2d(1, ch[0], 3, padding=1)

        # Down path
        self.down0 = nn.ModuleList([ResBlock(ch[0], ch[0], t_dim), ResBlock(ch[0], ch[0], t_dim)])
        self.attn_down0 = SelfAttention(ch[0]) if 0 in attn_levels else None
        self.ds0 = Downsample(ch[0])

        self.down1 = nn.ModuleList([ResBlock(ch[0], ch[1], t_dim), ResBlock(ch[1], ch[1], t_dim)])
        self.attn_down1 = SelfAttention(ch[1]) if 1 in attn_levels else None
        self.ds1 = Downsample(ch[1])

        self.down2 = nn.ModuleList([ResBlock(ch[1], ch[2], t_dim), ResBlock(ch[2], ch[2], t_dim)])
        self.attn_down2 = SelfAttention(ch[2]) if 2 in attn_levels else None
        self.ds2 = Downsample(ch[2])

        # Bottleneck
        self.mid0 = ResBlock(ch[2], ch[2], t_dim)
        self.attn = SelfAttention(ch[2])
        self.mid1 = ResBlock(ch[2], ch[2], t_dim)

        # Up path
        self.us2 = Upsample(ch[2])
        self.up2 = nn.ModuleList([ResBlock(ch[2] * 2, ch[2], t_dim), ResBlock(ch[2], ch[2], t_dim)])
        self.attn_up2 = SelfAttention(ch[2]) if 2 in attn_levels else None

        self.us1 = Upsample(ch[2])
        self.up1 = nn.ModuleList([ResBlock(ch[2] + ch[1], ch[1], t_dim), ResBlock(ch[1], ch[1], t_dim)])
        self.attn_up1 = SelfAttention(ch[1]) if 1 in attn_levels else None

        self.us0 = Upsample(ch[1])
        self.up0 = nn.ModuleList([ResBlock(ch[1] + ch[0], ch[0], t_dim), ResBlock(ch[0], ch[0], t_dim)])
        self.attn_up0 = SelfAttention(ch[0]) if 0 in attn_levels else None

        self.out_norm = nn.GroupNorm(8, ch[0])
        self.out_conv = nn.Conv2d(ch[0], 1, 3, padding=1)

    def forward(
        self, x: torch.Tensor, t: torch.Tensor, class_label: torch.Tensor | None = None
    ) -> torch.Tensor:
        t_emb = self.time_embed(t)
        if class_label is not None and self.num_classes > 0:
            t_emb = t_emb + self.class_emb(class_label)

        h = self.input_conv(x)

        # Down
        for blk in self.down0:
            h = blk(h, t_emb)
        if self.attn_down0 is not None:
            h = self.attn_down0(h)
        skip0 = h
        h = self.ds0(h)

        for blk in self.down1:
            h = blk(h, t_emb)
        if self.attn_down1 is not None:
            h = self.attn_down1(h)
        skip1 = h
        h = self.ds1(h)

        for blk in self.down2:
            h = blk(h, t_emb)
        if self.attn_down2 is not None:
            h = self.attn_down2(h)
        skip2 = h
        h = self.ds2(h)

        # Bottleneck
        h = self.mid0(h, t_emb)
        h = self.attn(h)
        h = self.mid1(h, t_emb)

        # Up
        h = self.us2(h)
        h = torch.cat([h, skip2], dim=1)
        for blk in self.up2:
            h = blk(h, t_emb)
        if self.attn_up2 is not None:
            h = self.attn_up2(h)

        h = self.us1(h)
        h = torch.cat([h, skip1], dim=1)
        for blk in self.up1:
            h = blk(h, t_emb)
        if self.attn_up1 is not None:
            h = self.attn_up1(h)

        h = self.us0(h)
        h = torch.cat([h, skip0], dim=1)
        for blk in self.up0:
            h = blk(h, t_emb)
        if self.attn_up0 is not None:
            h = self.attn_up0(h)

        return self.out_conv(F.silu(self.out_norm(h)))

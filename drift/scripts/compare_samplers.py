"""Compare DDPM vs DDIM sampling at various step counts.

Generates samples from the same checkpoint with DDPM (1000 steps) and
DDIM (25, 50, 100, 200 steps), then compares quality (MSD, autocorrelation)
and generation time.

Usage:
    python scripts/compare_samplers.py --checkpoint _data/checkpoints_8s_loops/epoch_0020.pt
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

from drift.dataset import get_dataloader
from drift.metrics import autocorrelation, batch_autocorrelation, mean_spectral_distance
from drift.sampler import generate_and_crop
from drift.scheduler import DDIMScheduler, DDPMScheduler
from drift.train import get_device, pad_to_target, target_width_for_duration
from drift.unet import UNet


def load_model(ckpt_path: Path, device: torch.device) -> tuple[UNet, dict]:
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    config = ckpt.get("config", {})
    attn_levels: set[int] = set()
    attn_str = config.get("attn_levels", "")
    if attn_str:
        attn_levels = {int(x.strip()) for x in attn_str.split(",")}
    base_ch = config.get("base_ch", 32)
    model = UNet(base_ch=base_ch, attn_levels=attn_levels).to(device)
    if "ema_state" in ckpt and ckpt["ema_state"]:
        model.load_state_dict(ckpt["ema_state"], strict=False)
    else:
        model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model, config


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare DDPM vs DDIM sampling")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--data", default="_data/segments_loops")
    parser.add_argument("--n-gen", type=int, default=10, dest="n_gen")
    parser.add_argument("--n-real", type=int, default=30, dest="n_real")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", default="_data/eval/ddim_comparison.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--eta", type=float, nargs="*", default=None,
                        help="Eta values to sweep (default: 0.0 only). E.g. --eta 0.0 0.5 1.0")
    args = parser.parse_args()

    device = get_device() if args.device == "auto" else torch.device(args.device)
    model, config = load_model(Path(args.checkpoint), device)
    duration = config.get("duration", 4)
    original_width = -(-duration * 22050 // 512)
    tw = target_width_for_duration(duration)

    print(f"Model: base_ch={config.get('base_ch', 32)}, duration={duration}s, width={tw}")

    # Load real samples for MSD comparison
    print(f"\nLoading {args.n_real} real samples...")
    loader = get_dataloader(
        Path(args.data), duration=duration, split="train",
        batch_size=args.n_real, num_workers=0, shuffle=True,
    )
    real_specs, _ = next(iter(loader))
    real_specs = pad_to_target(real_specs, tw)[:, :, :, :original_width]

    real_ac = batch_autocorrelation(real_specs.cpu(), min_lag=5)
    real_ac_mean = sum(s for _, s in real_ac) / len(real_ac)
    print(f"  Real autocorrelation: {real_ac_mean:.3f}")

    etas = args.eta if args.eta is not None else [0.0]
    ddim_steps = [200, 100, 50, 25]

    step_counts: list[tuple[str, int, float | None]] = [("DDPM", 1000, None)]
    for steps in ddim_steps:
        for eta in etas:
            label = f"DDIM-{steps}" if len(etas) == 1 else f"DDIM-{steps}-eta{eta}"
            step_counts.append((label, steps, eta))

    results = []

    for label, steps, eta in step_counts:
        print(f"\n{'='*60}")
        print(f"  {label} ({steps} steps{f', eta={eta}' if eta is not None else ''})")
        print(f"{'='*60}")

        if eta is None:
            scheduler = DDPMScheduler(num_steps=1000).to(device)
        else:
            scheduler = DDIMScheduler(num_inference_steps=steps, eta=eta).to(device)

        torch.manual_seed(args.seed)
        start_time = time.time()
        gen = generate_and_crop(model, scheduler, args.n_gen, device, original_width=original_width)
        elapsed = time.time() - start_time

        gen_cpu = gen.cpu()
        msd = mean_spectral_distance(real_specs, gen_cpu)
        ac_results = batch_autocorrelation(gen_cpu, min_lag=5)
        ac_mean = sum(s for _, s in ac_results) / len(ac_results)

        per_sample = elapsed / args.n_gen
        speedup = None

        result = {
            "label": label,
            "steps": steps,
            "n_samples": args.n_gen,
            "time_total_s": round(elapsed, 1),
            "time_per_sample_s": round(per_sample, 1),
            "msd": round(msd, 4),
            "autocorrelation_mean": round(ac_mean, 4),
            "autocorrelation_gap": round(real_ac_mean - ac_mean, 4),
        }
        results.append(result)

        print(f"  Time: {elapsed:.1f}s total, {per_sample:.1f}s/sample")
        print(f"  MSD:  {msd:.4f}")
        print(f"  Autocorrelation: {ac_mean:.3f} (gap: {real_ac_mean - ac_mean:.3f})")

    # Compute speedups relative to DDPM
    ddpm_time = results[0]["time_per_sample_s"]
    for r in results:
        r["speedup"] = round(ddpm_time / r["time_per_sample_s"], 1) if r["time_per_sample_s"] > 0 else None

    # Summary table
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Real autocorrelation: {real_ac_mean:.3f}")
    print()
    print(f"  {'Method':<12} {'Steps':>5} {'Time/sample':>11} {'Speedup':>8} {'MSD':>8} {'AutoCorr':>8} {'Gap':>8}")
    print(f"  {'-'*12} {'-'*5} {'-'*11} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for r in results:
        speedup_str = f"{r['speedup']:.1f}x" if r['speedup'] else "—"
        print(f"  {r['label']:<12} {r['steps']:>5} {r['time_per_sample_s']:>9.1f}s {speedup_str:>8} {r['msd']:>8.4f} {r['autocorrelation_mean']:>8.3f} {r['autocorrelation_gap']:>8.3f}")

    # Save JSON
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "checkpoint": args.checkpoint,
        "real_autocorrelation": round(real_ac_mean, 4),
        "results": results,
    }
    out_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()

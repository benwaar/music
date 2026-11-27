"""Evaluate training loss across saved checkpoints.

Loads each checkpoint, runs forward-only on a subsample of the training set,
and records the average MSE loss. Optionally plots the loss curve.

Usage:
    python scripts/evaluate_loss.py                          # all checkpoints
    python scripts/evaluate_loss.py --max-batches 200        # subsample (fast)
    python scripts/evaluate_loss.py --plot docs/images/m2b-loss-curve.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import torch

from drift.dataset import get_dataloader
from drift.scheduler import DDPMScheduler
from drift.train import TARGET_WIDTH, get_device, pad_to_target, train_step
from drift.unet import UNet


def evaluate_checkpoint(
    ckpt_path: Path,
    loader: torch.utils.data.DataLoader,
    device: torch.device,
    max_batches: int,
) -> float:
    """Compute average MSE loss for a single checkpoint."""
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)

    model = UNet(base_ch=32).to(device)
    scheduler = DDPMScheduler(num_steps=1000).to(device)

    if "ema_state" in ckpt and ckpt["ema_state"]:
        model.load_state_dict(ckpt["ema_state"], strict=False)
    else:
        model.load_state_dict(ckpt["model_state"])

    model.eval()

    total_loss = 0.0
    n_batches = 0

    with torch.no_grad():
        for batch in loader:
            if n_batches >= max_batches:
                break
            loss = train_step(model, scheduler, batch, device)
            total_loss += loss.item()
            n_batches += 1

    return total_loss / max(n_batches, 1)


def find_checkpoints(ckpt_dir: Path) -> list[tuple[int, Path]]:
    """Find all epoch_NNNN.pt checkpoints, return sorted (epoch, path) pairs."""
    results = []
    for p in sorted(ckpt_dir.glob("epoch_*.pt")):
        epoch = int(p.stem.split("_")[1])
        results.append((epoch, p))
    return results


def plot_loss_curve(
    results: list[dict],
    output_path: Path,
) -> None:
    """Plot epoch vs loss and save to file."""
    epochs = [r["epoch"] for r in results]
    losses = [r["loss"] for r in results]

    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    ax.plot(epochs, losses, "o-", color="#e84118", linewidth=2, markersize=6)
    ax.set_xlabel("Epoch", fontsize=12)
    ax.set_ylabel("MSE Loss", fontsize=12)
    ax.set_title("DDPM Training Loss Curve", fontsize=14)
    ax.grid(True, alpha=0.3)

    # Annotate trend
    if len(losses) >= 2:
        drop = losses[0] - losses[-1]
        pct = (drop / losses[0]) * 100
        last_drop = losses[-2] - losses[-1]
        last_pct = (last_drop / losses[-2]) * 100 if losses[-2] > 0 else 0
        ax.annotate(
            f"Total drop: {pct:.1f}%\nLast segment: {last_pct:.1f}%",
            xy=(epochs[-1], losses[-1]),
            xytext=(-120, 30),
            textcoords="offset points",
            fontsize=10,
            arrowprops={"arrowstyle": "->", "color": "#636e72"},
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "#dfe6e9"},
        )

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150)
    plt.close(fig)
    print(f"Plot saved: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate loss across checkpoints")
    parser.add_argument("--checkpoint-dir", default="_data/checkpoints", dest="checkpoint_dir")
    parser.add_argument("--data", default="_data/segments")
    parser.add_argument("--max-batches", type=int, default=200, dest="max_batches")
    parser.add_argument("--batch-size", type=int, default=16, dest="batch_size")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", default="_data/eval/loss_history.json")
    parser.add_argument("--plot", default="", help="Path to save loss curve plot")
    args = parser.parse_args()

    device = get_device() if args.device == "auto" else torch.device(args.device)

    checkpoints = find_checkpoints(Path(args.checkpoint_dir))
    if not checkpoints:
        print(f"No checkpoints found in {args.checkpoint_dir}")
        return

    print(f"Found {len(checkpoints)} checkpoints")
    print(f"Evaluating {args.max_batches} batches per checkpoint ({args.max_batches * args.batch_size} samples)")
    print()

    loader = get_dataloader(
        Path(args.data),
        duration=4,
        split="train",
        batch_size=args.batch_size,
        num_workers=0,
        shuffle=False,
    )

    results = []
    for epoch, ckpt_path in checkpoints:
        avg_loss = evaluate_checkpoint(ckpt_path, loader, device, args.max_batches)
        results.append({"epoch": epoch, "loss": round(avg_loss, 6), "checkpoint": str(ckpt_path)})
        print(f"  Epoch {epoch:>4}  loss = {avg_loss:.6f}")

    # Save JSON
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nResults saved: {out_path}")

    # Plot
    plot_path = Path(args.plot) if args.plot else Path("docs/images/m2b-loss-curve.png")
    plot_loss_curve(results, plot_path)

    # Summary
    if len(results) >= 2:
        first, last = results[0]["loss"], results[-1]["loss"]
        drop_pct = (first - last) / first * 100
        still_dropping = results[-1]["loss"] < results[-2]["loss"]
        print(f"\nSummary:")
        print(f"  Loss dropped {drop_pct:.1f}% (epoch {results[0]['epoch']} → {results[-1]['epoch']})")
        print(f"  Still dropping: {'YES — more training would help' if still_dropping else 'PLATEAUED — architectural changes needed'}")


if __name__ == "__main__":
    main()

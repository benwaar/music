#!/usr/bin/env python3
"""
Render chip-tune files to WAV using CLI emulators.

Reads downloaded chip files from _data/ and renders them to
_data/rendered_wav/{chip_type}/ as WAV files.

Emulators required:
  openmpt123  — MOD/XM tracker files (brew install openmpt123)
  sidplayfp   — SID C64 files        (brew install sidplayfp)
  vgm2wav     — VGM/VGZ files        (build from source or package manager)

Usage:
    python scripts/render_wav.py
    python scripts/render_wav.py --types mod sid
    python scripts/render_wav.py --types vgm --limit 50
    python scripts/render_wav.py --data _data --out _data/rendered_wav
"""
import argparse
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TIMEOUT = 120  # seconds per file

TOOLS_BIN = PROJECT_ROOT / "_tools" / "bin"
DEFAULT_DATA = Path("_data")
DEFAULT_OUT = Path("_data/rendered_wav")

CHIP_TYPES = ["mod", "sid", "vgm", "ay"]


def _find_tool(name: str) -> str:
    """Return the path to a tool binary, checking _tools/bin/ first."""
    local = TOOLS_BIN / name
    if local.is_file():
        return str(local)
    return name


def source_files(chip_type: str, data: Path) -> list[Path]:
    """Return all source files for a chip type."""
    if chip_type == "mod":
        return sorted(
            list((data / "modarchive" / "mod").glob("*.mod"))
            + list((data / "modarchive" / "xm").glob("*.xm"))
        )
    if chip_type == "sid":
        return sorted((data / "hvsc" / "sid").glob("*.sid"))
    if chip_type == "vgm":
        return sorted(
            list((data / "vgm").glob("*.vgm"))
            + list((data / "vgm").glob("*.vgz"))
        )
    if chip_type == "ay":
        return sorted((data / "ay").rglob("*.emul"))
    raise ValueError(f"Unknown chip type: {chip_type}")


def output_path(chip_type: str, src: Path, out: Path) -> Path:
    """Return the destination WAV path for a source file."""
    subdir_map = {"mod": "modarchive", "sid": "sid", "vgm": "vgm", "ay": "ay"}
    subdir = out / subdir_map[chip_type]
    return subdir / (src.stem + ".wav")


def render_cmd(chip_type: str, src: Path, dst: Path) -> list[str | None]:
    """Build the render command for a chip type.

    MOD/XM returns a shell pipeline string (needs shell=True).
    SID and VGM return a simple command list.
    """
    if chip_type == "mod":
        openmpt = _find_tool("openmpt123")
        return (
            f'"{openmpt}" --batch --stdout --samplerate 22050 --channels 1 --no-float'
            f' "{src.resolve()}" 2>/dev/null'
            f' | ffmpeg -f s16le -ar 22050 -ac 1 -i - "{dst}" -y -loglevel error'
        )
    if chip_type == "sid":
        return [_find_tool("sidplayfp"), "--sidlite", f"-w{dst}", "-t60", str(src)]
    if chip_type == "vgm":
        return [_find_tool("vgmplay"), "-w", "-W", str(dst.parent) + "/", str(src)]
    raise ValueError(f"Unknown chip type: {chip_type}")


def _render_one(
    chip_type: str, src: Path, dst: Path, error_log: Path,
) -> str:
    """Render a single file. Returns 'ok', 'skip', or 'fail'."""
    if dst.exists():
        return "skip"
    try:
        if chip_type == "ay":
            from drift.gme_render import render_emul_to_wav

            if not render_emul_to_wav(src, dst):
                raise RuntimeError("libgme render failed")
            return "ok"

        cmd = render_cmd(chip_type, src, dst)
        if isinstance(cmd, str):
            result = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=TIMEOUT,
            )
        else:
            result = subprocess.run(
                cmd, capture_output=True, timeout=TIMEOUT,
            )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="replace").strip())
        return "ok"
    except Exception as exc:
        msg = f"FAIL [{chip_type}] {src} — {exc}\n"
        with _log_lock:
            with error_log.open("a") as f:
                f.write(msg)
        if dst.exists():
            dst.unlink()
        return f"fail:{exc}"


_log_lock = threading.Lock()
_print_lock = threading.Lock()


def render_files(
    chip_type: str,
    files: list[Path],
    out: Path,
    error_log: Path,
    workers: int = 1,
) -> None:
    subdir_map = {"mod": "modarchive", "sid": "sid", "vgm": "vgm", "ay": "ay"}
    out_dir = out / subdir_map[chip_type]
    out_dir.mkdir(parents=True, exist_ok=True)

    total = len(files)
    ok = skip = fail = 0
    done = 0

    def _process(i: int, src: Path) -> tuple[int, str, str]:
        dst = output_path(chip_type, src, out)
        status = _render_one(chip_type, src, dst, error_log)
        return i, src.name, status

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_process, i, src): i
            for i, src in enumerate(files, 1)
        }
        for future in as_completed(futures):
            i, name, status = future.result()
            done += 1
            if status == "skip":
                skip += 1
            elif status == "ok":
                ok += 1
                with _print_lock:
                    print(f"  [{done}/{total}] rendered {name}", flush=True)
            else:
                fail += 1
                exc_msg = status.removeprefix("fail:")
                with _print_lock:
                    print(f"  [{done}/{total}] FAIL {name}: {exc_msg}", file=sys.stderr, flush=True)

    print(f"  {chip_type}: {ok} rendered, {skip} skipped, {fail} failed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=CHIP_TYPES,
        default=CHIP_TYPES,
        metavar="TYPE",
        help=f"chip types to render (default: all — {', '.join(CHIP_TYPES)})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="max files to render per chip type",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA,
        help="root data directory (default: _data)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="output directory (default: _data/rendered_wav)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="parallel render processes (default: 1, try 8 for SID)",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    error_log = args.out / "errors.log"

    for chip_type in args.types:
        files = source_files(chip_type, args.data)
        if args.limit:
            files = files[: args.limit]
        print(f"\n=== {chip_type.upper()} ({len(files)} files) ===")
        if not files:
            print("  No source files found — skipping.")
            continue
        render_files(chip_type, files, args.out, error_log, workers=args.workers)

    print(f"\nDone. Errors (if any) logged to {error_log}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Local ImageMagick optimizer for Agent Skills and AI media workflows."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_INPUTS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".tif", ".tiff"}
FORMATS = {"same": None, "webp": ".webp", "jpg": ".jpg", "png": ".png", "avif": ".avif"}


def find_magick(explicit: str | None) -> str:
    found = explicit or shutil.which("magick")
    if not found:
        raise RuntimeError("ImageMagick 7+ was not found. Install it and put magick on PATH.")
    return found


def identify(magick: str, source: Path) -> dict:
    command = [magick, "identify", "-format", "%m|%w|%h|%[channels]|%[colorspace]|%b", str(source)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    parts = result.stdout.strip().split("|", 5)
    if len(parts) != 6:
        raise RuntimeError(f"Could not parse ImageMagick identify output for {source}")
    channels = parts[3]
    return {
        "format": parts[0].lower(),
        "width": int(parts[1]),
        "height": int(parts[2]),
        "channels": channels,
        "colorspace": parts[4],
        "has_alpha": "a" in channels.lower() or "alpha" in channels.lower(),
        "bytes": source.stat().st_size,
        "identify_size": parts[5],
    }


def build_command(magick: str, source: Path, output: Path, fmt: str, quality: int | None,
                  max_dimension: int | None, strip: bool) -> list[str]:
    command = [magick, str(source)]
    if max_dimension:
        command += ["-resize", f"{max_dimension}x{max_dimension}>"]
    if strip:
        command.append("-strip")
    if fmt == "same":
        fmt = source.suffix.lower().lstrip(".")
        if fmt == "jpeg":
            fmt = "jpg"
    if fmt == "webp":
        command += ["-define", "webp:method=6", "-quality", str(quality or 92)]
    elif fmt == "jpg":
        command += ["-interlace", "Plane", "-sampling-factor", "4:4:4", "-quality", str(quality or 92)]
    elif fmt == "png":
        command += ["-define", "png:compression-level=9"]
    elif fmt == "avif":
        command += ["-quality", str(quality or 90)]
    command.append(str(output))
    return command


def optimize_one(source: Path, output_dir: Path, args: argparse.Namespace, magick: str,
                 relative_to: Path | None = None) -> dict:
    if not source.is_file():
        raise FileNotFoundError(str(source))
    before = identify(magick, source)
    fmt = args.format
    if fmt == "same":
        fmt = "jpg" if source.suffix.lower() in {".jpg", ".jpeg"} else source.suffix.lower().lstrip(".")
        if fmt not in {"png", "jpg", "webp", "avif"}:
            raise ValueError(f"Cannot preserve unsupported source format: {source.suffix}")
    if fmt == "jpg" and before["has_alpha"]:
        raise ValueError("JPEG output is unsafe for an image with transparency; choose WebP or PNG.")
    output_subdir = output_dir
    if relative_to is not None:
        output_subdir = output_dir / source.relative_to(relative_to).parent
    output_subdir.mkdir(parents=True, exist_ok=True)
    output = output_subdir / (source.stem + (FORMATS[args.format] or source.suffix.lower()))
    upper_limit = args.max_mb * 1024 * 1024 if args.max_mb else None
    lower_limit = args.min_mb * 1024 * 1024 if args.min_mb else None
    if lower_limit and upper_limit and lower_limit > upper_limit:
        raise ValueError("--min-mb cannot be greater than --max-mb")
    qualities = [args.quality] if args.quality else ([98, 95, 92, 90, 88, 85, 82, 79, 76, 73, 70] if fmt != "png" else [None])
    attempts = []
    for quality in qualities:
        subprocess.run(build_command(magick, source, output, fmt, quality, args.max_dimension, args.strip), check=True)
        after = identify(magick, output)
        attempts.append({"quality": quality, "bytes": after["bytes"]})
        in_range = (lower_limit is None or after["bytes"] >= lower_limit) and (upper_limit is None or after["bytes"] <= upper_limit)
        if in_range or (upper_limit is None and lower_limit is None) or (upper_limit is not None and after["bytes"] <= upper_limit and lower_limit is None):
            return {
                "status": "ok", "source": str(source), "output": str(output), "mode": args.mode,
                "format": fmt, "quality": quality, "source_bytes": before["bytes"],
                "output_bytes": after["bytes"], "saved_bytes": before["bytes"] - after["bytes"],
                "source_dimensions": [before["width"], before["height"]],
                "output_dimensions": [after["width"], after["height"]], "has_alpha": before["has_alpha"],
                "stripped_metadata": args.strip, "size_range_mb": {"min": args.min_mb, "max": args.max_mb}, "attempts": attempts,
            }
    if upper_limit:
        raise RuntimeError(f"Could not meet the requested size range for {source}; maximum is {args.max_mb} MiB")
    raise RuntimeError(f"Could not reach the requested minimum size for {source} without adding artificial data")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", type=Path, default=Path("optimized"))
    parser.add_argument("--mode", choices=("compress", "ai-upload", "ai-video"), default="compress")
    parser.add_argument("--format", choices=tuple(FORMATS), default="same", help="same preserves the source format")
    parser.add_argument("--min-mb", type=float, help="Optional minimum output size in MiB")
    parser.add_argument("--max-mb", type=float)
    parser.add_argument("--quality", type=int)
    parser.add_argument("--max-dimension", type=int)
    parser.add_argument("--strip", action="store_true", help="Remove metadata and color profiles")
    parser.add_argument("--magick")


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize images with ImageMagick and verify output bytes.")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("input", type=Path)
    inspect_parser.add_argument("--magick")
    optimize_parser = sub.add_parser("optimize")
    optimize_parser.add_argument("input", type=Path)
    add_common(optimize_parser)
    batch_parser = sub.add_parser("batch")
    batch_parser.add_argument("input_dir", type=Path)
    batch_parser.add_argument("--recursive", action="store_true")
    add_common(batch_parser)
    args = parser.parse_args()
    try:
        magick = find_magick(getattr(args, "magick", None))
        if args.command == "inspect":
            print(json.dumps(identify(magick, args.input), ensure_ascii=False, indent=2))
            return 0
        sources = [args.input] if args.command == "optimize" else sorted(
            p for p in (args.input_dir.rglob("*") if args.recursive else args.input_dir.iterdir())
            if p.is_file() and p.suffix.lower() in SUPPORTED_INPUTS
        )
        if not sources:
            raise RuntimeError("No supported image files found.")
        results = []
        for source in sources:
            try:
                relative_to = args.input_dir if args.command == "batch" and args.recursive else None
                results.append(optimize_one(source, args.output_dir, args, magick, relative_to))
            except Exception as exc:  # report per-file failures for batch jobs
                results.append({"status": "error", "source": str(source), "error": str(exc)})
        manifest = args.output_dir / "manifest.json"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"tool": "image-compression", "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"manifest": str(manifest), "results": results}, ensure_ascii=False, indent=2))
        return 0 if all(item["status"] == "ok" for item in results) else 2
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

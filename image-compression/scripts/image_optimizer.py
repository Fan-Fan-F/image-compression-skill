#!/usr/bin/env python3
"""Local ImageMagick optimizer for Agent Skills and AI media workflows."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

SUPPORTED_INPUTS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".tif", ".tiff"}
FORMATS = {"same": None, "webp": ".webp", "jpg": ".jpg", "png": ".png", "avif": ".avif"}


def find_magick(explicit: str | None) -> str:
    found = explicit or shutil.which("magick")
    if not found:
        raise RuntimeError("ImageMagick 7+ was not found. Install it and put magick on PATH.")
    return found


def identify(magick: str, source: Path) -> dict:
    command = [magick, "identify", "-format", "%m|%w|%h|%[channels]|%[colorspace]|%b|%A|%[opaque]|%n\n", str(source)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    rows = result.stdout.strip().splitlines()
    if len(rows) != 1:
        raise ValueError("Multi-frame images are not supported; no frames were discarded.")
    parts = rows[0].split("|")
    if len(parts) != 9:
        raise RuntimeError(f"Could not parse ImageMagick identify output for {source}")
    if parts[8] != "1":
        raise ValueError("Multi-frame images are not supported; no frames were discarded.")
    alpha, opaque = parts[6].lower(), parts[7].lower()
    if alpha not in {"undefined", "blend", "copy", "update"} or opaque not in {"true", "false"}:
        raise RuntimeError("ImageMagick did not return an explicit alpha/opacity result.")
    channels = parts[3]
    return {
        "format": parts[0].lower(),
        "width": int(parts[1]),
        "height": int(parts[2]),
        "channels": channels,
        "colorspace": parts[4],
        "has_alpha": alpha != "undefined",
        "is_opaque": opaque == "true",
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


def same_file(first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    return first.exists() and second.exists() and first.samefile(second)


def guard_output(output: Path, sources: list[Path], overwrite: bool) -> None:
    if any(same_file(output, source) for source in sources):
        raise ValueError("An output aliases a source image; source replacement is never allowed.")
    if os.path.lexists(output) and not overwrite:
        raise FileExistsError("Output already exists; choose another directory or explicitly use --overwrite.")
    if output.is_dir():
        raise IsADirectoryError(str(output))


def publish(candidate: Path, output: Path, sources: list[Path], overwrite: bool) -> None:
    guard_output(output, sources, overwrite)
    if overwrite:
        os.replace(candidate, output)
    elif os.name == "nt":
        os.rename(candidate, output)  # Windows refuses an existing destination.
    else:
        os.link(candidate, output)  # POSIX rename would silently replace it.


def output_path(source: Path, output_dir: Path, fmt: str, relative_to: Path | None = None) -> Path:
    parent = source.relative_to(relative_to).parent if relative_to is not None else Path()
    return output_dir / parent / (source.stem + (FORMATS[fmt] or source.suffix.lower()))


def plan_outputs(sources: list[Path], output_dir: Path, fmt: str, relative_to: Path | None) -> list[Path]:
    outputs = [output_path(source, output_dir, fmt, relative_to) for source in sources]
    key = lambda path: str(path.resolve()).casefold()
    counts = Counter(key(path) for path in outputs)
    outputs = [path.with_name(source.name + path.suffix) if counts[key(path)] > 1 else path
               for source, path in zip(sources, outputs)]
    if len({key(path) for path in outputs}) != len(outputs):
        raise ValueError("Ambiguous batch filenames remain after conversion naming; split the batch or rename inputs.")
    for path in outputs:
        if any(same_file(path, source) for source in sources):
            raise ValueError("A planned batch output aliases a source; choose a separate output directory.")
    return outputs


def validate_options(args: argparse.Namespace) -> None:
    for name in ("min_mb", "max_mb"):
        value = getattr(args, name)
        if value is not None and (not math.isfinite(value * 1024 * 1024) or value <= 0):
            raise ValueError(f"--{name.replace('_', '-')} must be a positive finite size.")
    if args.min_mb is not None and args.max_mb is not None and args.min_mb > args.max_mb:
        raise ValueError("--min-mb cannot be greater than --max-mb")
    if args.quality is not None and not 1 <= args.quality <= 100:
        raise ValueError("--quality must be between 1 and 100.")
    if args.max_dimension is not None and args.max_dimension <= 0:
        raise ValueError("--max-dimension must be positive.")


def optimize_one(source: Path, output_dir: Path, args: argparse.Namespace, magick: str,
                 relative_to: Path | None = None, output: Path | None = None) -> dict:
    if not source.is_file():
        raise FileNotFoundError(str(source))
    validate_options(args)
    output = output or output_path(source, output_dir, args.format, relative_to)
    overwrite = getattr(args, "overwrite", False)
    guard_output(output, [source], overwrite)
    before = identify(magick, source.resolve())
    fmt = args.format
    if fmt == "same":
        fmt = "jpg" if source.suffix.lower() in {".jpg", ".jpeg"} else source.suffix.lower().lstrip(".")
        if fmt not in {"png", "jpg", "webp", "avif"}:
            raise ValueError(f"Cannot preserve unsupported source format: {source.suffix}")
    if fmt == "jpg" and not before["is_opaque"]:
        raise ValueError("JPEG output is unsafe for an image with transparency; choose WebP or PNG.")
    output.parent.mkdir(parents=True, exist_ok=True)
    upper_limit = args.max_mb * 1024 * 1024 if args.max_mb else None
    lower_limit = args.min_mb * 1024 * 1024 if args.min_mb else None
    if lower_limit and upper_limit and lower_limit > upper_limit:
        raise ValueError("--min-mb cannot be greater than --max-mb")
    qualities = [args.quality] if args.quality else ([98, 95, 92, 90, 88, 85, 82, 79, 76, 73, 70] if fmt != "png" else [None])
    attempts = []
    with tempfile.TemporaryDirectory(prefix=".image-opt-", dir=output.parent) as directory:
        candidate = Path(directory) / ("candidate" + output.suffix)
        for quality in qualities:
            subprocess.run(build_command(magick, source.resolve(), candidate, fmt, quality, args.max_dimension, args.strip), check=True)
            after = identify(magick, candidate)
            actual_format = "jpg" if after["format"] == "jpeg" else after["format"]
            if actual_format != fmt or not after["bytes"]:
                raise RuntimeError("Encoded image did not match the requested format or was empty.")
            if not args.max_dimension and (after["width"], after["height"]) != (before["width"], before["height"]):
                raise RuntimeError("Encoded image changed dimensions without permission.")
            if args.max_dimension and max(after["width"], after["height"]) > args.max_dimension:
                raise RuntimeError("Encoded image exceeded the requested dimensions.")
            if not before["is_opaque"] and after["is_opaque"]:
                raise RuntimeError("Encoded image lost transparency.")
            attempts.append({"quality": quality, "bytes": after["bytes"]})
            in_range = (lower_limit is None or after["bytes"] >= lower_limit) and (upper_limit is None or after["bytes"] <= upper_limit)
            if not in_range:
                continue
            publish(candidate, output, [source], overwrite)
            return {
                "status": "ok", "source": str(source), "output": str(output), "mode": args.mode,
                "format": fmt, "quality": quality, "source_bytes": before["bytes"],
                "output_bytes": after["bytes"], "saved_bytes": before["bytes"] - after["bytes"],
                "source_dimensions": [before["width"], before["height"]],
                "output_dimensions": [after["width"], after["height"]], "has_alpha": before["has_alpha"], "is_opaque": before["is_opaque"],
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
    parser.add_argument("--overwrite", action="store_true", help="Atomically replace an existing non-source output after successful verification")
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
        validate_options(args)
        if args.command == "batch" and same_file(args.output_dir, args.input_dir):
            raise ValueError("Batch output directory must differ from the input directory.")
        exclude_output_subtree = args.command == "batch" and args.output_dir.resolve().is_relative_to(args.input_dir.resolve())
        sources = [args.input] if args.command == "optimize" else sorted(
            p for p in (args.input_dir.rglob("*") if args.recursive else args.input_dir.iterdir())
            if p.is_file() and p.suffix.lower() in SUPPORTED_INPUTS
            and (not exclude_output_subtree or not p.resolve().is_relative_to(args.output_dir.resolve()))
        )
        if not sources:
            raise RuntimeError("No supported image files found.")
        relative_to = args.input_dir if args.command == "batch" and args.recursive else None
        outputs = plan_outputs(sources, args.output_dir, args.format, relative_to)
        manifest = args.output_dir / "manifest.json"
        guard_output(manifest, sources, args.overwrite)
        results = []
        for source, output in zip(sources, outputs):
            try:
                results.append(optimize_one(source, args.output_dir, args, magick, relative_to, output))
            except Exception as exc:  # report per-file failures for batch jobs
                results.append({"status": "error", "source": str(source), "error": str(exc)})
        args.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix=".image-opt-", dir=args.output_dir) as directory:
                candidate = Path(directory) / "manifest.json"
                candidate.write_text(json.dumps({"tool": "image-compression", "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
                publish(candidate, manifest, sources, args.overwrite)
        except Exception as exc:
            message = (f"{type(exc).__name__}: {exc}. A previous manifest may describe an earlier run; "
                       "do not use it as the success record for this run. Already published images were not rolled back.")
            print(json.dumps({"status": "partial", "manifest": None, "manifest_error": message, "results": results}, ensure_ascii=False, indent=2))
            print(f"error: manifest publication failed: {message}", file=sys.stderr)
            return 1
        print(json.dumps({"manifest": str(manifest), "results": results}, ensure_ascii=False, indent=2))
        return 0 if all(item["status"] == "ok" for item in results) else 2
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

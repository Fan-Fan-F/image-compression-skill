# Image Compression Skill

Version 1.0.0. MIT-licensed OpenClaw/Codex Agent Skill for reducing image file size with ImageMagick.

This project compresses the image file itself. It does not turn processed images into ZIP archives. ZIP is only a convenient way to distribute this repository.

## Features

- Preserve PNG, JPEG, WebP, or AVIF with `--format same`.
- Explicitly convert to `webp`, `jpg`, `png`, or `avif` when requested.
- Set an upper limit with `--max-mb` or a user-selected range with `--min-mb` and `--max-mb`.
- Preserve dimensions by default; optional aspect-preserving `--max-dimension` resizing.
- Inspect alpha, dimensions, colorspace, format, and exact bytes.
- Single-file, batch, AI-upload, and AI-video preparation modes.
- JSON manifest with output verification and per-file failure reports.
- Local-only operation: no uploads, API keys, source deletion, or default overwrites.

## Requirements

- Python 3.10 or newer.
- ImageMagick 7 or newer, with the `magick` executable available on PATH.
- AVIF requires an ImageMagick build with AVIF delegate support.

Python uses only the standard library; Pillow is not required.

## Installation

### Windows

```powershell
winget install --id ImageMagick.ImageMagick --exact --source winget --accept-source-agreements --accept-package-agreements
magick -version
python --version
```

### macOS

```bash
brew install imagemagick
magick -version
python3 --version
```

### Debian or Ubuntu

```bash
sudo apt update
sudo apt install imagemagick python3
magick -version
python3 --version
```

### Import as an Agent Skill

Copy the `image-compression/` directory into the target Agent's skills directory. The Agent should load `image-compression/SKILL.md` when asked to compress, convert, batch-optimize, inspect, or prepare images for AI upload or video input. The root README and release files are for repository users; `SKILL.md` is the Agent-facing contract.

## Usage

Inspect without creating an output:

```bash
python image-compression/scripts/image_optimizer.py inspect input.png
```

Preserve the source format and keep output between 4 and 5 MiB when possible:

```bash
python image-compression/scripts/image_optimizer.py optimize input.png --format same --min-mb 4 --max-mb 5 --output-dir optimized
```

Convert to WebP and keep it below 5 MiB:

```bash
python image-compression/scripts/image_optimizer.py optimize input.png --format webp --max-mb 5 --output-dir optimized
```

Prepare an AI-video delivery copy:

```bash
python image-compression/scripts/image_optimizer.py optimize input.png --mode ai-video --format webp --max-dimension 2048 --max-mb 10 --output-dir video-input
```

Batch process a directory recursively:

```bash
python image-compression/scripts/image_optimizer.py batch ./inputs --recursive --format same --max-mb 10 --output-dir optimized
```

If ImageMagick is not on PATH, pass its full path with `--magick`.

## Format and quality policy

`same` preserves the source image format. PNG remains PNG, JPEG remains JPEG, and WebP remains WebP. PNG is lossless and does not use JPEG/WebP-style visual quality; its size reduction may be limited. If a PNG target cannot be reached, the tool reports the limitation instead of silently converting, padding, or deleting data. WebP, JPEG, and AVIF can use quality search and are visually lossy unless a lossless mode is explicitly implemented.

JPEG is rejected for images with transparency. Metadata is preserved by default; use `--strip` only when removing EXIF, ICC profiles, comments, and thumbnails is acceptable.

## AI workflows

Keep a master PNG outside the delivery directory. For opaque AI artwork, WebP is often a good delivery choice when the destination accepts it. For video input, use an approved maximum dimension; aspect ratio is preserved and no silent crop or stretch is performed. Vendor limits are not hardcoded and must be checked separately when a platform is named.

## Safety

The tool is local-only. It does not upload files, read API keys, delete source files, or overwrite sources by default. Outputs are written to a separate directory. Review the generated `manifest.json` before any external upload.

## Development and verification

From the repository root:

```bash
python -m unittest discover -s image-compression/tests -v
python image-compression/scripts/image_optimizer.py --help
python -m py_compile image-compression/scripts/image_optimizer.py image-compression/tests/test_optimizer.py
```

## License

MIT. See `LICENSE`.

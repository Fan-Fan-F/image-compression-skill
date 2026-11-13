# Image Compression Skill

Version 1.0.5. MIT-licensed OpenClaw/Codex Agent Skill for reducing image file size with ImageMagick.

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

The repository contains the Agent instructions and Python helper, but it does not bundle Python or ImageMagick. ImageMagick is a separate native application and must be installed on the user's machine. The Agent should check both dependencies before processing the first image and report the exact missing dependency instead of presenting a generic script error.

## Installation

### Windows

```powershell
winget install --id Python.Python.3.13 --exact --source winget --accept-source-agreements --accept-package-agreements
winget install --id ImageMagick.ImageMagick --exact --source winget --accept-source-agreements --accept-package-agreements
python --version
magick -version
```

### macOS

```bash
brew install python
brew install imagemagick
python3 --version
magick -version
```

### Debian or Ubuntu

```bash
sudo apt update
sudo apt install imagemagick python3
python3 --version
magick -version
```

### Import as an Agent Skill

Copy the `image-compression/` directory into the target Agent's skills directory. The Agent should load `image-compression/SKILL.md` when asked to compress, convert, batch-optimize, inspect, or prepare images for AI upload or video input. The root README and release files are for repository users; `SKILL.md` is the Agent-facing contract.

### Dependency preflight

Before first use, check:

```text
Python 3.10+ available
ImageMagick 7+ available as `magick`
```

If a dependency is missing, stop before touching user images. On Windows, offer the official `winget` installation; on macOS, Homebrew; on Debian/Ubuntu, apt. Installing software can require user approval, administrator privileges, a network connection, and a new terminal after PATH changes. The Agent must not claim the Skill is ready until `python --version` and `magick -version` both succeed.

If ImageMagick is installed but not on PATH, allow the user to provide its full executable path with `--magick`. Do not download random binaries or third-party installers.

## Usage: natural language first

When this repository is installed as an Agent Skill, users should not need to type Python commands. Describe the task naturally and let the Agent inspect the file, choose or confirm the format, run ImageMagick, validate the byte range, and report the output path.

Examples:

- "把桌面上的 123.png 压缩到 5MB 以内，保持 PNG 格式，不要删除原图。"
- "把这张图片压缩到 4 到 5MB 之间，如果 PNG 做不到就先告诉我，不要擅自转格式。"
- "把这张图转成高质量 WebP，控制在 5MB 以内，原图保留。"
- "把这个文件夹里的图片批量优化成适合 AI 视频上传的文件，保持比例，不要裁切。"

The Agent should ask only for a missing decision that materially affects the result, such as whether format conversion or resizing is allowed. It should execute the local helper automatically, preserve sources, and report format, dimensions, bytes, quality, manifest, and verification status.

The commands below are optional fallbacks for developers, automation scripts, or users running the repository without an Agent.

## CLI usage (optional)

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

Recursive batch output preserves each source file's relative directory. When a format conversion would make same-directory inputs such as `foo.png` and `foo.jpg` share one target, only that collision group uses `foo.png.webp` and `foo.jpg.webp`; unrelated `bar.png` still becomes `bar.webp`. A final global planning check rejects any remaining ambiguous names, including a third input such as `foo.png.jpg` whose normal target would overlap a collision name. No files are encoded in that case; split the batch or rename the conflicting inputs.

The output subtree is excluded when it is inside the recursive input directory. Batch output cannot equal the input directory, and no planned output may alias any source file, including through symlinks or hard links.

Existing output images and `manifest.json` are preserved by default. Use a new output directory for each run. When replacement of previous delivery files is explicitly intended, add `--overwrite`; this only permits replacing non-source outputs after a complete candidate passes verification. Source replacement remains prohibited with that flag. Images and the manifest are published atomically from temporary siblings. A failed file leaves no candidate images and does not replace an existing output; batches still report individual failures and can retain successfully completed files.

If ImageMagick is not on PATH, pass its full path with `--magick`.

If `python` or `magick` is not recognized immediately after installation, close and reopen the terminal so PATH changes are loaded. On Windows, if ImageMagick is installed but still unavailable as `magick`, use its full executable path, for example `C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe`, with `--magick`. The Agent should verify the explicit path before processing.

## Format and quality policy

`same` preserves the source image format. PNG remains PNG, JPEG remains JPEG, and WebP remains WebP. PNG is lossless and does not use JPEG/WebP-style visual quality; its size reduction may be limited. If a PNG target cannot be reached, the tool reports the limitation instead of silently converting, padding, or deleting data. WebP, JPEG, and AVIF can use quality search and are visually lossy unless a lossless mode is explicitly implemented.

JPEG is rejected for images with actual transparent pixels. ImageMagick's explicit alpha trait supplies `has_alpha`; its separate opacity property supplies `is_opaque` and determines JPEG safety. Opaque grayscale, RGB and fully opaque RGBA inputs can be converted to JPEG. Unknown opacity results fail safely. Multi-frame inputs are rejected before encoding, rather than discarding frames or producing untracked numbered files. Metadata is preserved by default; use `--strip` only when removing EXIF, ICC profiles, comments, and thumbnails is acceptable.

## AI workflows

Keep a master PNG outside the delivery directory. For opaque AI artwork, WebP is often a good delivery choice when the destination accepts it. For video input, use an approved maximum dimension; aspect ratio is preserved and no silent crop or stretch is performed. Vendor limits are not hardcoded and must be checked separately when a platform is named.

## Safety

The tool is local-only. It does not upload files, read API keys, delete or replace source files. Outputs are written to a separate directory. Candidates are written and inspected inside temporary directories on the output filesystem, then published atomically after size, format, dimensions and transparency checks. Temporary candidates are cleaned on failure. Default publication refuses an existing destination, including one created during encoding; explicit `--overwrite` uses atomic replacement for non-source outputs. Windows uses non-overwriting rename; POSIX uses a hard link for default publication and fails safely if the filesystem cannot support it. Review the generated `manifest.json` before any external upload.

Size bounds must be positive and finite; quality is 1–100 and maximum dimension must be positive. An impossible byte range reports failure without publishing a new delivery image. The unchanged manifest fields remain available, with `is_opaque` added alongside `has_alpha`. Publication is per file, not an all-or-nothing transaction across a whole batch.

If manifest generation or publication fails after images have been published, the CLI exits with status 1 and still prints structured JSON with `status: "partial"`, `manifest: null`, `manifest_error`, and the actual per-file `results`. Successful image records describe the verified files already on disk; these files are not rolled back. With explicit `--overwrite`, an older manifest may remain and describe earlier output dimensions or sizes: do not use that old manifest as this run's success record. Resolve the report write/lock error and use the structured partial results to determine what completed before retrying.

## Development and verification

From the repository root:

```bash
python image-compression/tests/test_optimizer.py
python image-compression/scripts/image_optimizer.py --help
python -m py_compile image-compression/scripts/image_optimizer.py image-compression/tests/test_optimizer.py
```

The tests create only synthetic images in temporary directories and exercise the actual existing ImageMagick executable. No user images, network requests or new dependencies are used. Set `IMAGEMAGICK_BINARY` to an explicit executable path when it is not on PATH. In CI, set `REQUIRE_IMAGEMAGICK=1` so a missing encoder fails the run; without that requirement, unavailable native integration tests are explicitly skipped. Native encoder versions and platform results must be reported separately from Python-only checks.

The cloud workflow tests Windows/Linux with Python 3.10/3.13. It fetches portable ImageMagick 7.1.2-35 from the official GitHub release and checks pinned SHA-256 digests inside disposable runners; it does not install or update the user's local encoder. Native integration tests are required there rather than silently skipped.

## License

MIT. See `LICENSE`.

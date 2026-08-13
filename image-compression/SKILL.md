---
name: "image-compression"
description: "Optimize large images for delivery and AI media workflows with ImageMagick, target-size search, batch processing, resizing, and verification."
---

# Image compression and AI media optimization

Use this skill when a user needs to reduce image size, prepare generated images for an AI image/video service, batch-optimize assets, preserve visual quality, or satisfy a hard byte limit.

## Natural-language operation

This is an Agent Skill, so the normal user interface is natural language, not a terminal. When the user asks to compress, optimize, convert, or prepare an image, resolve the referenced local file, inspect it, choose the appropriate command, execute the helper, and report the verified result. Do not ask the user to type the Python command unless they specifically request command-line instructions or are using the repository without an Agent.

Examples of requests this skill should handle directly:

- "把桌面上的 123.png 压缩到 5MB 以内，保持 PNG，不要删除原图。"
- "把这张图压缩到 4 到 5MB，如果 PNG 无法达到就告诉我。"
- "转成高质量 WebP，控制在 5MB 以下。"
- "批量优化这个文件夹，准备给 AI 视频使用，保持比例，不要裁切。"

Before execution, ask only about a materially missing choice: format conversion, resizing, or source replacement. Do not expose implementation details as a prerequisite for ordinary use.

## Scope and modes

Choose one mode explicitly:

- `compress`: preserve pixel dimensions and find the highest quality that fits the size limit.
- `ai-upload`: optimize a still image for upload; preserve dimensions unless the user gives a maximum dimension or platform requirement.
- `ai-video`: prepare a still for video input; choose a safe output format, optionally resize to a maximum dimension, and preserve or normalize aspect ratio only when requested.
- `inspect`: report format, dimensions, alpha, color space, metadata, bytes, and available ImageMagick delegates without writing output.

Do not invent vendor-specific limits. If a platform is named, check its current documentation when live research is available; otherwise state that the profile is generic.

## Safety defaults

- Inspect every input before encoding. Resolve exact paths, including repeated spaces and parentheses.
- Never overwrite source files by default. Use a dedicated output directory and preserve base names.
- If replacement is explicitly requested, move originals to a recoverable backup before replacing. Permanently delete only after a separate explicit confirmation.
- Never upload files or expose API keys. This skill is local-only.
- Treat `--max-mb` as a hard upper bound in bytes; leave headroom by default.
- Preserve pixel dimensions unless resizing is explicitly requested or the selected AI-video profile requires it. Report every dimension change.
- Never claim lossless quality for lossy WebP, JPEG, or AVIF. Use `visually low loss`; use lossless encodings only when exact pixels matter.
- Keep color profiles when color-managed delivery matters. Use `-strip` only after warning that metadata and profiles can be removed.

## Tool and dependency policy

- ImageMagick 7+ is the primary encoder and inspector.
- Python 3.10+ runs the portable helper and uses only the standard library.
- Prefer official package managers: Windows `winget`, macOS Homebrew, Debian/Ubuntu apt.
- Verify `magick -version` and fail clearly when ImageMagick is unavailable.
- AVIF is optional: detect delegate support before using it; default to WebP when compatibility is uncertain.

## Workflow

1. **Inspect**: file existence, regular-file check, bytes, format, width/height, channels, alpha, colorspace, profiles, and format support.
2. **Select format**:
   - alpha/transparency or exact pixels: PNG lossless or WebP lossless; warn if the size limit is impossible without resizing or palette reduction;
   - opaque rendered artwork or photos: WebP lossy by default;
   - older broad compatibility: JPEG for opaque images;
   - AVIF only when explicitly requested or a verified workflow supports it.
3. **Select dimensions**: keep source dimensions by default. For `ai-video`, use a user-approved `--max-dimension`; never silently crop or change aspect ratio. A resize preserves aspect ratio and uses a high-quality Lanczos filter.
4. **Encode**: start at high quality (WebP 92, JPEG 92), strip metadata only when accepted, and use WebP method 6.
5. **Search**: use `--format same` when the output must remain PNG/JPEG/WebP, or select WebP/JPEG/AVIF explicitly. If a hard target is supplied, test quality values from high to low and select the highest result inside the requested `--min-mb` and `--max-mb` range. For lossless PNG, the range may be impossible without resizing or color reduction; report that instead of adding artificial padding or silently changing pixels.
6. **Batch**: process all matching images, continue after individual failures, and record success/failure for each file.
7. **Verify**: check exact output bytes, dimensions, format, alpha, and readable identify output. Generate a JSON manifest with source/output, bytes, savings, quality, dimensions, mode, and metadata policy.
8. **Report**: list found/missing/failed files and exact output paths. Never claim completion before verification.

## Format guidance

- PNG: lossless; best for transparency, text, diagrams, and flat UI art. `-strip` can remove profiles; PNG `quality` is not a visual-quality knob.
- WebP: default modern delivery format. Use quality 85–95 for visually low loss; lossless WebP when exact pixels matter.
- JPEG: opaque images only; quality 88–94, 4:4:4 sampling for fine color detail. Avoid repeated generation loss.
- AVIF: often smaller, but optional and compatibility-dependent.

## Reusable commands

```bash
python scripts/image_optimizer.py inspect input.png
python scripts/image_optimizer.py optimize input.png --mode compress --format same --min-mb 4 --max-mb 5
python scripts/image_optimizer.py optimize input.png --mode ai-video --format webp --max-dimension 2048 --max-mb 10
python scripts/image_optimizer.py batch ./inputs --output-dir ./optimized --mode ai-upload --max-mb 10
```

On Windows, if `magick` is not on PATH, add `--magick "C:\\Program Files\\ImageMagick-7.1.2-Q16-HDRI\\magick.exe"`.

## Quality strategy

- A quality number is not a size guarantee. File complexity, dimensions, alpha, and encoder build affect bytes.
- For a 5 MB limit, aim for 4.7–4.9 MB; for 10 MB, aim for 9.3–9.8 MB.
- Prefer the highest tested quality that passes. If quality would become visibly poor, ask before resizing.
- For AI video, dimension reduction often improves upload reliability more than aggressive quality loss; make it explicit and report it.
- For important artwork, inspect representative 100% crops for gradients, thin lines, text, faces, clouds, reflections, and transparency edges.

## Agent import guidance

A compatible Agent should load this file when a user asks for image compression, image upload preparation, AI video preprocessing, WebP conversion, or batch image optimization. It should execute the local helper when available, preserve sources, use exact byte verification, and report the manifest. See the repository README for installation, examples, and troubleshooting.

## Completion contract

Report source files found and missing, output paths, format, mode, quality, metadata policy, dimensions before/after, input/output bytes, savings, verification status, and backup/delete status. Mark unresolved issues as blocked instead of claiming success.

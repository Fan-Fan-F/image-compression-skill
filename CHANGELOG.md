# Changelog

## 1.0.5 - 2026-11-13

- Refuse source/output aliases, including hard links and resolved paths; `--overwrite` never authorizes source replacement.
- Encode and inspect candidates in temporary sibling directories, then publish atomically. Preserve existing delivery files and manifests by default; explicit overwrite replaces only fully verified non-source outputs. Failed candidates are cleaned without changing prior outputs.
- Pre-plan batch filenames, preserve recursive directories, and disambiguate only conversion collision groups using their original filename extensions. Reject remaining global filename ambiguities and any output that aliases another input before encoding. Exclude an output subtree from recursive inputs and reject batch output equal to input.
- Use explicit ImageMagick alpha and opacity properties, allowing opaque grayscale/RGBA JPEG conversion while retaining the transparent-image safeguard. Reject multi-frame inputs without silently dropping frames.
- Validate numeric bounds before writing output. Add real synthetic-image regressions for file protection, failed size targets, collisions, recursive paths, opacity and multi-frame input; support required native execution in CI without downloading dependencies during tests.
- Return structured partial results and exit status 1 if final manifest generation/publication fails. Verified image outputs remain published; warn that an older manifest may describe the previous run rather than claim an all-or-nothing batch rollback.

## 1.0.2 - 2026-08-13

- Fixed recursive batch output collisions by preserving relative directories.

## 1.0.4 - 2026-08-13

- Added official Python installation commands for Windows, macOS, and Debian/Ubuntu.
- Clarified PATH refresh and explicit ImageMagick path handling.

## 1.0.3 - 2026-08-13

- Added explicit dependency preflight for Python and ImageMagick.
- Documented that the repository does not bundle native software.
- Added installation approval, PATH, privilege, and official-source guidance.

## 1.0.1 - 2026-08-13

- Clarified natural-language-first Agent operation.
- Marked CLI commands as optional fallbacks for developers and standalone use.
- Made the documented standalone test command work without package markers.

## 1.0.0 - 2026-08-13

- Initial GitHub-ready release.
- Added `inspect`, `optimize`, and `batch` CLI commands.
- Added format preservation with `--format same`.
- Added explicit PNG, JPEG, WebP, and optional AVIF output.
- Added `--min-mb` and `--max-mb` target-size controls.
- Added AI-upload and AI-video workflow guidance.
- Added JSON manifests, validation, tests, MIT license, and security-oriented defaults.

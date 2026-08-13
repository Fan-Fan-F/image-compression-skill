# Format selection

## Decision order

1. Is transparency or exact pixel identity required?
2. Does the destination support WebP or AVIF?
3. Is there a hard byte limit?
4. Is the image being delivered as a still or used as video input?

## PNG
Lossless. Use for alpha, UI screenshots, diagrams, text, and flat-color artwork. For photographic or rendered artwork, PNG often wastes space. PNG `quality` does not behave like JPEG/WebP visual quality.

## WebP
Default for modern opaque delivery and AI uploads when accepted. Lossy quality 85–95 is usually visually low loss. Lossless WebP preserves pixels but can remain large.

## JPEG
Opaque images only. Quality 88–94 with 4:4:4 sampling is a compatibility-first choice. Do not repeatedly re-encode already-lossy JPEGs.

## AVIF
Can be smaller at similar quality, but use only after checking ImageMagick delegate support and destination compatibility.

## Metadata
Metadata may include EXIF, thumbnails, comments, ICC profiles, and orientation. `-strip` removes it and can alter color-managed workflows. Preserve metadata by default in important color-managed assets; strip only when the user accepts it.

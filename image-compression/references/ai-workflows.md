# AI image and video workflows

## Generic still upload

- Inspect alpha and dimensions.
- Prefer WebP quality 90–94 for opaque artwork if the service supports it.
- Preserve dimensions unless the service publishes a maximum.
- Keep a PNG master outside the delivery folder.

## Generic video input

- Confirm the service's current input format, dimension, aspect-ratio, and size limits before applying a vendor profile.
- If no profile is known, use WebP or JPEG only when the service supports it; otherwise use PNG/JPEG conservatively.
- Use `--max-dimension` only with user approval. The helper preserves aspect ratio and never crops silently.
- For 16:9 and 9:16, normalize only when the user explicitly requests it; padding/cropping changes composition and must be reported.

## Oversized generated art

A 4096–10032 px square PNG may be ideal as a master but excessive for video upload. Keep the master, create a delivery copy, and compare a 100% crop before replacing anything. A small dimension reduction can preserve perceived quality better than forcing a very low quality value.

## Platform limits

Do not hardcode claims for Kling, Runway, Wan, Seedance, or other services without current documentation. Use a generic profile and ask for the named platform's limit when it matters.

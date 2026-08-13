# Target-size strategy

A quality number is not a file-size guarantee.

1. Inspect source bytes, dimensions, alpha, and format.
2. Encode at quality 92.
3. Measure exact bytes.
4. Test descending quality values and choose the highest passing value.
5. Leave headroom: target 4.7–4.9 MB for a 5 MB cap and 9.3–9.8 MB for a 10 MB cap.
6. If the minimum acceptable quality cannot pass, stop and report that resizing is required.
7. Resize only when approved, preserve aspect ratio, then repeat quality search.
8. Verify final format, bytes, dimensions, alpha, and manifest entries.

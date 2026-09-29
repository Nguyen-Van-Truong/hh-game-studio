"""Pixel contract for the four-cell diagnostic atlas, not an art-quality score."""
from __future__ import annotations

import math


def inspect_pixels(width, height, rgba):
    """Blender pixels use a bottom-left origin; atlas frame IDs start top-left."""
    if (type(width) is not int or type(height) is not int or (width, height) != (128, 128)
            or len(rgba) != width * height * 4):
        return {"passed": False, "failures": ["dimensions"]}
    failures = []

    def pixel(x, y):
        values = rgba[(y * width + x) * 4:(y * width + x) * 4 + 4]
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            failures.append(f"invalid_pixel:{x}:{y}")
            return (0, 0, 0, 0)
        return values

    # Sample every inner pixel, including the area the unrelated GLB quad
    # previously covered. Leave the rasterized outer edges out of this oracle.
    counts = []
    for frame, (x0, y0) in enumerate(((0, 64), (64, 64), (0, 0), (64, 0))):
        count = 0
        for y in range(y0 + 8, y0 + 56):
            for x in range(x0 + 8, x0 + 56):
                r, g, b, a = pixel(x, y)
                color = (r > 1.7 * max(g, b) if frame == 0 else
                         g > 1.7 * max(r, b) if frame == 1 else
                         b > 1.7 * max(r, g) if frame == 2 else
                         min(r, g) > 1.7 * b and abs(r - g) < 0.3)
                if a >= 0.99 and color:
                    count += 1
        counts.append(count)
        if count != 48 * 48:
            failures.append(f"cell:{frame}")
    gap_pixels = {(x, y) for x in (0, 63, 64, 127) for y in range(128)}
    gap_pixels |= {(x, y) for y in (0, 63, 64, 127) for x in range(128)}
    opaque_gaps = sum(pixel(x, y)[3] > 0.01 for x, y in gap_pixels)
    if opaque_gaps:
        failures.append("cell_gutters")
    return {"passed": not failures, "failures": failures,
            "cell_inner_pixels": counts, "opaque_gutter_pixels": opaque_gaps,
            "gutter_pixels_checked": len(gap_pixels)}

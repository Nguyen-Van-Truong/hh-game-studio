"""Compare 8-bit PNGs, detect a blank frame, and check individual pixels.

A pixel counts as changed when the maximum absolute per-channel difference
(RGBA, after expanding gray and palette) is greater than ``pixel_tolerance``.
``changed_ratio`` is changed pixels / total pixels. PASS when the images are the
same size and ``changed_ratio <= threshold``. Different sizes are FAIL and do
not write a diff. A frame is blank when the luminance standard deviation is
below 2.0 or at least 99.5% of pixels share one RGB color.
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from typing import Any

from . import common as C
from . import pngio

BLANK_STDDEV = 2.0
BLANK_DOMINANT = 0.995
_MAX_BYTES = 64 * 1024 * 1024


def validate_thresholds(threshold: float, pixel_tolerance: int) -> tuple[float, int]:
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(float(threshold)):
        raise C.GamekitError("BAD_REQUEST", "threshold must be a finite number")
    if not 0.0 <= float(threshold) <= 1.0:
        raise C.GamekitError("BAD_REQUEST", "threshold must be between 0 and 1")
    if isinstance(pixel_tolerance, bool) or not isinstance(pixel_tolerance, int) or not 0 <= pixel_tolerance <= 255:
        raise C.GamekitError("BAD_REQUEST", "pixel tolerance must be an integer 0..255")
    return float(threshold), pixel_tolerance


def parse_expect_color(spec: str) -> tuple[int, int, tuple[int, int, int], int]:
    """``x,y,#rrggbb,tol`` — max channel abs diff of RGB at that pixel must be <= tol."""
    parts = spec.split(",")
    if len(parts) != 4:
        raise C.GamekitError("BAD_REQUEST", f"expect-color must be x,y,#rrggbb,tol: {spec!r}")
    try:
        x = int(parts[0].strip())
        y = int(parts[1].strip())
        tol = int(parts[3].strip())
    except ValueError as exc:
        raise C.GamekitError("BAD_REQUEST", f"expect-color has a non-integer: {spec!r}") from exc
    text = parts[2].strip()
    if len(text) != 7 or not text.startswith("#"):
        raise C.GamekitError("BAD_REQUEST", f"color must be #rrggbb: {text!r}")
    try:
        rgb = (int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16))
    except ValueError as exc:
        raise C.GamekitError("BAD_REQUEST", f"color must be #rrggbb: {text!r}") from exc
    if x < 0 or y < 0 or not 0 <= tol <= 255:
        raise C.GamekitError("BAD_REQUEST", f"expect-color out of range: {spec!r}")
    return x, y, rgb, tol


def _load(path: str | Path) -> pngio.Image:
    file = Path(path)
    if not file.is_file():
        raise C.GamekitError("NOT_FOUND", f"png not found: {file}")
    size = file.stat().st_size
    if size > _MAX_BYTES:
        raise C.GamekitError("BAD_REQUEST", f"png is too large ({size} bytes): {file}")
    try:
        return pngio.read(file)
    except pngio.PngError as exc:
        raise C.GamekitError("BAD_REQUEST", str(exc)) from exc


def _rgba(image: pngio.Image) -> bytes:
    try:
        return image.to_rgba()
    except pngio.PngError as exc:
        raise C.GamekitError("BAD_REQUEST", str(exc)) from exc


def blank(image: pngio.Image) -> dict[str, Any]:
    """Blank when luminance std-dev < 2 or >= 99.5% of pixels share one RGB color."""
    rgba = _rgba(image)
    n = image.width * image.height
    counts: dict[tuple[int, int, int], int] = {}
    sum_y = 0.0
    sum_y2 = 0.0
    for i in range(n):
        o = i * 4
        r, g, b = rgba[o], rgba[o + 1], rgba[o + 2]
        y = 0.299 * r + 0.587 * g + 0.114 * b
        sum_y += y
        sum_y2 += y * y
        key = (r, g, b)
        counts[key] = counts.get(key, 0) + 1
    mean = sum_y / n
    var = sum_y2 / n - mean * mean
    if var < 0.0:
        var = 0.0
    std = math.sqrt(var)
    dominant = max(counts.values()) / n
    return {
        "blank": std < BLANK_STDDEV or dominant >= BLANK_DOMINANT,
        "luminance_stddev": round(std, 6),
        "dominant_ratio": round(dominant, 6),
        "width": image.width,
        "height": image.height,
    }


def check_colors(image: pngio.Image, specs: list[str]) -> list[dict[str, Any]]:
    rgba = _rgba(image)
    rows = []
    for spec in specs:
        x, y, rgb, tol = parse_expect_color(spec)
        if x >= image.width or y >= image.height:
            rows.append({"spec": spec, "ok": False, "detail": "pixel out of range"})
            continue
        o = (y * image.width + x) * 4
        got = (rgba[o], rgba[o + 1], rgba[o + 2])
        diff = max(abs(got[i] - rgb[i]) for i in range(3))
        rows.append({
            "spec": spec,
            "ok": diff <= tol,
            "got": "#{:02x}{:02x}{:02x}".format(*got),
            "diff": diff,
            "tolerance": tol,
        })
    return rows


def diff_image(a: pngio.Image, b: pngio.Image) -> pngio.Image:
    """RGB image of absolute RGB channel differences. Sizes must already match."""
    left, right = _rgba(a), _rgba(b)
    n = a.width * a.height
    out = bytearray(n * 3)
    for i in range(n):
        o = i * 4
        d = i * 3
        out[d] = abs(left[o] - right[o])
        out[d + 1] = abs(left[o + 1] - right[o + 1])
        out[d + 2] = abs(left[o + 2] - right[o + 2])
    return pngio.Image(a.width, a.height, "RGB", bytes(out))


def compare(
    a: pngio.Image,
    b: pngio.Image,
    *,
    threshold: float = 0.01,
    pixel_tolerance: int = 8,
) -> dict[str, Any]:
    threshold, pixel_tolerance = validate_thresholds(threshold, pixel_tolerance)
    if a.width != b.width or a.height != b.height:
        return {
            "ok": False,
            "status": "FAIL",
            "reason": "size_mismatch",
            "size_a": [a.width, a.height],
            "size_b": [b.width, b.height],
            "changed_ratio": None,
            "mean_abs_diff": None,
            "max_diff": None,
            "bbox": None,
            "changed": None,
            "total": None,
            "threshold": threshold,
            "pixel_tolerance": pixel_tolerance,
        }
    left, right = _rgba(a), _rgba(b)
    total = a.width * a.height
    changed = 0
    sum_abs = 0
    max_diff = 0
    min_x = min_y = 10**9
    max_x = max_y = -1
    for i in range(total):
        o = i * 4
        pixel_max = 0
        for channel in range(4):
            delta = abs(left[o + channel] - right[o + channel])
            sum_abs += delta
            if delta > pixel_max:
                pixel_max = delta
        if pixel_max > max_diff:
            max_diff = pixel_max
        if pixel_max > pixel_tolerance:
            changed += 1
            x = i % a.width
            y = i // a.width
            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y
            if x > max_x:
                max_x = x
            if y > max_y:
                max_y = y
    ratio = changed / total
    passed = ratio <= threshold + 1e-12
    return {
        "ok": passed,
        "status": "PASS" if passed else "FAIL",
        "reason": None if passed else "pixels",
        "size": [a.width, a.height],
        "changed_ratio": round(ratio, 8),
        "mean_abs_diff": round(sum_abs / (total * 4), 6),
        "max_diff": max_diff,
        "bbox": None if changed == 0 else [min_x, min_y, max_x, max_y],
        "changed": changed,
        "total": total,
        "threshold": threshold,
        "pixel_tolerance": pixel_tolerance,
    }


def _refuse_project_write(path: Path) -> None:
    if path.name.lower() == "private.raw":
        raise C.GamekitError("FORBIDDEN_PATH", "refusing private.raw")
    if C.is_within(path, C.STUDIO_DIR / ".local"):
        raise C.GamekitError("FORBIDDEN_PATH", "refusing to write under studio/.local")
    reason = C.forbidden_reason(path)
    if reason:
        raise C.GamekitError("FORBIDDEN_PATH", reason)
    current = path.parent
    for _ in range(12):
        if (current / "project.godot").is_file():
            raise C.GamekitError(
                "FORBIDDEN_PATH",
                f"{path} is inside a Godot project; write the diff outside the project",
            )
        parent = current.parent
        if parent == current:
            break
        current = parent


def _write_diff(path: Path, image: pngio.Image) -> None:
    _refuse_project_write(path)
    if path.suffix.lower() != ".png":
        raise C.GamekitError("BAD_PATH", "diff output must be a .png file")
    C.atomic_write_bytes(path, pngio.encode(image))


def compare_files(
    path_a: str | Path,
    path_b: str | Path,
    *,
    threshold: float = 0.01,
    pixel_tolerance: int = 8,
    diff_out: str | Path | None = None,
    diff_when: str = "fail",
    expect_color: list[str] | None = None,
) -> dict[str, Any]:
    """Compare two PNG files. ``diff_when`` is ``fail`` (default), ``always``, or ``never``."""
    left, right = _load(path_a), _load(path_b)
    result = compare(left, right, threshold=threshold, pixel_tolerance=pixel_tolerance)
    colors = check_colors(left, list(expect_color or []))
    if colors:
        result["expect_color"] = colors
        if not all(row["ok"] for row in colors):
            result["ok"] = False
            result["status"] = "FAIL"
            if result.get("reason") is None:
                result["reason"] = "expect_color"
    want_diff = diff_out is not None and diff_when != "never" and result.get("reason") != "size_mismatch"
    if want_diff and (diff_when == "always" or not result["ok"]):
        target = Path(diff_out)
        if not target.is_absolute():
            target = Path(os.path.abspath(str(target)))
        _write_diff(target, diff_image(left, right))
        result["diff"] = str(target)
    return result


def blank_file(path: str | Path, expect_color: list[str] | None = None) -> dict[str, Any]:
    image = _load(path)
    info = blank(image)
    colors = check_colors(image, list(expect_color or []))
    color_ok = all(row["ok"] for row in colors) if colors else True
    is_blank = bool(info["blank"])
    if not color_ok:
        status = "FAIL"
    elif is_blank:
        status = "BLANK"
    else:
        status = "NOT_BLANK"
    out: dict[str, Any] = {
        "ok": is_blank and color_ok,
        "status": status,
        "blank": is_blank,
        "luminance_stddev": info["luminance_stddev"],
        "dominant_ratio": info["dominant_ratio"],
        "size": [info["width"], info["height"]],
    }
    if colors:
        out["expect_color"] = colors
    return out


def _cmd_vcheck(args: argparse.Namespace) -> dict[str, Any]:
    if args.blank:
        if args.a or args.b:
            raise C.GamekitError("BAD_REQUEST", "--blank reads one png; do not also pass two images")
        return blank_file(args.blank, args.expect_color)
    if not args.a or not args.b:
        raise C.GamekitError("BAD_REQUEST", "vcheck needs two png paths, or --blank <png>")
    return compare_files(
        args.a,
        args.b,
        threshold=args.threshold,
        pixel_tolerance=args.pixel_tolerance,
        diff_out=args.diff_out,
        diff_when="always" if args.diff_out else "never",
        expect_color=args.expect_color,
    )


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("vcheck", help="diff two PNGs, or test one PNG for a blank frame")
    parser.add_argument("a", nargs="?", help="first png")
    parser.add_argument("b", nargs="?", help="second png")
    parser.add_argument("--threshold", type=float, default=0.01, help="max changed_ratio that still PASSes")
    parser.add_argument("--pixel-tolerance", dest="pixel_tolerance", type=int, default=8,
                        help="max channel abs diff ignored when counting changed pixels")
    parser.add_argument("--diff-out", dest="diff_out", default=None, help="write an absolute-difference RGB png")
    parser.add_argument("--blank", default=None, help="report whether this png is a blank frame")
    parser.add_argument("--expect-color", dest="expect_color", action="append", default=[],
                        metavar="X,Y,#RRGGBB,TOL", help="check one pixel; repeatable")
    parser.set_defaults(func=_cmd_vcheck)

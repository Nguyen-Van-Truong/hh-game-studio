"""Pure-Python PNG read/write for 8-bit images (stdlib zlib only).

Supported: grayscale, RGB, palette, gray+alpha, RGBA, and scanline filters 0–4
(None, Sub, Up, Average, Paeth). Adam7 interlacing and any bit depth other than
8 are refused with a clear error. Ancillary chunks (gAMA, tEXt, …) are skipped;
unknown critical chunks are refused.
"""

from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_EDGE = 8192
MAX_PIXELS = 3840 * 2160
_MAX_CHUNK = 32 * 1024 * 1024

# color type, bytes per pixel
MODES: dict[str, tuple[int, int]] = {
    "L": (0, 1),
    "RGB": (2, 3),
    "P": (3, 1),
    "LA": (4, 2),
    "RGBA": (6, 4),
}
_TYPE_TO_MODE = {color: mode for mode, (color, _channels) in MODES.items()}


class PngError(ValueError):
    """A PNG could not be read or written."""


@dataclass(frozen=True)
class Image:
    """Unfiltered 8-bit pixels, row-major. ``palette`` is RGB triplets for mode P."""

    width: int
    height: int
    mode: str
    pixels: bytes
    palette: bytes | None = None
    transparency: bytes | None = None

    def __post_init__(self) -> None:
        spec = MODES.get(self.mode)
        if spec is None:
            raise PngError(f"unknown mode {self.mode!r} (use L, RGB, P, LA, RGBA)")
        channels = spec[1]
        if isinstance(self.width, bool) or isinstance(self.height, bool):
            raise PngError("width and height must be integers")
        if not isinstance(self.width, int) or not isinstance(self.height, int):
            raise PngError("width and height must be integers")
        if self.width < 1 or self.height < 1:
            raise PngError("width and height must be positive")
        if self.width > MAX_EDGE or self.height > MAX_EDGE or self.width * self.height > MAX_PIXELS:
            raise PngError(f"image exceeds {MAX_EDGE}px edge or {MAX_PIXELS} pixels")
        expect = self.width * self.height * channels
        if not isinstance(self.pixels, (bytes, bytearray)) or len(self.pixels) != expect:
            raise PngError(f"pixel buffer must be {expect} bytes for {self.mode}")
        if not isinstance(self.pixels, bytes):
            object.__setattr__(self, "pixels", bytes(self.pixels))
        if self.mode == "P":
            if not isinstance(self.palette, (bytes, bytearray)) or len(self.palette) % 3 or not 3 <= len(self.palette) <= 768:
                raise PngError("palette must be 1..256 RGB triplets")
            if not isinstance(self.palette, bytes):
                object.__setattr__(self, "palette", bytes(self.palette))
            colors = len(self.palette) // 3
            if any(index >= colors for index in self.pixels):
                raise PngError("palette index out of range")
            if self.transparency is not None and (
                not isinstance(self.transparency, (bytes, bytearray)) or not 1 <= len(self.transparency) <= colors
            ):
                raise PngError("palette tRNS must be 1..len(palette) alpha bytes")
        elif self.palette is not None:
            raise PngError("palette is only valid for mode P")
        if self.transparency is not None and not isinstance(self.transparency, (bytes, bytearray)):
            raise PngError("transparency must be bytes")
        if self.transparency is not None and not isinstance(self.transparency, bytes):
            object.__setattr__(self, "transparency", bytes(self.transparency))
        if self.mode == "L" and self.transparency is not None and len(self.transparency) != 2:
            raise PngError("grayscale tRNS must be 2 bytes")
        if self.mode == "RGB" and self.transparency is not None and len(self.transparency) != 6:
            raise PngError("RGB tRNS must be 6 bytes")
        if self.mode in ("LA", "RGBA") and self.transparency is not None:
            raise PngError(f"tRNS is not valid for mode {self.mode}")

    @property
    def channels(self) -> int:
        return MODES[self.mode][1]

    def to_rgba(self) -> bytes:
        """Expand to 8-bit RGBA. A tRNS key color (or palette alpha) becomes alpha 0..255."""
        n = self.width * self.height
        src = self.pixels
        if self.mode == "RGBA":
            return src
        out = bytearray(n * 4)
        if self.mode == "RGB":
            key = struct.unpack(">HHH", self.transparency) if self.transparency else None
            for i in range(n):
                o = i * 3
                r, g, b = src[o], src[o + 1], src[o + 2]
                out[i * 4] = r
                out[i * 4 + 1] = g
                out[i * 4 + 2] = b
                out[i * 4 + 3] = 0 if key is not None and (r, g, b) == key else 255
            return bytes(out)
        if self.mode == "L":
            key_g = struct.unpack(">H", self.transparency)[0] if self.transparency else None
            for i in range(n):
                v = src[i]
                out[i * 4] = v
                out[i * 4 + 1] = v
                out[i * 4 + 2] = v
                out[i * 4 + 3] = 0 if key_g is not None and v == key_g else 255
            return bytes(out)
        if self.mode == "LA":
            for i in range(n):
                v, a = src[i * 2], src[i * 2 + 1]
                o = i * 4
                out[o] = v
                out[o + 1] = v
                out[o + 2] = v
                out[o + 3] = a
            return bytes(out)
        colors = len(self.palette or b"") // 3
        alphas = [255] * colors
        if self.transparency:
            for i, alpha in enumerate(self.transparency):
                alphas[i] = alpha
        pal = self.palette or b""
        for i in range(n):
            idx = src[i]
            if idx >= colors:
                raise PngError(f"palette index {idx} out of range")
            o = i * 4
            p = idx * 3
            out[o] = pal[p]
            out[o + 1] = pal[p + 1]
            out[o + 2] = pal[p + 2]
            out[o + 3] = alphas[idx]
        return bytes(out)


def _chunk(tag: bytes, data: bytes) -> bytes:
    if len(tag) != 4:
        raise PngError("chunk type must be 4 bytes")
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _filters_for(filter_type: int | list[int] | tuple[int, ...], height: int) -> list[int]:
    if isinstance(filter_type, int) and not isinstance(filter_type, bool):
        if filter_type not in (0, 1, 2, 3, 4):
            raise PngError(f"filter type must be 0..4, not {filter_type}")
        return [filter_type] * height
    if isinstance(filter_type, (list, tuple)) and len(filter_type) == height:
        out: list[int] = []
        for item in filter_type:
            if isinstance(item, bool) or not isinstance(item, int) or item not in (0, 1, 2, 3, 4):
                raise PngError(f"filter type must be 0..4, not {item!r}")
            out.append(item)
        return out
    raise PngError("filter_type must be an int 0..4 or one filter per row")


def _filter_row(ftype: int, row: bytes, prev: bytes, bpp: int) -> bytes:
    if ftype == 0:
        return row
    n = len(row)
    out = bytearray(n)
    for i in range(n):
        left = row[i - bpp] if i >= bpp else 0
        up = prev[i]
        if ftype == 1:
            pred = left
        elif ftype == 2:
            pred = up
        elif ftype == 3:
            pred = (left + up) // 2
        else:
            ul = prev[i - bpp] if i >= bpp else 0
            pred = _paeth(left, up, ul)
        out[i] = (row[i] - pred) & 255
    return bytes(out)


def _unfilter_row(ftype: int, row: bytes, prev: bytes, bpp: int) -> bytearray:
    if ftype > 4:
        raise PngError(f"invalid scanline filter {ftype}")
    n = len(row)
    out = bytearray(n)
    if ftype == 0:
        out[:] = row
        return out
    for i in range(n):
        left = out[i - bpp] if i >= bpp else 0
        up = prev[i]
        if ftype == 1:
            pred = left
        elif ftype == 2:
            pred = up
        elif ftype == 3:
            pred = (left + up) // 2
        else:
            ul = prev[i - bpp] if i >= bpp else 0
            pred = _paeth(left, up, ul)
        out[i] = (row[i] + pred) & 255
    return out


def filtered_scanlines(image: Image, filter_type: int | list[int] | tuple[int, ...] = 0) -> bytes:
    """Scanlines with a filter byte in front of each row, before deflate."""
    filters = _filters_for(filter_type, image.height)
    stride = image.width * image.channels
    prev = bytes(stride)
    parts: list[bytes] = []
    px = image.pixels
    for y, ftype in enumerate(filters):
        row = px[y * stride : (y + 1) * stride]
        parts.append(bytes((ftype,)))
        parts.append(_filter_row(ftype, row, prev, image.channels))
        prev = row
    return b"".join(parts)


def encode(image: Image, filter_type: int | list[int] | tuple[int, ...] = 0) -> bytes:
    color_type = MODES[image.mode][0]
    ihdr = struct.pack(">IIBBBBB", image.width, image.height, 8, color_type, 0, 0, 0)
    raw = filtered_scanlines(image, filter_type)
    compressed = zlib.compress(raw, 9)
    parts = [SIGNATURE, _chunk(b"IHDR", ihdr)]
    if image.mode == "P":
        parts.append(_chunk(b"PLTE", image.palette or b""))
    if image.transparency:
        parts.append(_chunk(b"tRNS", image.transparency))
    parts.append(_chunk(b"IDAT", compressed))
    parts.append(_chunk(b"IEND", b""))
    return b"".join(parts)


def _inflate(data: bytes, expected: int) -> bytes:
    dec = zlib.decompressobj()
    try:
        raw = dec.decompress(data, expected)
        if not dec.eof:
            extra = dec.decompress(dec.unconsumed_tail, 1)
            if extra or not dec.eof:
                raise PngError("image data is larger than the IHDR size")
    except zlib.error as exc:
        raise PngError(f"bad deflate data: {exc}") from exc
    if len(raw) != expected:
        raise PngError(f"image data length {len(raw)} != {expected}")
    return raw


def _unfilter(raw: bytes, width: int, height: int, channels: int) -> bytes:
    stride = width * channels
    expected = height * (stride + 1)
    if len(raw) != expected:
        raise PngError(f"scanlines length {len(raw)} != {expected}")
    out = bytearray(height * stride)
    prev = bytes(stride)
    for y in range(height):
        i = y * (stride + 1)
        recon = _unfilter_row(raw[i], raw[i + 1 : i + 1 + stride], prev, channels)
        out[y * stride : (y + 1) * stride] = recon
        prev = bytes(recon)
    return bytes(out)


def decode(data: bytes) -> Image:
    if not isinstance(data, (bytes, bytearray)):
        raise PngError("png data must be bytes")
    blob = bytes(data)
    if not blob.startswith(SIGNATURE):
        raise PngError("not a PNG (bad signature)")
    pos = 8
    width = height = color_type = 0
    saw_ihdr = False
    saw_iend = False
    idat_closed = False
    palette: bytes | None = None
    trns: bytes | None = None
    idat = bytearray()
    while pos + 8 <= len(blob):
        length = struct.unpack(">I", blob[pos : pos + 4])[0]
        tag = blob[pos + 4 : pos + 8]
        if length > _MAX_CHUNK:
            raise PngError(f"chunk {tag!r} is too large")
        if pos + 12 + length > len(blob):
            raise PngError("truncated PNG chunk")
        chunk = blob[pos + 8 : pos + 8 + length]
        crc = struct.unpack(">I", blob[pos + 8 + length : pos + 12 + length])[0]
        actual = zlib.crc32(tag + chunk) & 0xFFFFFFFF
        if crc != actual:
            name = tag.decode("ascii", "replace")
            raise PngError(f"bad CRC for chunk {name}")
        pos += 12 + length
        if len(tag) != 4 or not tag.isalpha():
            raise PngError("chunk type is not 4 letters")
        if saw_iend:
            raise PngError("data after IEND")
        if tag == b"IHDR":
            if saw_ihdr or length != 13:
                raise PngError("bad IHDR")
            width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(">IIBBBBB", chunk)
            saw_ihdr = True
            if comp != 0 or filt != 0:
                raise PngError("unsupported PNG compression or filter method")
            if interlace != 0:
                raise PngError("interlaced PNG is not supported")
            if bit_depth != 8:
                raise PngError(f"only 8-bit PNG is supported (bit depth {bit_depth})")
            if color_type not in _TYPE_TO_MODE:
                raise PngError(f"unsupported color type {color_type}")
            if width < 1 or height < 1 or width > MAX_EDGE or height > MAX_EDGE or width * height > MAX_PIXELS:
                raise PngError(f"image exceeds {MAX_EDGE}px edge or {MAX_PIXELS} pixels")
            continue
        if not saw_ihdr:
            raise PngError("IHDR missing")
        if tag == b"PLTE":
            if idat or palette is not None or length % 3 or not 3 <= length <= 768:
                raise PngError("bad PLTE")
            if color_type in (0, 4):
                raise PngError("PLTE is not valid for grayscale")
            palette = chunk
            continue
        if tag == b"tRNS":
            if idat or trns is not None:
                raise PngError("bad tRNS")
            trns = chunk
            continue
        if tag == b"IDAT":
            if idat_closed:
                raise PngError("IDAT chunks are not consecutive")
            if color_type == 3 and palette is None:
                raise PngError("PLTE missing before IDAT")
            if len(idat) + length > _MAX_CHUNK:
                raise PngError("IDAT data is too large")
            idat.extend(chunk)
            continue
        if tag == b"IEND":
            if length != 0:
                raise PngError("bad IEND")
            if not idat:
                raise PngError("PNG has no IDAT")
            saw_iend = True
            break
        if tag[:1].isupper():
            raise PngError(f"unsupported critical chunk {tag.decode('ascii', 'replace')}")
        if idat:
            idat_closed = True
    if not saw_iend:
        raise PngError("truncated PNG (no IEND)")
    if pos != len(blob):
        raise PngError("data after IEND")
    mode = _TYPE_TO_MODE[color_type]
    channels = MODES[mode][1]
    if mode == "P":
        assert palette is not None
    if mode == "L" and trns is not None and len(trns) != 2:
        raise PngError("grayscale tRNS must be 2 bytes")
    if mode == "RGB" and trns is not None and len(trns) != 6:
        raise PngError("RGB tRNS must be 6 bytes")
    if mode in ("LA", "RGBA") and trns is not None:
        raise PngError(f"tRNS is not valid for mode {mode}")
    if mode == "P" and trns is not None and not 1 <= len(trns) <= len(palette or b"") // 3:
        raise PngError("palette tRNS must be 1..len(palette) alpha bytes")
    raw = _inflate(bytes(idat), height * (width * channels + 1))
    pixels = _unfilter(raw, width, height, channels)
    return Image(width, height, mode, pixels, palette if mode == "P" else None, trns)


def read(path: str | Path) -> Image:
    file = Path(path)
    if not file.is_file():
        raise PngError(f"file not found: {file}")
    return decode(file.read_bytes())


def write(path: str | Path, image: Image, filter_type: int | list[int] | tuple[int, ...] = 0) -> None:
    file = Path(path)
    data = encode(image, filter_type)
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(f".{file.name}.hhtmp-{os.getpid()}")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, file)
    finally:
        if tmp.exists():
            tmp.unlink()

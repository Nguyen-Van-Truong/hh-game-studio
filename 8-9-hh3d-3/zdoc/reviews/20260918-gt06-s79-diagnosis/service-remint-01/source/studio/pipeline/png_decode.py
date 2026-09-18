"""Bounded, in-memory PNG decoding for the initial GT05 fixture profile.

Supported: RGB8/RGBA8, noninterlaced, compression/filter methods 0, filters 0–4,
and only IHDR / one or more consecutive IDAT / IEND chunks. Supported ancillary
chunks: NONE. Palette, transparency chunks, APNG, metadata and color-profile
chunks are rejected, including otherwise legal PNG features. Returned samples
are straight-alpha RGBA8; no gamma/color conversion is applied. Material slot
color-space semantics and the aggregate image budget remain the caller's job.

All chunks/CRCs and dimensions are admitted before inflation/allocation. The
zlib output limit is the exact expected filtered size plus one overflow byte;
no unbounded flush is used. Peak working memory includes filtered bytes, output
bytearray and its immutable copy (under three RGBA buffers plus small rows).
An isolated host still owns CPU/wall/RAM caps when inspecting untrusted input.
No filesystem, network, engine, importer or publication access occurs here.

PNG specification sections 5.3/5.6, 9 and 10–11:
https://www.w3.org/TR/png-3/
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
import zlib

MAX_PNG_BYTES = 1_048_576
MAX_DIMENSION = 4096
MAX_RGBA_BYTES = 128 * 1024 * 1024
MAX_CHUNKS = 4096
SUPPORTED_ANCILLARY = ()
_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PNGRejected(ValueError):
    """Stable code only, without echoing candidate data."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise PNGRejected(code)


@dataclass(frozen=True, slots=True)
class DecodedPNG:
    width: int
    height: int
    source_color_type: int
    rgba8: bytes
    source_sha256: str
    rgba8_sha256: str


def _parse(raw: bytes) -> tuple[int, int, int, bytes]:
    _need(type(raw) is bytes and 57 <= len(raw) <= MAX_PNG_BYTES, "PNG_BYTE_LIMIT_OR_TYPE")
    _need(raw[:8] == _SIGNATURE, "PNG_SIGNATURE")
    offset = 8
    chunks = 0
    dimensions = None
    compressed = []
    while offset < len(raw):
        chunks += 1
        _need(chunks <= MAX_CHUNKS, "PNG_CHUNK_LIMIT")
        _need(offset + 12 <= len(raw), "PNG_CHUNK_HEADER")
        length = struct.unpack_from(">I", raw, offset)[0]
        kind = raw[offset + 4:offset + 8]
        _need(length <= 0x7FFFFFFF and offset + 12 + length <= len(raw), "PNG_CHUNK_BOUNDS")
        _need(all(65 <= char <= 90 or 97 <= char <= 122 for char in kind) and
              65 <= kind[2] <= 90, "PNG_CHUNK_TYPE")
        start = offset + 8
        end = start + length
        payload = raw[start:end]
        expected_crc = struct.unpack_from(">I", raw, end)[0]
        actual_crc = zlib.crc32(payload, zlib.crc32(kind)) & 0xFFFFFFFF
        _need(actual_crc == expected_crc, "PNG_CRC")
        offset = end + 4
        if chunks == 1:
            _need(kind == b"IHDR" and length == 13, "PNG_IHDR_FIRST")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            _need(1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION,
                  "PNG_DIMENSION_LIMIT")
            _need(width * height * 4 <= MAX_RGBA_BYTES, "PNG_RGBA_LIMIT")
            _need(depth == 8 and color in (2, 6) and compression == filtering == interlace == 0,
                  "PNG_PROFILE_UNSUPPORTED")
            dimensions = (width, height, color)
        elif kind == b"IDAT":
            compressed.append(payload)
        elif kind == b"IEND":
            _need(length == 0 and compressed and offset == len(raw), "PNG_IEND_OR_TRAILING_BYTES")
            _need(any(compressed), "PNG_EMPTY_IDAT")
            return (*dimensions, b"".join(compressed))
        else:
            # A closed allowlist also rejects intervening chunks: no split IDAT run.
            raise PNGRejected("PNG_CHUNK_UNSUPPORTED_OR_ORDER")
    raise PNGRejected("PNG_MISSING_IEND")


def _inflate(compressed: bytes, expected: int) -> bytes:
    try:
        decoder = zlib.decompressobj(zlib.MAX_WBITS)
        filtered = decoder.decompress(compressed, expected + 1)
    except zlib.error:
        raise PNGRejected("PNG_ZLIB_STREAM") from None
    _need(len(filtered) <= expected, "PNG_INFLATE_LIMIT")
    _need(decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data,
          "PNG_ZLIB_EOF_OR_TRAILING_DATA")
    _need(len(filtered) == expected, "PNG_SCANLINE_LENGTH")
    return filtered


def _paeth(left: int, above: int, upper_left: int) -> int:
    prediction = left + above - upper_left
    a, b, c = abs(prediction - left), abs(prediction - above), abs(prediction - upper_left)
    if a <= b and a <= c:
        return left
    return above if b <= c else upper_left


def decode_png(raw: bytes) -> DecodedPNG:
    """Decode exactly this closed PNG profile, preserving unconverted samples."""
    width, height, color, compressed = _parse(raw)
    channels = 3 if color == 2 else 4
    row_bytes = width * channels
    filtered = _inflate(compressed, (row_bytes + 1) * height)
    rgba = bytearray(width * height * 4)
    previous = bytearray(row_bytes)
    for y in range(height):
        start = y * (row_bytes + 1)
        filter_type = filtered[start]
        _need(filter_type <= 4, "PNG_FILTER_TYPE")
        row = bytearray(filtered[start + 1:start + 1 + row_bytes])
        if filter_type:
            for x in range(row_bytes):
                left = row[x - channels] if x >= channels else 0
                above = previous[x]
                if filter_type == 1:
                    predictor = left
                elif filter_type == 2:
                    predictor = above
                elif filter_type == 3:
                    predictor = (left + above) // 2
                else:
                    upper_left = previous[x - channels] if x >= channels else 0
                    predictor = _paeth(left, above, upper_left)
                row[x] = (row[x] + predictor) & 255
        target = y * width * 4
        if channels == 4:
            rgba[target:target + width * 4] = row
        else:
            expanded = bytearray(b"\xff" * (width * 4))
            expanded[0::4], expanded[1::4], expanded[2::4] = row[0::3], row[1::3], row[2::3]
            rgba[target:target + width * 4] = expanded
        previous = row
    pixels = bytes(rgba)
    return DecodedPNG(width, height, color, pixels, hashlib.sha256(raw).hexdigest(),
                      hashlib.sha256(pixels).hexdigest())

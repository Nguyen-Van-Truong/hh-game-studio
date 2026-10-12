"""Pure-Python media checks for gamekit asset intake.

Images: PNG, JPEG, and WebP width/height, a power-of-two flag, and a warning above 8192 px.
WAV: PCM 16/24/32-bit integer and 32-bit float. Peak dBFS plus integrated loudness
(ITU-R BS.1770-4): K-weighting is two biquads whose coefficients come from the standard
bilinear formulas at the file's sample rate, then 400 ms blocks with 75% overlap, an
absolute gate of -70 LUFS and a relative gate of -10 LU. At most the first 120 s are
analyzed. Silence that never passes the absolute gate is reported as gated, not as a
fake loudness number.

OGG: duration from the last granule when the ident header is Vorbis or Opus, otherwise
the string "unknown". glTF/GLB: meshes, primitives, mode-4 triangle count, vertex count,
materials, embedded images, skins, animations, and POSITION bounds in meters.
"""

from __future__ import annotations

import array
import json
import math
import re
import struct
import sys
import zlib
from typing import Any

from . import common as C

MAX_EDGE = 8192
ANALYZE_SECONDS = 120
MUSIC_TARGET_LUFS = -16.0
MUSIC_TOLERANCE_LU = 3.0
ABS_GATE_LUFS = -70.0
REL_GATE_LU = -10.0
LUFS_OFFSET = -0.691
MIN_SAMPLE_RATE = 8000
MAX_SAMPLE_RATE = 384000

# BS.1770-4 high-shelf and RLB high-pass, bilinear (match the published 48 kHz table).
_SHELF_F0 = 1681.974450955533
_SHELF_G = 3.999843853973347
_SHELF_Q = 0.7071752369554196
_SHELF_VB_EXP = 0.4996667741545416
_RLB_F0 = 38.13547087602444
_RLB_Q = 0.5003270373238773

_GLTF_MODES = {
    0: "POINTS",
    1: "LINES",
    2: "LINE_LOOP",
    3: "LINE_STRIP",
    4: "TRIANGLES",
    5: "TRIANGLE_STRIP",
    6: "TRIANGLE_FAN",
}
_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
_WAVE_GUID_TAIL = bytes.fromhex("00001000800000aa00389b71")


def _fail(detail: str) -> None:
    raise C.GamekitError("VALIDATION_FAILED", detail)


def _round(value: float, places: int) -> float:
    return round(float(value), places)


# ---------------------------------------------------------------- images


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _image_checks(fmt: str, width: int, height: int) -> dict[str, Any]:
    if width <= 0 or height <= 0 or width > 1_000_000 or height > 1_000_000:
        _fail(f"{fmt} dimensions are not usable: {width}x{height}")
    warnings = []
    if width > MAX_EDGE or height > MAX_EDGE:
        warnings.append(f"dimension exceeds {MAX_EDGE}")
    return {
        "kind": "image",
        "format": fmt,
        "width": width,
        "height": height,
        "power_of_two": _is_power_of_two(width) and _is_power_of_two(height),
        "warnings": warnings,
    }


def _parse_png(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        _fail("not a PNG")
    length = int.from_bytes(data[8:12], "big")
    tag = data[12:16]
    if tag != b"IHDR" or length < 13 or 16 + length + 4 > len(data):
        _fail("PNG IHDR chunk is missing")
    payload = data[16 : 16 + length]
    crc = int.from_bytes(data[16 + length : 20 + length], "big")
    if (zlib.crc32(tag + payload) & 0xFFFFFFFF) != crc:
        _fail("PNG IHDR checksum does not match")
    width = int.from_bytes(payload[0:4], "big")
    height = int.from_bytes(payload[4:8], "big")
    return width, height


def _parse_jpeg(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        _fail("not a JPEG")
    i = 2
    n = len(data)
    while i < n:
        if data[i] != 0xFF:
            _fail("JPEG marker is not aligned")
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            break
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            if marker == 0xD9:
                break
            continue
        if i + 2 > n:
            _fail("JPEG segment is truncated")
        seglen = int.from_bytes(data[i : i + 2], "big")
        if seglen < 2 or i + seglen > n:
            _fail("JPEG segment length is invalid")
        if marker in _SOF_MARKERS:
            if seglen < 7:
                _fail("JPEG frame header is truncated")
            height = int.from_bytes(data[i + 3 : i + 5], "big")
            width = int.from_bytes(data[i + 5 : i + 7], "big")
            return width, height
        if marker == 0xDA:
            break
        i += seglen
    _fail("JPEG has no SOF frame header")
    return 0, 0


def _parse_webp(data: bytes) -> tuple[int, int]:
    if len(data) < 16 or data[0:4] != b"RIFF" or data[8:12] != b"WEBP":
        _fail("not a WebP")
    pos = 12
    n = len(data)
    while pos + 8 <= n:
        tag = data[pos : pos + 4]
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        start = pos + 8
        if size < 0 or start + size > n:
            _fail("WebP chunk overruns the file")
        chunk = data[start : start + size]
        if tag == b"VP8X" and len(chunk) >= 10:
            width = 1 + int.from_bytes(chunk[4:7], "little")
            height = 1 + int.from_bytes(chunk[7:10], "little")
            return width, height
        if tag == b"VP8 " and len(chunk) >= 10 and chunk[3:6] == b"\x9d\x01\x2a":
            width = int.from_bytes(chunk[6:8], "little") & 0x3FFF
            height = int.from_bytes(chunk[8:10], "little") & 0x3FFF
            return width, height
        if tag == b"VP8L" and len(chunk) >= 5 and chunk[0] == 0x2F:
            bits = int.from_bytes(chunk[1:5], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height
        pos = start + size + (size & 1)
    _fail("WebP has no VP8, VP8L, or VP8X dimension chunk")
    return 0, 0


def _parse_svg(data: bytes) -> dict[str, Any]:
    head = data[:8192].lower()
    if b"<svg" not in head and b"<svg" not in data[:65536].lower():
        _fail("not an SVG")
    text = data[:65536].decode("utf-8", errors="replace")

    def _px(pattern: str) -> float | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    width = _px(r"\bwidth\s*=\s*['\"]\s*([0-9]+(?:\.[0-9]+)?)")
    height = _px(r"\bheight\s*=\s*['\"]\s*([0-9]+(?:\.[0-9]+)?)")
    if width is None or height is None:
        box = re.search(
            r"\bviewBox\s*=\s*['\"]\s*[0-9.]+\s+[0-9.]+\s+([0-9.]+)\s+([0-9.]+)",
            text,
            flags=re.IGNORECASE,
        )
        if box:
            width = float(box.group(1))
            height = float(box.group(2))
    warnings = []
    iw = ih = None
    if width is not None and height is not None and width > 0 and height > 0:
        iw, ih = int(round(width)), int(round(height))
        checks = _image_checks("svg", iw, ih)
        return checks
    warnings.append("svg width and height were not found")
    return {"kind": "image", "format": "svg", "width": None, "height": None, "power_of_two": False, "warnings": warnings}


# ---------------------------------------------------------------- loudness (BS.1770-4)


def k_weight_coefficients(sample_rate: int) -> dict[str, tuple[float, float, float, float, float]]:
    """Return ``(b0, b1, b2, a1, a2)`` for the shelf and the RLB high-pass. ``a0`` is 1."""
    if sample_rate < MIN_SAMPLE_RATE or sample_rate > MAX_SAMPLE_RATE:
        _fail(f"sample rate {sample_rate} is outside {MIN_SAMPLE_RATE}..{MAX_SAMPLE_RATE}")
    if _SHELF_F0 >= sample_rate / 2:
        _fail(f"sample rate {sample_rate} is too low for BS.1770 K-weighting")

    def _shelf() -> tuple[float, float, float, float, float]:
        k = math.tan(math.pi * _SHELF_F0 / sample_rate)
        vh = 10.0 ** (_SHELF_G / 20.0)
        vb = vh ** _SHELF_VB_EXP
        a0 = 1.0 + k / _SHELF_Q + k * k
        b0 = (vh + vb * k / _SHELF_Q + k * k) / a0
        b1 = 2.0 * (k * k - vh) / a0
        b2 = (vh - vb * k / _SHELF_Q + k * k) / a0
        a1 = 2.0 * (k * k - 1.0) / a0
        a2 = (1.0 - k / _SHELF_Q + k * k) / a0
        return (b0, b1, b2, a1, a2)

    def _rlb() -> tuple[float, float, float, float, float]:
        k = math.tan(math.pi * _RLB_F0 / sample_rate)
        a0 = 1.0 + k / _RLB_Q + k * k
        # Published tables leave the numerator at 1, -2, 1 and fold a0 into a1/a2 only.
        a1 = 2.0 * (k * k - 1.0) / a0
        a2 = (1.0 - k / _RLB_Q + k * k) / a0
        return (1.0, -2.0, 1.0, a1, a2)

    return {"pre": _shelf(), "rlb": _rlb()}


def _apply_k_weight(samples: array.array, sample_rate: int) -> array.array:
    coeff = k_weight_coefficients(sample_rate)
    b0, b1, b2, a1, a2 = coeff["pre"]
    c0, c1, c2, d1, d2 = coeff["rlb"]
    out = array.array("d", [0.0]) * len(samples)
    x1 = x2 = y1 = y2 = 0.0
    u1 = u2 = v1 = v2 = 0.0
    for i, x in enumerate(samples):
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2 = x1
        x1 = x
        y2 = y1
        y1 = y
        v = c0 * y + c1 * u1 + c2 * u2 - d1 * v1 - d2 * v2
        u2 = u1
        u1 = y
        v2 = v1
        v1 = v
        out[i] = v
    return out


def _channel_weights(channels: int) -> list[float]:
    """BS.1770 power weights. Surround gain 1.41 is about +1.5 dB on the mean square. LFE is dropped."""
    if channels == 1:
        return [1.0]
    if channels == 2:
        return [1.0, 1.0]
    if channels == 6:
        return [1.0, 1.0, 1.0, 0.0, 1.41, 1.41]
    if channels == 8:
        return [1.0, 1.0, 1.0, 0.0, 1.41, 1.41, 1.41, 1.41]
    return [1.0] * channels


def _lufs_from_energy(mean_square: float) -> float:
    return LUFS_OFFSET + 10.0 * math.log10(mean_square)


def measure_loudness(channels: list[array.array], sample_rate: int) -> dict[str, Any]:
    """Integrated loudness of already-normalized channels. Gated silence returns null LUFS."""
    if not channels or len(channels[0]) == 0:
        _fail("audio has no samples to measure")
    n = len(channels[0])
    weighted = [_apply_k_weight(ch, sample_rate) for ch in channels]
    gains = _channel_weights(len(channels))
    block = int(round(0.4 * sample_rate))
    hop = max(1, int(round(0.1 * sample_rate)))
    warnings = []
    if n >= block:
        starts = range(0, n - block + 1, hop)
        length = block
    else:
        starts = range(0, 1)
        length = n
        warnings.append("shorter than the 400 ms gating block; one partial block was measured")
    energies: list[float] = []
    for start in starts:
        end = start + length
        total = 0.0
        for ch, gain in zip(weighted, gains):
            if gain == 0.0:
                continue
            acc = 0.0
            for i in range(start, end):
                y = ch[i]
                acc += y * y
            total += gain * acc
        energies.append(total / float(length))
    abs_energy = 10.0 ** ((ABS_GATE_LUFS - LUFS_OFFSET) / 10.0)
    passed = [e for e in energies if e >= abs_energy and e > 0.0]
    if not passed:
        return {
            "integrated_lufs": None,
            "loudness_gated": True,
            "gating_blocks": len(energies),
            "gating_blocks_used": 0,
            "warnings": warnings + ["integrated loudness gated below -70 LUFS"],
        }
    absolute = _lufs_from_energy(sum(passed) / len(passed))
    # Relative gate is absolute-gated loudness minus 10 LU (REL_GATE_LU is -10).
    threshold_lufs = absolute + REL_GATE_LU
    rel_energy = 10.0 ** ((threshold_lufs - LUFS_OFFSET) / 10.0)
    kept = [e for e in passed if e >= rel_energy]
    if not kept:
        kept = passed
    integrated = _lufs_from_energy(sum(kept) / len(kept))
    return {
        "integrated_lufs": _round(integrated, 4),
        "loudness_gated": False,
        "gating_blocks": len(energies),
        "gating_blocks_used": len(kept),
        "warnings": warnings,
    }


# ---------------------------------------------------------------- WAV / OGG / MP3


def _dbfs(peak: float) -> float | None:
    if peak <= 0.0:
        return None
    return _round(20.0 * math.log10(peak), 4)


def _wav_chunks(data: bytes) -> tuple[bytes, bytes]:
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        _fail("not a RIFF WAVE")
    pos = 12
    fmt = None
    pcm = None
    while pos + 8 <= len(data):
        tag = data[pos : pos + 4]
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        start = pos + 8
        if start + size > len(data):
            _fail("wav chunk overruns the file")
        chunk = data[start : start + size]
        pos = start + size
        if size & 1 and pos < len(data):
            pos += 1
        if tag == b"fmt " and fmt is None:
            fmt = chunk
        elif tag == b"data" and pcm is None:
            pcm = chunk
    if fmt is None or pcm is None:
        _fail("wav is missing fmt or data")
    return fmt, pcm


def _wav_format(fmt: bytes) -> tuple[int, int, int, int, int]:
    if len(fmt) < 16:
        _fail("wav fmt chunk is truncated")
    audio_format, channels, rate, _byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", fmt, 0)
    if audio_format == 0xFFFE:
        if len(fmt) < 40 or fmt[28:40] != _WAVE_GUID_TAIL:
            _fail("wav extensible subformat is not PCM or float")
        audio_format = int.from_bytes(fmt[24:26], "little")
    if audio_format not in (1, 3):
        _fail(f"wav encoding {audio_format} is not PCM or IEEE float")
    if channels < 1 or channels > 16:
        _fail(f"wav channel count {channels} is not supported")
    if rate < MIN_SAMPLE_RATE or rate > MAX_SAMPLE_RATE:
        _fail(f"wav sample rate {rate} is outside {MIN_SAMPLE_RATE}..{MAX_SAMPLE_RATE}")
    if audio_format == 1 and bits not in (16, 24, 32):
        _fail(f"wav PCM bit depth {bits} is not 16, 24, or 32")
    if audio_format == 3 and bits != 32:
        _fail("wav float encoding must be 32-bit")
    width = bits // 8
    if block_align != width * channels:
        _fail("wav block align does not match channels and bit depth")
    return audio_format, channels, rate, bits, block_align


def _decode_wav(pcm: bytes, audio_format: int, channels: int, bits: int, block_align: int, frames: int) -> tuple[list[array.array], float]:
    need = frames * block_align
    blob = pcm[:need]
    if len(blob) < need:
        _fail("wav data chunk is shorter than its frame count")
    chans = [array.array("d", [0.0]) * frames for _ in range(channels)]
    peak = 0.0
    if audio_format == 1 and bits == 16:
        raw = array.array("h")
        raw.frombytes(blob)
        if sys.byteorder != "little":
            raw.byteswap()
        scale = 1.0 / 32768.0
        for i, v in enumerate(raw):
            x = v * scale
            chans[i % channels][i // channels] = x
            ax = abs(x)
            if ax > peak:
                peak = ax
        return chans, peak
    if audio_format == 1 and bits == 32:
        raw = array.array("i")
        raw.frombytes(blob)
        if sys.byteorder != "little":
            raw.byteswap()
        scale = 1.0 / 2147483648.0
        for i, v in enumerate(raw):
            x = v * scale
            chans[i % channels][i // channels] = x
            ax = abs(x)
            if ax > peak:
                peak = ax
        return chans, peak
    if audio_format == 3 and bits == 32:
        raw = array.array("f")
        raw.frombytes(blob)
        if sys.byteorder != "little":
            raw.byteswap()
        for i, v in enumerate(raw):
            x = float(v)
            chans[i % channels][i // channels] = x
            ax = abs(x)
            if ax > peak:
                peak = ax
        return chans, peak
    # 24-bit little-endian sign-extended.
    scale = 1.0 / 8388608.0
    for frame in range(frames):
        base = frame * block_align
        for ch in range(channels):
            o = base + ch * 3
            v = blob[o] | (blob[o + 1] << 8) | (blob[o + 2] << 16)
            if v >= 0x800000:
                v -= 0x1000000
            x = v * scale
            chans[ch][frame] = x
            ax = abs(x)
            if ax > peak:
                peak = ax
    return chans, peak


def _encoding_name(audio_format: int, bits: int) -> str:
    if audio_format == 3:
        return "pcm_f32"
    return {16: "pcm_s16", 24: "pcm_s24", 32: "pcm_s32"}[bits]


def _inspect_wav(data: bytes) -> dict[str, Any]:
    fmt, pcm = _wav_chunks(data)
    audio_format, channels, rate, bits, block_align = _wav_format(fmt)
    total_frames = len(pcm) // block_align
    if total_frames <= 0:
        _fail("wav has no samples")
    max_frames = rate * ANALYZE_SECONDS
    analyzed = min(total_frames, max_frames)
    decoded, peak = _decode_wav(pcm, audio_format, channels, bits, block_align, analyzed)
    loud = measure_loudness(decoded, rate)
    warnings = list(loud["warnings"])
    if analyzed < total_frames:
        warnings.append(f"peak and loudness cover the first {ANALYZE_SECONDS} s only")
    peak_db = _dbfs(peak)
    clipping = peak_db is not None and peak_db >= -0.1
    lufs = loud["integrated_lufs"]
    outside = False
    if lufs is not None and abs(lufs - MUSIC_TARGET_LUFS) > MUSIC_TOLERANCE_LU:
        outside = True
        warnings.append(
            f"integrated loudness {lufs} LUFS is outside the music window "
            f"{MUSIC_TARGET_LUFS} +/- {MUSIC_TOLERANCE_LU} LU"
        )
    if clipping:
        warnings.append("clipping (peak >= -0.1 dBFS)")
    return {
        "kind": "audio",
        "format": "wav",
        "sample_rate": rate,
        "channels": channels,
        "bits_per_sample": bits,
        "encoding": _encoding_name(audio_format, bits),
        "duration_seconds": _round(total_frames / float(rate), 6),
        "analyzed_seconds": _round(analyzed / float(rate), 6),
        "peak_dbfs": peak_db,
        "integrated_lufs": lufs,
        "loudness_gated": loud["loudness_gated"],
        "gating_blocks": loud["gating_blocks"],
        "gating_blocks_used": loud["gating_blocks_used"],
        "clipping": clipping,
        "loudness_target_lufs": MUSIC_TARGET_LUFS,
        "loudness_tolerance_lu": MUSIC_TOLERANCE_LU,
        "loudness_window": "music",
        "loudness_outside_window": outside,
        "sfx_loudness": "informational",
        "warnings": warnings,
    }


def _ogg_pages(data: bytes):
    i = 0
    n = len(data)
    while True:
        j = data.find(b"OggS", i)
        if j < 0 or j + 27 > n:
            return
        if data[j + 4] != 0:
            i = j + 4
            continue
        nseg = data[j + 26]
        table = j + 27
        if table + nseg > n:
            return
        body_len = sum(data[table : table + nseg])
        body_at = table + nseg
        if body_at + body_len > n:
            return
        granule = int.from_bytes(data[j + 6 : j + 14], "little", signed=True)
        serial = int.from_bytes(data[j + 14 : j + 18], "little")
        yield serial, granule, data[body_at : body_at + body_len]
        i = body_at + body_len


def _ogg_duration(data: bytes) -> tuple[str, float | str]:
    codecs: dict[int, tuple[str, int, int]] = {}
    last: dict[int, int] = {}
    pages = 0
    for serial, granule, body in _ogg_pages(data):
        pages += 1
        if serial not in codecs:
            if body.startswith(b"\x01vorbis") and len(body) >= 16:
                rate = int.from_bytes(body[12:16], "little")
                codecs[serial] = ("vorbis", rate, 0)
            elif body.startswith(b"OpusHead") and len(body) >= 12:
                preskip = int.from_bytes(body[10:12], "little")
                codecs[serial] = ("opus", 48000, preskip)
        if granule >= 0:
            prev = last.get(serial, -1)
            if granule > prev:
                last[serial] = granule
    if pages == 0:
        _fail("not an Ogg stream")
    for serial, (codec, rate, preskip) in codecs.items():
        granule = last.get(serial, -1)
        if rate <= 0 or granule < 0:
            continue
        samples = granule - preskip if codec == "opus" else granule
        if samples < 0:
            continue
        return codec, _round(samples / float(rate), 6)
    return "unknown", "unknown"


def _inspect_ogg(data: bytes) -> dict[str, Any]:
    codec, duration = _ogg_duration(data)
    warnings = []
    if duration == "unknown":
        warnings.append("ogg duration is unknown (no Vorbis or Opus granule)")
    return {"kind": "audio", "format": "ogg", "codec": codec, "duration_seconds": duration, "warnings": warnings}


def _inspect_mp3(data: bytes) -> dict[str, Any]:
    start = 0
    if data[:3] == b"ID3" and len(data) >= 10:
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        start = 10 + size
    limit = min(len(data) - 1, start + 8192)
    i = start
    found = False
    while i < limit:
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            version = (data[i + 1] >> 3) & 0x03
            layer = (data[i + 1] >> 1) & 0x03
            bitrate = (data[i + 2] >> 4) & 0x0F
            sample_rate = (data[i + 2] >> 2) & 0x03
            if version != 1 and layer != 0 and bitrate not in (0, 15) and sample_rate != 3:
                found = True
                break
        i += 1
    if not found:
        _fail("not an MP3 frame stream")
    return {
        "kind": "audio",
        "format": "mp3",
        "duration_seconds": "unknown",
        "warnings": ["mp3 duration and loudness are not measured in v1"],
    }


# ---------------------------------------------------------------- glTF / GLB


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    return int(value)


def _gltf_document_from_json(data: bytes) -> dict[str, Any]:
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        _fail(f"glTF JSON is invalid: {exc}")
    if not isinstance(doc, dict):
        _fail("glTF root must be an object")
    version = str((doc.get("asset") or {}).get("version", "")) if isinstance(doc.get("asset"), dict) else ""
    if not version.startswith("2"):
        _fail("only glTF 2.x is accepted")
    return doc


def _gltf_document_from_glb(data: bytes) -> tuple[dict[str, Any], bytes]:
    if len(data) < 20 or data[:4] != b"glTF":
        _fail("not a GLB")
    version, length = struct.unpack_from("<II", data, 4)
    if version != 2:
        _fail(f"GLB version {version} is not 2")
    if length < 20 or length > len(data):
        _fail("GLB length does not match the file")
    offset = 12
    doc = None
    binary = b""
    end = min(length, len(data))
    while offset + 8 <= end:
        clen, ctype = struct.unpack_from("<II", data, offset)
        offset += 8
        if clen < 0 or offset + clen > end:
            _fail("GLB chunk overruns the file")
        chunk = data[offset : offset + clen]
        offset += clen
        if ctype == 0x4E4F534A and doc is None:
            doc = _gltf_document_from_json(chunk.strip(b" \x00"))
        elif ctype == 0x004E4942 and not binary:
            binary = chunk
    if doc is None:
        _fail("GLB has no JSON chunk")
    return doc, binary


def external_gltf_uris(doc: dict[str, Any], *, glb: bool) -> list[str]:
    """URIs that are not ``data:`` URIs. A GLB's first buffer may omit its URI (the BIN chunk)."""
    problems = []
    buffers = doc.get("buffers") if isinstance(doc.get("buffers"), list) else []
    for index, buf in enumerate(buffers):
        if not isinstance(buf, dict):
            problems.append(f"buffers[{index}] is not an object")
            continue
        uri = buf.get("uri")
        if uri is None:
            if glb and index == 0:
                continue
            problems.append(f"buffers[{index}] has no data: URI")
        elif not isinstance(uri, str) or not uri.startswith("data:"):
            problems.append(f"buffers[{index}] URI is external")
    images = doc.get("images") if isinstance(doc.get("images"), list) else []
    for index, img in enumerate(images):
        if not isinstance(img, dict):
            problems.append(f"images[{index}] is not an object")
            continue
        uri = img.get("uri")
        if isinstance(uri, str):
            if not uri.startswith("data:"):
                problems.append(f"images[{index}] URI is external")
        elif "bufferView" not in img:
            problems.append(f"images[{index}] has no data: URI or bufferView")
    return problems


def _accessor(doc: dict[str, Any], index: Any, what: str) -> dict[str, Any]:
    accs = doc.get("accessors")
    i = _as_int(index)
    if not isinstance(accs, list) or i is None or i < 0 or i >= len(accs) or not isinstance(accs[i], dict):
        _fail(f"glTF {what} accessor {index} is missing")
    if _as_int(accs[i].get("count")) is None:
        _fail(f"glTF accessor {i} has no count")
    return accs[i]


def _summarize_gltf(doc: dict[str, Any], *, fmt: str, binary: bytes) -> dict[str, Any]:
    warnings: list[str] = []
    buffers = doc.get("buffers") if isinstance(doc.get("buffers"), list) else []
    embedded_need = 0
    for index, buf in enumerate(buffers):
        if isinstance(buf, dict) and buf.get("uri") is None:
            embedded_need = max(embedded_need, _as_int(buf.get("byteLength")) or 0)
            if fmt == "glb" and index > 0:
                warnings.append("extra GLB buffer has no URI")
    if fmt == "glb" and embedded_need > len(binary):
        _fail("GLB BIN chunk is shorter than buffer.byteLength")
    meshes = doc.get("meshes") if isinstance(doc.get("meshes"), list) else []
    triangles = 0
    vertices = 0
    primitives = 0
    other_modes: list[dict[str, Any]] = []
    bmin: list[float] | None = None
    bmax: list[float] | None = None
    for mesh in meshes:
        if not isinstance(mesh, dict):
            continue
        for prim in mesh.get("primitives") or []:
            if not isinstance(prim, dict):
                continue
            primitives += 1
            mode = _as_int(prim.get("mode"))
            if mode is None:
                mode = 4
            attrs = prim.get("attributes") if isinstance(prim.get("attributes"), dict) else {}
            pos_index = attrs.get("POSITION")
            pos_count = 0
            if pos_index is not None:
                acc = _accessor(doc, pos_index, "POSITION")
                pos_count = _as_int(acc.get("count")) or 0
                vertices += pos_count
                mn, mx = acc.get("min"), acc.get("max")
                if isinstance(mn, list) and isinstance(mx, list) and len(mn) >= 3 and len(mx) >= 3:
                    try:
                        mn3 = [float(mn[i]) for i in range(3)]
                        mx3 = [float(mx[i]) for i in range(3)]
                    except (TypeError, ValueError):
                        warnings.append("POSITION min/max is not numeric")
                    else:
                        if bmin is None or bmax is None:
                            bmin, bmax = mn3, mx3
                        else:
                            bmin = [min(bmin[i], mn3[i]) for i in range(3)]
                            bmax = [max(bmax[i], mx3[i]) for i in range(3)]
                else:
                    warnings.append("POSITION accessor missing min/max")
            else:
                warnings.append("primitive has no POSITION")
            if "indices" in prim:
                elements = _as_int(_accessor(doc, prim.get("indices"), "indices").get("count")) or 0
            else:
                elements = pos_count
            if mode == 4:
                if elements % 3:
                    warnings.append("triangle index count is not divisible by 3")
                triangles += elements // 3
            else:
                other_modes.append({"mode": mode, "name": _GLTF_MODES.get(mode, "UNKNOWN"), "elements": elements})
    images = doc.get("images") if isinstance(doc.get("images"), list) else []
    embedded_images = 0
    for img in images:
        if not isinstance(img, dict):
            continue
        uri = img.get("uri")
        if (isinstance(uri, str) and uri.startswith("data:")) or ("bufferView" in img and not isinstance(uri, str)):
            embedded_images += 1
    skins = doc.get("skins") if isinstance(doc.get("skins"), list) else []
    joint_counts = []
    for skin in skins:
        joints = skin.get("joints") if isinstance(skin, dict) else None
        joint_counts.append(len(joints) if isinstance(joints, list) else 0)
    animations = []
    for index, anim in enumerate(doc.get("animations") or []):
        if not isinstance(anim, dict):
            continue
        duration = None
        for sampler in anim.get("samplers") or []:
            if not isinstance(sampler, dict) or "input" not in sampler:
                continue
            mx = _accessor(doc, sampler.get("input"), "animation input").get("max")
            if isinstance(mx, list) and mx:
                try:
                    val = float(mx[0])
                except (TypeError, ValueError):
                    continue
                duration = val if duration is None else max(duration, val)
        name = anim.get("name") if isinstance(anim.get("name"), str) and anim.get("name") else f"animation_{index}"
        channels = anim.get("channels") if isinstance(anim.get("channels"), list) else []
        animations.append({
            "name": name,
            "channels": len(channels),
            "duration": None if duration is None else _round(duration, 6),
        })
    extent = None
    over = under = False
    if bmin is not None and bmax is not None:
        extent = [_round(bmax[i] - bmin[i], 6) for i in range(3)]
        longest = max(extent)
        over = longest > 200.0
        under = longest < 0.005
        if over:
            warnings.append("bounds exceed 200 m")
        if under:
            warnings.append("bounds smaller than 0.005 m")
    external = external_gltf_uris(doc, glb=(fmt == "glb"))
    nodes = doc.get("nodes") if isinstance(doc.get("nodes"), list) else []
    materials = doc.get("materials") if isinstance(doc.get("materials"), list) else []
    textures = doc.get("textures") if isinstance(doc.get("textures"), list) else []
    return {
        "kind": "model",
        "format": fmt,
        "meshes": len(meshes),
        "primitives": primitives,
        "triangles": triangles,
        "vertices": vertices,
        "other_modes": other_modes,
        "materials": len(materials),
        "images": len(images),
        "images_embedded": embedded_images,
        "textures": len(textures),
        "skins": len(skins),
        "joint_counts": joint_counts,
        "animations": animations,
        "nodes": len(nodes),
        "bounds_min": None if bmin is None else [_round(v, 6) for v in bmin],
        "bounds_max": None if bmax is None else [_round(v, 6) for v in bmax],
        "bounds_extent_m": extent,
        "bounds_over_200m": over,
        "bounds_under_0_005m": under,
        "external_uris": external[:20],
        "warnings": warnings,
    }


def _inspect_model(data: bytes, ext: str) -> dict[str, Any]:
    if ext == ".glb":
        doc, binary = _gltf_document_from_glb(data)
        checks = _summarize_gltf(doc, fmt="glb", binary=binary)
        if checks["external_uris"]:
            checks["warnings"] = list(checks["warnings"]) + ["glb still references an external URI"]
        return checks
    doc = _gltf_document_from_json(data)
    external = external_gltf_uris(doc, glb=False)
    if external:
        _fail("gltf has external buffer or image URIs; v1 only allows data: URIs (prefer .glb): " + "; ".join(external[:5]))
    return _summarize_gltf(doc, fmt="gltf", binary=b"")


# ---------------------------------------------------------------- fonts, text, dispatch


def _inspect_font(data: bytes, fmt: str) -> dict[str, Any]:
    if fmt == "woff2":
        if not data.startswith(b"wOF2"):
            _fail("not a WOFF2 font")
    elif not data.startswith((b"\x00\x01\x00\x00", b"true", b"OTTO")):
        _fail(f"not a {fmt} font")
    return {"kind": "font", "format": fmt, "warnings": []}


def _inspect_text(data: bytes, fmt: str) -> dict[str, Any]:
    if fmt == "json":
        try:
            json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            _fail(f"json asset is not valid JSON: {exc}")
        return {"kind": "data", "format": "json", "valid_json": True, "warnings": []}
    try:
        data.decode("utf-8")
        utf8 = True
    except UnicodeDecodeError:
        utf8 = False
    warnings = [] if utf8 else ["text is not valid UTF-8"]
    return {"kind": "text", "format": "txt", "utf8": utf8, "warnings": warnings}


def inspect_media(data: bytes, ext: str) -> dict[str, Any]:
    """Inspect ``data`` for a filename extension (``.png``, ``png``, ...)."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        _fail("media is empty")
    suffix = ext.lower() if ext.startswith(".") else "." + ext.lower()
    blob = bytes(data)
    if suffix == ".png":
        return _image_checks("png", *_parse_png(blob))
    if suffix in (".jpg", ".jpeg"):
        return _image_checks("jpeg", *_parse_jpeg(blob))
    if suffix == ".webp":
        return _image_checks("webp", *_parse_webp(blob))
    if suffix == ".svg":
        return _parse_svg(blob)
    if suffix == ".wav":
        return _inspect_wav(blob)
    if suffix == ".ogg":
        return _inspect_ogg(blob)
    if suffix == ".mp3":
        return _inspect_mp3(blob)
    if suffix in (".glb", ".gltf"):
        return _inspect_model(blob, suffix)
    if suffix in (".ttf", ".otf", ".woff2"):
        return _inspect_font(blob, suffix[1:])
    if suffix in (".json", ".txt"):
        return _inspect_text(blob, suffix[1:])
    _fail(f"extension {suffix} is not inspected")
    return {}

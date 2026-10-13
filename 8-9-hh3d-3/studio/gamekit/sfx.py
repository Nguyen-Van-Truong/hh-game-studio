"""hh sfx: deterministic synthetic PCM presets.

``hh sfx presets`` lists the built-in voices. ``hh sfx generate`` writes one
mono 16-bit WAV outside any registered project. The bytes come from a fixed
xorshift voice in this module: no sample library, no network, no license stamp.
Copy the file into a game only with ``hh asset add`` so the ledger and Godot
import stay in that transaction.

Quality worker registers this module from ``hh.py``. This file does not edit
the dispatcher.
"""

from __future__ import annotations

import argparse
import array
import math
import os
import struct
import sys
from pathlib import Path
from typing import Any, Callable

from . import common as C
from . import media_inspect as M

SCHEMA = "hh-sfx-presets-1"
SYNTH_VERSION = 1
TEMPLATE_PATH = Path(__file__).resolve().parent / "effects" / "sfx_presets.json"
PRESET_IDS = ("ui_click", "pickup", "jump", "impact", "explosion")
_BLOCKED_DIRS = ("superagent-grokdo", "12-10-hh-world-grokdo")
_SALT = {"ui_click": 0x51, "pickup": 0xA2, "jump": 0x13, "impact": 0x77, "explosion": 0x2C}
_PRESET_KEYS = {"id", "description", "default_seed", "duration", "duration_min", "duration_max"}


class _Rng:
    """32-bit xorshift. Same seed always yields the same stream."""

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF
        if self.state == 0:
            self.state = 0x6D2B79F5

    def u32(self) -> int:
        x = self.state & 0xFFFFFFFF
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17) & 0xFFFFFFFF
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return self.state

    def uni(self) -> float:
        return (self.u32() & 0xFFFFFF) / float(0x1000000)

    def bip(self) -> float:
        return self.uni() * 2.0 - 1.0


class _Phase:
    def __init__(self) -> None:
        self.p = 0.0

    def step(self, freq: float, rate: int) -> float:
        self.p = (self.p + freq / float(rate)) % 1.0
        return math.sin(2.0 * math.pi * self.p)


def _fail(detail: str, code: str = "VALIDATION_FAILED") -> None:
    raise C.GamekitError(code, detail)


def _num(value: Any, name: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _fail(f"{name} must be a finite number")
    number = float(value)
    if number < lo or number > hi:
        _fail(f"{name} must be in {lo}..{hi}")
    return number


def _int(value: Any, name: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{name} must be an integer")
    if value < lo or value > hi:
        _fail(f"{name} must be in {lo}..{hi}")
    return value


def _table() -> dict[str, Any]:
    data = C.read_json(TEMPLATE_PATH)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        _fail("sfx preset template is malformed")
    limits = data.get("limits")
    if not isinstance(limits, dict):
        _fail("sfx preset limits are missing")
    rates = limits.get("sample_rates")
    if rates != [22050, 44100, 48000]:
        _fail("sfx sample rates must be 22050, 44100, and 48000")
    duration = limits.get("duration_seconds")
    peak = limits.get("peak_dbfs")
    seed = limits.get("seed")
    if not isinstance(duration, dict) or not isinstance(peak, dict) or not isinstance(seed, dict):
        _fail("sfx limit ranges are missing")
    _num(duration.get("min"), "duration min", 0.02, 0.02)
    _num(duration.get("max"), "duration max", 2.0, 2.0)
    _num(peak.get("min"), "peak min", -24.0, -24.0)
    _num(peak.get("max"), "peak max", -1.0, -1.0)
    _num(peak.get("default"), "peak default", -6.0, -6.0)
    _int(seed.get("min"), "seed min", 0, 0)
    _int(seed.get("max"), "seed max", 2147483647, 2147483647)
    if limits.get("channels") != 1 or limits.get("bits_per_sample") != 16:
        _fail("sfx output is mono 16-bit PCM")
    _int(limits.get("max_bytes"), "max_bytes", 262144, 262144)
    rows = data.get("presets")
    if not isinstance(rows, list) or [row.get("id") if isinstance(row, dict) else None for row in rows] != list(PRESET_IDS):
        _fail("sfx presets must be ui_click, pickup, jump, impact, explosion")
    origin = data.get("origin")
    if not isinstance(origin, str) or "not recordings" not in origin.lower() or "not foley" not in origin.lower():
        _fail("sfx template must say these are not recordings and not Foley")
    for row in rows:
        if not isinstance(row, dict) or set(row) != _PRESET_KEYS:
            _fail("sfx preset record has unexpected fields")
        text = str(row.get("description", "")).lower()
        if "synthetic" not in text or "not a recording" not in text:
            _fail(f"{row.get('id')}: description must say synthetic and not a recording")
        _int(row.get("default_seed"), f"{row['id']} seed", 0, 2147483647)
        duration_value = _num(row.get("duration"), f"{row['id']} duration", 0.02, 2.0)
        lo = _num(row.get("duration_min"), f"{row['id']} duration_min", 0.02, 2.0)
        hi = _num(row.get("duration_max"), f"{row['id']} duration_max", 0.02, 2.0)
        if not lo <= duration_value <= hi:
            _fail(f"{row['id']}: duration is outside its own range")
        if row["id"] not in _SALT or row["id"] not in _VOICES:
            _fail(f"{row['id']}: no voice is implemented")
    return data


def _preset(preset_id: str) -> dict[str, Any]:
    if not isinstance(preset_id, str):
        _fail("preset must be a string")
    for row in _table()["presets"]:
        if row["id"] == preset_id:
            return row
    _fail(f"unknown sfx preset {preset_id!r}", "BAD_REQUEST")
    raise AssertionError("unreachable")


def _decay(t: float, rate_k: float) -> float:
    return math.exp(-t * rate_k)


def _voice_click(buf: list[float], rate: int, detune: float, rng: _Rng) -> None:
    tone = _Phase()
    tick = _Phase()
    gap = int(0.011 * rate)
    for i in range(len(buf)):
        t = i / rate
        buf[i] = tone.step(1900.0 * detune, rate) * _decay(t, 62.0)
        buf[i] += rng.bip() * _decay(t, 140.0) * 0.28
        if i >= gap:
            buf[i] += tick.step(2700.0 * detune, rate) * _decay((i - gap) / rate, 80.0) * 0.55


def _voice_pickup(buf: list[float], rate: int, detune: float, rng: _Rng) -> None:
    low = _Phase()
    high = _Phase()
    split = int(len(buf) * 0.48)
    click = int(0.004 * rate)
    for i in range(len(buf)):
        if i < split:
            t = i / rate
            attack = 1.0 if t > 0.008 else t / 0.008
            buf[i] = low.step(523.25 * detune, rate) * attack * _decay(t, 4.0)
        else:
            t = (i - split) / rate
            attack = 1.0 if t > 0.006 else t / 0.006
            buf[i] = high.step(783.99 * detune, rate) * attack * _decay(t, 5.0) * 0.9
        if i < click:
            buf[i] += rng.bip() * 0.15


def _voice_jump(buf: list[float], rate: int, detune: float, rng: _Rng) -> None:
    del rng
    fund = _Phase()
    harm = _Phase()
    last = max(1, len(buf) - 1)
    for i in range(len(buf)):
        t = i / rate
        freq = (260.0 * detune) * ((920.0 / 260.0) ** (i / last))
        attack = 1.0 if t > 0.01 else t / 0.01
        buf[i] = (fund.step(freq, rate) + 0.18 * harm.step(freq * 2.0, rate)) * attack * _decay(t, 3.2)


def _voice_impact(buf: list[float], rate: int, detune: float, rng: _Rng) -> None:
    body = _Phase()
    tick = _Phase()
    for i in range(len(buf)):
        t = i / rate
        buf[i] = body.step(90.0 * detune, rate) * _decay(t, 10.0) * 0.9
        buf[i] += rng.bip() * _decay(t, 22.0) * 0.55
        if t < 0.012:
            buf[i] += tick.step(420.0 * detune, rate) * _decay(t, 80.0) * 0.4


def _voice_explosion(buf: list[float], rate: int, detune: float, rng: _Rng) -> None:
    body = _Phase()
    sub = _Phase()
    last = max(1, len(buf) - 1)
    dt = 1.0 / float(rate)
    alpha = dt / (dt + 1.0 / (2.0 * math.pi * 380.0))
    low = 0.0
    for i in range(len(buf)):
        t = i / rate
        freq = (150.0 * detune) * ((42.0 / 150.0) ** (i / last))
        low += alpha * (rng.bip() - low)
        buf[i] = body.step(freq, rate) * _decay(t, 2.4) * 0.75
        buf[i] += low * _decay(t, 1.6) * 0.85
        buf[i] += sub.step(48.0 * detune, rate) * _decay(t, 1.1) * 0.35


_VOICES: dict[str, Callable[[list[float], int, float, _Rng], None]] = {
    "ui_click": _voice_click,
    "pickup": _voice_pickup,
    "jump": _voice_jump,
    "impact": _voice_impact,
    "explosion": _voice_explosion,
}


def _fade(buf: list[float], rate: int) -> None:
    n = len(buf)
    seconds = n / float(rate)
    fade_in = min(n - 1, max(1, int(round(rate * min(0.004, seconds * 0.08)))))
    fade_out = min(n - 1, max(1, int(round(rate * min(0.03, seconds * 0.20)))))
    for i in range(n):
        gain = 1.0
        if i < fade_in:
            gain *= 0.5 - 0.5 * math.cos(math.pi * (i / fade_in))
        tail = n - 1 - i
        if tail < fade_out:
            gain *= 0.5 - 0.5 * math.cos(math.pi * (tail / fade_out))
        buf[i] *= gain


def _render(preset_id: str, frames: int, rate: int, seed: int) -> list[float]:
    rng = _Rng((seed + 1) * 0x9E3779B1 + _SALT[preset_id])
    detune = 0.975 + rng.uni() * 0.05
    buf = [0.0] * frames
    _VOICES[preset_id](buf, rate, detune, rng)
    _fade(buf, rate)
    peak = max(abs(sample) for sample in buf)
    if peak < 1e-4 or not math.isfinite(peak):
        _fail("synthesis produced silence")
    scale = 1.0 / peak
    return [sample * scale for sample in buf]


def _quantize(samples: list[float], peak_dbfs: float) -> list[int]:
    amp = (10.0 ** (peak_dbfs / 20.0)) * 32767.0
    codes: list[int] = []
    for sample in samples:
        code = int(round(sample * amp))
        if code > 32767:
            code = 32767
        elif code < -32767:
            code = -32767
        codes.append(code)
    return codes


def _peak_dbfs(codes: list[int]) -> float:
    peak_code = max(abs(code) for code in codes)
    if peak_code <= 0:
        _fail("synthesis produced silence")
    peak = peak_code / 32768.0
    if peak >= 1.0:
        _fail("synthesis clipped")
    measured = round(20.0 * math.log10(peak), 4)
    if measured >= -0.1:
        _fail(f"synthesis peak {measured} dBFS is at or above -0.1 dBFS")
    return measured


def _encode_wav(codes: list[int], rate: int) -> bytes:
    raw = array.array("h", codes)
    if sys.byteorder != "little":
        raw.byteswap()
    frames = raw.tobytes()
    block = 2
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * block, block, 16)
    body = b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(frames)) + frames
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _decode_wav(data: bytes) -> tuple[int, list[int]]:
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise C.GamekitError("READBACK_MISMATCH", "output is not a RIFF WAVE")
    pos = 12
    fmt = None
    pcm = None
    while pos + 8 <= len(data):
        tag = data[pos : pos + 4]
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        start = pos + 8
        if start + size > len(data):
            raise C.GamekitError("READBACK_MISMATCH", "wav chunk overruns the file")
        chunk = data[start : start + size]
        pos = start + size
        if size & 1 and pos < len(data):
            pos += 1
        if tag == b"fmt " and fmt is None:
            fmt = chunk
        elif tag == b"data" and pcm is None:
            pcm = chunk
    if fmt is None or pcm is None or len(fmt) < 16:
        raise C.GamekitError("READBACK_MISMATCH", "wav is missing fmt or data")
    audio_format, channels, rate, _byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", fmt, 0)
    if (audio_format, channels, bits, block_align) != (1, 1, 16, 2):
        raise C.GamekitError("READBACK_MISMATCH", "wav is not mono 16-bit PCM")
    if len(pcm) % 2:
        raise C.GamekitError("READBACK_MISMATCH", "wav data length is odd")
    raw = array.array("h")
    raw.frombytes(pcm)
    if sys.byteorder != "little":
        raw.byteswap()
    return rate, list(raw)


def _params(
    preset_id: str,
    *,
    seed: int | None,
    sample_rate: int,
    duration: float | None,
    peak_dbfs: float,
) -> tuple[dict[str, Any], int, int, float, float, int]:
    row = _preset(preset_id)
    limits = _table()["limits"]
    if seed is None:
        seed = row["default_seed"]
    seed = _int(seed, "seed", limits["seed"]["min"], limits["seed"]["max"])
    if isinstance(sample_rate, bool) or sample_rate not in limits["sample_rates"]:
        _fail(f"sample_rate must be one of {limits['sample_rates']}")
    if duration is None:
        duration = float(row["duration"])
    duration = _num(duration, "duration", float(row["duration_min"]), float(row["duration_max"]))
    peak_dbfs = _num(peak_dbfs, "peak_dbfs", limits["peak_dbfs"]["min"], limits["peak_dbfs"]["max"])
    frames = int(round(duration * sample_rate))
    if frames < 16:
        _fail("duration is too short for this sample rate")
    return row, seed, sample_rate, duration, peak_dbfs, frames


def synthesize(
    preset: str,
    *,
    seed: int | None = None,
    sample_rate: int = 44100,
    duration: float | None = None,
    peak_dbfs: float = -6.0,
) -> tuple[bytes, dict[str, Any]]:
    """Return WAV bytes and a JSON-safe description. Does not touch the disk."""
    row, used_seed, rate, requested, target_peak, frames = _params(
        preset, seed=seed, sample_rate=sample_rate, duration=duration, peak_dbfs=peak_dbfs
    )
    codes = _quantize(_render(row["id"], frames, rate, used_seed), target_peak)
    if codes[0] != 0 or codes[-1] != 0:
        _fail("synthesis fade did not reach silence at the ends")
    measured = _peak_dbfs(codes)
    if measured > target_peak + 0.2:
        _fail(f"synthesis peak {measured} dBFS is louder than the requested {target_peak} dBFS")
    data = _encode_wav(codes, rate)
    if len(data) > _table()["limits"]["max_bytes"]:
        _fail(f"wav is larger than {_table()['limits']['max_bytes']} bytes", "BAD_REQUEST")
    meta = _meta(row, used_seed, rate, requested, frames, target_peak, measured, data, codes)
    held = meta.pop("_codes")
    decoded_rate, decoded = _decode_wav(data)
    if decoded_rate != rate or decoded != held:
        _fail("internal wav decode did not match the PCM")
    return data, meta


def _meta(
    row: dict[str, Any],
    seed: int,
    rate: int,
    requested: float,
    frames: int,
    target_peak: float,
    measured: float,
    data: bytes,
    codes: list[int],
) -> dict[str, Any]:
    parameters = {
        "preset": row["id"],
        "seed": seed,
        "sample_rate": rate,
        "requested_duration_seconds": requested,
        "frames": frames,
        "peak_dbfs": target_peak,
        "channels": 1,
        "bits_per_sample": 16,
    }
    return {
        "preset": row["id"],
        "description": row["description"],
        "seed": seed,
        "sample_rate": rate,
        "channels": 1,
        "bits_per_sample": 16,
        "encoding": "pcm_s16le",
        "requested_duration_seconds": requested,
        "duration_seconds": round(frames / float(rate), 6),
        "frames": frames,
        "peak_dbfs": measured,
        "headroom_db": round(-measured, 4),
        "target_peak_dbfs": target_peak,
        "sha256": C.sha256_bytes(data),
        "bytes": len(data),
        "parameters": parameters,
        "provenance": {
            "generator": "studio.gamekit.sfx",
            "version": SYNTH_VERSION,
            "method": "deterministic_pcm_s16le",
            "preset": row["id"],
            "seed": seed,
            "parameters": parameters,
            "license": None,
            "recorded": False,
            "foley": False,
            "origin": "original synthetic game-stylized prototype from this tool, not a recording",
        },
        "_codes": codes,
    }


def _output_path(out: str | Path) -> Path:
    try:
        raw = Path(out)
    except TypeError as exc:
        raise C.GamekitError("BAD_PATH", "output path is not a path") from exc
    if not raw.is_absolute():
        raise C.GamekitError("BAD_PATH", "output path must be absolute")
    absolute = Path(os.path.abspath(str(raw)))
    parts = [part.lower() for part in absolute.parts]
    for blocked in _BLOCKED_DIRS:
        if blocked in parts:
            raise C.GamekitError("FORBIDDEN_PATH", f"{blocked} is outside this tool's write scope")
    reason = C.forbidden_reason(absolute)
    if reason:
        raise C.GamekitError("FORBIDDEN_PATH", reason)
    resolved = C.refuse_unsafe_host_path(absolute, what="sfx output")
    if resolved.suffix.lower() != ".wav":
        raise C.GamekitError("BAD_PATH", "output path must end in .wav")
    for project in C.list_projects():
        root = Path(os.path.abspath(str(project.root)))
        if C.is_within(resolved, root):
            raise C.GamekitError("FORBIDDEN_PATH", f"sfx output must stay outside registered project {project.project_id}")
    if not resolved.parent.is_dir():
        raise C.GamekitError("BAD_PATH", "output directory does not exist")
    return resolved


def _readback(path: Path, data: bytes, codes: list[int], rate: int) -> dict[str, Any]:
    got = path.read_bytes()
    if got != data or C.sha256_bytes(got) != C.sha256_bytes(data):
        raise C.GamekitError("READBACK_MISMATCH", "output bytes do not match the wav that was written")
    got_rate, got_codes = _decode_wav(got)
    if got_rate != rate or got_codes != codes:
        raise C.GamekitError("READBACK_MISMATCH", "decoded PCM does not match the synthesized samples")
    checks = M.inspect_media(got, ".wav")
    peak = checks.get("peak_dbfs")
    if checks.get("clipping") is True or not isinstance(peak, (int, float)) or isinstance(peak, bool) or peak >= -0.1:
        raise C.GamekitError("READBACK_MISMATCH", "decoded wav is clipping or has no peak under -0.1 dBFS")
    return checks


def _rollback(path: Path, previous: bytes | None) -> None:
    if previous is None:
        if path.is_file():
            path.unlink()
        return
    C.atomic_write_bytes(path, previous)


def generate(
    out: str | Path,
    preset: str,
    *,
    seed: int | None = None,
    sample_rate: int = 44100,
    duration: float | None = None,
    peak_dbfs: float = -6.0,
    replace: bool = False,
) -> dict[str, Any]:
    """Write one deterministic WAV. Refuses registered projects, links, and overwrite."""
    if not isinstance(replace, bool):
        _fail("replace must be a boolean")
    # Reject a bad preset before the overwrite check, so an existing file is not reported as a conflict.
    _params(preset, seed=seed, sample_rate=sample_rate, duration=duration, peak_dbfs=peak_dbfs)
    path = _output_path(out)
    max_bytes = _table()["limits"]["max_bytes"]
    previous: bytes | None = None
    if path.exists():
        if not path.is_file():
            _fail("output path exists and is not a file")
        if path.stat().st_size > max_bytes:
            _fail("existing file is larger than the wav size cap", "BAD_REQUEST")
        if not replace:
            raise C.GamekitError("CONFLICT", f"{path} already exists; pass --replace to overwrite")
        previous = path.read_bytes()
    data, meta = synthesize(preset, seed=seed, sample_rate=sample_rate, duration=duration, peak_dbfs=peak_dbfs)
    _decoded_rate, codes = _decode_wav(data)
    if len(data) > max_bytes:
        _fail(f"wav is larger than {max_bytes} bytes", "BAD_REQUEST")
    try:
        C.atomic_write_bytes(path, data)
        checks = _readback(path, data, codes, meta["sample_rate"])
    except C.GamekitError:
        try:
            _rollback(path, previous)
        except Exception as exc:
            raise C.GamekitError(
                "STATE_CORRUPT", f"output readback failed and the previous bytes could not be restored: {exc}"
            ) from exc
        raise
    meta.update({
        "ok": True,
        "kind": "sfx.generate",
        "path": str(path),
        "replaced": previous is not None,
        "readback": "DECODE_SHA_MATCH",
        "checks": checks,
        "import_via": {
            "command": "hh asset add",
            "reason": "This file stays outside registered projects. Copy it into a game only with hh asset add so the ledger, checkpoint, and Godot import stay in that transaction.",
            "suggested_dest": f"res://assets/sfx/{meta['preset']}.wav",
            "license_note": "This tool does not assign a license. Do not pass CC0-1.0 unless the owner has a real CC0 dedication. self-made requires a real author name.",
        },
    })
    return meta


def presets() -> dict[str, Any]:
    table = _table()
    return {
        "ok": True,
        "kind": "sfx.presets",
        "schema": SCHEMA,
        "version": SYNTH_VERSION,
        "origin": table["origin"],
        "license": None,
        "recorded": False,
        "foley": False,
        "limits": table["limits"],
        "presets": table["presets"],
        "import_via": "hh asset add",
    }


def _cmd_presets(_a: argparse.Namespace) -> dict[str, Any]:
    return presets()


def _cmd_generate(a: argparse.Namespace) -> dict[str, Any]:
    return generate(
        a.out,
        a.preset,
        seed=a.seed,
        sample_rate=a.sample_rate,
        duration=a.duration,
        peak_dbfs=a.peak_dbfs,
        replace=bool(a.replace),
    )


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("sfx", help="list or generate synthetic game-stylized WAV presets")
    commands = parser.add_subparsers(dest="action", required=True)
    listed = commands.add_parser("presets", help="list deterministic synthetic presets and their limits")
    listed.set_defaults(func=_cmd_presets)
    write = commands.add_parser("generate", help="write one deterministic mono 16-bit WAV outside any registered project")
    write.add_argument("--preset", required=True, help="ui_click, pickup, jump, impact, or explosion")
    write.add_argument("--out", required=True, help="absolute .wav path, outside registered projects")
    write.add_argument("--seed", type=int, default=None)
    write.add_argument("--sample-rate", type=int, default=44100)
    write.add_argument("--duration", type=float, default=None, help="seconds, inside that preset's range")
    write.add_argument("--peak-dbfs", type=float, default=-6.0, help="target peak, from -24 to -1")
    write.add_argument("--replace", action="store_true", help="overwrite an existing wav")
    write.set_defaults(func=_cmd_generate)

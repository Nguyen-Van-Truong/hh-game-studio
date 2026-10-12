"""W7 selftest: license gate, PNG/WAV/GLB intake, Godot import, credits, verify, replay."""

from __future__ import annotations

import array
import json
import math
import struct
import zlib
from pathlib import Path

from .. import asset as A
from .. import common as C
from . import Ctx

AUTHOR = "Kit Author"


def png_rgb(width: int, height: int, color: tuple[int, int, int] = (20, 40, 80)) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = (b"\x00" + bytes(color) * width) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def _wav_pcm(frames: bytes, rate: int, channels: int, bits: int) -> bytes:
    block = channels * (bits // 8)
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * block, block, bits)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(frames)) + frames
    return b"RIFF" + struct.pack("<I", len(body)) + body


def sine_wav() -> bytes:
    """1 s, 1 kHz, 48 kHz, 16-bit mono, peak -20 dBFS."""
    rate = 48000
    amp = 10 ** (-20 / 20)
    raw = array.array("h", [0]) * rate
    for i in range(rate):
        v = int(round(amp * math.sin(2 * math.pi * 1000 * i / rate) * 32768.0))
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        raw[i] = v
    return _wav_pcm(raw.tobytes(), rate, 1, 16)


def silence_wav() -> bytes:
    return _wav_pcm(b"\x00\x00" * 48000, 48000, 1, 16)


def triangle_glb() -> bytes:
    """One indexed triangle. POSITION min/max is the unit right triangle on z=0."""
    positions = struct.pack("<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    indices = struct.pack("<3H", 0, 1, 2)
    binary = positions + indices
    doc = {
        "asset": {"version": "2.0", "generator": "hh-gamekit"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "Tri"}],
        "meshes": [{"name": "Tri", "primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "mode": 4}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
             "min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 0.0]},
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(positions), "target": 34962},
            {"buffer": 0, "byteOffset": len(positions), "byteLength": len(indices), "target": 34963},
        ],
        "buffers": [{"byteLength": len(binary)}],
    }
    payload = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    blob = binary + b"\x00" * ((4 - len(binary) % 4) % 4)
    chunks = struct.pack("<II", len(payload), 0x4E4F534A) + payload
    chunks += struct.pack("<II", len(blob), 0x004E4942) + blob
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def _sidecar_ok(project: C.Project, res: str) -> bool:
    side = Path(str(project.res_to_path(res)) + ".import")
    if not side.is_file():
        return False
    body = side.read_bytes()
    return b"importer" in body or b"remap" in body


def run(ctx: Ctx) -> None:
    project = ctx.project("gk-assets", {}, main_scene=None)
    src = ctx.root / "src"
    src.mkdir()
    (src / "hero.png").write_bytes(png_rgb(64, 32))
    (src / "tone.wav").write_bytes(sine_wav())
    (src / "tri.glb").write_bytes(triangle_glb())

    png_r = ctx.guard("add png", lambda: A.add(
        project, src / "hero.png", "res://assets/hero.png", "CC0-1.0", AUTHOR,
        command_id="w7.png.1", ai_generated=True))
    wav_r = ctx.guard("add wav", lambda: A.add(
        project, src / "tone.wav", "res://assets/tone.wav", "CC0-1.0", AUTHOR,
        command_id="w7.wav.1", source_url="https://example.com/tone"))
    glb_r = ctx.guard("add glb", lambda: A.add(
        project, src / "tri.glb", "res://assets/tri.glb", "CC0-1.0", AUTHOR,
        command_id="w7.glb.1"))
    ctx.check(
        "three adds committed",
        all(r is not None and r.get("status") == "COMMITTED" and r.get("ok") is True for r in (png_r, wav_r, glb_r)),
    )

    ledger_path = project.res_to_path("res://hh_assets.json")
    ledger = C.read_json(ledger_path) if ledger_path.is_file() else {"assets": []}
    assets = ledger.get("assets") or []
    by = {a.get("res"): a for a in assets if isinstance(a, dict)}
    ctx.check("ledger has 3 entries", len(assets) == 3, count=len(assets))
    png_checks = (by.get("res://assets/hero.png") or {}).get("checks") or {}
    ctx.check("png 64x32", png_checks.get("width") == 64 and png_checks.get("height") == 32, checks=png_checks)
    wav_checks = (by.get("res://assets/tone.wav") or {}).get("checks") or {}
    peak = wav_checks.get("peak_dbfs")
    lufs = wav_checks.get("integrated_lufs")
    ctx.check(
        "wav peak about -20 dBFS",
        isinstance(peak, (int, float)) and abs(float(peak) - (-20.0)) <= 0.2,
        peak=peak,
    )
    ctx.check(
        "wav lufs about -23",
        isinstance(lufs, (int, float)) and abs(float(lufs) - (-23.0)) <= 1.5,
        lufs=lufs,
    )
    glb_checks = (by.get("res://assets/tri.glb") or {}).get("checks") or {}
    ctx.check("glb triangles == 1", glb_checks.get("triangles") == 1, triangles=glb_checks.get("triangles"),
              vertices=glb_checks.get("vertices"))
    for res in ("res://assets/hero.png", "res://assets/tone.wav", "res://assets/tri.glb"):
        ctx.check(f"godot imported {res}", _sidecar_ok(project, res))

    nc_dest = project.res_to_path("res://assets/nc.png")
    ctx.expect_error(
        "CC-BY-NC-4.0 rejected",
        "LICENSE_REJECTED",
        A.add,
        project,
        src / "hero.png",
        "res://assets/nc.png",
        "CC-BY-NC-4.0",
        AUTHOR,
        command_id="w7.nc.1",
    )
    ctx.check("nc dest was not written", not nc_dest.exists())
    after_nc = C.read_json(ledger_path) if ledger_path.is_file() else {"assets": []}
    ctx.check("ledger still 3 after reject", len(after_nc.get("assets") or []) == 3)

    cred = ctx.guard("credits", lambda: A.credits(project, "w7.credits.1"))
    credits_path = project.res_to_path("res://CREDITS.md")
    text = credits_path.read_text(encoding="utf-8") if credits_path.is_file() else ""
    ctx.check("credits committed", cred is not None and cred.get("status") == "COMMITTED")
    ctx.check(
        "credits contain the author",
        AUTHOR in text and "AI-generated content" in text and "https://example.com/tone" in text,
        sample=text[:500],
    )

    ver = ctx.guard("verify", lambda: A.verify(project))
    ctx.check("verify passes", ver is not None and ver.get("ok") is True,
              problems=None if ver is None else ver.get("problems"),
              untracked=None if ver is None else ver.get("untracked"))

    target = project.res_to_path("res://assets/hero.png")
    blob = bytearray(target.read_bytes())
    blob[len(blob) // 2] ^= 0x5A
    tampered = bytes(blob)
    target.write_bytes(tampered)
    ver2 = A.verify(project)
    ctx.check(
        "tamper makes verify fail",
        ver2.get("ok") is False and any("hero.png" in p for p in ver2.get("problems", [])),
        problems=ver2.get("problems"),
    )

    if png_r is not None:
        again = A.add(
            project, src / "hero.png", "res://assets/hero.png", "CC0-1.0", AUTHOR,
            command_id="w7.png.1", ai_generated=True)
        ctx.check(
            "same command_id replays",
            again.get("replayed") is True and again.get("sha256") == png_r.get("sha256"),
        )
        ctx.check("replay did not rewrite the tampered file", target.read_bytes() == tampered)
        ctx.expect_error(
            "same command_id different request is CONFLICT",
            "CONFLICT",
            A.add,
            project,
            src / "hero.png",
            "res://assets/hero.png",
            "CC0-1.0",
            AUTHOR,
            command_id="w7.png.1",
            ai_generated=True,
            notes="changed",
        )
    else:
        ctx.check("same command_id replays", False, detail="png add did not commit")

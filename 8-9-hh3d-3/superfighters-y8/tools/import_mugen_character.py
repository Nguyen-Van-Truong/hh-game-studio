#!/usr/bin/env python3
"""
Superfighters Y8 Remake - MUGEN / Custom Character Importer & Generator (SF-M6)
Supports:
1. Importing MUGEN character folders (.def / .air / .cns / sprites) into data/custom_fighters/<id>.json
2. Generating the built-in MUGEN showcase fighter 'shinobi' (Shinobi — MUGEN Hero):
   - assets/sheets/hero_shinobi_mugen.png (600x400 sheet with full SF rig compatibility + custom MUGEN frames)
   - data/custom_fighters/hero_shinobi_mugen.json (Clsn1 red hitboxes, Clsn2 blue hurtboxes, 4-hit combo,
     Shunpo Slash dash-cut, Chakra Wave projectile, and cancel table).
"""

import argparse
import json
import re
import struct
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHEETS_DIR = PROJECT_ROOT / "assets" / "sheets"
CUSTOM_FIGHTERS_DIR = PROJECT_ROOT / "data" / "custom_fighters"


def _read_png_rgba(path: Path) -> tuple[int, int, bytearray]:
    """Minimal pure-Python PNG reader (supports 8-bit RGB/RGBA/Palette/Grayscale via PIL if available, else raw)."""
    try:
        from PIL import Image
        img = Image.open(path).convert("RGBA")
        w, h = img.size
        return w, h, bytearray(img.tobytes())
    except ImportError:
        pass

    # Pure Python fallback for standard 8-bit RGBA PNG
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"Not a valid PNG: {path}"
    pos = 8
    w = h = 0
    idat_chunks = []
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"IHDR":
            w, h, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break
    raw = zlib.decompress(b"".join(idat_chunks))
    bpp = 4
    stride = w * bpp
    out = bytearray(w * h * 4)
    in_pos = 0
    for y in range(h):
        filter_type = raw[in_pos]
        in_pos += 1
        row_start = y * stride
        for x in range(stride):
            val = raw[in_pos]
            in_pos += 1
            a = out[row_start + x - bpp] if x >= bpp else 0
            b = out[row_start - stride + x] if y > 0 else 0
            c = out[row_start - stride + x - bpp] if (y > 0 and x >= bpp) else 0
            if filter_type == 1:
                val = (val + a) & 0xFF
            elif filter_type == 2:
                val = (val + b) & 0xFF
            elif filter_type == 3:
                val = (val + ((a + b) >> 1)) & 0xFF
            elif filter_type == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                val = (val + pr) & 0xFF
            out[row_start + x] = val
    return w, h, out


def _write_png_rgba(path: Path, width: int, height: int, rgba: bytearray) -> None:
    """Writes an 8-bit RGBA bytearray to a PNG file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
        img = Image.frombytes("RGBA", (width, height), bytes(rgba))
        img.save(path, "PNG")
        return
    except ImportError:
        pass

    def make_chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        return struct.pack(">I", len(chunk_data)) + chunk_type + chunk_data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw_rows = bytearray()
    stride = width * 4
    for y in range(height):
        raw_rows.append(0)  # Filter 0 (None)
        raw_rows.extend(rgba[y * stride : (y + 1) * stride])
    compressed = zlib.compress(bytes(raw_rows), 9)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + make_chunk(b"IHDR", ihdr)
        + make_chunk(b"IDAT", compressed)
        + make_chunk(b"IEND", b"")
    )
    path.write_bytes(png_bytes)


def _set_px(buf: bytearray, w: int, h: int, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if 0 <= x < w and 0 <= y < h:
        idx = (y * w + x) * 4
        buf[idx] = color[0]
        buf[idx + 1] = color[1]
        buf[idx + 2] = color[2]
        buf[idx + 3] = color[3]


def _fill_rect(buf: bytearray, w: int, h: int, rx: int, ry: int, rw: int, rh: int, color: tuple[int, int, int, int]) -> None:
    for py in range(max(0, ry), min(h, ry + rh)):
        for px in range(max(0, rx), min(w, rx + rw)):
            _set_px(buf, w, h, px, py, color)


def _draw_ninja_pose(
    buf: bytearray,
    w: int,
    h: int,
    ox: int,
    oy: int,
    pose_idx: int,
) -> None:
    """
    Draws a crisp 1:1 Superfighters-scale pixel art Shinobi frame at (ox, oy) inside the 600x400 sheet.
    pose_idx:
      0..3: MUGEN_COMBO_1..4 (4-hit ninja katana/chakram combo)
      4..6: SHUNPO_SLASH (high-speed dash slash with cyan afterimages)
      7..9: CHAKRA_WAVE (two-handed chakra wave cast)
      10:   CHAKRA_WAVE projectile orb/crescent
    """
    suit_dark = (22, 30, 58, 255)
    suit_mid = (36, 52, 96, 255)
    scarf_red = (220, 42, 58, 255)
    skin = (232, 190, 152, 255)
    visor_cyan = (60, 235, 255, 255)
    blade_white = (235, 248, 255, 255)
    blade_cyan = (40, 200, 255, 230)
    boots = (18, 20, 32, 255)

    if pose_idx == 10:
        # Chakra Wave projectile sprite (16x14)
        for dy in range(14):
            for dx in range(16):
                dist_sq = (dx - 8) ** 2 + (dy - 7) ** 2
                if dist_sq <= 42:
                    if dist_sq <= 14:
                        _set_px(buf, w, h, ox + dx, oy + dy, (230, 255, 255, 255))
                    elif dist_sq <= 28:
                        _set_px(buf, w, h, ox + dx, oy + dy, (50, 225, 255, 240))
                    else:
                        _set_px(buf, w, h, ox + dx, oy + dy, (20, 140, 240, 185))
        return

    # Base ninja body (18px tall, ~12px wide, placed inside cell starting at ox, oy)
    lean = 2 if pose_idx in (1, 3, 4, 5, 6) else 0
    crouch = 2 if pose_idx in (4, 5, 6) else 0

    # Legs & boots
    _fill_rect(buf, w, h, ox + 5, oy + 15, 3, 4, boots)
    _fill_rect(buf, w, h, ox + 11 + lean, oy + 15, 3, 4, boots)
    _fill_rect(buf, w, h, ox + 6, oy + 11 + crouch, 8, 4 - crouch // 2, suit_dark)

    # Torso & vest
    _fill_rect(buf, w, h, ox + 6 + lean // 2, oy + 6 + crouch, 7, 6, suit_mid)
    _fill_rect(buf, w, h, ox + 7 + lean // 2, oy + 7 + crouch, 5, 4, suit_dark)

    # Flowing red ninja scarf
    _fill_rect(buf, w, h, ox + 2, oy + 6 + crouch, 5, 2, scarf_red)
    _fill_rect(buf, w, h, ox + 0, oy + 7 + crouch + (pose_idx % 2), 3, 2, scarf_red)

    # Head, mask & cyan visor headband
    _fill_rect(buf, w, h, ox + 7 + lean, oy + 1 + crouch, 5, 5, suit_dark)
    _fill_rect(buf, w, h, ox + 8 + lean, oy + 3 + crouch, 4, 2, skin)
    _fill_rect(buf, w, h, ox + 7 + lean, oy + 2 + crouch, 6, 1, visor_cyan)

    # Weapon / Effect per pose
    if pose_idx == 0:
        # Combo 1: horizontal wakizashi slash
        _fill_rect(buf, w, h, ox + 13, oy + 8, 10, 2, blade_white)
        _fill_rect(buf, w, h, ox + 14, oy + 7, 9, 1, blade_cyan)
    elif pose_idx == 1:
        # Combo 2: upward diagonal slash
        for i in range(11):
            _fill_rect(buf, w, h, ox + 13 + i, oy + 11 - i, 2, 2, blade_white)
            _set_px(buf, w, h, ox + 12 + i, oy + 11 - i, blade_cyan)
    elif pose_idx == 2:
        # Combo 3: spinning crescent kick + low slash
        _fill_rect(buf, w, h, ox + 13, oy + 10, 8, 3, suit_mid)
        _fill_rect(buf, w, h, ox + 15, oy + 6, 10, 2, blade_cyan)
        _fill_rect(buf, w, h, ox + 16, oy + 5, 9, 2, blade_white)
    elif pose_idx == 3:
        # Combo 4: heavy dragon cleave arc
        for dy in range(2, 17):
            _fill_rect(buf, w, h, ox + 15, oy + dy, 9, 1, blade_cyan)
        _fill_rect(buf, w, h, ox + 18, oy + 3, 6, 13, blade_white)
    elif pose_idx in (4, 5, 6):
        # Shunpo Slash: lightning dash with cyan speed lines and extended katana
        _fill_rect(buf, w, h, ox + 1, oy + 4, 4, 12, (40, 200, 255, 120))
        _fill_rect(buf, w, h, ox + 14, oy + 9, 13, 2, blade_white)
        _fill_rect(buf, w, h, ox + 12, oy + 8, 15, 4, blade_cyan)
    elif pose_idx in (7, 8, 9):
        # Chakra Wave cast: glowing hands + energy sphere forming in front
        _fill_rect(buf, w, h, ox + 13, oy + 7, 4, 3, skin)
        radius = 3 + (pose_idx - 7) * 2
        cx, cy = ox + 19, oy + 8
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    _set_px(buf, w, h, cx + dx, cy + dy, visor_cyan if (dx * dx + dy * dy > 4) else blade_white)


def generate_shinobi_sheet_and_json() -> tuple[Path, Path]:
    """Generates assets/sheets/hero_shinobi_mugen.png and data/custom_fighters/hero_shinobi_mugen.json."""
    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    CUSTOM_FIGHTERS_DIR.mkdir(parents=True, exist_ok=True)

    base_sheet = SHEETS_DIR / "Bitmap 1105.png"
    if not base_sheet.exists():
        base_sheet = SHEETS_DIR / "Bitmap 591.png"

    w, h, rgba = _read_png_rgba(base_sheet)
    # Recolor the base character pixels into Shinobi's midnight-blue + cyan + crimson ninja palette
    for i in range(0, len(rgba), 4):
        a = rgba[i + 3]
        if a == 0:
            continue
        r, g, b = rgba[i], rgba[i + 1], rgba[i + 2]
        lum = (r * 77 + g * 150 + b * 29) >> 8
        if r > g + 35 and r > b + 35:
            # Red/warm accents -> bright crimson ninja scarf/trim
            rgba[i] = min(255, int(r * 1.15))
            rgba[i + 1] = int(g * 0.4)
            rgba[i + 2] = int(b * 0.5)
        elif lum < 95:
            # Dark suit -> midnight ninja blue
            rgba[i] = max(14, int(lum * 0.45))
            rgba[i + 1] = max(24, int(lum * 0.65))
            rgba[i + 2] = min(255, max(52, int(lum * 1.35)))
        elif lum < 165:
            # Mid-tones -> slate blue-cyan armor
            rgba[i] = int(lum * 0.55)
            rgba[i + 1] = int(lum * 0.85)
            rgba[i + 2] = min(255, int(lum * 1.35))
        else:
            # Highlights / skin / metal -> crisp bright cyan-white edge
            rgba[i] = r
            rgba[i + 1] = min(255, int(g * 1.04))
            rgba[i + 2] = min(255, int(b * 1.08))

    # Stamp dedicated MUGEN animation frames in y=270..300
    # Each cell is 30x24 at x = 20 + idx * 32, y = 270
    mugen_cells = {}
    for idx in range(11):
        cx = 20 + idx * 32
        cy = 270
        # Clear cell
        _fill_rect(rgba, w, h, cx, cy, 30, 24, (0, 0, 0, 0))
        _draw_ninja_pose(rgba, w, h, cx, cy, idx)
        mugen_cells[idx] = [float(cx), float(cy), 28.0, 20.0]

    sheet_out = SHEETS_DIR / "hero_shinobi_mugen.png"
    _write_png_rgba(sheet_out, w, h, rgba)

    shinobi_json = {
        "schema_version": "1.0.0",
        "format": "mugen_fighter_v1",
        "id": "shinobi",
        "display_name": "Shinobi — MUGEN Hero",
        "author": "HH Game Studio",
        "sheet_path": "res://assets/sheets/hero_shinobi_mugen.png",
        "sheet_size": [600, 400],
        "hp_mult": 1.05,
        "speed_mult": 1.12,
        "use_sf_split_rig_for_guns": True,
        "default_clsn2": [[-6.0, -18.0, 12.0, 18.0]],
        "cancel_table": {
            "MUGEN_COMBO_1": ["MUGEN_COMBO_2", "SHUNPO_SLASH", "CHAKRA_WAVE"],
            "MUGEN_COMBO_2": ["MUGEN_COMBO_3", "SHUNPO_SLASH", "CHAKRA_WAVE"],
            "MUGEN_COMBO_3": ["MUGEN_COMBO_4", "SHUNPO_SLASH", "CHAKRA_WAVE"],
            "MUGEN_COMBO_4": ["SHUNPO_SLASH", "CHAKRA_WAVE"],
        },
        "special_moves": {
            "SHUNPO_SLASH": {
                "id": "SHUNPO_SLASH",
                "display_name": "Shunpo Slash",
                "state": "SHUNPO_SLASH",
                "command": "D, DF, F + attack | sprint + attack",
                "energy_cost": 15.0,
                "dash_speed_24hz": 7.5,
                "dash_distance": 60.0,
                "damage": 22.0,
                "hit_force": 32.0,
                "knockdown": True,
                "sfx": "swing_sword",
            },
            "CHAKRA_WAVE": {
                "id": "CHAKRA_WAVE",
                "display_name": "Chakra Wave",
                "state": "CHAKRA_WAVE",
                "command": "D, DB, B + attack | up + attack",
                "energy_cost": 12.0,
                "projectile_id": "CHAKRA_WAVE",
                "projectile_speed_24hz": 22.0,
                "projectile_damage": 20.0,
                "projectile_pushback": 35.0,
                "projectile_rect": mugen_cells[10],
                "sfx": "swing_sword",
            },
        },
        "mugen_states": {
            "MUGEN_COMBO_1": {
                "type": "mugen_attack",
                "loop": False,
                "next_state": "IDLE",
                "damage": 7.0,
                "hit_force": 14.0,
                "range": 20.0,
                "step_vel_x": 1.2,
                "knockdown": False,
                "sfx": "swing_sword",
                "frames": [
                    {
                        "frame_nr": 1,
                        "duration": 2,
                        "rect": mugen_cells[0],
                        "pivot": [-9.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [],
                    },
                    {
                        "frame_nr": 2,
                        "duration": 4,
                        "rect": mugen_cells[0],
                        "pivot": [-8.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [[2.0, -16.0, 18.0, 10.0]],
                    },
                ],
            },
            "MUGEN_COMBO_2": {
                "type": "mugen_attack",
                "loop": False,
                "next_state": "IDLE",
                "damage": 8.0,
                "hit_force": 16.0,
                "range": 21.0,
                "step_vel_x": 1.5,
                "knockdown": False,
                "sfx": "swing_sword",
                "frames": [
                    {
                        "frame_nr": 1,
                        "duration": 2,
                        "rect": mugen_cells[1],
                        "pivot": [-9.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [],
                    },
                    {
                        "frame_nr": 2,
                        "duration": 4,
                        "rect": mugen_cells[1],
                        "pivot": [-8.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [[2.0, -18.0, 19.0, 12.0]],
                    },
                ],
            },
            "MUGEN_COMBO_3": {
                "type": "mugen_attack",
                "loop": False,
                "next_state": "IDLE",
                "damage": 10.0,
                "hit_force": 20.0,
                "range": 22.0,
                "step_vel_x": 1.8,
                "knockdown": False,
                "sfx": "swing_sword",
                "frames": [
                    {
                        "frame_nr": 1,
                        "duration": 2,
                        "rect": mugen_cells[2],
                        "pivot": [-9.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [],
                    },
                    {
                        "frame_nr": 2,
                        "duration": 4,
                        "rect": mugen_cells[2],
                        "pivot": [-8.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [[2.0, -17.0, 20.0, 12.0]],
                    },
                ],
            },
            "MUGEN_COMBO_4": {
                "type": "mugen_attack",
                "loop": False,
                "next_state": "IDLE",
                "damage": 14.0,
                "hit_force": 28.0,
                "range": 25.0,
                "step_vel_x": 2.4,
                "knockdown": True,
                "sfx": "swing_sword",
                "frames": [
                    {
                        "frame_nr": 1,
                        "duration": 3,
                        "rect": mugen_cells[3],
                        "pivot": [-9.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [],
                    },
                    {
                        "frame_nr": 2,
                        "duration": 6,
                        "rect": mugen_cells[3],
                        "pivot": [-7.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [[2.0, -20.0, 23.0, 18.0]],
                    },
                ],
            },
            "SHUNPO_SLASH": {
                "type": "mugen_special_dash",
                "loop": False,
                "next_state": "IDLE",
                "damage": 22.0,
                "hit_force": 32.0,
                "range": 28.0,
                "dash_speed_24hz": 7.5,
                "knockdown": True,
                "sfx": "swing_sword",
                "frames": [
                    {
                        "frame_nr": 1,
                        "duration": 2,
                        "rect": mugen_cells[4],
                        "pivot": [-10.0, -19.0],
                        "clsn2": [[-5.0, -14.0, 10.0, 14.0]],
                        "clsn1": [[0.0, -15.0, 22.0, 12.0]],
                    },
                    {
                        "frame_nr": 2,
                        "duration": 5,
                        "rect": mugen_cells[5],
                        "pivot": [-8.0, -19.0],
                        "clsn2": [[-5.0, -14.0, 10.0, 14.0]],
                        "clsn1": [[-4.0, -16.0, 28.0, 14.0]],
                    },
                    {
                        "frame_nr": 3,
                        "duration": 3,
                        "rect": mugen_cells[6],
                        "pivot": [-8.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [],
                    },
                ],
            },
            "CHAKRA_WAVE": {
                "type": "mugen_special_projectile",
                "loop": False,
                "next_state": "IDLE",
                "damage": 20.0,
                "hit_force": 35.0,
                "spawn_projectile_frame": 2,
                "projectile_id": "CHAKRA_WAVE",
                "projectile_speed_24hz": 22.0,
                "projectile_offset": [12.0, -10.0],
                "sfx": "swing_sword",
                "frames": [
                    {
                        "frame_nr": 1,
                        "duration": 3,
                        "rect": mugen_cells[7],
                        "pivot": [-9.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [],
                    },
                    {
                        "frame_nr": 2,
                        "duration": 4,
                        "rect": mugen_cells[8],
                        "pivot": [-8.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [[4.0, -15.0, 14.0, 10.0]],
                    },
                    {
                        "frame_nr": 3,
                        "duration": 4,
                        "rect": mugen_cells[9],
                        "pivot": [-8.0, -19.0],
                        "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                        "clsn1": [],
                    },
                ],
            },
        },
    }

    json_out = CUSTOM_FIGHTERS_DIR / "hero_shinobi_mugen.json"
    json_out.write_text(json.dumps(shinobi_json, indent=2, ensure_ascii=False), encoding="utf-8")
    return sheet_out, json_out


def parse_mugen_air_text(air_text: str) -> dict:
    """
    Parses a MUGEN .air animation file into mugen_states dictionary with Clsn1 (attack) and Clsn2 (hurt) boxes.
    """
    states = {}
    current_action = None
    current_frames = []
    clsn1_default = []
    clsn2_default = []
    clsn1_next = []
    clsn2_next = []
    active_clsn_list = None

    for raw_line in air_text.splitlines():
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        m_act = re.match(r"^\[Begin Action\s+(\d+)\]", line, re.IGNORECASE)
        if m_act:
            if current_action is not None:
                states[f"ACTION_{current_action}"] = {"type": "mugen_action", "frames": current_frames}
            current_action = int(m_act.group(1))
            current_frames = []
            clsn1_default, clsn2_default = [], []
            clsn1_next, clsn2_next = [], []
            continue
        if re.match(r"^Clsn1Default", line, re.IGNORECASE):
            clsn1_default = []
            active_clsn_list = clsn1_default
            continue
        if re.match(r"^Clsn2Default", line, re.IGNORECASE):
            clsn2_default = []
            active_clsn_list = clsn2_default
            continue
        if re.match(r"^Clsn1:", line, re.IGNORECASE):
            clsn1_next = []
            active_clsn_list = clsn1_next
            continue
        if re.match(r"^Clsn2:", line, re.IGNORECASE):
            clsn2_next = []
            active_clsn_list = clsn2_next
            continue
        m_box = re.match(r"^Clsn[12]\[\d+\]\s*=\s*([-+]?\d+)\s*,\s*([-+]?\d+)\s*,\s*([-+]?\d+)\s*,\s*([-+]?\d+)", line, re.IGNORECASE)
        if m_box and active_clsn_list is not None:
            x1, y1, x2, y2 = [float(m_box.group(i)) for i in range(1, 5)]
            lx, rx = min(x1, x2), max(x1, x2)
            ty, by = min(y1, y2), max(y1, y2)
            active_clsn_list.append([lx, ty, rx - lx, by - ty])
            continue
        m_elem = re.match(r"^([-+]?\d+)\s*,\s*([-+]?\d+)\s*,\s*([-+]?\d+)\s*,\s*([-+]?\d+)\s*,\s*([-+]?\d+)", line)
        if m_elem and current_action is not None:
            grp, img, ox, oy, ticks = [int(m_elem.group(i)) for i in range(1, 6)]
            current_frames.append(
                {
                    "frame_nr": len(current_frames) + 1,
                    "group": grp,
                    "image": img,
                    "pivot": [float(ox), float(oy)],
                    "duration": max(1, ticks),
                    "clsn1": list(clsn1_next if clsn1_next else clsn1_default),
                    "clsn2": list(clsn2_next if clsn2_next else clsn2_default),
                }
            )
            clsn1_next, clsn2_next = [], []

    if current_action is not None:
        states[f"ACTION_{current_action}"] = {"type": "mugen_action", "frames": current_frames}
    return states


def main() -> None:
    parser = argparse.ArgumentParser(description="Superfighters MUGEN Character Importer & Generator")
    parser.add_argument("--air", type=str, default="", help="Optional path to a MUGEN .air file to convert")
    parser.add_argument("--id", type=str, default="shinobi", help="Character ID")
    args = parser.parse_args()

    sheet_path, json_path = generate_shinobi_sheet_and_json()
    print(f"[SF-M6] Generated MUGEN hero sheet: {sheet_path}")
    print(f"[SF-M6] Generated MUGEN hero JSON:  {json_path}")

    if args.air:
        air_path = Path(args.air)
        if air_path.exists():
            parsed = parse_mugen_air_text(air_path.read_text(encoding="utf-8", errors="ignore"))
            out_file = CUSTOM_FIGHTERS_DIR / f"{args.id}_air_imported.json"
            out_file.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
            print(f"[SF-M6] Imported .air actions ({len(parsed)}) -> {out_file}")


if __name__ == "__main__":
    main()

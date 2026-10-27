#!/usr/bin/env python3
"""
Builds the custom physics-first arena map "steel_harbor" ("STEEL HARBOR (NEW)")
with 100% pixel-accurate visual-to-physics alignment (0.0px discrepancy) and
compiles its definition into data/sf_compiled_maps.json.
"""

import json
import math
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = ROOT / "assets" / "maps"
JSON_PATH = ROOT / "data" / "sf_compiled_maps.json"

IMG_W = 800
IMG_H = 500
ORIGIN_X = -400.0
ORIGIN_Y = -240.0


def wx_to_px(wx: float) -> int:
    return int(round(wx - ORIGIN_X))


def wy_to_py(wy: float) -> int:
    return int(round(wy - ORIGIN_Y))


def wrect_to_prect(left: float, top: float, right: float, bottom: float):
    # Inclusive top-left to inclusive bottom-right for PIL rectangle
    return (wx_to_px(left), wy_to_py(top), wx_to_px(right) - 1, wy_to_py(bottom) - 1)


def draw_hazard_stripes(img: Image.Image, x0: int, y0: int, x1: int, y1: int, period: int = 8):
    px = img.load()
    for y in range(max(0, y0), min(IMG_H, y1)):
        for x in range(max(0, x0), min(IMG_W, x1)):
            if ((x + y) // (period // 2)) % 2 == 0:
                px[x, y] = (232, 182, 34, 255)
            else:
                px[x, y] = (28, 32, 38, 255)


def draw_concrete_slab(draw: ImageDraw.ImageDraw, img: Image.Image, left: float, top: float, right: float, bottom: float, hazard_left: bool = False, hazard_right: bool = False):
    x0, y0 = wx_to_px(left), wy_to_py(top)
    x1, y1 = wx_to_px(right), wy_to_py(bottom)
    # Main concrete body
    draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=(72, 79, 89, 255))
    # Top steel wear plate (exact top_y surface!)
    draw.rectangle((x0, y0, x1 - 1, min(y1 - 1, y0 + 2)), fill=(164, 176, 190, 255))
    draw.line((x0, y0, x1 - 1, y0), fill=(218, 228, 238, 255))
    # Sub-surface shadow & bottom steel trim
    if y1 - y0 >= 8:
        draw.line((x0, y0 + 3, x1 - 1, y0 + 3), fill=(44, 49, 58, 255))
        draw.rectangle((x0, max(y0 + 4, y1 - 3), x1 - 1, y1 - 1), fill=(46, 52, 60, 255))
    # Vertical expansion joints & rivets
    for sx in range(x0 + 24, x1 - 12, 32):
        draw.line((sx, y0 + 3, sx, y1 - 3), fill=(54, 60, 69, 255))
        draw.point((sx - 3, y0 + 5), fill=(112, 122, 134, 255))
        draw.point((sx + 3, y0 + 5), fill=(112, 122, 134, 255))
    # Hazard stripes at ledges
    if hazard_left:
        draw_hazard_stripes(img, x0, y0 + 1, min(x1, x0 + 14), min(y1, y0 + 6))
    if hazard_right:
        draw_hazard_stripes(img, max(x0, x1 - 14), y0 + 1, x1, min(y1, y0 + 6))


def draw_steel_catwalk(draw: ImageDraw.ImageDraw, img: Image.Image, left: float, top: float, right: float, bottom: float, hazard_right: bool = False, hazard_left: bool = False):
    x0, y0 = wx_to_px(left), wy_to_py(top)
    x1, y1 = wx_to_px(right), wy_to_py(bottom)
    # Exact 4px physical collision slab [y0 .. y1-1]
    draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=(116, 130, 146, 255))
    draw.line((x0, y0, x1 - 1, y0), fill=(214, 226, 240, 255))
    draw.line((x0, y1 - 1, x1 - 1, y1 - 1), fill=(52, 60, 70, 255))
    for rx in range(x0 + 4, x1 - 4, 8):
        draw.point((rx, y0 + 1), fill=(68, 78, 90, 255))
        draw.point((rx + 1, y0 + 1), fill=(68, 78, 90, 255))
    if hazard_left:
        draw_hazard_stripes(img, x0, y0 + 1, min(x1, x0 + 12), y1)
    if hazard_right:
        draw_hazard_stripes(img, max(x0, x1 - 12), y0 + 1, x1, y1)
    # Decorative visual support truss underneath (purely below y1 so it doesn't interfere with top surface y0)
    truss_h = 5
    draw.line((x0, y1 + truss_h, x1 - 1, y1 + truss_h), fill=(56, 65, 76, 220))
    for tx in range(x0, x1 - 8, 12):
        draw.line((tx, y1, tx + 6, y1 + truss_h), fill=(72, 82, 96, 210))
        draw.line((tx + 6, y1 + truss_h, min(x1 - 1, tx + 12), y1), fill=(72, 82, 96, 210))


def draw_ladder(draw: ImageDraw.ImageDraw, left: float, top: float, right: float, bottom: float):
    x0, y0 = wx_to_px(left), wy_to_py(top)
    x1, y1 = wx_to_px(right), wy_to_py(bottom)
    # Side rails
    draw.rectangle((x0 + 1, y0, x0 + 2, y1 - 1), fill=(156, 168, 182, 255))
    draw.rectangle((x1 - 3, y0, x1 - 2, y1 - 1), fill=(156, 168, 182, 255))
    draw.line((x0, y0, x0, y1 - 1), fill=(64, 72, 84, 255))
    draw.line((x1 - 1, y0, x1 - 1, y1 - 1), fill=(64, 72, 84, 255))
    # Top safety handrail caps
    draw.rectangle((x0, y0, x0 + 3, y0 + 2), fill=(232, 182, 34, 255))
    draw.rectangle((x1 - 4, y0, x1 - 1, y0 + 2), fill=(232, 182, 34, 255))
    # Horizontal rungs every 6px
    for ry in range(y0 + 3, y1 - 2, 6):
        draw.line((x0 + 3, ry, x1 - 4, ry), fill=(210, 220, 232, 255))
        draw.line((x0 + 3, ry + 1, x1 - 4, ry + 1), fill=(88, 98, 112, 255))


def draw_hatch_shaft(draw: ImageDraw.ImageDraw, left: float, top: float, right: float, bottom: float):
    """Draws an open vertical ladder hatch passage cut through a concrete/steel slab."""
    x0, y0 = wx_to_px(left), wy_to_py(top)
    x1, y1 = wx_to_px(right), wy_to_py(bottom)
    # Recessed dark shaft interior so players clearly see the slab is open
    draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=(18, 24, 34, 215))
    # Steel coaming trim plates lining the left and right walls of the hatch opening
    draw.rectangle((x0, y0, x0 + 1, y1 - 1), fill=(122, 134, 148, 255))
    draw.rectangle((x1 - 2, y0, x1 - 1, y1 - 1), fill=(122, 134, 148, 255))


def draw_hatch_grating(draw: ImageDraw.ImageDraw, left: float, top: float, right: float, bottom: float):
    """Draws a semi-open one-way (CLOUD) steel safety grating over a ladder hatch mouth."""
    x0, y0 = wx_to_px(left), wy_to_py(top)
    x1, y1 = wx_to_px(right), wy_to_py(bottom)
    # Top/bottom thin steel frame bars
    draw.line((x0, y0, x1 - 1, y0), fill=(224, 192, 68, 235))
    draw.line((x0, y1 - 1, x1 - 1, y1 - 1), fill=(68, 78, 92, 220))
    # Open grating bars every 4px so ladder rails/rungs remain clearly visible through the hatch
    for gx in range(x0 + 2, x1 - 2, 4):
        draw.line((gx, y0 + 1, gx, y1 - 2), fill=(148, 160, 176, 185))


def draw_portal_doorway(draw: ImageDraw.ImageDraw, left: float, top: float, right: float, bottom: float):
    """Draws an industrial transit doorway at a map portal entry/exit."""
    x0, y0 = wx_to_px(left), wy_to_py(top)
    x1, y1 = wx_to_px(right), wy_to_py(bottom)
    draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=(10, 14, 20, 255), outline=(112, 126, 142, 255))
    draw.rectangle((x0 + 1, y0 + 1, x1 - 2, y0 + 3), fill=(232, 182, 34, 255))
    draw.rectangle((x0 + 2, y0 + 4, x1 - 3, y1 - 1), fill=(16, 22, 32, 255))


def draw_stairs_45(draw: ImageDraw.ImageDraw, x_start: float, y_start: float, x_end: float, y_end: float):
    # Exact 1:1 45-degree staircase matching the slope polygon hypotenuse
    px0, py0 = wx_to_px(x_start), wy_to_py(y_start)
    px1, py1 = wx_to_px(x_end), wy_to_py(y_end)
    steps = 16
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps
        sx0 = int(round(px0 + (px1 - px0) * t0))
        sy0 = int(round(py0 + (py1 - py0) * t0))
        sx1 = int(round(px0 + (px1 - px0) * t1))
        sy1 = int(round(py0 + (py1 - py0) * t1))
        left_x = min(sx0, sx1)
        right_x = max(sx0, sx1)
        top_y = min(sy0, sy1)
        bot_y = max(sy0, sy1)
        # Step tread & stringer beam
        draw.rectangle((left_x, top_y, right_x, bot_y + 4), fill=(96, 108, 122, 255))
        draw.line((left_x, top_y, right_x, top_y), fill=(214, 226, 238, 255))
    # Heavy diagonal steel stringer underneath
    draw.line((px0, py0 + 4, px1, py1 + 4), fill=(142, 156, 172, 255), width=2)
    draw.line((px0, py0 + 7, px1, py1 + 7), fill=(52, 60, 72, 255), width=2)


def generate_layers():
    MAPS_DIR.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 1. BACKGROUND LAYER (steel_harbor_bg.png)
    # =========================================================================
    bg = Image.new("RGBA", (IMG_W, IMG_H), (12, 18, 28, 255))
    bg_draw = ImageDraw.Draw(bg)

    # Atmospheric night-harbor sky gradient
    for py in range(IMG_H):
        t = py / float(IMG_H)
        r = int(12 + 22 * (t ** 1.3))
        g = int(18 + 34 * (t ** 1.2))
        b = int(32 + 48 * t)
        bg_draw.line((0, py, IMG_W - 1, py), fill=(r, g, b, 255))

    # Distant moon & harbor haze
    moon_cx, moon_cy = wx_to_px(-180.0), wy_to_py(-136.0)
    for rad, alpha in [(42, 24), (28, 45), (18, 220)]:
        bg_draw.ellipse((moon_cx - rad, moon_cy - rad, moon_cx + rad, moon_cy + rad), fill=(224, 236, 248, alpha))

    # Distant harbor skyline & gantry cranes silhouette
    horizon_y = wy_to_py(76.0)
    silhouette_buildings = [
        (-350, -60, 44), (-295, -90, 52), (-230, -45, 38),
        (-155, -82, 48), (-85, -38, 36), (35, -74, 46),
        (95, -48, 38), (165, -96, 56), (235, -62, 44), (295, -80, 50),
    ]
    for bx, by_top, bw in silhouette_buildings:
        x0 = wx_to_px(bx)
        y0 = wy_to_py(by_top)
        bg_draw.rectangle((x0, y0, x0 + bw, horizon_y), fill=(18, 26, 38, 255))
        # Distant lit windows
        for wy in range(y0 + 6, horizon_y - 8, 8):
            for wx in range(x0 + 5, x0 + bw - 5, 7):
                if ((wx * 7 + wy * 13) % 5) == 0:
                    bg_draw.rectangle((wx, wy, wx + 2, wy + 3), fill=(218, 178, 88, 180))

    # Background structural steel columns & cross-bracing inside the harbor hangar
    pillar_xs = [-356, -236, -128, -48, 48, 128, 236, 336]
    ceil_py = wy_to_py(-172.0)
    bot_py = wy_to_py(210.0)
    for px_w in pillar_xs:
        px_i = wx_to_px(px_w)
        bg_draw.rectangle((px_i - 5, ceil_py, px_i + 5, bot_py), fill=(26, 34, 46, 255))
        bg_draw.line((px_i - 5, ceil_py, px_i - 5, bot_py), fill=(44, 56, 72, 255))
        bg_draw.line((px_i + 5, ceil_py, px_i + 5, bot_py), fill=(16, 22, 30, 255))
        for ry in range(ceil_py + 8, bot_py, 14):
            bg_draw.point((px_i - 3, ry), fill=(68, 82, 100, 255))
            bg_draw.point((px_i + 3, ry), fill=(68, 82, 100, 255))

    # Control tower rooms (Left Tower: x in [-356, -236], y in [-48, 12]; Right Tower: x in [236, 356], y in [-48, 12])
    for t_left, t_right in [(-356.0, -236.0), (236.0, 356.0)]:
        tx0, tx1 = wx_to_px(t_left), wx_to_px(t_right)
        ty0, ty1 = wy_to_py(-48.0), wy_to_py(12.0)
        bg_draw.rectangle((tx0, ty0, tx1, ty1), fill=(32, 40, 52, 255))
        # Control room monitor panels & brick lines
        for by in range(ty0 + 6, ty1, 8):
            bg_draw.line((tx0, by, tx1, by), fill=(24, 30, 40, 255))
        # Glowing control panel on back wall
        panel_x = (tx0 + tx1) // 2 - 18
        panel_y = ty0 + 16
        bg_draw.rectangle((panel_x, panel_y, panel_x + 36, panel_y + 18), fill=(18, 24, 32, 255), outline=(74, 92, 112, 255))
        bg_draw.rectangle((panel_x + 4, panel_y + 4, panel_x + 16, panel_y + 12), fill=(42, 168, 132, 220))
        bg_draw.rectangle((panel_x + 20, panel_y + 4, panel_x + 32, panel_y + 8), fill=(228, 142, 44, 220))

    # Elevator shaft vertical guide rails at x = -148.0 (w = 37 -> [-166.5, -129.5], y in [-52, 85])
    el_x0, el_x1 = wx_to_px(-166.0), wx_to_px(-130.0)
    el_y0, el_y1 = wy_to_py(-52.0), wy_to_py(86.0)
    bg_draw.rectangle((el_x0, el_y0, el_x1, el_y1), fill=(20, 26, 36, 220))
    bg_draw.line((el_x0 + 2, el_y0, el_x0 + 2, el_y1), fill=(68, 82, 98, 255))
    bg_draw.line((el_x1 - 2, el_y0, el_x1 - 2, el_y1), fill=(68, 82, 98, 255))
    for cy in range(el_y0 + 6, el_y1, 10):
        bg_draw.line((el_x0 + 3, cy, el_x1 - 3, cy), fill=(34, 44, 56, 255))

    # Central dock water pit glow at the bottom (x in [-48, 48], y in [156, 230])
    pit_x0, pit_x1 = wx_to_px(-48.0), wx_to_px(48.0)
    pit_y0, pit_y1 = wy_to_py(160.0), wy_to_py(250.0)
    bg_draw.rectangle((pit_x0, pit_y0, pit_x1, pit_y1), fill=(14, 42, 64, 255))
    for wy in range(pit_y0, pit_y1, 5):
        bg_draw.line((pit_x0 + 4, wy, pit_x1 - 4, wy), fill=(36, 98, 138, 180))

    bg.save(MAPS_DIR / "steel_harbor_bg.png")

    # =========================================================================
    # 2. MIDGROUND PHYSICS GEOMETRY LAYER (steel_harbor_mid.png)
    #    Every collider is drawn to exact 1:1 pixel coordinates!
    # =========================================================================
    mid = Image.new("RGBA", (IMG_W, IMG_H), (0, 0, 0, 0))
    mid_draw = ImageDraw.Draw(mid)

    # 45-degree staircases (stairs_left: (-164, 76) -> (-228, 12); stairs_right: (164, 76) -> (228, 12))
    draw_stairs_45(mid_draw, -228.0, 12.0, -164.0, 76.0)
    draw_stairs_45(mid_draw, 164.0, 76.0, 228.0, 12.0)

    # Solid concrete/steel decks & walls (exact Rect2 coordinates!)
    # ceiling_main: [-380, -196, 380, -172]
    draw_concrete_slab(mid_draw, mid, -380.0, -196.0, 380.0, -172.0)
    # Outer walls: [-380, -196, -356, 220] & [356, -196, 380, 220]
    draw_concrete_slab(mid_draw, mid, -380.0, -196.0, -356.0, 220.0)
    draw_concrete_slab(mid_draw, mid, 356.0, -196.0, 380.0, 220.0)
    # Control Tower Foundations: [-356, 12, -228, 108] & [228, 12, 356, 108] (top_y = 12.0 is tower_left_floor / tower_right_floor)
    draw_concrete_slab(mid_draw, mid, -356.0, 12.0, -228.0, 108.0, hazard_right=True)
    draw_concrete_slab(mid_draw, mid, 228.0, 12.0, 356.0, 108.0, hazard_left=True)
    # Main decks split around 20px ladder hatch openings [-78, -58] and [58, 78]:
    draw_concrete_slab(mid_draw, mid, -228.0, 76.0, -78.0, 108.0, hazard_right=True)
    draw_concrete_slab(mid_draw, mid, -58.0, 76.0, -48.0, 108.0, hazard_left=True, hazard_right=True)
    draw_hatch_shaft(mid_draw, -78.0, 76.0, -58.0, 108.0)
    draw_concrete_slab(mid_draw, mid, 48.0, 76.0, 58.0, 108.0, hazard_left=True, hazard_right=True)
    draw_concrete_slab(mid_draw, mid, 78.0, 76.0, 228.0, 108.0, hazard_left=True)
    draw_hatch_shaft(mid_draw, 58.0, 76.0, 78.0, 108.0)
    # Subdecks: subdeck_center [-128, 140, -48, 156], subdeck_right [48, 140, 128, 156]
    draw_concrete_slab(mid_draw, mid, -128.0, 140.0, -48.0, 156.0, hazard_right=True)
    draw_concrete_slab(mid_draw, mid, 48.0, 140.0, 128.0, 156.0, hazard_left=True)
    # Control Tower Roofs split around 20px ladder hatch openings [-308, -288] and [288, 308]:
    draw_concrete_slab(mid_draw, mid, -356.0, -56.0, -308.0, -48.0, hazard_right=True)
    draw_concrete_slab(mid_draw, mid, -288.0, -56.0, -232.0, -48.0, hazard_left=True, hazard_right=True)
    draw_hatch_shaft(mid_draw, -308.0, -56.0, -288.0, -48.0)
    draw_concrete_slab(mid_draw, mid, 232.0, -56.0, 288.0, -48.0, hazard_left=True, hazard_right=True)
    draw_concrete_slab(mid_draw, mid, 308.0, -56.0, 356.0, -48.0, hazard_left=True)
    draw_hatch_shaft(mid_draw, 288.0, -56.0, 308.0, -48.0)

    # Bidirectional Portal Doorways at x = -356..-340 and x = 340..356 (connecting tower floors y=12 <-> crane walkways y=-108)
    draw_portal_doorway(mid_draw, -356.0, -24.0, -340.0, 12.0)
    draw_portal_doorway(mid_draw, -356.0, -144.0, -340.0, -108.0)
    draw_portal_doorway(mid_draw, 340.0, -24.0, 356.0, 12.0)
    draw_portal_doorway(mid_draw, 340.0, -144.0, 356.0, -108.0)

    # One-way steel catwalks (CLOUD tags, exact 4px thickness)
    # catwalk_left: [-228, -52, -167, -48] -> stops at x = -167.0 so elevator shaft [-166.5, -129.5] is 100% unobstructed!
    draw_steel_catwalk(mid_draw, mid, -228.0, -52.0, -167.0, -48.0, hazard_left=True, hazard_right=True)
    # catwalk_right: [40, -52, 92, -48] -> right edge at x = 92.0 is the exact fulcrum for crate_hanging_2!
    draw_steel_catwalk(mid_draw, mid, 40.0, -52.0, 92.0, -48.0, hazard_left=True, hazard_right=True)
    # crane_walk_left: [-356, -108, -196, -104]
    draw_steel_catwalk(mid_draw, mid, -356.0, -108.0, -196.0, -104.0, hazard_right=True)
    # crane_walk_right: [196, -108, 356, -104]
    draw_steel_catwalk(mid_draw, mid, 196.0, -108.0, 356.0, -104.0, hazard_left=True)

    # Ladders drawn ON TOP of the open hatch shafts, with top handrails extending 12px above top platforms!
    draw_ladder(mid_draw, -306.0, -120.0, -290.0, 12.0)   # ladder_left_upper (y: -120..12)
    draw_ladder(mid_draw, 290.0, -120.0, 306.0, 12.0)     # ladder_right_upper (y: -120..12)
    draw_ladder(mid_draw, -76.0, 64.0, -60.0, 140.0)      # ladder_pit_left (y: 64..140)
    draw_ladder(mid_draw, 60.0, 64.0, 76.0, 140.0)        # ladder_pit_right (y: 64..140)

    # Semi-open one-way (CLOUD) steel safety gratings across the 4 ladder hatch mouths
    draw_hatch_grating(mid_draw, -308.0, -56.0, -288.0, -52.0)
    draw_hatch_grating(mid_draw, 288.0, -56.0, 308.0, -52.0)
    draw_hatch_grating(mid_draw, -78.0, 76.0, -58.0, 80.0)
    draw_hatch_grating(mid_draw, 58.0, 76.0, 78.0, 80.0)

    # Ceiling anchor brackets at x = -112.0 and x = 96.0 on ceiling_main bottom (y = -172.0)
    for ax in [-112.0, 96.0]:
        apx = wx_to_px(ax)
        apy = wy_to_py(-172.0)
        mid_draw.rectangle((apx - 5, apy - 4, apx + 5, apy + 2), fill=(218, 172, 42, 255), outline=(40, 44, 52, 255))

    mid.save(MAPS_DIR / "steel_harbor_mid.png")

    # =========================================================================
    # 3. FOREGROUND DETAIL LAYER (steel_harbor_fg.png)
    # =========================================================================
    fg = Image.new("RGBA", (IMG_W, IMG_H), (0, 0, 0, 0))
    fg_draw = ImageDraw.Draw(fg)
    # Subtle top gantry beam shadow & rivets at ceiling_main
    fg_draw.rectangle((wx_to_px(-380), wy_to_py(-196), wx_to_px(380) - 1, wy_to_py(-188)), fill=(16, 20, 28, 140))
    fg.save(MAPS_DIR / "steel_harbor_fg.png")


def build_map_definition() -> dict:
    full_weapon_mask = [1] * 17 + [0] * 13

    ground_boxes = [
        # Main overhead crane ceiling beam: [-380, -196, 380, -172] -> bottom at y = -172.0
        {"var_name": "ceiling_main", "material": "Metal", "x": 0.0, "y": -184.0, "w": 760.0, "h": 24.0, "angle": 0.0, "tags": ["NONE"]},
        # Outer boundary walls
        {"var_name": "wall_left_outer", "material": "Ground", "x": -368.0, "y": 12.0, "w": 24.0, "h": 416.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "wall_right_outer", "material": "Ground", "x": 368.0, "y": 12.0, "w": 24.0, "h": 416.0, "angle": 0.0, "tags": ["NONE"]},
        # Control tower foundations & floors (top_y = 12.0, bottom_y = 108.0): [-356, 12, -228, 108] & [228, 12, 356, 108]
        {"var_name": "tower_left_floor", "material": "Ground", "x": -292.0, "y": 60.0, "w": 128.0, "h": 96.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "tower_right_floor", "material": "Ground", "x": 292.0, "y": 60.0, "w": 128.0, "h": 96.0, "angle": 0.0, "tags": ["NONE"]},
        # Main concrete harbor decks (top_y = 76.0..108.0), split around 20px ladder hatches [-78, -58] and [58, 78]
        {"var_name": "deck_left_outer", "material": "Ground", "x": -153.0, "y": 92.0, "w": 150.0, "h": 32.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "deck_left_lip", "material": "Ground", "x": -53.0, "y": 92.0, "w": 10.0, "h": 32.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "hatch_deck_left", "material": "Metal", "x": -68.0, "y": 78.0, "w": 20.0, "h": 4.0, "angle": 0.0, "tags": ["CLOUD"]},
        {"var_name": "deck_right_lip", "material": "Ground", "x": 53.0, "y": 92.0, "w": 10.0, "h": 32.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "deck_right_outer", "material": "Ground", "x": 153.0, "y": 92.0, "w": 150.0, "h": 32.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "hatch_deck_right", "material": "Metal", "x": 68.0, "y": 78.0, "w": 20.0, "h": 4.0, "angle": 0.0, "tags": ["CLOUD"]},
        # Lower maintenance subdecks (top_y = 140.0)
        {"var_name": "subdeck_center", "material": "Metal", "x": -88.0, "y": 148.0, "w": 80.0, "h": 16.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "subdeck_right", "material": "Metal", "x": 88.0, "y": 148.0, "w": 80.0, "h": 16.0, "angle": 0.0, "tags": ["NONE"]},
        # Control tower roofs (top_y = -56.0, bottom_y = -48.0), split around 20px ladder hatches [-308, -288] and [288, 308]
        {"var_name": "tower_left_roof_l", "material": "Metal", "x": -332.0, "y": -52.0, "w": 48.0, "h": 8.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "tower_left_roof_r", "material": "Metal", "x": -260.0, "y": -52.0, "w": 56.0, "h": 8.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "hatch_tower_left", "material": "Metal", "x": -298.0, "y": -54.0, "w": 20.0, "h": 4.0, "angle": 0.0, "tags": ["CLOUD"]},
        {"var_name": "tower_right_roof_l", "material": "Metal", "x": 260.0, "y": -52.0, "w": 56.0, "h": 8.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "tower_right_roof_r", "material": "Metal", "x": 332.0, "y": -52.0, "w": 48.0, "h": 8.0, "angle": 0.0, "tags": ["NONE"]},
        {"var_name": "hatch_tower_right", "material": "Metal", "x": 298.0, "y": -54.0, "w": 20.0, "h": 4.0, "angle": 0.0, "tags": ["CLOUD"]},
        # One-way steel catwalks (CLOUD, top_y = -52.0)
        # catwalk_left spans [-228.0, -167.0] so elevator `lift` [-166.5, -129.5] has 100% clear vertical travel!
        {"var_name": "catwalk_left", "material": "Metal", "x": -197.5, "y": -50.0, "w": 61.0, "h": 4.0, "angle": 0.0, "tags": ["CLOUD"]},
        # catwalk_right spans [40.0, 92.0] at top_y = -52.0 (right edge x = 92.0 is the fulcrum for crate_hanging_2!)
        {"var_name": "catwalk_right", "material": "Metal", "x": 66.0, "y": -50.0, "w": 52.0, "h": 4.0, "angle": 0.0, "tags": ["CLOUD"]},
        # High crane walkways (CLOUD, top_y = -108.0): [-356, -108, -196, -104] & [196, -108, 356, -104]
        {"var_name": "crane_walk_left", "material": "Metal", "x": -276.0, "y": -106.0, "w": 160.0, "h": 4.0, "angle": 0.0, "tags": ["CLOUD"]},
        {"var_name": "crane_walk_right", "material": "Metal", "x": 276.0, "y": -106.0, "w": 160.0, "h": 4.0, "angle": 0.0, "tags": ["CLOUD"]},
        # Ladders (top_y extends 12px above top platform, 0 solid NONE slabs intersecting shafts!)
        {"var_name": "ladder_left_upper", "material": "Metal", "x": -298.0, "y": -54.0, "w": 16.0, "h": 132.0, "angle": 0.0, "tags": ["LADDER"]},
        {"var_name": "ladder_right_upper", "material": "Metal", "x": 298.0, "y": -54.0, "w": 16.0, "h": 132.0, "angle": 0.0, "tags": ["LADDER"]},
        {"var_name": "ladder_pit_left", "material": "Metal", "x": -68.0, "y": 102.0, "w": 16.0, "h": 76.0, "angle": 0.0, "tags": ["LADDER"]},
        {"var_name": "ladder_pit_right", "material": "Metal", "x": 68.0, "y": 102.0, "w": 16.0, "h": 76.0, "angle": 0.0, "tags": ["LADDER"]},
    ]

    ground_polygons = [
        {
            "var_name": "stairs_left",
            "material": "Metal",
            "x": -196.0,
            "y": 44.0,
            "angle": 0.0,
            "vertices": [[-32.0, -32.0], [32.0, 32.0], [-32.0, 32.0]],
            "tags": ["NONE"],
            "tilt_value": -2.0,
        },
        {
            "var_name": "stairs_right",
            "material": "Metal",
            "x": 196.0,
            "y": 44.0,
            "angle": 0.0,
            "vertices": [[-32.0, 32.0], [32.0, -32.0], [32.0, 32.0]],
            "tags": ["NONE"],
            "tilt_value": 2.0,
        },
    ]

    def make_prop(var_name: str, ptype: str, x: float, y: float) -> dict:
        return {
            "var_name": var_name,
            "type": ptype,
            "candidates": [ptype],
            "x": x,
            "y": y,
            "angle": 0.0,
            "branch_group": 0,
            "branch_id": 0,
            "conditions": [],
        }

    premade_props = [
        # Showcase #1: Open vertical drop lane on left side at x = -112.0 -> drops straight onto barrel_exp_drop on deck_left (y = 76.0)
        make_prop("crate_hanging_1", "CRATE_HANGING", -112.0, -96.0),
        # Showcase #2: Partial ledge strike on right side at x = 96.0 -> hits right edge of catwalk_right (x = 92.0, y = -52.0),
        # pivots clockwise on fulcrum (92.0, -52.0), slides off to the right, and settles flat (0 deg) on deck_right (y = 76.0)!
        make_prop("crate_hanging_2", "CRATE_HANGING", 96.0, -96.0),
        # Explosive barrel on deck_left directly below crate_hanging_1
        make_prop("barrel_exp_drop", "BARREL_EXPLOSIVE", -112.0, 68.5),
        # Left deck cover & stacked crates (clear of stairs_left x=-164 and hatch_deck_left [-78, -58])
        make_prop("crate_deck_l1", "CRATE", -148.0, 68.0),
        make_prop("crate_deck_l2", "CRATE", -148.0, 52.0),
        make_prop("barrel_deck_l", "BARREL", -92.0, 68.5),
        make_prop("gascan_catwalk_l", "GASCAN", -196.0, -57.5),
        # Subdeck props (clear of ladder_pit_left [-76, -60] and ladder_pit_right [60, 76])
        make_prop("table_subdeck_l", "TABLE", -96.0, 135.0),
        make_prop("barrel_exp_sub_r", "BARREL_EXPLOSIVE", 96.0, 132.5),
        # Left control tower props (floor y = 12.0, clear of ladder_left_upper [-306, -290] and portal [-356, -340])
        make_prop("desk_tower_l", "DESK", -268.0, 5.0),
        make_prop("comp_tower_l", "COMP", -274.0, -8.0),
        make_prop("screen_tower_l", "COMP_SCREEN", -262.0, -8.0),
        make_prop("chair_tower_l", "CHAIR", -246.0, 6.0),
        # Right control tower props (floor y = 12.0, clear of ladder_right_upper [290, 306] and portal [340, 356])
        make_prop("filecab_tower_r", "FILECAB", 324.0, 4.5),
        make_prop("table_tower_r", "TABLE", 268.0, 7.0),
        make_prop("chair_r_tower_r", "CHAIR_R", 248.0, 6.0),
        # Upper crane walkway props (floor y = -108.0)
        make_prop("crate_crane_l", "CRATE", -240.0, -116.0),
        make_prop("gascan_crane_r", "GASCAN", 256.0, -113.5),
    ]

    ai_nodes = [
        {"index": 0, "id": "n0", "x": -334.0, "y": 12.0, "tag": "", "body_ref": "null"},
        {"index": 1, "id": "n1", "x": -128.0, "y": 76.0, "tag": "", "body_ref": "null"},
        {"index": 2, "id": "n2", "x": -164.0, "y": 76.0, "tag": "", "body_ref": "null"},
        {"index": 3, "id": "n_lift", "x": -148.0, "y": 76.0, "tag": "", "body_ref": "lift"},
        {"index": 4, "id": "n4", "x": -68.0, "y": 76.0, "tag": "", "body_ref": "null"},
        {"index": 5, "id": "n5", "x": -68.0, "y": 140.0, "tag": "", "body_ref": "null"},
        {"index": 6, "id": "n6", "x": 68.0, "y": 140.0, "tag": "", "body_ref": "null"},
        {"index": 7, "id": "n7", "x": 68.0, "y": 76.0, "tag": "", "body_ref": "null"},
        {"index": 8, "id": "n8", "x": 164.0, "y": 76.0, "tag": "", "body_ref": "null"},
        {"index": 9, "id": "n9", "x": 334.0, "y": 12.0, "tag": "", "body_ref": "null"},
        {"index": 10, "id": "n10", "x": -228.0, "y": 12.0, "tag": "", "body_ref": "null"},
        {"index": 11, "id": "n11", "x": -298.0, "y": 12.0, "tag": "", "body_ref": "null"},
        {"index": 12, "id": "n12", "x": 228.0, "y": 12.0, "tag": "", "body_ref": "null"},
        {"index": 13, "id": "n13", "x": 298.0, "y": 12.0, "tag": "", "body_ref": "null"},
        {"index": 14, "id": "n14", "x": -196.0, "y": -52.0, "tag": "", "body_ref": "null"},
        {"index": 15, "id": "n15", "x": 0.0, "y": -52.0, "tag": "", "body_ref": "null"},
        {"index": 16, "id": "n16", "x": 66.0, "y": -52.0, "tag": "", "body_ref": "null"},
        {"index": 17, "id": "n17", "x": -298.0, "y": -108.0, "tag": "", "body_ref": "null"},
        {"index": 18, "id": "n18", "x": 298.0, "y": -108.0, "tag": "", "body_ref": "null"},
        {"index": 19, "id": "n19", "x": -298.0, "y": -56.0, "tag": "", "body_ref": "null"},
        {"index": 20, "id": "n20", "x": 298.0, "y": -56.0, "tag": "", "body_ref": "null"},
    ]

    def bind_pair(a: int, b: int, action: str = "ROAD"):
        return [
            {"id": "", "from": a, "to": b, "mode": "STATIC", "action": action},
            {"id": "", "from": b, "to": a, "mode": "STATIC", "action": action},
        ]

    ai_binds = []
    for a, b in [(0, 11), (11, 10), (10, 2), (2, 3), (3, 1), (1, 4), (7, 8), (8, 12), (12, 13), (13, 9), (19, 14), (15, 16)]:
        ai_binds.extend(bind_pair(a, b, "ROAD"))
    for a, b in [(4, 5), (6, 7), (11, 19), (19, 17), (13, 20), (20, 18)]:
        ai_binds.extend(bind_pair(a, b, "LADDER"))
    ai_binds.extend(bind_pair(4, 7, "SPRINTJUMP"))
    ai_binds.extend(bind_pair(5, 6, "SPRINTJUMP"))
    ai_binds.append({"id": "", "from": 17, "to": 14, "mode": "STATIC", "action": "DIVE"})
    ai_binds.append({"id": "", "from": 18, "to": 12, "mode": "STATIC", "action": "DIVE"})
    ai_binds.append({"id": "", "from": 16, "to": 8, "mode": "STATIC", "action": "DIVE"})
    ai_binds.append({"id": "", "from": 14, "to": 2, "mode": "STATIC", "action": "DIVE"})

    return {
        "bounds_rect": [-380.0, -210.0, 760.0, 440.0],
        "bg_color": "#0c121c",
        "acid_kill_y": 215.0,
        "player_spawns": [
            [-128.0, 76.0],
            [128.0, 76.0],
            [-276.0, 12.0],
            [276.0, 12.0],
            [-196.0, -52.0],
            [66.0, -52.0],
            [-256.0, -108.0],
            [256.0, -108.0],
        ],
        "weapon_spawns": [
            {"x": 0.0, "y": -52.0, "mask": full_weapon_mask},
            {"x": -128.0, "y": 76.0, "mask": full_weapon_mask},
            {"x": 128.0, "y": 76.0, "mask": full_weapon_mask},
            {"x": -276.0, "y": 12.0, "mask": full_weapon_mask},
            {"x": 276.0, "y": 12.0, "mask": full_weapon_mask},
            {"x": -256.0, "y": -108.0, "mask": full_weapon_mask},
        ],
        "portals": [
            {
                "entry_rect": [-356.0, -24.0, 16.0, 36.0],
                "exit_rect": [-356.0, -144.0, 16.0, 36.0],
                "dir": [-1.0, 0.0],
                "door_open": True,
                "ignore_vel": False,
            },
            {
                "entry_rect": [-356.0, -144.0, 16.0, 36.0],
                "exit_rect": [-356.0, -24.0, 16.0, 36.0],
                "dir": [-1.0, 0.0],
                "door_open": True,
                "ignore_vel": False,
            },
            {
                "entry_rect": [340.0, -24.0, 16.0, 36.0],
                "exit_rect": [340.0, -144.0, 16.0, 36.0],
                "dir": [1.0, 0.0],
                "door_open": True,
                "ignore_vel": False,
            },
            {
                "entry_rect": [340.0, -144.0, 16.0, 36.0],
                "exit_rect": [340.0, -24.0, 16.0, 36.0],
                "dir": [1.0, 0.0],
                "door_open": True,
                "ignore_vel": False,
            },
        ],
        "ground_boxes": ground_boxes,
        "ground_polygons": ground_polygons,
        "ground_circles": [],
        "premade_props": premade_props,
        "elevators": [
            {
                "var_name": "lift",
                "type": "LIFT_01",
                "direction": "vertical",
                "x": -148.0,
                "y": 80.5,
                "distance": 128.0,
                "speed": 1.0,
            }
        ],
        "hanging_lamps": [
            {"x": -256.0, "y": -172.0, "rope_length": 24.0},
            {"x": 0.0, "y": -172.0, "rope_length": 28.0},
            {"x": 276.0, "y": -172.0, "rope_length": 24.0},
        ],
        "glasses": [
            {"x1": -40.0, "y1": -52.0, "x2": 40.0, "y2": -52.0},
            {"x1": -236.0, "y1": -48.0, "x2": -236.0, "y2": -18.0},
            {"x1": 236.0, "y1": -48.0, "x2": 236.0, "y2": -18.0},
        ],
        "ai_path_grid": {
            "nodes": ai_nodes,
            "binds": ai_binds,
        },
        "bg_layers": [
            {
                "bitmap": "steel_harbor_bg.png",
                "alias_bitmap": "steel_harbor_bg.png",
                "path": "res://assets/maps/steel_harbor_bg.png",
                "tx": ORIGIN_X,
                "ty": ORIGIN_Y,
                "sx": 1.0,
                "sy": 1.0,
                "parallax": 1.0,
            },
            {
                "bitmap": "steel_harbor_mid.png",
                "alias_bitmap": "steel_harbor_mid.png",
                "path": "res://assets/maps/steel_harbor_mid.png",
                "tx": ORIGIN_X,
                "ty": ORIGIN_Y,
                "sx": 1.0,
                "sy": 1.0,
                "parallax": 1.0,
            },
        ],
        "fg_layers": [
            {
                "bitmap": "steel_harbor_fg.png",
                "path": "res://assets/maps/steel_harbor_fg.png",
                "tx": ORIGIN_X,
                "ty": ORIGIN_Y,
                "sx": 1.0,
                "sy": 1.0,
                "mask_rects": [],
            }
        ],
        "animated_props": [],
    }


def update_compiled_maps_json():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    vs_ids = data.get("vs_map_ids", [])
    if "steel_harbor" not in vs_ids:
        vs_ids.append("steel_harbor")
    data["vs_map_ids"] = vs_ids
    data["maps"]["steel_harbor"] = build_map_definition()
    data["map_count"] = len(data["maps"])
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[build_steel_harbor_map] Updated {JSON_PATH} (map_count={data['map_count']})")


if __name__ == "__main__":
    generate_layers()
    update_compiled_maps_json()
    print("[build_steel_harbor_map] Generated steel_harbor_bg.png, steel_harbor_mid.png, steel_harbor_fg.png successfully.")

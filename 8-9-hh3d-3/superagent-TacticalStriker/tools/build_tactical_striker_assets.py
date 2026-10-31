#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TS-WP1 & TS-WP2 Upgrade: Extracts the 5 HD Facial Expression Portraits AND the 6 Clean
Transparent HD Action Pose Sprites (idle, run, jump, punch, aim, roll) from
`agent_zero_character_sheet_1793104476989.jpg` with Largest-Connected-Component filtering
so zero stray grid specks or ruler ticks ever remain.
"""

import math
import os
from collections import deque
from PIL import Image, ImageDraw

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PORTRAITS_DIR = os.path.join(ROOT_DIR, "assets", "portraits")
SHEETS_DIR = os.path.join(ROOT_DIR, "assets", "sheets")
POSES_DIR = os.path.join(ROOT_DIR, "assets", "sprites", "agent_zero")
ARTIFACT_DIR = r"C:\Users\truon\.gemini\antigravity\brain\fb4592d9-c914-4d42-b275-d495b41a423b"
SRC_SHEET = os.path.join(ARTIFACT_DIR, "agent_zero_character_sheet_1793104476989.jpg")


def add_rounded_border(img: Image.Image, border_col=(65, 195, 255, 255)) -> Image.Image:
    out = img.convert("RGBA").resize((128, 128), Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(out)
    d.rectangle([0, 0, 127, 127], outline=border_col, width=3)
    d.rectangle([3, 3, 124, 124], outline=(14, 18, 28, 220), width=1)
    return out


def extract_clean_hd_pose(sheet_img: Image.Image, box: tuple, tol: float = 17.5) -> Image.Image:
    """
    1. Crops `box` from `sheet_img` and removes exterior blueprint slate background & grid lines.
    2. Runs 8-connected component labeling on remaining opaque pixels and discards any
       disconnected speck/ruler fragment smaller than 250 pixels.
    3. Applies a smooth 1px anti-aliased alpha ramp on the outer contour edge.
    """
    crop = sheet_img.crop(box).convert("RGBA")
    w, h = crop.size
    px = crop.load()

    samples = [
        px[2, 2][:3],
        px[w - 3, 2][:3],
        px[2, min(h - 3, 18)][:3],
        px[w - 3, min(h - 3, 18)][:3],
    ]
    rs = sum(c[0] for c in samples) / len(samples)
    gs = sum(c[1] for c in samples) / len(samples)
    bs = sum(c[2] for c in samples) / len(samples)

    def is_bg(r, g, b):
        if r + g + b < 66:
            return False
        dist = math.sqrt((r - rs) ** 2 + (g - gs) ** 2 + (b - bs) ** 2)
        if dist <= tol:
            return True
        if r < 56 and g < 68 and b < 88 and (b > r + 4) and abs(r - rs) < 24 and abs(b - bs) < 28:
            return True
        return False

    visited = [[False] * w for _ in range(h)]
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if is_bg(*px[x, y][:3]):
                visited[y][x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not visited[y][x] and is_bg(*px[x, y][:3]):
                visited[y][x] = True
                q.append((x, y))

    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                r, g, b, _ = px[nx, ny]
                if is_bg(r, g, b):
                    visited[ny][nx] = True
                    q.append((nx, ny))

    for y in range(h):
        for x in range(w):
            if visited[y][x]:
                px[x, y] = (0, 0, 0, 0)

    # Step 2: Keep only connected components with >= 250 opaque pixels (eliminates stray grid specks)
    comp_vis = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 0 and not comp_vis[y][x]:
                comp = []
                cq = deque([(x, y)])
                comp_vis[y][x] = True
                while cq:
                    cx, cy = cq.popleft()
                    comp.append((cx, cy))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h and not comp_vis[ny][nx] and px[nx, ny][3] > 0:
                                comp_vis[ny][nx] = True
                                cq.append((nx, ny))
                if len(comp) < 250:
                    for rx, ry in comp:
                        px[rx, ry] = (0, 0, 0, 0)
                        visited[ry][rx] = True

    # Step 3: Smooth 1px outer contour alpha feathering
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 0:
                bg_n = 0
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] == 0:
                        bg_n += 1
                if bg_n >= 3:
                    r, g, b, _ = px[x, y]
                    px[x, y] = (r, g, b, 150)
                elif bg_n == 2:
                    r, g, b, _ = px[x, y]
                    px[x, y] = (r, g, b, 220)

    bbox = crop.getbbox()
    if bbox:
        crop = crop.crop(bbox)
    return crop


def main():
    os.makedirs(PORTRAITS_DIR, exist_ok=True)
    os.makedirs(SHEETS_DIR, exist_ok=True)
    os.makedirs(POSES_DIR, exist_ok=True)
    if not os.path.exists(SRC_SHEET):
        raise FileNotFoundError(f"Missing source sheet: {SRC_SHEET}")

    src = Image.open(SRC_SHEET).convert("RGBA")

    sheet_dst = os.path.join(SHEETS_DIR, "agent_zero_tactical_sheet.png")
    src.save(sheet_dst)

    # 1. Extract 5 HD Expression Portraits
    expr_boxes = {
        "confident": ((346, 88, 524, 296), (64, 195, 255, 255)),
        "fierce": ((550, 88, 728, 296), (255, 195, 65, 255)),
        "shout": ((752, 88, 930, 296), (255, 95, 65, 255)),
        "hurt": ((954, 88, 1132, 296), (255, 60, 75, 255)),
        "victory": ((1156, 88, 1334, 296), (90, 245, 155, 255)),
    }
    for key, (box, bcol) in expr_boxes.items():
        crop = src.crop(box)
        framed = add_rounded_border(crop, bcol)
        out_path = os.path.join(PORTRAITS_DIR, f"agent_zero_expr_{key}.png")
        framed.save(out_path)

    main_portrait = src.crop((54, 64, 318, 410)).resize((160, 208), Image.Resampling.LANCZOS)
    main_portrait.save(os.path.join(PORTRAITS_DIR, "agent_zero_portrait.png"))

    # 2. Extract 6 Clean Transparent HD Action Poses for In-Game Rendering
    pose_boxes = {
        "idle": (346, 422, 462, 668),
        "run": (450, 456, 634, 668),
        "jump": (598, 384, 762, 618),
        "punch": (738, 444, 964, 668),
        "aim": (952, 450, 1166, 668),
        "roll": (1184, 472, 1332, 668),
    }
    for p_key, p_box in pose_boxes.items():
        pose_img = extract_clean_hd_pose(src, p_box, tol=17.5)
        pose_path = os.path.join(POSES_DIR, f"pose_{p_key}.png")
        pose_img.save(pose_path)
        print(f"Saved spotless HD Pose '{p_key}': {pose_img.size} -> {pose_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Builds the spotless Master Comparison Board for the 4 Original Base Character Models
of SuperAgent with exact full head-to-boot bounding boxes.
"""

import math
import os
import shutil
from collections import deque
from PIL import Image, ImageDraw

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT_DIR, "assets", "previews", "base_character_designs_2026_10_27")
ARTIFACT_DIR = r"C:\Users\truon\.gemini\antigravity\brain\fb4592d9-c914-4d42-b275-d495b41a423b"

SHEET_A = os.path.join(ARTIFACT_DIR, "agent_zero_character_sheet_1793104476989.jpg")
SHEET_B = os.path.join(ARTIFACT_DIR, "superagent_chibi_brawler_sheet_1793104764257.jpg")
SHEET_C = os.path.join(ARTIFACT_DIR, "style_c_martial_artist_sheet_1793104765256.jpg")

from generate_superagent_base_character_samples import (
    draw_old_y8_reference,
    get_font,
    render_pixel_style_pose,
)


def extract_clean_cutout(sheet_img: Image.Image, box: tuple, tol: float = 18.0) -> Image.Image:
    """
    Crops `box` from `sheet_img` and removes the blueprint slate background & grid lines
    outside the character's dark ink outline.
    """
    crop = sheet_img.crop(box).convert("RGBA")
    w, h = crop.size
    px = crop.load()

    samples = [
        px[2, 2][:3],
        px[w - 3, 2][:3],
        px[2, min(h - 3, 16)][:3],
        px[w - 3, min(h - 3, 16)][:3],
    ]
    rs = sum(c[0] for c in samples) / len(samples)
    gs = sum(c[1] for c in samples) / len(samples)
    bs = sum(c[2] for c in samples) / len(samples)

    def is_bg(r, g, b):
        # Protect black/dark-ink outlines (sum < 65)
        if r + g + b < 65:
            return False
        dist = math.sqrt((r - rs) ** 2 + (g - gs) ** 2 + (b - bs) ** 2)
        if dist <= tol:
            return True
        # Blueprint slate grid lines
        if r < 52 and g < 65 and b < 85 and (b > r + 4) and abs(r - rs) < 24 and abs(b - bs) < 28:
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

    bbox = crop.getbbox()
    if bbox:
        crop = crop.crop(bbox)
    return crop


def fit_inside(img: Image.Image, max_w: int, max_h: int, nearest: bool = False) -> Image.Image:
    w, h = img.size
    if w <= 0 or h <= 0:
        return img
    scale = min(max_w / float(w), max_h / float(h))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return img.resize((nw, nh), resample)


def build_master_4_models_board():
    im_a = Image.open(SHEET_A)
    im_b = Image.open(SHEET_B)
    im_c = Image.open(SHEET_C)

    # Full standing models (head-to-toe including boots)
    hero_a_full = extract_clean_cutout(im_a, (66, 62, 312, 668), tol=16.0)
    hero_b_full = extract_clean_cutout(im_b, (108, 52, 346, 492), tol=18.0)
    hero_c_full = extract_clean_cutout(im_c, (62, 68, 344, 668), tol=16.0)

    # Bottom-row action poses (head-to-toe including boots, zero overlap)
    idle_a = extract_clean_cutout(im_a, (345, 420, 466, 668), tol=16.0)
    punch_a = extract_clean_cutout(im_a, (730, 422, 968, 668), tol=16.0)
    gun_a = extract_clean_cutout(im_a, (948, 430, 1170, 668), tol=16.0)

    idle_b = extract_clean_cutout(im_b, (92, 508, 218, 684), tol=18.0)
    punch_b = extract_clean_cutout(im_b, (708, 444, 926, 686), tol=18.0)
    gun_b = extract_clean_cutout(im_b, (952, 504, 1120, 684), tol=18.0)

    idle_c = extract_clean_cutout(im_c, (348, 452, 486, 662), tol=16.0)
    punch_c = extract_clean_cutout(im_c, (728, 424, 982, 662), tol=16.0)
    gun_c = extract_clean_cutout(im_c, (988, 476, 1146, 662), tol=16.0)

    # Expression portraits (Confident, Shout, Hurt)
    exprs_a = [
        im_a.crop((344, 86, 526, 298)),
        im_a.crop((750, 86, 932, 298)),
        im_a.crop((954, 86, 1134, 298)),
    ]
    exprs_b = [
        im_b.crop((430, 56, 594, 232)),
        im_b.crop((798, 56, 962, 232)),
        im_b.crop((982, 56, 1146, 232)),
    ]
    exprs_c = [
        im_c.crop((386, 86, 558, 268)),
        im_c.crop((768, 86, 940, 268)),
        im_c.crop((960, 86, 1132, 268)),
    ]

    W, H = 1680, 980
    canvas = Image.new("RGBA", (W, H), (11, 14, 22, 255))
    d = ImageDraw.Draw(canvas)
    f_title = get_font(22, True)
    f_sub = get_font(14, False)
    f_col = get_font(15, True)
    f_lbl = get_font(13, True)
    f_txt = get_font(12, False)

    # Top Header
    d.rounded_rectangle([16, 12, W - 16, 84], radius=12, fill=(20, 26, 40), outline=(85, 185, 255), width=2)
    d.text(
        (30, 20),
        "SO SANH TRUC QUAN: NHAN VAT Y8 CU vs 4 MAU THIET KE NHAN VAT CO BAN MOI (SUPERAGENT)",
        fill=(115, 220, 255),
        font=f_title,
    )
    d.text(
        (30, 52),
        "Thiet ke rieng 100% cho Nhan Vat Co Ban cua SuperAgent: Khong gu lung, khong kinh den Y8, co Khuon Xuong Song & 5 Bieu Cam song dong",
        fill=(220, 230, 245),
        font=f_sub,
    )

    # Left Column: Old Superfighters Y8 (Crossed Out)
    ox, oy, ow, oh = 16, 96, 220, H - 112
    d.rounded_rectangle([ox, oy, ox + ow, oy + oh], radius=10, fill=(36, 20, 24), outline=(210, 65, 65), width=2)
    d.text((ox + 14, oy + 12), "CU: SUPERFIGHTERS Y8", fill=(255, 115, 115), font=f_col)
    d.text((ox + 14, oy + 34), "(Bi loai bo vi giong Y8)", fill=(240, 175, 175), font=f_txt)

    old_spr = draw_old_y8_reference().resize((176, 210), Image.Resampling.NEAREST)
    canvas.alpha_composite(old_spr, (ox + 22, oy + 70))
    d.line([(ox + 108, oy + 140), (ox + 90, oy + 175), (ox + 90, oy + 235)], fill=(255, 80, 80), width=4)
    d.line([(ox + 30, oy + 85), (ox + ow - 30, oy + 255)], fill=(255, 60, 60, 210), width=5)
    d.line([(ox + ow - 30, oy + 85), (ox + 30, oy + 255)], fill=(255, 60, 60, 210), width=5)

    flaws = [
        "1. Khuon xuong GU LUNG:",
        "   Dau lao ve truoc, co ruc",
        "2. Dau hop vuong 7x6 px:",
        "   Khong co cam, khong co tai",
        "3. Kinh den ngang 5x1 px:",
        "   Che kin mat, VO HON",
        "4. Khong co Bieu Cam:",
        "   Dung, dam, trung don y het",
        "5. Tay chan que 2px:",
        "   Khong co khop goi/khuyd",
    ]
    for i, line in enumerate(flaws):
        col = (255, 135, 135) if line[0].isdigit() else (230, 185, 185)
        d.text((ox + 12, oy + 295 + i * 26), line, fill=col, font=f_txt)

    models = [
        {
            "code": "MAU A (3.5 DAU - KHUYEN NGHI #1)",
            "name": "Tactical Striker (Agent Zero)",
            "desc": "Dang Chu S hien dai, ao khoac ngan, 5 bieu cam ro net",
            "accent": (70, 195, 255),
            "type": "hd_sheet",
            "full": hero_a_full,
            "idle": idle_a,
            "exprs": exprs_a,
            "punch": punch_a,
            "gun": gun_a,
        },
        {
            "code": "MAU B (2.5 DAU - BIEU CAM SIEU RO)",
            "name": "Chibi-Tactical Expressive Brawler",
            "desc": "Dau lon 40% nhin ro mat tu xa, nam dam to uy luc",
            "accent": (255, 135, 70),
            "type": "hd_sheet",
            "full": hero_b_full,
            "idle": idle_b,
            "exprs": exprs_b,
            "punch": punch_b,
            "gun": gun_b,
        },
        {
            "code": "MAU C (4.0 DAU - VO SI DUONG PHO)",
            "name": "Dynamic Street Martial Artist",
            "desc": "Giai phau 4 dau can doi, the thu MMA, bang tran do",
            "accent": (255, 205, 75),
            "type": "hd_sheet",
            "full": hero_c_full,
            "idle": idle_c,
            "exprs": exprs_c,
            "punch": punch_c,
            "gun": gun_c,
        },
        {
            "code": "MAU D (3.2 DAU - HI-BIT PIXEL RIG)",
            "name": "Hi-Bit Expressive Pixel Agent",
            "desc": "Pixel Art 32x42 sac net gap doi Y8 + 5 mat bieu cam",
            "accent": (90, 240, 155),
            "type": "pixel_rig",
        },
    ]

    avail_w = W - ox - ow - 28
    col_w = avail_w // 4
    for idx, m in enumerate(models):
        cx = ox + ow + 12 + idx * col_w
        cy = oy
        cw = col_w - 10
        ch = oh
        d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=10, fill=(18, 24, 36), outline=m["accent"], width=2)
        d.text((cx + 12, cy + 10), m["code"], fill=m["accent"], font=f_col)
        d.text((cx + 12, cy + 32), m["name"], fill=(240, 246, 255), font=f_lbl)
        d.text((cx + 12, cy + 50), m["desc"], fill=(185, 200, 225), font=f_txt)

        # Box 1: Full Anatomy & Posture
        b1_y, b1_h = cy + 74, 250
        d.rounded_rectangle([cx + 10, b1_y, cx + cw - 10, b1_y + b1_h], radius=8, fill=(24, 32, 44))
        d.text((cx + 16, b1_y + 8), "1. Khuon Xuong Song & Dang Dung:", fill=(140, 245, 180), font=f_lbl)
        if m["type"] == "hd_sheet":
            hero_fit = fit_inside(m["full"], cw - 40, b1_h - 36, nearest=False)
            canvas.alpha_composite(hero_fit, (cx + (cw - hero_fit.width) // 2, b1_y + 32 + (b1_h - 36 - hero_fit.height) // 2))
        else:
            p_idle = render_pixel_style_pose(1, "idle", "confident").resize((210, 210), Image.Resampling.NEAREST)
            canvas.alpha_composite(p_idle, (cx + (cw - 210) // 2, b1_y + 28))

        # Box 2: Facial Expressions Strip
        b2_y, b2_h = b1_y + b1_h + 10, 145
        d.rounded_rectangle([cx + 10, b2_y, cx + cw - 10, b2_y + b2_h], radius=8, fill=(24, 32, 44))
        d.text((cx + 16, b2_y + 8), "2. Bieu Cam Mat (Tu tin / Het / Trung don):", fill=(255, 215, 115), font=f_lbl)
        e_w = (cw - 40) // 3
        for e_i in range(3):
            ex_pos = cx + 14 + e_i * (e_w + 6)
            ey_pos = b2_y + 34
            if m["type"] == "hd_sheet":
                ecrop = fit_inside(m["exprs"][e_i].convert("RGBA"), e_w, 98, nearest=False)
                canvas.alpha_composite(ecrop, (ex_pos + (e_w - ecrop.width) // 2, ey_pos))
            else:
                ekey = ["confident", "shout", "hurt"][e_i]
                ecrop = render_pixel_style_pose(1, "idle", ekey).crop((10, 4, 34, 28)).resize((92, 92), Image.Resampling.NEAREST)
                canvas.alpha_composite(ecrop, (ex_pos + (e_w - 92) // 2, ey_pos + 2))

        # Box 3: Action Poses (Heavy Punch & Gun Aim)
        b3_y, b3_h = b2_y + b2_h + 10, 175
        d.rounded_rectangle([cx + 10, b3_y, cx + cw - 10, b3_y + b3_h], radius=8, fill=(24, 32, 44))
        d.text((cx + 16, b3_y + 8), "3. Hanh Dong (Dam Uy Luc & Ban Sung):", fill=(135, 225, 255), font=f_lbl)
        if m["type"] == "hd_sheet":
            p_fit = fit_inside(m["punch"], (cw - 36) // 2, 132, nearest=False)
            g_fit = fit_inside(m["gun"], (cw - 36) // 2, 132, nearest=False)
            canvas.alpha_composite(p_fit, (cx + 16, b3_y + 34 + (132 - p_fit.height) // 2))
            canvas.alpha_composite(g_fit, (cx + cw // 2 + 4, b3_y + 34 + (132 - g_fit.height) // 2))
        else:
            p_fit = render_pixel_style_pose(1, "punch", "shout").resize((132, 132), Image.Resampling.NEAREST)
            g_fit = render_pixel_style_pose(1, "gun", "fierce").resize((132, 132), Image.Resampling.NEAREST)
            canvas.alpha_composite(p_fit, (cx + 14, b3_y + 32))
            canvas.alpha_composite(g_fit, (cx + cw // 2 + 2, b3_y + 32))

        # Box 4: Actual In-Game Stage Preview
        b4_y = b3_y + b3_h + 10
        b4_h = cy + ch - b4_y - 10
        d.rounded_rectangle([cx + 10, b4_y, cx + cw - 10, b4_y + b4_h], radius=8, fill=(20, 26, 38))
        d.text((cx + 16, b4_y + 8), "4. Kich Thuoc Tren San Dau (In-Game):", fill=(180, 245, 210), font=f_lbl)

        floor_y = b4_y + b4_h - 32
        d.rectangle([cx + 16, floor_y, cx + cw - 16, b4_y + b4_h - 12], fill=(58, 68, 86))
        d.rectangle([cx + 16, floor_y, cx + cw - 16, floor_y + 5], fill=(120, 138, 165))

        # Wooden Crate (38x38)
        cr_x = cx + 30
        d.rectangle([cr_x, floor_y - 38, cr_x + 38, floor_y], fill=(160, 108, 56), outline=(28, 20, 14), width=2)
        d.line([(cr_x, floor_y - 38), (cr_x + 38, floor_y)], fill=(115, 74, 36), width=2)

        if m["type"] == "hd_sheet":
            st_idle = fit_inside(m["idle"], 80, 78, nearest=False)
            st_punch = fit_inside(m["punch"], 100, 78, nearest=False)
            canvas.alpha_composite(st_idle, (cr_x + 56, floor_y - st_idle.height))
            canvas.alpha_composite(st_punch, (cr_x + 146, floor_y - st_punch.height))
            for bx in (cr_x + 58, cr_x + 162):
                d.rectangle([bx, floor_y - 84, bx + 38, floor_y - 78], fill=(18, 22, 30), outline=(0, 0, 0))
                d.rectangle([bx + 1, floor_y - 83, bx + 31, floor_y - 79], fill=(80, 240, 120))
        else:
            st_idle = render_pixel_style_pose(1, "idle", "confident").resize((84, 84), Image.Resampling.NEAREST)
            st_punch = render_pixel_style_pose(1, "punch", "shout").resize((84, 84), Image.Resampling.NEAREST)
            canvas.alpha_composite(st_idle, (cr_x + 48, floor_y - 76))
            canvas.alpha_composite(st_punch, (cr_x + 136, floor_y - 76))
            for bx in (cr_x + 68, cr_x + 158):
                d.rectangle([bx, floor_y - 84, bx + 38, floor_y - 78], fill=(18, 22, 30), outline=(0, 0, 0))
                d.rectangle([bx + 1, floor_y - 83, bx + 31, floor_y - 79], fill=(80, 240, 120))

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "superagent_base_char_4_models_master_board.png")
    canvas.save(out_path)
    if os.path.exists(ARTIFACT_DIR):
        shutil.copy2(out_path, os.path.join(ARTIFACT_DIR, "superagent_base_char_4_models_master_board.png"))
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    build_master_4_models_board()

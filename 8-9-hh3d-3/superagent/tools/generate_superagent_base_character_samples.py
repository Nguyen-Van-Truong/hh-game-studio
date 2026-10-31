#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates 6 completely original Base Character design prototypes for SuperAgent,
breaking away 100% from the Superfighters Y8 hunchback spine, blocky head, and
expressionless sunglasses bar.

Showcases for the single Default/Basic Character ("AGENT ZERO - Nhan Vat Co Ban"):
- Anatomy & Spine comparison (Y8 Hunchback Box vs New Original Spine/Posture)
- 5 Distinct Facial Expressions per style (Confident, Fierce, Shout, Hurt/Shock, Victory)
- 6 Core Action Poses per style (Idle, Run, Jump, Heavy Punch, Gun Aim, Combat Roll)
- Actual In-Game Arena 1x & 3x Scale Preview on Steel Harbor floor with crates
"""

import math
import os
import shutil
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT_DIR, "assets", "previews", "base_character_designs_2026_10_27")
ARTIFACT_DIR = r"C:\Users\truon\.gemini\antigravity\brain\fb4592d9-c914-4d42-b275-d495b41a423b"


def get_font(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\tahomabd.ttf" if bold else r"C:\Windows\Fonts\tahoma.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ==============================================================================
# COLOR PALETTES FOR THE DEFAULT BASIC CHARACTER ("AGENT ZERO")
# ==============================================================================
OUTLINE = (15, 18, 26, 255)
SKIN_LIT = (255, 224, 196, 255)
SKIN_MID = (238, 192, 158, 255)
SKIN_SHD = (196, 142, 110, 255)

HAIR_LIT = (68, 78, 105, 255)
HAIR_MID = (42, 48, 68, 255)
HAIR_SHD = (24, 28, 42, 255)

JACKET_LIT = (56, 132, 235, 255)
JACKET_MID = (34, 92, 185, 255)
JACKET_SHD = (20, 56, 122, 255)
TRIM_ACCENT = (255, 210, 64, 255)
SHIRT_WHITE = (240, 245, 255, 255)

GLOVE_RED = (230, 55, 65, 255)
GLOVE_SHD = (155, 28, 38, 255)

PANTS_LIT = (64, 74, 94, 255)
PANTS_MID = (45, 52, 68, 255)
PANTS_SHD = (28, 33, 45, 255)

BOOT_LIT = (85, 92, 110, 255)
BOOT_DARK = (32, 36, 48, 255)
BOOT_SOLE = (235, 70, 70, 255)

EYE_WHITE = (255, 255, 255, 255)
EYE_IRIS = (32, 140, 240, 255)
EYE_PUPIL = (12, 16, 24, 255)
MOUTH_RED = (210, 68, 82, 255)

GUN_METAL = (140, 152, 172, 255)
GUN_DARK = (58, 64, 78, 255)
MUZZLE_GLOW = (255, 230, 90, 255)


def px(img: Image.Image, x: int, y: int, col: tuple):
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((int(x), int(y)), col)


def rect_px(img: Image.Image, x: int, y: int, w: int, h: int, col: tuple):
    for yy in range(int(y), int(y + h)):
        for xx in range(int(x), int(x + w)):
            px(img, xx, yy, col)


def line_px(img: Image.Image, x0: int, y0: int, x1: int, y1: int, col: tuple, thick: int = 1):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        t = i / float(steps)
        cx = int(round(x0 + (x1 - x0) * t))
        cy = int(round(y0 + (y1 - y0) * t))
        if thick <= 1:
            px(img, cx, cy, col)
        else:
            r = thick // 2
            rect_px(img, cx - r, cy - r, thick, thick, col)


def add_pixel_outline(img: Image.Image, out_col: tuple = OUTLINE) -> Image.Image:
    w, h = img.size
    res = img.copy()
    src = img.load()
    dst = res.load()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if src[x, y][3] == 0:
                if (
                    src[x - 1, y][3] > 0
                    or src[x + 1, y][3] > 0
                    or src[x, y - 1][3] > 0
                    or src[x, y + 1][3] > 0
                ):
                    dst[x, y] = out_col
    return res


# ==============================================================================
# REFERENCE 0: OLD SUPERFIGHTERS Y8 HUNCHBACK SPRITE (FOR DIRECT CONTRAST)
# ==============================================================================
def draw_old_y8_reference() -> Image.Image:
    """Draws the exact 17x21 blocky hunchback Y8 silhouette to show what we are replacing."""
    img = Image.new("RGBA", (40, 48), (0, 0, 0, 0))
    ox, oy = 12, 18
    # Blocky head pushed forward (hunchback)
    rect_px(img, ox + 5, oy + 0, 6, 2, (110, 75, 45, 255))  # flat hair
    rect_px(img, ox + 5, oy + 2, 6, 5, (230, 180, 145, 255))  # boxy head
    rect_px(img, ox + 6, oy + 3, 5, 1, (0, 0, 0, 255))  # lifeless black bar glasses
    # Boxy hunchback torso
    rect_px(img, ox + 3, oy + 7, 8, 7, (150, 155, 165, 255))
    # Stick legs
    rect_px(img, ox + 4, oy + 14, 2, 6, (60, 65, 80, 255))
    rect_px(img, ox + 8, oy + 14, 2, 6, (60, 65, 80, 255))
    # Floating blocky fist
    rect_px(img, ox + 9, oy + 9, 3, 3, (230, 180, 145, 255))
    return add_pixel_outline(img, (0, 0, 0, 255))


# ==============================================================================
# FACE & EXPRESSION DRAWER (5 DISTINCT EXPRESSIONS, NO SUNGLASSES)
# ==============================================================================
def draw_expressive_head_pixel(
    img: Image.Image,
    hx: int,
    hy: int,
    head_w: int,
    head_h: int,
    expr: str = "confident",
    hair_style: str = "spiky_modern",
    bandana: bool = False,
):
    """
    Draws an expressive head with chin taper, real eyes (sclera + iris + catchlight),
    dynamic eyebrows, and expressive mouth.
    expr in: 'confident', 'fierce', 'shout', 'hurt', 'victory'
    """
    # Cranium + tapered jaw (not a flat box!)
    rect_px(img, hx, hy + 1, head_w, head_h - 2, SKIN_LIT)
    rect_px(img, hx + 1, hy + head_h - 1, head_w - 2, 1, SKIN_MID)  # sculpted chin
    rect_px(img, hx, hy + 2, 2, head_h - 3, SKIN_MID)  # back-of-face shading
    # Ear on left side
    rect_px(img, hx - 1, hy + head_h // 2, 1, 2, SKIN_MID)

    # Hair with volume and dynamic strands
    if hair_style == "spiky_modern":
        rect_px(img, hx - 1, hy - 2, head_w + 2, 3, HAIR_MID)
        rect_px(img, hx + 1, hy - 3, head_w - 1, 2, HAIR_LIT)
        # Swept front spikes
        px(img, hx + head_w + 1, hy - 2, HAIR_LIT)
        px(img, hx + head_w, hy - 1, HAIR_MID)
        px(img, hx - 2, hy - 1, HAIR_SHD)
        rect_px(img, hx - 1, hy + 1, 2, 3, HAIR_SHD)  # sideburn
    elif hair_style == "chibi_fluffy":
        rect_px(img, hx - 1, hy - 3, head_w + 3, 4, HAIR_MID)
        rect_px(img, hx + 1, hy - 4, head_w, 2, HAIR_LIT)
        px(img, hx + head_w + 2, hy - 2, HAIR_LIT)
        rect_px(img, hx - 1, hy + 1, 2, 4, HAIR_SHD)
    elif hair_style == "martial_bandana":
        rect_px(img, hx - 1, hy - 2, head_w + 1, 3, HAIR_SHD)
        px(img, hx + 2, hy - 3, HAIR_MID)
        px(img, hx + 5, hy - 3, HAIR_MID)
        # Red combat headband + flowing tails
        rect_px(img, hx - 1, hy + 1, head_w + 1, 2, GLOVE_RED)
        px(img, hx - 3, hy + 1, GLOVE_RED)
        px(img, hx - 4, hy + 2, GLOVE_SHD)
        px(img, hx - 5, hy + 3, GLOVE_RED)
    elif hair_style == "arcade_pompadour":
        rect_px(img, hx - 1, hy - 3, head_w + 3, 4, (195, 115, 52, 255))
        rect_px(img, hx + 1, hy - 4, head_w + 2, 2, (235, 155, 78, 255))
        rect_px(img, hx - 1, hy + 1, 2, 3, (145, 78, 32, 255))
    elif hair_style == "cyber_sleek":
        rect_px(img, hx - 1, hy - 2, head_w + 2, 3, (220, 232, 250, 255))
        rect_px(img, hx + 2, hy - 3, head_w, 2, (255, 255, 255, 255))
        rect_px(img, hx - 1, hy + 1, 2, 3, (150, 170, 200, 255))

    # Eye & Mouth coordinates (3/4 front-right view: two visible eyes or prominent front eye)
    ey = hy + max(2, head_h // 2 - 1)
    ex_back = hx + head_w - 2
    ex_front = hx + head_w - 5 if head_w >= 9 else hx + head_w - 4

    if expr == "confident":
        # Two crisp eyes with white catchlight + confident smirk
        if head_w >= 9:
            rect_px(img, ex_front, ey, 2, 3, EYE_PUPIL)
            px(img, ex_front, ey, EYE_WHITE)
            rect_px(img, ex_back, ey, 2, 3, EYE_PUPIL)
            px(img, ex_back, ey, EYE_WHITE)
            # Eyebrows
            rect_px(img, ex_front, ey - 1, 2, 1, HAIR_SHD)
            rect_px(img, ex_back, ey - 1, 2, 1, HAIR_SHD)
        else:
            rect_px(img, ex_front, ey, 2, 2, EYE_PUPIL)
            px(img, ex_front, ey, EYE_WHITE)
            px(img, ex_back, ey, EYE_PUPIL)
            rect_px(img, ex_front, ey - 1, 3, 1, HAIR_SHD)
        # Confident upward smirk
        px(img, hx + head_w - 4, hy + head_h - 2, MOUTH_RED)
        px(img, hx + head_w - 5, hy + head_h - 3, SKIN_SHD)

    elif expr == "fierce":
        # Angled fierce eyebrows + glowing blue iris focus + clenched teeth
        rect_px(img, ex_front, ey, 2, 2, EYE_PUPIL)
        px(img, ex_front + 1, ey, EYE_IRIS)
        px(img, ex_back, ey, EYE_PUPIL)
        # Slanted angry brows
        px(img, ex_front - 1, ey - 2, HAIR_SHD)
        px(img, ex_front, ey - 1, HAIR_SHD)
        px(img, ex_back, ey - 1, HAIR_SHD)
        # Clenched white grin
        rect_px(img, hx + head_w - 5, hy + head_h - 2, 3, 1, EYE_WHITE)

    elif expr == "shout":
        # Fierce eyes + wide open battle cry mouth
        rect_px(img, ex_front, ey, 2, 2, EYE_PUPIL)
        px(img, ex_front, ey, EYE_WHITE)
        px(img, ex_front, ey - 1, HAIR_SHD)
        # Open shouting mouth
        rect_px(img, hx + head_w - 5, hy + head_h - 3, 3, 2, MOUTH_RED)
        px(img, hx + head_w - 5, hy + head_h - 3, EYE_WHITE)  # upper teeth

    elif expr == "hurt":
        # Wincing > < eyes + shocked open mouth + sweat drop
        px(img, ex_front - 1, ey - 1, EYE_PUPIL)
        px(img, ex_front, ey, EYE_PUPIL)
        px(img, ex_front - 1, ey + 1, EYE_PUPIL)
        px(img, ex_back, ey, EYE_PUPIL)
        rect_px(img, hx + head_w - 4, hy + head_h - 2, 2, 2, MOUTH_RED)
        # Cyan sweat drop
        px(img, hx + 1, hy + 2, (100, 220, 255, 255))
        px(img, hx + 1, hy + 3, (180, 245, 255, 255))

    elif expr == "victory":
        # Happy curved wink ^ ^ + bright white smile
        px(img, ex_front - 1, ey, EYE_PUPIL)
        px(img, ex_front, ey - 1, EYE_PUPIL)
        px(img, ex_front + 1, ey, EYE_PUPIL)
        px(img, ex_back, ey - 1, EYE_PUPIL)
        rect_px(img, hx + head_w - 5, hy + head_h - 2, 3, 1, EYE_WHITE)
        px(img, hx + head_w - 4, hy + head_h - 1, MOUTH_RED)


# ==============================================================================
# 5 PIXEL-ART / HI-BIT ORIGINAL CHARACTER STYLES + 1 HD VECTOR CEL-SHADED STYLE
# ==============================================================================
def render_pixel_style_pose(style_id: int, pose: str = "idle", expr: str = "confident") -> Image.Image:
    """
    Renders one of the pixel/hi-bit styles (Styles 1, 2, 3, 5, 6) in the requested pose & expression.
    Canvas is 48x48 transparent RGBA, ground baseline at y = 43.
    """
    img = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    gy = 43  # Ground baseline

    # Configure anatomy parameters per style
    if style_id == 1:
        # Style 1: Modern Hi-Bit Anime Striker (3.5 heads, S-curve spine, 28x36)
        head_w, head_h = 8, 8
        torso_w, torso_h = 8, 10
        leg_h = 11
        hair = "spiky_modern"
        j_lit, j_mid, j_shd = JACKET_LIT, JACKET_MID, JACKET_SHD
    elif style_id == 2:
        # Style 2: Chibi-Tactical Expressive Brawler (2.5 heads, big expressive face + big fists/boots)
        head_w, head_h = 11, 10
        torso_w, torso_h = 8, 8
        leg_h = 8
        hair = "chibi_fluffy"
        j_lit, j_mid, j_shd = (245, 95, 65, 255), (205, 58, 36, 255), (140, 32, 20, 255)
    elif style_id == 3:
        # Style 3: Street Martial Artist (4.0 heads, muscular V-taper torso, MMA guard, headband)
        head_w, head_h = 8, 8
        torso_w, torso_h = 10, 12
        leg_h = 13
        hair = "martial_bandana"
        j_lit, j_mid, j_shd = (235, 240, 250, 255), (195, 205, 222, 255), (140, 152, 175, 255)
    elif style_id == 5:
        # Style 5: Neo-Arcade Heroic Agent (3.0 heads, heroic lean-back posture, energetic jacket)
        head_w, head_h = 9, 9
        torso_w, torso_h = 9, 9
        leg_h = 10
        hair = "arcade_pompadour"
        j_lit, j_mid, j_shd = (65, 205, 135, 255), (38, 158, 98, 255), (22, 105, 62, 255)
    else:
        # Style 6: Sleek Cyber-Runner (3.8 heads, forward kinetic lean, glowing scarf)
        head_w, head_h = 8, 8
        torso_w, torso_h = 7, 11
        leg_h = 12
        hair = "cyber_sleek"
        j_lit, j_mid, j_shd = (95, 75, 195, 255), (62, 46, 145, 255), (38, 26, 95, 255)

    cx = 22
    fist_size = 4 if style_id == 2 else 3

    if pose == "idle":
        # Dynamic athletic stance: wide planted boots, articulated knees, S-curve spine, upright neck
        hip_y = gy - leg_h
        torso_y = hip_y - torso_h
        head_x = cx - head_w // 2 + (1 if style_id == 6 else 0)
        head_y = torso_y - head_h - 1

        # Flowing scarf for Style 6
        if style_id == 6:
            line_px(img, cx - 2, torso_y + 1, cx - 10, torso_y - 2, (0, 235, 255, 255), 2)
            line_px(img, cx - 4, torso_y + 2, cx - 12, torso_y + 1, (0, 165, 220, 255), 1)

        # Back leg (shaded, slightly bent knee)
        line_px(img, cx + 2, hip_y, cx + 4, hip_y + leg_h // 2, PANTS_SHD, 3)
        line_px(img, cx + 4, hip_y + leg_h // 2, cx + 5, gy - 2, PANTS_SHD, 3)
        rect_px(img, cx + 3, gy - 3, 5, 3, BOOT_DARK)
        rect_px(img, cx + 3, gy - 1, 5, 1, BOOT_SOLE)

        # Front leg (lit, athletic wide stance)
        line_px(img, cx - 2, hip_y, cx - 4, hip_y + leg_h // 2, PANTS_LIT, 3)
        line_px(img, cx - 4, hip_y + leg_h // 2, cx - 5, gy - 2, PANTS_MID, 3)
        rect_px(img, cx - 7, gy - 3, 5, 3, BOOT_LIT)
        rect_px(img, cx - 7, gy - 1, 5, 1, BOOT_SOLE)

        # V-Tapered Torso (wider chest, tapered waist + belt)
        rect_px(img, cx - torso_w // 2, torso_y, torso_w, torso_h - 2, j_mid)
        rect_px(img, cx - torso_w // 2 + 1, torso_y, torso_w - 1, torso_h // 2, j_lit)
        rect_px(img, cx - torso_w // 2 + 1, torso_y + torso_h - 2, torso_w - 2, 2, j_shd)
        # Inner white tee / chest trim
        rect_px(img, cx + 1, torso_y + 1, 2, torso_h - 3, SHIRT_WHITE)
        rect_px(img, cx - torso_w // 2 + 1, hip_y - 1, torso_w - 2, 1, TRIM_ACCENT)

        # Upright Neck (NOT hunched!)
        rect_px(img, cx - 1, torso_y - 2, 3, 2, SKIN_MID)

        # Back arm (guard hand near chin/chest)
        line_px(img, cx + torso_w // 2 - 1, torso_y + 2, cx + torso_w // 2 + 3, torso_y + 5, j_shd, 2)
        rect_px(img, cx + torso_w // 2 + 3, torso_y + 3, fist_size, fist_size, GLOVE_SHD)

        # Head with expressive face
        draw_expressive_head_pixel(img, head_x, head_y, head_w, head_h, expr, hair)

        # Front arm (bent elbow, raised combat guard)
        line_px(img, cx - torso_w // 2, torso_y + 2, cx - torso_w // 2 - 2, torso_y + 6, j_lit, 2)
        line_px(img, cx - torso_w // 2 - 2, torso_y + 6, cx + 1, torso_y + 5, SKIN_LIT, 2)
        rect_px(img, cx + 1, torso_y + 4, fist_size, fist_size, GLOVE_RED)

    elif pose == "run":
        # Forward 30-degree sprint lean, high knee drive, pumping arms
        hip_y = gy - leg_h + 2
        torso_y = hip_y - torso_h + 1
        # Back leg extended behind
        line_px(img, cx - 2, hip_y, cx - 9, gy - 4, PANTS_SHD, 3)
        rect_px(img, cx - 11, gy - 5, 4, 3, BOOT_DARK)
        # Front leg driving knee high forward
        line_px(img, cx + 2, hip_y, cx + 8, hip_y + 3, PANTS_LIT, 3)
        line_px(img, cx + 8, hip_y + 3, cx + 5, gy - 2, PANTS_MID, 3)
        rect_px(img, cx + 4, gy - 3, 5, 3, BOOT_LIT)
        # Leaning torso
        line_px(img, cx, hip_y, cx + 4, torso_y + 1, j_mid, torso_w - 1)
        line_px(img, cx + 1, hip_y - 2, cx + 5, torso_y + 1, j_lit, torso_w // 2)
        # Neck + Head leaning forward
        rect_px(img, cx + 4, torso_y - 2, 3, 2, SKIN_MID)
        draw_expressive_head_pixel(img, cx + 2, torso_y - head_h - 1, head_w, head_h, "fierce", hair)
        # Pumping arms
        line_px(img, cx + 3, torso_y + 2, cx - 5, torso_y + 6, j_lit, 2)
        rect_px(img, cx - 7, torso_y + 5, fist_size, fist_size, GLOVE_RED)
        line_px(img, cx + 5, torso_y + 2, cx + 11, torso_y + 4, j_shd, 2)
        rect_px(img, cx + 11, torso_y + 2, fist_size, fist_size, GLOVE_RED)

    elif pose == "jump":
        # Airborne tucked knee + dynamic upward reach
        hip_y = gy - leg_h - 6
        torso_y = hip_y - torso_h
        # Back leg tucked
        line_px(img, cx - 1, hip_y, cx - 5, hip_y + 6, PANTS_SHD, 3)
        rect_px(img, cx - 7, hip_y + 6, 4, 3, BOOT_DARK)
        # Front leg high knee tuck
        line_px(img, cx + 2, hip_y, cx + 7, hip_y + 2, PANTS_LIT, 3)
        line_px(img, cx + 7, hip_y + 2, cx + 5, hip_y + 7, PANTS_MID, 3)
        rect_px(img, cx + 4, hip_y + 7, 5, 3, BOOT_LIT)
        # Torso
        rect_px(img, cx - torso_w // 2, torso_y, torso_w, torso_h - 1, j_lit)
        rect_px(img, cx, torso_y - 2, 3, 2, SKIN_MID)
        draw_expressive_head_pixel(img, cx - head_w // 2 + 1, torso_y - head_h - 1, head_w, head_h, "confident", hair)
        # Arms raised dynamically
        line_px(img, cx - torso_w // 2, torso_y + 2, cx - torso_w // 2 - 4, torso_y - 3, j_lit, 2)
        rect_px(img, cx - torso_w // 2 - 5, torso_y - 5, fist_size, fist_size, GLOVE_RED)

    elif pose == "punch":
        # Deep lunge + shoulder rotation + oversized impact fist with 3-layer smear arc
        hip_y = gy - leg_h + 2
        torso_y = hip_y - torso_h + 1
        # Wide lunge legs
        line_px(img, cx - 2, hip_y, cx - 8, gy - 2, PANTS_SHD, 3)
        rect_px(img, cx - 10, gy - 3, 5, 3, BOOT_DARK)
        line_px(img, cx + 2, hip_y, cx + 8, gy - 2, PANTS_LIT, 3)
        rect_px(img, cx + 7, gy - 3, 5, 3, BOOT_LIT)
        # Torso twisted into punch
        rect_px(img, cx - torso_w // 2 + 1, torso_y, torso_w, torso_h - 1, j_lit)
        rect_px(img, cx + 1, torso_y - 2, 3, 2, SKIN_MID)
        draw_expressive_head_pixel(img, cx - head_w // 2 + 2, torso_y - head_h - 1, head_w, head_h, "shout", hair)
        # Full extended punch arm + impact smear
        line_px(img, cx + 3, torso_y + 3, cx + 14, torso_y + 3, j_lit, 3)
        rect_px(img, cx + 14, torso_y + 1, fist_size + 2, fist_size + 2, GLOVE_RED)
        # Crisp 3-layer punch shock arc
        line_px(img, cx + 18, torso_y - 2, cx + 21, torso_y + 3, TRIM_ACCENT, 2)
        line_px(img, cx + 21, torso_y + 3, cx + 18, torso_y + 8, TRIM_ACCENT, 2)
        line_px(img, cx + 19, torso_y, cx + 21, torso_y + 3, EYE_WHITE, 1)

    elif pose == "gun":
        # Tactical weaver gun stance + dual-hand pistol grip + muzzle flash
        hip_y = gy - leg_h + 1
        torso_y = hip_y - torso_h
        line_px(img, cx - 2, hip_y, cx - 5, gy - 2, PANTS_LIT, 3)
        rect_px(img, cx - 7, gy - 3, 5, 3, BOOT_LIT)
        line_px(img, cx + 2, hip_y, cx + 6, gy - 2, PANTS_SHD, 3)
        rect_px(img, cx + 5, gy - 3, 5, 3, BOOT_DARK)
        rect_px(img, cx - torso_w // 2, torso_y, torso_w, torso_h - 1, j_mid)
        rect_px(img, cx, torso_y - 2, 3, 2, SKIN_MID)
        draw_expressive_head_pixel(img, cx - head_w // 2 + 1, torso_y - head_h - 1, head_w, head_h, "fierce", hair)
        # Extended aim arm + detailed pistol
        line_px(img, cx + 2, torso_y + 3, cx + 12, torso_y + 2, j_lit, 2)
        rect_px(img, cx + 11, torso_y + 1, 3, 3, GLOVE_RED)
        rect_px(img, cx + 13, torso_y - 1, 7, 3, GUN_METAL)
        rect_px(img, cx + 13, torso_y + 1, 2, 3, GUN_DARK)
        # Muzzle flash star
        rect_px(img, cx + 21, torso_y - 2, 3, 4, MUZZLE_GLOW)
        px(img, cx + 22, torso_y - 1, EYE_WHITE)

    elif pose == "roll":
        # Compact acrobatic tuck roll with motion trail
        cy = gy - 11
        rect_px(img, cx - 6, cy - 6, 12, 12, j_mid)
        rect_px(img, cx - 4, cy - 5, 8, 8, j_lit)
        rect_px(img, cx + 2, cy - 4, 5, 5, HAIR_MID)
        rect_px(img, cx - 5, cy + 2, 5, 4, BOOT_LIT)
        line_px(img, cx - 10, cy - 4, cx - 4, cy - 8, (120, 210, 255, 255), 1)
        line_px(img, cx - 11, cy + 2, cx - 5, cy + 6, (120, 210, 255, 255), 1)

    return add_pixel_outline(img, OUTLINE)


# ==============================================================================
# STYLE 4: HD VECTOR / CEL-SHADED PUPPET HERO (SMOOTH ANTI-ALIASED 2D ART)
# ==============================================================================
def render_vector_cel_pose(pose: str = "idle", expr: str = "confident", scale_size: int = 192) -> Image.Image:
    """
    Renders Style 4: Clean Vector / Cel-Shaded Puppet Hero at high resolution
    (smooth ink outlines, cel shading, expressive cartoon/anime eyes & mouth, zero pixelation).
    """
    W = 240
    H = 240
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    gy = 212
    cx = 110

    def poly_ink(pts, fill_col, outline_col=OUTLINE, width=4):
        d.polygon(pts, fill=fill_col)
        d.line(pts + [pts[0]], fill=outline_col, width=width, joint="curve")

    def limb_ink(p0, p1, r, fill_col, width=4):
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        L = max(1.0, math.hypot(dx, dy))
        nx, ny = -dy / L * r, dx / L * r
        pts = [
            (p0[0] + nx, p0[1] + ny),
            (p1[0] + nx * 0.85, p1[1] + ny * 0.85),
            (p1[0] - nx * 0.85, p1[1] - ny * 0.85),
            (p0[0] - nx, p0[1] - ny),
        ]
        poly_ink(pts, fill_col, OUTLINE, width)

    lean = 18 if pose in ("run", "punch") else 0
    hip_x, hip_y = cx, gy - 58 if pose != "jump" else gy - 82
    sh_x, sh_y = cx + lean, hip_y - 52

    # Red flowing scarf
    scarf_pts = [
        (sh_x - 8, sh_y + 4),
        (sh_x - 54 - lean, sh_y - 10),
        (sh_x - 68 - lean, sh_y + 10),
        (sh_x - 16, sh_y + 18),
    ]
    poly_ink(scarf_pts, GLOVE_RED, OUTLINE, 4)

    # Back Leg
    if pose == "run":
        limb_ink((hip_x, hip_y), (hip_x - 42, gy - 16), 11, PANTS_SHD)
    else:
        limb_ink((hip_x + 8, hip_y), (hip_x + 22, gy - 14), 11, PANTS_SHD)
        poly_ink([(hip_x + 12, gy - 16), (hip_x + 38, gy - 16), (hip_x + 42, gy - 2), (hip_x + 10, gy - 2)], BOOT_DARK)

    # Front Leg
    if pose == "run":
        limb_ink((hip_x, hip_y), (hip_x + 36, hip_y + 18), 12, PANTS_LIT)
        limb_ink((hip_x + 36, hip_y + 18), (hip_x + 24, gy - 10), 10, PANTS_MID)
    else:
        limb_ink((hip_x - 8, hip_y), (hip_x - 22, gy - 14), 12, PANTS_LIT)
        poly_ink([(hip_x - 32, gy - 16), (hip_x - 6, gy - 16), (hip_x - 4, gy - 2), (hip_x - 36, gy - 2)], BOOT_LIT)

    # Athletic V-Tapered Jacket Torso (S-curve posture)
    torso_pts = [
        (sh_x - 24, sh_y),
        (sh_x + 24, sh_y),
        (hip_x + 15, hip_y + 4),
        (hip_x - 15, hip_y + 4),
    ]
    poly_ink(torso_pts, JACKET_LIT, OUTLINE, 4)
    # Inner white shirt & gold belt
    poly_ink([(sh_x - 6, sh_y + 2), (sh_x + 10, sh_y + 2), (hip_x + 5, hip_y), (hip_x - 4, hip_y)], SHIRT_WHITE, OUTLINE, 3)
    poly_ink([(hip_x - 16, hip_y - 4), (hip_x + 16, hip_y - 4), (hip_x + 16, hip_y + 5), (hip_x - 16, hip_y + 5)], TRIM_ACCENT, OUTLINE, 3)

    # Neck
    poly_ink([(sh_x - 7, sh_y - 12), (sh_x + 9, sh_y - 12), (sh_x + 9, sh_y + 3), (sh_x - 7, sh_y + 3)], SKIN_MID, OUTLINE, 3)

    # Sculpted Head (Anime/Cartoon jaw taper, NOT a box)
    hx, hy = sh_x + 2, sh_y - 36
    head_pts = [
        (hx - 22, hy - 18),
        (hx + 24, hy - 18),
        (hx + 26, hy + 6),
        (hx + 12, hy + 24),
        (hx - 6, hy + 24),
        (hx - 22, hy + 8),
    ]
    poly_ink(head_pts, SKIN_LIT, OUTLINE, 4)

    # Swept Spiky Hair
    hair_pts = [
        (hx - 26, hy - 4),
        (hx - 32, hy - 22),
        (hx - 12, hy - 34),
        (hx + 8, hy - 38),
        (hx + 34, hy - 24),
        (hx + 24, hy - 12),
        (hx + 36, hy - 8),
        (hx + 16, hy - 4),
        (hx - 14, hy - 6),
    ]
    poly_ink(hair_pts, HAIR_MID, OUTLINE, 4)

    # Expressive Vector Eyes & Mouth
    for ex_off in (-2, 13):
        ex = hx + ex_off
        ey = hy + 2
        if expr in ("confident", "fierce", "shout"):
            d.ellipse([ex - 5, ey - 7, ex + 5, ey + 7], fill=EYE_WHITE, outline=OUTLINE, width=2)
            d.ellipse([ex - 3, ey - 5, ex + 4, ey + 6], fill=EYE_IRIS)
            d.ellipse([ex - 2, ey - 3, ex + 3, ey + 4], fill=EYE_PUPIL)
            d.ellipse([ex - 3, ey - 5, ex + 1, ey - 1], fill=EYE_WHITE)  # catchlight
            brow_y = ey - 10 if expr == "confident" else ey - 8
            d.line([(ex - 6, brow_y - (2 if expr == "fierce" else 0)), (ex + 6, brow_y + (2 if expr == "fierce" else 0))], fill=OUTLINE, width=3)
        elif expr == "hurt":
            d.line([(ex - 5, ey - 5), (ex + 4, ey), (ex - 5, ey + 5)], fill=OUTLINE, width=3)
        elif expr == "victory":
            d.arc([ex - 6, ey - 6, ex + 6, ey + 6], start=190, end=350, fill=OUTLINE, width=3)

    # Mouth
    if expr == "confident":
        d.arc([hx - 2, hy + 8, hx + 16, hy + 18], start=10, end=165, fill=OUTLINE, width=3)
    elif expr == "fierce":
        d.polygon([(hx, hy + 12), (hx + 16, hy + 11), (hx + 14, hy + 18), (hx + 2, hy + 18)], fill=EYE_WHITE, outline=OUTLINE)
    elif expr in ("shout", "hurt"):
        d.ellipse([hx + 2, hy + 10, hx + 16, hy + 21], fill=MOUTH_RED, outline=OUTLINE, width=3)
    elif expr == "victory":
        d.chord([hx - 2, hy + 9, hx + 18, hy + 20], start=0, end=180, fill=MOUTH_RED, outline=OUTLINE, width=3)

    # Front Arm / Action
    if pose == "punch":
        limb_ink((sh_x + 10, sh_y + 10), (sh_x + 74, sh_y + 8), 11, JACKET_LIT)
        d.ellipse([sh_x + 68, sh_y - 8, sh_x + 102, sh_y + 24], fill=GLOVE_RED, outline=OUTLINE, width=4)
        d.arc([sh_x + 88, sh_y - 26, sh_x + 126, sh_y + 42], start=-55, end=55, fill=TRIM_ACCENT, width=6)
    elif pose == "gun":
        limb_ink((sh_x + 10, sh_y + 10), (sh_x + 64, sh_y + 6), 10, JACKET_LIT)
        poly_ink([(sh_x + 64, sh_y - 6), (sh_x + 104, sh_y - 6), (sh_x + 104, sh_y + 8), (sh_x + 64, sh_y + 8)], GUN_METAL, OUTLINE, 4)
        d.ellipse([sh_x + 106, sh_y - 14, sh_x + 128, sh_y + 12], fill=MUZZLE_GLOW)
    else:
        limb_ink((sh_x - 16, sh_y + 8), (sh_x - 24, sh_y + 34), 10, JACKET_LIT)
        limb_ink((sh_x - 24, sh_y + 34), (sh_x + 6, sh_y + 26), 9, SKIN_LIT)
        d.ellipse([sh_x + 2, sh_y + 14, sh_x + 26, sh_y + 36], fill=GLOVE_RED, outline=OUTLINE, width=4)

    if scale_size != W:
        return img.resize((scale_size, scale_size), Image.Resampling.LANCZOS)
    return img


# ==============================================================================
# BUILD INDIVIDUAL STYLE SHOWCASE BOARDS & MASTER COMPARISON SHEET
# ==============================================================================
STYLES_META = [
    {
        "id": 1,
        "code": "MAU 1 (KHUYEN NGHI #1)",
        "title": "Modern Hi-Bit Anime Striker (Ty le 3.5 Dau - Khuon Xuong Chu S)",
        "subtitle": "Lung thang khoe khoan, vai chu V, 2 mat sang co hon + 5 bieu cam song dong, khop tay chan ro rang",
        "accent": (64, 185, 255),
    },
    {
        "id": 2,
        "code": "MAU 2 (BIU CAM SIEU RO)",
        "title": "Expressive Pocket Brawler (Ty le 2.5 Dau - Nam Dam & Bieu Cam Lon)",
        "subtitle": "Dau & mat lon nhin ro bieu cam tu xa (kieu River City / Mega Man Zero), nam dam to uy luc",
        "accent": (255, 115, 75),
    },
    {
        "id": 3,
        "code": "MAU 3 (VO SI DUONG PHO)",
        "title": "Street Martial Artist (Ty le 4.0 Dau - Giai Phau Vo Thuat KOF / Streets of Rage)",
        "subtitle": "Ty le co the can doi 4 dau, the thu Boxing/MMA chuyen nghiep, bang tran do bay theo chuyen dong",
        "accent": (255, 205, 70),
    },
    {
        "id": 4,
        "code": "MAU 4 (VECTOR HD-2D MUOT)",
        "title": "Clean Vector / Cel-Shaded Hero (Khong O Vuong Pixel - Net Muc Muot HD)",
        "subtitle": "Ve bang duong cong Vector & Cel-Shading muot ma (kieu Guacamelee / Shank), bieu cam nhu phim hoat hinh",
        "accent": (190, 115, 255),
    },
    {
        "id": 5,
        "code": "MAU 5 (NEO-ARCADE SONG DONG)",
        "title": "Neo-Arcade Action Hero (Ty le 3.0 Dau - Phong Cach Scott Pilgrim / Metal Slug)",
        "subtitle": "Dang dung ngung cao day khi chat, toc bong benh, bieu cam hai huoc & co gian Squash-and-Stretch",
        "accent": (75, 230, 150),
    },
    {
        "id": 6,
        "code": "MAU 6 (TOC DO CAO SLEEK)",
        "title": "Sleek Cyber-Runner (Ty le 3.8 Dau - Dang Thon Dai Toc Do Kieu Katana ZERO)",
        "subtitle": "Khung xuong thanh thoat nghien ve truoc san sang but toc, khan nang luong Cyan bay nguoc",
        "accent": (0, 235, 255),
    },
]


def draw_spine_comparison_diagram(canvas: Image.Image, x: int, y: int, w: int, h: int, style_meta: dict):
    """Draws a side-by-side Spine & Anatomy diagram: Old Y8 Hunchback vs New Original Spine."""
    d = ImageDraw.Draw(canvas)
    f_b = get_font(14, True)
    f_r = get_font(12, False)
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=(20, 25, 36), outline=(55, 68, 95), width=2)
    d.text((x + 14, y + 10), "1. SO SANH KHUON XUONG SONG & DAU (SPINE & HEAD ANATOMY)", fill=(255, 220, 110), font=f_b)

    # Left half: Old Y8 Hunchback
    lx = x + 16
    ly = y + 38
    lw = w // 2 - 24
    lh = h - 50
    d.rounded_rectangle([lx, ly, lx + lw, ly + lh], radius=8, fill=(36, 22, 26), outline=(180, 60, 60), width=1)
    d.text((lx + 10, ly + 8), "CU (Superfighters Y8): Gung lung + Kinh den", fill=(255, 120, 120), font=f_b)
    old_spr = draw_old_y8_reference().resize((160, 192), Image.Resampling.NEAREST)
    canvas.alpha_composite(old_spr, (lx + 10, ly + 30))
    # Draw hunchback red spine curve overlay
    sx = lx + 92
    sy = ly + 100
    d.line([(sx, sy - 20), (sx - 16, sy + 10), (sx - 16, sy + 52)], fill=(255, 70, 70), width=4)
    d.text((lx + 145, ly + 55), "- Dau vuong 7x6", fill=(235, 175, 175), font=f_r)
    d.text((lx + 145, ly + 75), "- Co lao ve truoc (Gu)", fill=(235, 175, 175), font=f_r)
    d.text((lx + 145, ly + 95), "- Kinh den 5x1 vo hon", fill=(235, 175, 175), font=f_r)
    d.text((lx + 145, ly + 115), "- 0 bieu cam khuon mat", fill=(235, 175, 175), font=f_r)
    d.text((lx + 145, ly + 135), "- Chan que 2px cung", fill=(235, 175, 175), font=f_r)

    # Right half: New SuperAgent Original Anatomy
    rx = x + w // 2 + 8
    ry = ly
    rw = lw
    rh = lh
    d.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=8, fill=(18, 34, 32), outline=style_meta["accent"], width=2)
    d.text((rx + 10, ry + 8), f"MOI ({style_meta['code']}): Xuong Chu S + Co Hon", fill=(130, 255, 175), font=f_b)

    sid = style_meta["id"]
    if sid == 4:
        new_spr = render_vector_cel_pose("idle", "confident", 180)
    else:
        new_spr = render_pixel_style_pose(sid, "idle", "confident").resize((180, 180), Image.Resampling.NEAREST)
    canvas.alpha_composite(new_spr, (rx + 4, ry + 26))

    # S-Curve green spine indicator
    nsx = rx + 92
    nsy = ry + 95
    d.line([(nsx + 4, nsy - 32), (nsx - 3, nsy - 6), (nsx + 3, nsy + 26), (nsx - 6, nsy + 64)], fill=(80, 255, 140), width=4)
    d.text((rx + 150, ry + 55), "+ Cot song Chu S khoe", fill=(195, 255, 215), font=f_r)
    d.text((rx + 150, ry + 75), "+ Co & Vai tach biet", fill=(195, 255, 215), font=f_r)
    d.text((rx + 150, ry + 95), "+ Mat 2 tang + anh sang", fill=(195, 255, 215), font=f_r)
    d.text((rx + 150, ry + 115), "+ 5 Bieu cam song dong", fill=(195, 255, 215), font=f_r)
    d.text((rx + 150, ry + 135), "+ Khop goi & khuyd tay", fill=(195, 255, 215), font=f_r)


def draw_arena_preview_box(canvas: Image.Image, x: int, y: int, w: int, h: int, style_meta: dict):
    """Renders the character at actual 1x/2x scale on the Steel Harbor stage next to crates & platforms."""
    d = ImageDraw.Draw(canvas)
    f_b = get_font(14, True)
    f_r = get_font(12, False)
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=(18, 22, 32), outline=(65, 82, 115), width=2)
    d.text((x + 14, y + 10), "4. DAT TRONG SAN DAU SUPERAGENT THUC TE (IN-GAME ARENA CONTEXT)", fill=(130, 225, 255), font=f_b)

    # Stage sky & industrial background pillars
    sx, sy = x + 14, y + 36
    sw, sh = w - 28, h - 48
    d.rectangle([sx, sy, sx + sw, sy + sh], fill=(24, 30, 44))
    for gx in range(sx + 30, sx + sw, 90):
        d.rectangle([gx, sy, gx + 14, sy + sh], fill=(30, 38, 54))

    # Steel floor girder
    floor_y = sy + sh - 38
    d.rectangle([sx, floor_y, sx + sw, sy + sh], fill=(52, 60, 76))
    d.rectangle([sx, floor_y, sx + sw, floor_y + 6], fill=(115, 130, 155))

    # Wooden crate for scale comparison
    cx_crate = sx + 55
    cy_crate = floor_y - 36
    d.rectangle([cx_crate, cy_crate, cx_crate + 36, floor_y], fill=(158, 106, 56), outline=(28, 20, 14), width=2)
    d.line([(cx_crate, cy_crate), (cx_crate + 36, floor_y)], fill=(115, 74, 36), width=2)

    sid = style_meta["id"]
    poses = [("idle", "confident", "Dung (Idle)"), ("run", "fierce", "Chay (Run)"), ("punch", "shout", "Dam (Combo)"), ("gun", "fierce", "Ban (Aim)")]
    px_step = (sw - 140) // len(poses)
    for idx, (p_name, ex_name, label) in enumerate(poses):
        char_x = sx + 125 + idx * px_step
        if sid == 4:
            spr = render_vector_cel_pose(p_name, ex_name, 92)
            canvas.alpha_composite(spr, (char_x - 46, floor_y - 82))
        else:
            spr = render_pixel_style_pose(sid, p_name, ex_name).resize((96, 96), Image.Resampling.NEAREST)
            canvas.alpha_composite(spr, (char_x - 48, floor_y - 86))
        # Overhead mini HP + Stamina bar
        d.rectangle([char_x - 22, floor_y - 88, char_x + 22, floor_y - 82], fill=(20, 24, 32), outline=(0, 0, 0))
        d.rectangle([char_x - 21, floor_y - 87, char_x + 14, floor_y - 84], fill=(75, 235, 110))
        d.text((char_x - 32, floor_y + 10), label, fill=(220, 230, 245), font=f_r)


def generate_individual_style_sheet(style_meta: dict) -> str:
    W, H = 1360, 820
    canvas = Image.new("RGBA", (W, H), (12, 15, 22, 255))
    d = ImageDraw.Draw(canvas)
    f_title = get_font(22, True)
    f_sub = get_font(14, False)
    f_sec = get_font(15, True)
    f_lbl = get_font(13, True)

    # Top Header Banner
    d.rounded_rectangle([16, 14, W - 16, 86], radius=12, fill=(22, 28, 42), outline=style_meta["accent"], width=2)
    d.text((32, 24), f"{style_meta['code']} — {style_meta['title']}", fill=style_meta["accent"], font=f_title)
    d.text((32, 54), f"Thiet ke rieng cho Nhan Vat Co Ban SuperAgent: {style_meta['subtitle']}", fill=(215, 225, 242), font=f_sub)

    # Top-Left: Spine & Anatomy Comparison (Old Y8 vs New)
    draw_spine_comparison_diagram(canvas, 16, 100, 650, 260, style_meta)

    # Top-Right: 5 Facial Expressions Showcase (Zoomed 6x)
    ex_x, ex_y, ex_w, ex_h = 682, 100, W - 698, 260
    d.rounded_rectangle([ex_x, ex_y, ex_x + ex_w, ex_y + ex_h], radius=10, fill=(20, 25, 36), outline=(55, 68, 95), width=2)
    d.text((ex_x + 14, ex_y + 10), "2. 5 BIEU CAM GUONG MAT SONG DONG (KHONG DUNG KINH DEN Y8)", fill=(255, 190, 120), font=f_sec)

    expr_list = [
        ("confident", "1. Tu Tin (Idle)"),
        ("fierce", "2. Chien Dau (Focus)"),
        ("shout", "3. Tung Chieu (Shout)"),
        ("hurt", "4. Trung Don (Hurt)"),
        ("victory", "5. Chien Thang (Win)"),
    ]
    sid = style_meta["id"]
    card_w = (ex_w - 28) // 5
    for idx, (e_key, e_title) in enumerate(expr_list):
        cx_card = ex_x + 14 + idx * card_w
        cy_card = ex_y + 40
        d.rounded_rectangle([cx_card + 4, cy_card, cx_card + card_w - 4, cy_card + 204], radius=8, fill=(28, 35, 50), outline=(65, 80, 110), width=1)
        if sid == 4:
            full_spr = render_vector_cel_pose("idle", e_key, 220)
            # Crop around head & upper chest
            head_crop = full_spr.crop((45, 20, 165, 140)).resize((116, 116), Image.Resampling.LANCZOS)
        else:
            full_spr = render_pixel_style_pose(sid, "idle", e_key)
            head_crop = full_spr.crop((10, 4, 34, 28)).resize((116, 116), Image.Resampling.NEAREST)
        canvas.alpha_composite(head_crop, (cx_card + (card_w - 116) // 2, cy_card + 18))
        d.text((cx_card + 10, cy_card + 158), e_title, fill=(235, 242, 255), font=f_lbl)

    # Bottom-Left: 6 Core Action Poses (Idle, Run, Jump, Heavy Punch, Gun Aim, Roll)
    px_box_x, px_box_y, px_box_w, px_box_h = 16, 376, 760, 428
    d.rounded_rectangle([px_box_x, px_box_y, px_box_x + px_box_w, px_box_y + px_box_h], radius=10, fill=(20, 25, 36), outline=(55, 68, 95), width=2)
    d.text((px_box_x + 14, px_box_y + 10), "3. 6 TU THE HANH DONG COT LOI CUA NHAN VAT CO BAN (6 CORE ACTION POSES)", fill=(150, 245, 175), font=f_sec)

    pose_list = [
        ("idle", "confident", "1. Dung Tho (Idle)"),
        ("run", "fierce", "2. Chay But Toc (Run)"),
        ("jump", "confident", "3. Bat Nhay (Jump)"),
        ("punch", "shout", "4. Dam Uy Luc (Combo)"),
        ("gun", "fierce", "5. Ngam Sung (Gun Aim)"),
        ("roll", "fierce", "6. Nhao Lon (Dodge Roll)"),
    ]
    p_card_w = (px_box_w - 28) // 3
    p_card_h = 180
    for idx, (p_key, e_key, p_title) in enumerate(pose_list):
        col = idx % 3
        row = idx // 3
        pcx = px_box_x + 14 + col * p_card_w
        pcy = px_box_y + 42 + row * (p_card_h + 10)
        d.rounded_rectangle([pcx + 4, pcy, pcx + p_card_w - 4, pcy + p_card_h], radius=8, fill=(26, 32, 46), outline=(60, 74, 102), width=1)
        if sid == 4:
            pspr = render_vector_cel_pose(p_key, e_key, 144)
        else:
            pspr = render_pixel_style_pose(sid, p_key, e_key).resize((144, 144), Image.Resampling.NEAREST)
        canvas.alpha_composite(pspr, (pcx + (p_card_w - 144) // 2, pcy + 4))
        d.text((pcx + 16, pcy + p_card_h - 26), p_title, fill=(235, 242, 255), font=f_lbl)

    # Bottom-Right: In-Game Arena Context Preview
    draw_arena_preview_box(canvas, 792, 376, W - 808, 428, style_meta)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"base_character_style_{sid}.png")
    canvas.save(out_path)
    if os.path.exists(ARTIFACT_DIR):
        shutil.copy2(out_path, os.path.join(ARTIFACT_DIR, f"base_character_style_{sid}.png"))
    return out_path


def generate_master_comparison_board() -> str:
    """Generates a single Master Comparison Board putting Old Y8 vs All 6 New Original Styles side-by-side."""
    W, H = 1540, 920
    canvas = Image.new("RGBA", (W, H), (10, 13, 20, 255))
    d = ImageDraw.Draw(canvas)
    f_title = get_font(22, True)
    f_sub = get_font(14, False)
    f_card = get_font(14, True)
    f_small = get_font(12, False)

    d.rounded_rectangle([16, 14, W - 16, 86], radius=12, fill=(22, 28, 42), outline=(90, 180, 255), width=2)
    d.text((30, 22), "BANG TONG HOP SO SANH: 6 MAU THIET KE RIENG CHO NHAN VAT CO BAN (SUPERAGENT)", fill=(110, 215, 255), font=f_title)
    d.text((30, 54), "Loai bo hoan toan khuon xuong gu lung & kinh den cua Superfighters Y8 -> Thay bang Khuon Xuong Chu S, Mat Co Hon & 5 Bieu Cam", fill=(220, 230, 245), font=f_sub)

    # Left column: Old Y8 crossed out
    ox, oy, ow, oh = 16, 100, 195, H - 116
    d.rounded_rectangle([ox, oy, ox + ow, oy + oh], radius=10, fill=(36, 20, 24), outline=(190, 60, 60), width=2)
    d.text((ox + 12, oy + 12), "BAN CU (Y8 GOC)", fill=(255, 110, 110), font=f_card)
    d.text((ox + 12, oy + 32), "Giong Superfighters", fill=(240, 170, 170), font=f_small)
    old_big = draw_old_y8_reference().resize((160, 192), Image.Resampling.NEAREST)
    canvas.alpha_composite(old_big, (ox + 16, oy + 65))
    # Red X over the old Y8 character
    d.line([(ox + 28, oy + 80), (ox + ow - 28, oy + 235)], fill=(255, 65, 65, 200), width=5)
    d.line([(ox + ow - 28, oy + 80), (ox + 28, oy + 235)], fill=(255, 65, 65, 200), width=5)

    issues = [
        "x Gu lung, co ruc",
        "x Dau hop vuong 7x6",
        "x Kinh den ngang 5x1",
        "x Khong co bieu cam",
        "x Tay chan que 2px",
        "x Giong het Y8 cu",
    ]
    for i, txt in enumerate(issues):
        d.text((ox + 14, oy + 280 + i * 28), txt, fill=(255, 165, 165), font=f_small)

    # 6 Columns for Styles 1..6
    avail_w = W - ox - ow - 32
    col_w = avail_w // 6
    for idx, meta in enumerate(STYLES_META):
        cx = ox + ow + 14 + idx * col_w
        cy = oy
        cw = col_w - 8
        ch = oh
        sid = meta["id"]
        d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=10, fill=(20, 26, 38), outline=meta["accent"], width=2)
        d.text((cx + 10, cy + 12), f"MAU {sid}", fill=meta["accent"], font=f_card)
        short_title = meta["title"].split("(")[0].strip()
        d.text((cx + 10, cy + 32), short_title[:22], fill=(235, 242, 255), font=f_small)

        # 1. Idle Pose (Zoomed)
        d.rounded_rectangle([cx + 8, cy + 58, cx + cw - 8, cy + 238], radius=8, fill=(28, 35, 50))
        if sid == 4:
            spr_idle = render_vector_cel_pose("idle", "confident", 160)
        else:
            spr_idle = render_pixel_style_pose(sid, "idle", "confident").resize((160, 160), Image.Resampling.NEAREST)
        canvas.alpha_composite(spr_idle, (cx + (cw - 160) // 2, cy + 68))
        d.text((cx + 14, cy + 216), "Dang Dung (Idle)", fill=(190, 210, 235), font=f_small)

        # 2. 3 Face Expressions strip (Confident, Shout, Hurt)
        d.rounded_rectangle([cx + 8, cy + 248, cx + cw - 8, cy + 382], radius=8, fill=(26, 32, 46))
        d.text((cx + 12, cy + 254), "Bieu Cam Mat:", fill=(255, 210, 120), font=f_small)
        for e_i, e_k in enumerate(["confident", "shout", "hurt"]):
            if sid == 4:
                f_spr = render_vector_cel_pose("idle", e_k, 160).crop((32, 14, 122, 104)).resize((62, 62), Image.Resampling.LANCZOS)
            else:
                f_spr = render_pixel_style_pose(sid, "idle", e_k).crop((10, 4, 34, 28)).resize((62, 62), Image.Resampling.NEAREST)
            canvas.alpha_composite(f_spr, (cx + 8 + e_i * 64, cy + 286))

        # 3. Punch & Gun Action Poses
        d.rounded_rectangle([cx + 8, cy + 392, cx + cw - 8, cy + 568], radius=8, fill=(28, 35, 50))
        d.text((cx + 12, cy + 398), "Ra Don & Ban Sung:", fill=(140, 245, 175), font=f_small)
        if sid == 4:
            spr_p = render_vector_cel_pose("punch", "shout", 110)
            spr_g = render_vector_cel_pose("gun", "fierce", 110)
        else:
            spr_p = render_pixel_style_pose(sid, "punch", "shout").resize((110, 110), Image.Resampling.NEAREST)
            spr_g = render_pixel_style_pose(sid, "gun", "fierce").resize((110, 110), Image.Resampling.NEAREST)
        canvas.alpha_composite(spr_p, (cx + 2, cy + 432))
        canvas.alpha_composite(spr_g, (cx + cw // 2 - 8, cy + 432))

        # 4. In-Game Stage Scale Box
        d.rounded_rectangle([cx + 8, cy + 578, cx + cw - 8, cy + ch - 12], radius=8, fill=(22, 28, 42))
        d.text((cx + 12, cy + 584), "Tren San Dau (In-Game):", fill=(130, 220, 255), font=f_small)
        floor_y = cy + ch - 36
        d.rectangle([cx + 12, floor_y, cx + cw - 12, cy + ch - 16], fill=(60, 70, 88))
        d.rectangle([cx + 12, floor_y, cx + cw - 12, floor_y + 5], fill=(120, 138, 165))
        # Crate
        d.rectangle([cx + 24, floor_y - 34, cx + 58, floor_y], fill=(158, 106, 56), outline=(28, 20, 14), width=2)
        if sid == 4:
            spr_st = render_vector_cel_pose("idle", "confident", 88)
            canvas.alpha_composite(spr_st, (cx + 82, floor_y - 78))
        else:
            spr_st = render_pixel_style_pose(sid, "idle", "confident").resize((92, 92), Image.Resampling.NEAREST)
            canvas.alpha_composite(spr_st, (cx + 80, floor_y - 82))

    out_path = os.path.join(OUT_DIR, "base_character_master_6_styles_comparison.png")
    canvas.save(out_path)
    if os.path.exists(ARTIFACT_DIR):
        shutil.copy2(out_path, os.path.join(ARTIFACT_DIR, "base_character_master_6_styles_comparison.png"))
    return out_path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    master = generate_master_comparison_board()
    print(f"Generated Master Comparison: {master}")
    for meta in STYLES_META:
        p = generate_individual_style_sheet(meta)
        print(f"Generated Style {meta['id']}: {p}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
CB-WP1: Studio HD-2D Chibi Brawler (2.5-Head, 18.0 World Units) Asset & Layered Atlas Builder.
Extracts and packages:
1. All 7 HD 256x256 Expression Portraits (CHEEKY_SMIRK, BLAZING_GLARE, WIDE_MOUTH_SHOUT,
   DIZZY_SPIRAL_HURT, ECSTATIC_VICTORY_LAUGH, LOW_HP_SWEAT, KO_STARS) into res://assets/portraits/
2. All 6 Spotless Transparent Studio HD-2D Action Pose Cutouts (idle, run, jump, punch, aim, roll)
   + Hero Neutral Pose with Connected-Component Filtering & 4-Texel Alpha Edge Color Extrusion
   into res://assets/sprites/chibi_brawler/
3. Complete Chibi Atlas & State Coverage Manifest (res://data/chibi_atlas_manifest.json)
"""

from collections import deque
import hashlib
import json
import math
import os
import shutil
from PIL import Image, ImageDraw
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BRAIN_SHEET_PATH = (
    r"C:\Users\truon\.gemini\antigravity\brain\fb4592d9-c914-4d42-b275-d495b41a423b"
    r"\superagent_chibi_brawler_sheet_1793104764257.jpg"
)
SHEETS_DIR = os.path.join(PROJECT_ROOT, "assets", "sheets")
PORTRAITS_DIR = os.path.join(PROJECT_ROOT, "assets", "portraits")
POSES_DIR = os.path.join(PROJECT_ROOT, "assets", "sprites", "chibi_brawler")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().upper()


def apply_alpha_edge_extrusion(rgba: np.ndarray, passes: int = 4) -> np.ndarray:
    """
    CB-EC-07 / CB-EC-53: Extrudes RGB colors of opaque border pixels into adjacent transparent
    pixels (while keeping alpha = 0) so linear mipmap filtering never samples dark background RGB.
    """
    out = rgba.copy()
    h, w, _ = out.shape
    opaque = out[:, :, 3] > 24
    rgb = out[:, :, :3].copy()
    for _ in range(passes):
        new_rgb = rgb.copy()
        new_opaque = opaque.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            shifted_op = np.zeros_like(opaque)
            shifted_rgb = np.zeros_like(rgb)
            y_src0, y_src1 = max(0, -dy), min(h, h - dy)
            x_src0, x_src1 = max(0, -dx), min(w, w - dx)
            y_dst0, y_dst1 = max(0, dy), min(h, h + dy)
            x_dst0, x_dst1 = max(0, dx), min(w, w + dx)
            shifted_op[y_dst0:y_dst1, x_dst0:x_dst1] = opaque[y_src0:y_src1, x_src0:x_src1]
            shifted_rgb[y_dst0:y_dst1, x_dst0:x_dst1] = rgb[y_src0:y_src1, x_src0:x_src1]
            fill_mask = (~new_opaque) & shifted_op
            new_rgb[fill_mask] = shifted_rgb[fill_mask]
            new_opaque[fill_mask] = True
        rgb = new_rgb
        opaque = new_opaque
    transparent_mask = out[:, :, 3] == 0
    out[transparent_mask, :3] = rgb[transparent_mask]
    return out


def extract_clean_pose(
    master_img: Image.Image,
    crop_box: tuple[int, int, int, int],
    min_component_px: int = 260,
    pose_key: str = "",
) -> Image.Image:
    """
    Extracts a clean RGBA character pose cutout from the master sheet:
    1. Border flood-fill background removal (handles dark slate BG + blueprint guide lines)
       WITHOUT punching holes in dark navy clothing/gloves inside the character outline!
    2. Explicit removal of the horizontal blueprint guide line at master y=538..544 & y=712..717.
    3. Connected-component filtering (removes detached speed lines, dust specks, guide ticks).
    4. Tight non-empty alpha crop + 4-pixel transparent margin + 4-texel RGB edge extrusion.
    """
    x0_m, y0_m, x1_m, y1_m = crop_box
    sub = master_img.crop(crop_box).convert("RGBA")
    arr = np.array(sub, dtype=np.int16)
    h, w, _ = arr.shape
    bg_ref = np.array([28, 34, 46], dtype=np.int16)
    guide_ref = np.array([58, 70, 88], dtype=np.int16)

    dist_bg = np.abs(arr[:, :, :3] - bg_ref).sum(axis=2)
    dist_guide = np.abs(arr[:, :, :3] - guide_ref).sum(axis=2)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # Background is dark slate; stop strictly at the dark ink outline (which has r,g,b < 24)
    is_dark_ink = (r < 24) & (g < 27) & (b < 35)
    is_slate_bg = (~is_dark_ink) & (
        (dist_bg < 30)
        | ((dist_guide < 38) & (b >= g) & (g >= r - 4) & (b < 112))
    )

    # Allow the horizontal blueprint rules at master y=539..543 and y=715..717 outside the character's black ink outline
    for my in list(range(max(y0_m, 539), min(y1_m, 544))) + list(range(max(y0_m, 715), min(y1_m, 718))):
        ly = my - y0_m
        line_mask = (~is_dark_ink[ly, :]) & (b[ly, :] >= g[ly, :] - 3) & (g[ly, :] >= r[ly, :] - 3) & (b[ly, :] < 118)
        is_slate_bg[ly, line_mask] = True

    visited = np.zeros((h, w), dtype=bool)
    q = deque()
    for x in range(w):
        if is_slate_bg[0, x]:
            visited[0, x] = True
            q.append((0, x))
        if is_slate_bg[h - 1, x]:
            visited[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(h):
        if is_slate_bg[y, 0]:
            visited[y, 0] = True
            q.append((y, 0))
        if is_slate_bg[y, w - 1]:
            visited[y, w - 1] = True
            q.append((y, w - 1))

    # For 'punch', also seed the enclosed slate background pocket between torso and punch arc (mx ~ 815, my ~ 620)
    if pose_key == "punch":
        px_seed, py_seed = 815 - x0_m, 620 - y0_m
        if 0 <= py_seed < h and 0 <= px_seed < w and not visited[py_seed, px_seed]:
            visited[py_seed, px_seed] = True
            q.append((py_seed, px_seed))
    elif pose_key == "aim":
        # Seed the enclosed slate background triangle between the two legs (mx ~ 1008, my ~ 685)
        ax_seed, ay_seed = 1008 - x0_m, 685 - y0_m
        if 0 <= ay_seed < h and 0 <= ax_seed < w and not visited[ay_seed, ax_seed]:
            visited[ay_seed, ax_seed] = True
            q.append((ay_seed, ax_seed))

    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                if is_slate_bg[ny, nx]:
                    visited[ny, nx] = True
                    q.append((ny, nx))

    bg_mask = visited
    rgba = np.array(sub, dtype=np.uint8)
    rgba[bg_mask, 3] = 0

    # Erase any remaining horizontal baseline rule pixels at master y >= 714 outside the shoes
    for my in range(max(y0_m, 714), y1_m):
        ly = my - y0_m
        for lx in range(w):
            if not is_dark_ink[ly, lx] and b[ly, lx] >= g[ly, lx] - 3 and r[ly, lx] < 115:
                rgba[ly, lx, 3] = 0

    # For 'run', use the exact measured left-ink silhouette contour to remove the left-side speed bars
    # while keeping 100% of the character's hair, back glove, shorts, calf, and sneakers intact!
    if pose_key == "run":
        for ly in range(h):
            my = y0_m + ly
            if my <= 547:
                min_mx = 403
            elif my <= 567:
                min_mx = 385
            elif my <= 596:
                min_mx = 398
            elif my <= 604:
                min_mx = 376
            elif my <= 612:
                min_mx = 352
            elif my <= 641:
                min_mx = 338
            elif my <= 657:
                min_mx = 372
            elif my <= 667:
                min_mx = 360
            elif my <= 676:
                min_mx = 345
            else:
                min_mx = 323
            cut_lx = max(0, min(w, min_mx - x0_m))
            rgba[ly, :cut_lx, 3] = 0
            # Clear the enclosed pocket under the back arm (mx 364..383, my 608..639) and under the back calf (mx 347..378, my >= 686)
            for lx in range(w):
                mx = x0_m + lx
                if 609 <= my <= 639 and 364 <= mx <= 383 and not is_dark_ink[ly, lx] and b[ly, lx] < r[ly, lx] + 4:
                    rgba[ly, lx, 3] = 0
                elif my >= 686 and 347 <= mx <= 378 and (my >= 691 or dist_bg[ly, lx] < 38 or r[ly, lx] > b[ly, lx] + 6):
                    rgba[ly, lx, 3] = 0

    # Soften 1px outer anti-aliasing fringe against dark slate background
    fg_mask = rgba[:, :, 3] > 0
    comp_visited = np.zeros((h, w), dtype=bool)
    for y0 in range(h):
        for x0 in range(w):
            if fg_mask[y0, x0] and not comp_visited[y0, x0]:
                comp = []
                cq = deque([(y0, x0)])
                comp_visited[y0, x0] = True
                while cq:
                    cy, cx = cq.popleft()
                    comp.append((cy, cx))
                    for ny, nx in (
                        (cy - 1, cx),
                        (cy + 1, cx),
                        (cy, cx - 1),
                        (cy, cx + 1),
                    ):
                        if (
                            0 <= ny < h
                            and 0 <= nx < w
                            and fg_mask[ny, nx]
                            and not comp_visited[ny, nx]
                        ):
                            comp_visited[ny, nx] = True
                            cq.append((ny, nx))
                if len(comp) < min_component_px:
                    for py, px in comp:
                        rgba[py, px, 3] = 0

    # Tight bounding box around remaining foreground
    ys, xs = np.where(rgba[:, :, 3] > 16)
    if len(xs) == 0 or len(ys) == 0:
        return sub

    pad = 4
    x_min = max(0, int(xs.min()) - pad)
    y_min = max(0, int(ys.min()) - pad)
    x_max = min(w, int(xs.max()) + 1 + pad)
    y_max = min(h, int(ys.max()) + 1 + pad)
    cropped = rgba[y_min:y_max, x_min:x_max].copy()
    extruded = apply_alpha_edge_extrusion(cropped, passes=4)
    return Image.fromarray(extruded, mode="RGBA")


def synthesize_low_hp_sweat_portrait(glare_img: Image.Image) -> Image.Image:
    """
    Creates the 6th required 256x256 Portrait: LOW_HP_SWEAT
    Uses the fierce portrait base + crisp anime cyan sweat droplets + subtle crimson danger rim.
    """
    out = glare_img.copy().convert("RGBA")
    draw = ImageDraw.Draw(out, "RGBA")
    # Subtle crimson danger vignette along inner frame
    for i in range(6):
        alpha = int(115 - i * 16)
        draw.rectangle([i, i, 255 - i, 255 - i], outline=(235, 38, 48, alpha), width=1)
    # Anime cyan sweat drop #1 on temple (with dark outline + white highlight)
    # Teardrop polygon at (66, 118)
    drop1 = [(68, 102), (60, 122), (63, 130), (73, 130), (76, 122)]
    draw.polygon(drop1, fill=(95, 228, 255, 245), outline=(15, 18, 26, 255))
    draw.ellipse([64, 118, 68, 124], fill=(255, 255, 255, 240))
    # Sweat drop #2 on cheek at (186, 146)
    drop2 = [(186, 134), (180, 150), (183, 156), (189, 156), (192, 150)]
    draw.polygon(drop2, fill=(95, 228, 255, 240), outline=(15, 18, 26, 255))
    draw.ellipse([183, 147, 186, 152], fill=(255, 255, 255, 235))
    return out


def synthesize_ko_stars_portrait(hurt_img: Image.Image) -> Image.Image:
    """
    Creates the 7th required 256x256 Portrait: KO_STARS
    Uses the dizzy spiral hurt portrait base + orbiting golden 4-point KO stars + KO badge tone.
    """
    out = hurt_img.copy().convert("RGBA")
    arr = np.array(out, dtype=np.float32)
    # Slightly desaturate & darken background to convey KO state while keeping face readable
    arr[:, :, :3] *= 0.88
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGBA")
    draw = ImageDraw.Draw(out, "RGBA")

    # Orbiting golden halo ellipse arc across top of head
    draw.arc([36, 20, 220, 74], start=195, end=345, fill=(255, 215, 55, 220), width=3)

    # Draw 3 crisp 4-point golden anime KO stars with dark ink outlines
    star_centers = [(58, 44, 15), (128, 26, 18), (198, 44, 15)]
    for cx, cy, r in star_centers:
        r_in = max(4, int(r * 0.36))
        pts = [
            (cx, cy - r),
            (cx + r_in, cy - r_in),
            (cx + r, cy),
            (cx + r_in, cy + r_in),
            (cx, cy + r),
            (cx - r_in, cy + r_in),
            (cx - r, cy),
            (cx - r_in, cy - r_in),
        ]
        draw.polygon(pts, fill=(255, 230, 64, 255), outline=(15, 18, 26, 255))
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 255, 255, 250))
    return out


def main() -> None:
    os.makedirs(SHEETS_DIR, exist_ok=True)
    os.makedirs(PORTRAITS_DIR, exist_ok=True)
    os.makedirs(POSES_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    dst_master = os.path.join(SHEETS_DIR, "chibi_brawler_master_sheet.jpg")
    if os.path.exists(BRAIN_SHEET_PATH):
        shutil.copy2(BRAIN_SHEET_PATH, dst_master)
    elif not os.path.exists(dst_master):
        raise FileNotFoundError(f"Missing Chibi Brawler concept sheet: {BRAIN_SHEET_PATH}")

    master_img = Image.open(dst_master).convert("RGBA")

    # 1. Extract the 5 Studio Portraits + Synthesize the 2 additional required Portraits = 7 total (256x256)
    portrait_crop_specs = {
        "cheeky_smirk": (433, 62, 590, 235),
        "blazing_glare": (617, 62, 773, 235),
        "wide_mouth_shout": (801, 62, 958, 235),
        "dizzy_spiral_hurt": (985, 62, 1141, 235),
        "ecstatic_victory_laugh": (1168, 62, 1325, 235),
    }

    extracted_portraits: dict[str, Image.Image] = {}
    portrait_manifest: dict[str, dict] = {}

    for key, box in portrait_crop_specs.items():
        crop = master_img.crop(box).resize((256, 256), Image.Resampling.LANCZOS)
        extracted_portraits[key] = crop

    extracted_portraits["low_hp_sweat"] = synthesize_low_hp_sweat_portrait(
        extracted_portraits["blazing_glare"]
    )
    extracted_portraits["ko_stars"] = synthesize_ko_stars_portrait(
        extracted_portraits["dizzy_spiral_hurt"]
    )

    # Save all 7 canonical portraits + short aliases for HUD convenience
    alias_map = {
        "confident": "cheeky_smirk",
        "fierce": "blazing_glare",
        "shout": "wide_mouth_shout",
        "hurt": "dizzy_spiral_hurt",
        "victory": "ecstatic_victory_laugh",
        "sweat": "low_hp_sweat",
        "ko": "ko_stars",
    }

    for key, p_img in extracted_portraits.items():
        out_path = os.path.join(PORTRAITS_DIR, f"chibi_expr_{key}.png")
        p_img.save(out_path, format="PNG")
        portrait_manifest[key] = {
            "res_path": f"res://assets/portraits/chibi_expr_{key}.png",
            "width": 256,
            "height": 256,
            "sha256": sha256_file(out_path),
        }
        print(f"Saved Chibi 256x256 Portrait '{key}' -> {out_path}")

    for short_alias, target_key in alias_map.items():
        out_alias = os.path.join(PORTRAITS_DIR, f"chibi_expr_{short_alias}.png")
        extracted_portraits[target_key].save(out_alias, format="PNG")

    # 2. Extract the 6 Bottom Action Poses + Top-Left Hero Pose
    # Note: For 'run', crop starting at x=316 so detached left-side speed lines are excluded cleanly.
    pose_crop_specs = {
        "hero": (122, 54, 340, 488, 600),
        "idle": (96, 512, 215, 720, 260),
        "run": (316, 520, 482, 720, 260),
        "jump": (550, 438, 656, 660, 260),
        "punch": (708, 482, 921, 720, 260),
        "aim": (963, 512, 1113, 720, 260),
        "roll": (1145, 512, 1331, 720, 260),
    }

    pose_manifest: dict[str, dict] = {}
    for p_key, (x0, y0, x1, y1, min_cc) in pose_crop_specs.items():
        clean_img = extract_clean_pose(master_img, (x0, y0, x1, y1), min_component_px=min_cc, pose_key=p_key)
        out_path = os.path.join(POSES_DIR, f"pose_{p_key}.png")
        clean_img.save(out_path, format="PNG")
        w_px, h_px = clean_img.size
        pose_manifest[p_key] = {
            "res_path": f"res://assets/sprites/chibi_brawler/pose_{p_key}.png",
            "width": w_px,
            "height": h_px,
            "pivot_px": [round(w_px * 0.5, 2), float(h_px - 4)],
            "units_per_pixel": 0.125,
            "target_world_height": 18.0 if p_key != "roll" else 14.0,
            "vulnerable_core_mask": {"head_ratio": 0.40, "torso_ratio": 0.32, "legs_ratio": 0.28},
            "sha256": sha256_file(out_path),
        }
        print(f"Saved spotless Chibi Pose '{p_key}': ({w_px}, {h_px}) -> {out_path}")

    # 3. Load compiled states from sf_compiled_rigs.json to build full 89-state coverage manifest
    compiled_rigs_path = os.path.join(DATA_DIR, "sf_compiled_rigs.json")
    state_coverage: dict[str, dict] = {}
    if os.path.exists(compiled_rigs_path):
        with open(compiled_rigs_path, "r", encoding="utf-8") as f:
            rigs_json = json.load(f)
        states_dict = rigs_json.get("states", {})
        for st_name in sorted(states_dict.keys()):
            st_u = st_name.upper()
            pose_ref = "idle"
            if st_u in ("ROLL", "DIVE"):
                pose_ref = "roll"
            elif st_u in ("RUN", "SPRINT"):
                pose_ref = "run"
            elif st_u in ("JUMP", "FALL", "FALL_F", "FALL_B", "CLIMB", "LEDGE_GRAB", "JUMPKICK", "JUMP_KICK"):
                pose_ref = "jump"
            elif st_u.startswith("AIM_") or st_u.startswith("START_"):
                pose_ref = "aim"
            elif (
                st_u.startswith("PUNCH")
                or st_u.startswith("MACHETE")
                or st_u.startswith("AXE")
                or st_u.startswith("SWORD")
                or st_u.startswith("BAT")
                or st_u.startswith("CHAINSAW")
                or st_u.startswith("KICK")
            ):
                pose_ref = "punch"
            state_coverage[st_u] = {
                "source_id": st_u,
                "pose_layer": pose_ref,
                "required": True,
            }

    # Add extra runtime & MUGEN / Powered Skill states
    extra_states = [
        "LEDGE_GRAB",
        "SKILL_1",
        "SKILL_2",
        "SKILL_3",
        "SKILL_4",
        "MUGEN_ATTACK_1",
        "MUGEN_ATTACK_2",
        "MUGEN_SPECIAL",
        "MUGEN_ULTIMATE",
        "WIN",
        "LAY",
    ]
    for est in extra_states:
        if est not in state_coverage:
            state_coverage[est] = {
                "source_id": est,
                "pose_layer": "jump" if est == "LEDGE_GRAB" else ("punch" if "SKILL" in est or "MUGEN" in est else "idle"),
                "required": True,
            }

    manifest_data = {
        "schema_version": 1,
        "generation_id": "chibi_25head_r4_v1",
        "style_id": "chibi_tactical_brawler_25head",
        "golden_fighter_id": "johnny",
        "source_concept_sha256": sha256_file(dst_master),
        "calibration": {
            "atlas_reference_body_px": 144,
            "units_per_pixel": 0.125,
            "neutral_height_world_units": 18.0,
            "hair_crest_allowance_world_units": 2.0,
            "head_ratio": 0.40,
            "torso_ratio": 0.32,
            "legs_ratio": 0.28,
            "head_world_units": 7.2,
            "torso_world_units": 5.76,
            "legs_world_units": 5.04,
            "glove_scale": 1.60,
            "contact_fist_accent_max_scale": 1.45,
            "head_pitch_factor": 0.40,
            "head_pitch_clamp_deg": [-28.0, 28.0],
            "aim_pitch_clamp_deg": [-90.0, 90.0],
            "face_lod_min_screen_px": 16.0,
        },
        "expressions": {
            "KO_STARS": {"priority": 6, "min_hold_sec": 0.35, "portrait_key": "ko_stars", "allow_blink": False},
            "ECSTATIC_VICTORY_LAUGH": {"priority": 5, "min_hold_sec": 0.50, "portrait_key": "ecstatic_victory_laugh", "allow_blink": False},
            "DIZZY_SPIRAL_HURT": {"priority": 4, "min_hold_sec": 0.14, "portrait_key": "dizzy_spiral_hurt", "allow_blink": False},
            "WIDE_MOUTH_SHOUT": {"priority": 3, "min_hold_sec": 0.12, "portrait_key": "wide_mouth_shout", "allow_blink": False},
            "LOW_HP_SWEAT": {"priority": 2, "min_hold_sec": 0.25, "enter_hp_ratio": 0.25, "exit_hp_ratio": 0.30, "portrait_key": "low_hp_sweat", "allow_blink": True},
            "BLAZING_GLARE": {"priority": 1, "min_hold_sec": 0.10, "portrait_key": "blazing_glare", "allow_blink": False},
            "CHEEKY_SMIRK": {"priority": 0, "min_hold_sec": 0.0, "portrait_key": "cheeky_smirk", "allow_blink": True},
        },
        "portraits": portrait_manifest,
        "poses": pose_manifest,
        "state_coverage_count": len(state_coverage),
        "state_coverage": state_coverage,
    }

    manifest_path = os.path.join(DATA_DIR, "chibi_atlas_manifest.json")
    tmp_manifest_path = manifest_path + ".tmp"
    with open(tmp_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_manifest_path, manifest_path)
    print(
        f"Saved atomic manifest ({len(state_coverage)} states, 7 portraits, {len(pose_manifest)} poses) -> {manifest_path}"
    )


if __name__ == "__main__":
    main()

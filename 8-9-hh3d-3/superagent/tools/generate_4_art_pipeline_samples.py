#!/usr/bin/env python3
"""
Superagent — Generator for:
1. All 4 Character Art Pipeline Visual Samples (Phương án A, B, C, D + Master 2x2 Comparison)
2. 8 High-Res Splash Portraits (assets/sprites/portraits/<id>_splash.png)
3. 8 High-Res Ultimate Cut-In Banners (assets/sprites/cutins/<id>_cutin.png)
4. 8 Custom Hybrid Sprite Sheets (assets/sheets/hero_<id>_mugen.png)
5. 8 LoL-Resource + 4-Skill Custom Fighter JSONs (data/custom_fighters/hero_<id>_mugen.json)
"""

import json
import math
import shutil
import subprocess
from collections import deque
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT.parent.parent
PREVIEW_DIR = REPO_ROOT / "_blender_preview_2026-10-27"
BLENDER_EXE = PROJECT_ROOT.parent / "studio" / ".local" / "tooling" / "blender-5.2.3-windows-x64" / "blender.exe"

SHEETS_DIR = PROJECT_ROOT / "assets" / "sheets"
PORTRAITS_DIR = PROJECT_ROOT / "assets" / "sprites" / "portraits"
CUTINS_DIR = PROJECT_ROOT / "assets" / "sprites" / "cutins"
SHOWCASE_DIR = PROJECT_ROOT / "assets" / "showcase"
CUSTOM_FIGHTERS_DIR = PROJECT_ROOT / "data" / "custom_fighters"
ARTIFACT_DIR = Path(r"C:\Users\truon\.gemini\antigravity\brain\fb4592d9-c914-4d42-b275-d495b41a423b")

AI_ORIG_SHEET = PREVIEW_DIR / "v3" / "out" / "pipeline_cases" / "ai_original_archetypes_sheet.png"
AI_REF_SHEET = PREVIEW_DIR / "v3" / "out" / "pipeline_cases" / "ai_reference_concept_sheet.png"


# ---------------------------------------------------------------------------
# 1. Character Metadata & LoL Resource + 4-Skill Kit Definitions (8 Heroes)
# ---------------------------------------------------------------------------
HERO_DEFS = {
    "solaria": {
        "id": "solaria",
        "display_name": "Solaria — Gold Striker",
        "short_name": "SOLARIA",
        "subtitle": "Sunforge Striker Monk",
        "roster_category": "ORIGINAL_POWERED",
        "hp_mult": 1.15,
        "speed_mult": 1.14,
        "palette": {
            "primary": (240, 242, 234, 255),      # White/Ivory tunic
            "secondary": (26, 155, 158, 255),     # Teal sash
            "accent": (255, 195, 45, 255),        # Gold gauntlets
            "hair": (235, 240, 248, 255),         # Silver-white braided hair
            "skin": (228, 178, 140, 255),
            "aura": (255, 210, 60, 220),
            "beam": (255, 230, 95, 255),
            "boots": (185, 140, 45, 255),
        },
        "orig_crop_full": (2, 0, 441, 644),
        "orig_crop_cutin": (11, 649, 429, 866),
        "resource_spec": {
            "resource_id": "SOLAR_MANTRA",
            "display_label": "SOLAR",
            "archetype": "COMBO_PIPS_AND_HEAT",
            "start_value": 25.0,
            "max_value": 100.0,
            "secondary_pips_max": 3,
            "regen_per_sec": 3.0,
            "on_hit_melee_gain": 12.0,
            "on_hit_skill_gain": 15.0,
            "on_hurt_gain": 8.0,
            "decay_delay_sec": 5.0,
            "decay_per_sec": 8.0,
            "bar_color_primary": "#FFA822",
            "bar_color_secondary": "#FFF380",
            "bar_color_max_glow": "#FFD700",
            "segments": 4,
            "passive_id": "PASSIVE_SUNFORGE_MANTRA",
            "passive_desc": "Moi chieu tich 1 Sun Pip (toi da 3). Don danh thuong tieu thu Pip luot nhanh +12 Solar.",
        },
        "skill_kit": {
            "skill_1": {
                "slot": 1, "id": "SKILL_1", "name": "Tam Lien Quyen (U/5)",
                "state": "SKILL_1", "cooldown_sec": 3.5, "resource_cost": 0.0,
                "resource_gain": 15.0, "pip_gain": 1, "damage": 18.0, "hit_force": 24.0,
                "dash_speed_24hz": 6.8, "dash_distance": 52.0, "knockdown": False,
                "icon_color": "#FFB830", "glyph": "Q", "sfx": "punch_heavy",
            },
            "skill_2": {
                "slot": 2, "id": "SKILL_2", "name": "Ho The Hoang Kim Chuong (I/6)",
                "state": "SKILL_2", "cooldown_sec": 5.5, "resource_cost": 20.0,
                "resource_gain": 0.0, "pip_gain": 1, "damage": 24.0, "hit_force": 36.0,
                "projectile_id": "SOLAR_CONE", "projectile_speed_24hz": 20.0,
                "knockdown": True, "shield_frames": 18.0,
                "icon_color": "#FFD040", "glyph": "W", "sfx": "explosion_small",
            },
            "skill_3": {
                "slot": 3, "id": "SKILL_3", "name": "Cuoc Phap Quang Toc (O/7)",
                "state": "SKILL_3", "cooldown_sec": 5.0, "resource_cost": 15.0,
                "resource_gain": 10.0, "pip_gain": 1, "damage": 20.0, "hit_force": 30.0,
                "dash_speed_24hz": 8.2, "dash_distance": 75.0, "knockdown": True,
                "icon_color": "#FF9500", "glyph": "E", "sfx": "swing_sword",
            },
            "skill_4": {
                "slot": 4, "id": "SKILL_4", "name": "ULT: Thai Duong Bao Pha (P/8)",
                "state": "SKILL_4", "cooldown_sec": 14.0, "resource_cost": 60.0,
                "resource_gain": 0.0, "pip_gain": 3, "damage": 44.0, "hit_force": 52.0,
                "dash_speed_24hz": 9.5, "dash_distance": 95.0, "knockdown": True,
                "is_ultimate": True, "aoe_radius": 96.0,
                "icon_color": "#FF5500", "glyph": "R", "sfx": "explosion_large",
            },
        },
    },
    "atlas": {
        "id": "atlas",
        "display_name": "Atlas — Titan Gauntlet",
        "short_name": "ATLAS",
        "subtitle": "Tectonic Reactor Brawler",
        "roster_category": "ORIGINAL_POWERED",
        "hp_mult": 1.35,
        "speed_mult": 1.04,
        "palette": {
            "primary": (75, 115, 105, 255),       # Heavy moss-green armor
            "secondary": (232, 128, 45, 255),     # Orange cape & trim
            "accent": (98, 255, 158, 255),        # Emerald reactor glow
            "hair": (38, 30, 26, 255),            # Short dark hair
            "skin": (142, 94, 66, 255),
            "aura": (98, 255, 158, 220),
            "beam": (255, 148, 42, 255),
            "boots": (48, 56, 52, 255),
        },
        "orig_crop_full": (445, 0, 885, 644),
        "orig_crop_cutin": (455, 649, 874, 866),
        "resource_spec": {
            "resource_id": "TITAN_HEAT",
            "display_label": "HEAT",
            "archetype": "RUMBLE_HEAT_OVERDRIVE",
            "start_value": 0.0,
            "max_value": 100.0,
            "secondary_pips_max": 0,
            "regen_per_sec": 0.0,
            "on_hit_melee_gain": 8.0,
            "on_hit_skill_gain": 0.0,
            "on_hurt_gain": 6.0,
            "decay_delay_sec": 4.0,
            "decay_per_sec": 12.0,
            "bar_color_primary": "#4CD964",
            "bar_color_secondary": "#FF9500",
            "bar_color_max_glow": "#FF2D55",
            "segments": 2,
            "passive_id": "PASSIVE_REACTOR_OVERDRIVE",
            "passive_desc": "Tung chieu tang +20 Nhiet. Danger Zone (50-99): +30% suc manh & giap. 100 Nhiet: Cuong hoa dam thuong x1.65.",
        },
        "skill_kit": {
            "skill_1": {
                "slot": 1, "id": "SKILL_1", "name": "Thiet Quyen Xung Kich (U/5)",
                "state": "SKILL_1", "cooldown_sec": 4.0, "resource_cost": 0.0,
                "resource_gain": 20.0, "damage": 22.0, "hit_force": 38.0,
                "dash_speed_24hz": 7.2, "dash_distance": 80.0, "knockdown": True,
                "icon_color": "#63FF9E", "glyph": "Q", "sfx": "punch_heavy",
            },
            "skill_2": {
                "slot": 2, "id": "SKILL_2", "name": "Dia Chan Tam Lien Cot (I/6)",
                "state": "SKILL_2", "cooldown_sec": 5.5, "resource_cost": 0.0,
                "resource_gain": 20.0, "damage": 25.0, "hit_force": 42.0,
                "shockwave_range": 120.0, "knockdown": True,
                "icon_color": "#FF9500", "glyph": "W", "sfx": "explosion_small",
            },
            "skill_3": {
                "slot": 3, "id": "SKILL_3", "name": "Tu Truong Hut & Dam Thung (O/7)",
                "state": "SKILL_3", "cooldown_sec": 6.0, "resource_cost": 0.0,
                "resource_gain": 20.0, "damage": 24.0, "hit_force": 44.0,
                "pull_props_range": 150.0, "knockdown": True,
                "icon_color": "#4CD964", "glyph": "E", "sfx": "metal_hit",
            },
            "skill_4": {
                "slot": 4, "id": "SKILL_4", "name": "ULT: Thien Thach Huy Diet (P/8)",
                "state": "SKILL_4", "cooldown_sec": 15.0, "resource_cost": 40.0,
                "resource_gain": -100.0, "damage": 48.0, "hit_force": 60.0,
                "dash_speed_24hz": 9.0, "dash_distance": 90.0, "knockdown": True,
                "is_ultimate": True, "aoe_radius": 150.0,
                "icon_color": "#FF2D55", "glyph": "R", "sfx": "explosion_large",
            },
        },
    },
    "shinobi": {
        "id": "shinobi",
        "display_name": "Shinobi — Void Assassin",
        "short_name": "SHINOBI",
        "subtitle": "Phantom Kunai Assassin",
        "roster_category": "ORIGINAL_POWERED",
        "hp_mult": 1.10,
        "speed_mult": 1.22,
        "palette": {
            "primary": (42, 36, 78, 255),         # Deep umbral purple suit
            "secondary": (195, 62, 168, 255),     # Neon magenta scarf/trim
            "accent": (148, 255, 68, 255),        # Acid neon green blade/clone
            "hair": (28, 24, 48, 255),            # Hooded mask
            "skin": (210, 180, 225, 255),
            "aura": (185, 65, 255, 220),
            "beam": (148, 255, 68, 255),
            "boots": (22, 18, 38, 255),
        },
        "orig_crop_full": (889, 0, 1328, 644),
        "orig_crop_cutin": (900, 649, 1319, 866),
        "resource_spec": {
            "resource_id": "VOID_ENERGY",
            "display_label": "ENERGY",
            "archetype": "ZED_AKALI_ENERGY",
            "start_value": 200.0,
            "max_value": 200.0,
            "secondary_pips_max": 0,
            "regen_per_sec": 25.0,
            "on_hit_melee_gain": 20.0,
            "on_hit_skill_gain": 15.0,
            "on_hurt_gain": 0.0,
            "decay_delay_sec": 0.0,
            "decay_per_sec": 0.0,
            "bar_color_primary": "#00F59B",
            "bar_color_secondary": "#9D4EDD",
            "bar_color_max_glow": "#95FF45",
            "segments": 4,
            "passive_id": "PASSIVE_KUNAI_RESONANCE",
            "passive_desc": "200 Void Energy hoi nhanh (+25/s). Danh trung muc tieu co An Hu Khong no them sat thuong & hoan +40 Energy.",
        },
        "skill_kit": {
            "skill_1": {
                "slot": 1, "id": "SHUNPO_SLASH", "name": "Toc Bien Hu Khong Tram (U/5)",
                "state": "SHUNPO_SLASH", "cooldown_sec": 3.0, "resource_cost": 45.0,
                "resource_gain": 0.0, "damage": 22.0, "hit_force": 32.0,
                "dash_speed_24hz": 8.5, "dash_distance": 95.0, "knockdown": True,
                "icon_color": "#9D4EDD", "glyph": "Q", "sfx": "swing_sword",
            },
            "skill_2": {
                "slot": 2, "id": "CHAKRA_WAVE", "name": "Phi Tieu Doc Luc Giac (I/6)",
                "state": "CHAKRA_WAVE", "cooldown_sec": 3.5, "resource_cost": 40.0,
                "resource_gain": 0.0, "damage": 20.0, "hit_force": 28.0,
                "projectile_id": "CHAKRA_WAVE", "projectile_speed_24hz": 23.0,
                "knockdown": False,
                "icon_color": "#00F59B", "glyph": "W", "sfx": "swing_sword",
            },
            "skill_3": {
                "slot": 3, "id": "SKILL_3", "name": "Phan Than Khoi Tim & Hoan Doi (O/7)",
                "state": "SKILL_3", "cooldown_sec": 6.5, "resource_cost": 50.0,
                "resource_gain": 0.0, "damage": 21.0, "hit_force": 30.0,
                "teleport_behind": True, "deflect_bullets": True, "knockdown": True,
                "icon_color": "#D04BA5", "glyph": "E", "sfx": "swing_sword",
            },
            "skill_4": {
                "slot": 4, "id": "SKILL_4", "name": "ULT: An Tu Than Hu Khong (P/8)",
                "state": "SKILL_4", "cooldown_sec": 14.0, "resource_cost": 70.0,
                "resource_gain": 40.0, "damage": 45.0, "hit_force": 48.0,
                "teleport_behind": True, "is_ultimate": True, "aoe_radius": 110.0, "knockdown": True,
                "icon_color": "#95FF45", "glyph": "R", "sfx": "explosion_large",
            },
        },
    },
    "tideweaver": {
        "id": "tideweaver",
        "display_name": "Tideweaver — Hydro Whip",
        "short_name": "TIDEWEAVER",
        "subtitle": "Magnetic Riptide Corsair",
        "roster_category": "ORIGINAL_POWERED",
        "hp_mult": 1.15,
        "speed_mult": 1.16,
        "palette": {
            "primary": (38, 62, 94, 255),         # Deep navy coat
            "secondary": (233, 112, 87, 255),     # Coral red trousers
            "accent": (69, 227, 255, 255),        # Hydro whip cyan
            "hair": (198, 78, 42, 255),           # Auburn-red high ponytail
            "skin": (236, 192, 156, 255),
            "aura": (69, 227, 255, 220),
            "beam": (80, 235, 255, 255),
            "boots": (54, 40, 34, 255),
        },
        "orig_crop_full": (1332, 0, 1772, 644),
        "orig_crop_cutin": (1345, 649, 1763, 865),
        "resource_spec": {
            "resource_id": "TIDAL_FLOW",
            "display_label": "TIDAL",
            "archetype": "NILAH_TIDAL_SURGE",
            "start_value": 40.0,
            "max_value": 100.0,
            "secondary_pips_max": 0,
            "regen_per_sec": 10.0,
            "on_hit_melee_gain": 12.0,
            "on_hit_skill_gain": 12.0,
            "on_hurt_gain": 6.0,
            "decay_delay_sec": 0.0,
            "decay_per_sec": 0.0,
            "bar_color_primary": "#00D2FF",
            "bar_color_secondary": "#3A7BD5",
            "bar_color_max_glow": "#80F5FF",
            "segments": 5,
            "passive_id": "PASSIVE_SLIPSTREAM_LASH",
            "passive_desc": "Di chuyen va danh trung tich Tidal Flow. Chieu Nuoc dap tat moi dam lua va keo/day muc tieu.",
        },
        "skill_kit": {
            "skill_1": {
                "slot": 1, "id": "SKILL_1", "name": "Thuy Tien Quat Kich (U/5)",
                "state": "SKILL_1", "cooldown_sec": 2.8, "resource_cost": 18.0,
                "resource_gain": 0.0, "damage": 20.0, "hit_force": 28.0,
                "whip_reach": 155.0, "extinguish_fire": True, "knockdown": False,
                "icon_color": "#00D2FF", "glyph": "Q", "sfx": "swing_sword",
            },
            "skill_2": {
                "slot": 2, "id": "SKILL_2", "name": "Khien Xoay Nuoc Phan Dan (I/6)",
                "state": "SKILL_2", "cooldown_sec": 6.0, "resource_cost": 25.0,
                "resource_gain": 0.0, "damage": 18.0, "hit_force": 32.0,
                "deflect_bullets": True, "extinguish_fire": True, "knockdown": True,
                "icon_color": "#45E3FF", "glyph": "W", "sfx": "swing_sword",
            },
            "skill_3": {
                "slot": 3, "id": "SKILL_3", "name": "Day Nuoc Du Bam (O/7)",
                "state": "SKILL_3", "cooldown_sec": 5.5, "resource_cost": 20.0,
                "resource_gain": 0.0, "damage": 22.0, "hit_force": 34.0,
                "dash_speed_24hz": 8.4, "dash_distance": 100.0, "extinguish_fire": True, "knockdown": True,
                "icon_color": "#3A7BD5", "glyph": "E", "sfx": "swing_sword",
            },
            "skill_4": {
                "slot": 4, "id": "SKILL_4", "name": "ULT: Dai Hong Thuy Xoay Kep (P/8)",
                "state": "SKILL_4", "cooldown_sec": 15.0, "resource_cost": 55.0,
                "resource_gain": 0.0, "damage": 44.0, "hit_force": 50.0,
                "is_ultimate": True, "aoe_radius": 145.0, "extinguish_fire": True, "knockdown": True,
                "icon_color": "#0099FF", "glyph": "R", "sfx": "explosion_large",
            },
        },
    },
    "goku": {
        "id": "goku",
        "display_name": "Son Goku — Saiyan Legend",
        "short_name": "GOKU",
        "subtitle": "Super Saiyan Z-Fighter",
        "roster_category": "ANIME_LEGENDS",
        "hp_mult": 1.30,
        "speed_mult": 1.20,
        "palette": {
            "primary": (246, 132, 42, 255),       # Turtle hermit orange gi
            "secondary": (33, 73, 126, 255),      # Navy blue undershirt/sash
            "accent": (80, 225, 255, 255),        # Kamehameha cyan-white
            "hair": (24, 26, 34, 255),            # Spiky black hair (turns gold in SSJ)
            "skin": (238, 192, 152, 255),
            "aura": (255, 215, 35, 230),
            "beam": (80, 225, 255, 255),
            "boots": (33, 73, 126, 255),
        },
        "ref_crop_full": (2, 0, 373, 765),
        "ref_crop_cutin": (22, 770, 357, 982),
        "resource_spec": {
            "resource_id": "SAIYAN_KI",
            "display_label": "KI",
            "archetype": "SAIYAN_KI_AWAKENING",
            "start_value": 50.0,
            "max_value": 100.0,
            "secondary_pips_max": 0,
            "regen_per_sec": 8.0,
            "on_hit_melee_gain": 12.0,
            "on_hit_skill_gain": 10.0,
            "on_hurt_gain": 10.0,
            "decay_delay_sec": 0.0,
            "decay_per_sec": 0.0,
            "bar_color_primary": "#38B6FF",
            "bar_color_secondary": "#FFD700",
            "bar_color_max_glow": "#FFF700",
            "segments": 4,
            "passive_id": "PASSIVE_Z_FIGHTER_KI",
            "passive_desc": "Tu hoi Ki & nap Ki khi giao tranh. Tung Ultimate (P/8) bien hinh Super Saiyan toc vang ruc sang trong 8s!",
        },
        "skill_kit": {
            "skill_1": {
                "slot": 1, "id": "SKILL_1", "name": "Dan Khi Cong Lien Hoan (U/5)",
                "state": "SKILL_1", "cooldown_sec": 2.5, "resource_cost": 15.0,
                "resource_gain": 0.0, "damage": 20.0, "hit_force": 30.0,
                "projectile_id": "KI_BLAST", "projectile_speed_24hz": 24.0, "knockdown": False,
                "icon_color": "#38B6FF", "glyph": "Q", "sfx": "swing_sword",
            },
            "skill_2": {
                "slot": 2, "id": "SKILL_2", "name": "Dich Chuyen Tuc Thoi (I/6)",
                "state": "SKILL_2", "cooldown_sec": 5.0, "resource_cost": 20.0,
                "resource_gain": 0.0, "damage": 24.0, "hit_force": 38.0,
                "teleport_behind": True, "knockdown": True,
                "icon_color": "#FFD700", "glyph": "W", "sfx": "punch_heavy",
            },
            "skill_3": {
                "slot": 3, "id": "SKILL_3", "name": "Kaioken Long Quyen (O/7)",
                "state": "SKILL_3", "cooldown_sec": 5.5, "resource_cost": 25.0,
                "resource_gain": 0.0, "damage": 28.0, "hit_force": 42.0,
                "dash_speed_24hz": 9.0, "dash_distance": 95.0, "knockdown": True,
                "icon_color": "#FF3B30", "glyph": "E", "sfx": "punch_heavy",
            },
            "skill_4": {
                "slot": 4, "id": "SKILL_4", "name": "ULT: Sieu Kamehameha SSJ (P/8)",
                "state": "SKILL_4", "cooldown_sec": 14.0, "resource_cost": 60.0,
                "resource_gain": 0.0, "damage": 52.0, "hit_force": 62.0,
                "is_ultimate": True, "beam_length": 460.0, "beam_height": 48.0,
                "awakening_sec": 8.0, "knockdown": True,
                "icon_color": "#00E5FF", "glyph": "R", "sfx": "explosion_large",
            },
        },
    },
    "luffy": {
        "id": "luffy",
        "display_name": "Monkey D. Luffy — Gear 5",
        "short_name": "LUFFY",
        "subtitle": "Straw Hat Rubber Captain",
        "roster_category": "ANIME_LEGENDS",
        "hp_mult": 1.32,
        "speed_mult": 1.18,
        "palette": {
            "primary": (237, 76, 68, 255),        # Red vest
            "secondary": (52, 121, 173, 255),     # Blue denim shorts
            "accent": (255, 59, 78, 255),         # Red Hawk Haki crimson
            "hair": (222, 193, 129, 255),         # Straw Hat gold
            "skin": (238, 190, 152, 255),
            "aura": (255, 110, 130, 220),
            "beam": (255, 70, 50, 255),
            "boots": (160, 120, 75, 255),
        },
        "ref_crop_full": (1163, 0, 1534, 765),
        "ref_crop_cutin": (1181, 770, 1513, 982),
        "resource_spec": {
            "resource_id": "GEAR_STEAM",
            "display_label": "GEAR",
            "archetype": "GEAR_STEAM_HAKI",
            "start_value": 30.0,
            "max_value": 100.0,
            "secondary_pips_max": 0,
            "regen_per_sec": 6.0,
            "on_hit_melee_gain": 12.0,
            "on_hit_skill_gain": 12.0,
            "on_hurt_gain": 12.0,
            "decay_delay_sec": 6.0,
            "decay_per_sec": 5.0,
            "bar_color_primary": "#FF3B30",
            "bar_color_secondary": "#FFFFFF",
            "bar_color_max_glow": "#FF9500",
            "segments": 4,
            "passive_id": "PASSIVE_GOMU_ELASTIC_BODY",
            "passive_desc": "Co the cao su giam 25% sat thuong don dam/gay. Khi Gear Steam >= 50 bat Gear Second (+15% toc do).",
        },
        "skill_kit": {
            "skill_1": {
                "slot": 1, "id": "SKILL_1", "name": "Gomu Gomu no Pistol (U/5)",
                "state": "SKILL_1", "cooldown_sec": 2.8, "resource_cost": 0.0,
                "resource_gain": 15.0, "damage": 22.0, "hit_force": 36.0,
                "stretch_reach": 185.0, "knockdown": True,
                "icon_color": "#FF5E3A", "glyph": "Q", "sfx": "punch_heavy",
            },
            "skill_2": {
                "slot": 2, "id": "SKILL_2", "name": "Bung Cao Su Phan Dan & Ten Lua (I/6)",
                "state": "SKILL_2", "cooldown_sec": 5.5, "resource_cost": 15.0,
                "resource_gain": 10.0, "damage": 18.0, "hit_force": 45.0,
                "deflect_bullets": True, "deflect_throwables": True, "knockdown": True,
                "icon_color": "#FFCC00", "glyph": "W", "sfx": "punch_light",
            },
            "skill_3": {
                "slot": 3, "id": "SKILL_3", "name": "Red Hawk Haki Gatling (O/7)",
                "state": "SKILL_3", "cooldown_sec": 5.0, "resource_cost": 25.0,
                "resource_gain": 0.0, "damage": 28.0, "hit_force": 38.0,
                "dash_speed_24hz": 6.5, "dash_distance": 65.0, "ignite_target": True, "knockdown": True,
                "icon_color": "#FF2D55", "glyph": "E", "sfx": "explosion_small",
            },
            "skill_4": {
                "slot": 4, "id": "SKILL_4", "name": "ULT: Gear 4/5 Bajrang Smash (P/8)",
                "state": "SKILL_4", "cooldown_sec": 15.0, "resource_cost": 60.0,
                "resource_gain": 0.0, "damage": 50.0, "hit_force": 64.0,
                "is_ultimate": True, "aoe_radius": 155.0, "launch_props": True, "knockdown": True,
                "icon_color": "#FFFFFF", "glyph": "R", "sfx": "explosion_large",
            },
        },
    },
    "naruto": {
        "id": "naruto",
        "display_name": "Naruto Uzumaki — Hokage",
        "short_name": "NARUTO",
        "subtitle": "Nine-Tails Kurama Shinobi",
        "roster_category": "ANIME_LEGENDS",
        "hp_mult": 1.25,
        "speed_mult": 1.20,
        "palette": {
            "primary": (239, 132, 52, 255),       # Bright orange jacket
            "secondary": (37, 48, 71, 255),       # Dark shoulders/pants
            "accent": (50, 184, 255, 255),        # Rasengan wind blue
            "hair": (245, 202, 67, 255),          # Spiky blonde hair
            "skin": (238, 192, 152, 255),
            "aura": (255, 110, 25, 225),
            "beam": (50, 200, 255, 255),
            "boots": (37, 48, 71, 255),
        },
        "ref_crop_full": (779, 0, 1140, 775),
        "ref_crop_cutin": (795, 780, 1125, 982),
        "resource_spec": {
            "resource_id": "CHAKRA_KURAMA",
            "display_label": "CHAKRA",
            "archetype": "CHAKRA_AND_NINE_TAILS",
            "start_value": 100.0,
            "max_value": 100.0,
            "secondary_pips_max": 9,
            "regen_per_sec": 12.0,
            "on_hit_melee_gain": 10.0,
            "on_hit_skill_gain": 10.0,
            "on_hurt_gain": 8.0,
            "decay_delay_sec": 0.0,
            "decay_per_sec": 0.0,
            "bar_color_primary": "#00B4D8",
            "bar_color_secondary": "#FF5400",
            "bar_color_max_glow": "#FF9E00",
            "segments": 4,
            "passive_id": "PASSIVE_NINE_TAILS_VESSEL",
            "passive_desc": "Thanh Chakra Xanh + 9 Duoi Cuu Vi Kurama. Chieu U/5 trieu hoi Phan Than AI chien dau tren ban do!",
        },
        "skill_kit": {
            "skill_1": {
                "slot": 1, "id": "SKILL_1", "name": "Kage Bunshin: Goi Phan Than AI (U/5)",
                "state": "SKILL_1", "cooldown_sec": 6.5, "resource_cost": 30.0,
                "resource_gain": 0.0, "pip_gain": 2, "damage": 16.0, "hit_force": 24.0,
                "summon_clone": True, "knockdown": False,
                "icon_color": "#FF9500", "glyph": "Q", "sfx": "explosion_small",
            },
            "skill_2": {
                "slot": 2, "id": "SKILL_2", "name": "Phong Don: Rasenshuriken (I/6)",
                "state": "SKILL_2", "cooldown_sec": 4.5, "resource_cost": 25.0,
                "resource_gain": 0.0, "pip_gain": 2, "damage": 26.0, "hit_force": 40.0,
                "projectile_id": "RASENSHURIKEN", "projectile_speed_24hz": 22.0, "knockdown": True,
                "icon_color": "#00D2FF", "glyph": "W", "sfx": "swing_sword",
            },
            "skill_3": {
                "slot": 3, "id": "SKILL_3", "name": "Vuot Chakra Cuu Vi (O/7)",
                "state": "SKILL_3", "cooldown_sec": 5.0, "resource_cost": 20.0,
                "resource_gain": 0.0, "pip_gain": 2, "damage": 24.0, "hit_force": 38.0,
                "dash_speed_24hz": 8.0, "dash_distance": 85.0, "knockdown": True,
                "icon_color": "#FF5400", "glyph": "E", "sfx": "punch_heavy",
            },
            "skill_4": {
                "slot": 4, "id": "SKILL_4", "name": "ULT: Bom Vi Thu Bijuudama (P/8)",
                "state": "SKILL_4", "cooldown_sec": 15.0, "resource_cost": 55.0,
                "resource_gain": 0.0, "pip_gain": 9, "damage": 50.0, "hit_force": 60.0,
                "is_ultimate": True, "aoe_radius": 150.0, "awakening_sec": 8.0, "knockdown": True,
                "icon_color": "#FF2D00", "glyph": "R", "sfx": "explosion_large",
            },
        },
    },
    "saitama": {
        "id": "saitama",
        "display_name": "Saitama — One Punch Hero",
        "short_name": "SAITAMA",
        "subtitle": "Caped Baldy — Unfazed Limitless",
        "roster_category": "ANIME_LEGENDS",
        "hp_mult": 1.60,
        "speed_mult": 1.25,
        "palette": {
            "primary": (255, 212, 63, 255),       # Iconic yellow jumpsuit
            "secondary": (243, 243, 237, 255),    # White cape
            "accent": (220, 69, 78, 255),         # Red gloves & boots
            "hair": (238, 192, 152, 255),         # Shiny bald head!
            "skin": (238, 192, 152, 255),
            "aura": (255, 65, 55, 225),
            "beam": (255, 235, 110, 255),
            "boots": (220, 69, 78, 255),
        },
        "ref_crop_full": (395, 0, 756, 766),
        "ref_crop_cutin": (412, 771, 742, 982),
        "resource_spec": {
            "resource_id": "SERIOUS_METER",
            "display_label": "SERIOUS",
            "archetype": "SAITAMA_SERIOUS_GAUGE",
            "start_value": 25.0,
            "max_value": 100.0,
            "secondary_pips_max": 0,
            "regen_per_sec": 5.0,
            "on_hit_melee_gain": 12.0,
            "on_hit_skill_gain": 15.0,
            "on_hurt_gain": 20.0,
            "decay_delay_sec": 0.0,
            "decay_per_sec": 0.0,
            "bar_color_primary": "#FFE600",
            "bar_color_secondary": "#E61919",
            "bar_color_max_glow": "#FF1E1E",
            "segments": 4,
            "passive_id": "PASSIVE_UNFAZED_HERO",
            "passive_desc": "Mien khang choang dan thuong khi Serious >= 50. O/7 hat tung toan bo thung go/do vat len troi; P/8 Dam Nghiem Tuc re doi man hinh!",
        },
        "skill_kit": {
            "skill_1": {
                "slot": 1, "id": "SKILL_1", "name": "Dam Thuong Lien Hoan (U/5)",
                "state": "SKILL_1", "cooldown_sec": 3.0, "resource_cost": 0.0,
                "resource_gain": 18.0, "damage": 28.0, "hit_force": 45.0,
                "dash_speed_24hz": 6.5, "dash_distance": 60.0, "knockdown": True,
                "icon_color": "#FFE600", "glyph": "Q", "sfx": "punch_heavy",
            },
            "skill_2": {
                "slot": 2, "id": "SKILL_2", "name": "Bat Nhay Ngang Tan Anh (I/6)",
                "state": "SKILL_2", "cooldown_sec": 4.5, "resource_cost": 15.0,
                "resource_gain": 10.0, "damage": 20.0, "hit_force": 38.0,
                "dash_speed_24hz": 10.0, "dash_distance": 120.0, "deflect_bullets": True, "knockdown": True,
                "icon_color": "#FF9500", "glyph": "W", "sfx": "swing_sword",
            },
            "skill_3": {
                "slot": 3, "id": "SKILL_3", "name": "Lat Ban: Hat Tung San Dau (O/7)",
                "state": "SKILL_3", "cooldown_sec": 6.0, "resource_cost": 25.0,
                "resource_gain": 10.0, "damage": 26.0, "hit_force": 50.0,
                "table_flip_props": True, "aoe_radius": 185.0, "knockdown": True,
                "icon_color": "#FF5E3A", "glyph": "E", "sfx": "explosion_small",
            },
            "skill_4": {
                "slot": 4, "id": "SKILL_4", "name": "ULT: Serious Punch - Mot Dam (P/8)",
                "state": "SKILL_4", "cooldown_sec": 16.0, "resource_cost": 70.0,
                "resource_gain": -100.0, "damage": 65.0, "hit_force": 85.0,
                "is_ultimate": True, "beam_length": 560.0, "beam_height": 110.0,
                "table_flip_props": True, "knockdown": True,
                "icon_color": "#E61919", "glyph": "R", "sfx": "explosion_large",
            },
        },
    },
}


# ---------------------------------------------------------------------------
# 2. Dark Background Segmentation & Outlined Sprite Helper (Pipeline C)
# ---------------------------------------------------------------------------
def segment_dark_background(img: Image.Image, threshold: float = 38.0, trim_ground_ratio: float = 0.89) -> Image.Image:
    """Removes the dark navy/slate background from an AI concept panel using border flood-fill + chroma distance."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    # Sample top-left & top-right sky colors
    bg_samples = [
        px[4, 4][:3],
        px[w - 5, 4][:3],
        px[4, h // 3][:3],
        px[w - 5, h // 3][:3],
    ]
    ground_y = int(h * trim_ground_ratio)

    visited = [[False] * w for _ in range(h)]
    q = deque()

    for x in range(w):
        q.append((x, 0))
        visited[0][x] = True
        if h > 1:
            q.append((x, h - 1))
            visited[h - 1][x] = True
    for y in range(h):
        if not visited[y][0]:
            q.append((0, y))
            visited[y][0] = True
        if not visited[y][w - 1]:
            q.append((w - 1, y))
            visited[y][w - 1] = True

    def is_bg_pixel(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        if a < 16:
            return True
        if y >= ground_y:
            # Ground rubble strip at bottom
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            sat = max(r, g, b) - min(r, g, b)
            if sat < 38 and lum < 120:
                return True
        for br, bg, bb in bg_samples:
            dist = math.sqrt((r - br) ** 2 + (g - bg) ** 2 + (b - bb) ** 2)
            if dist <= threshold:
                return True
        return False

    while q:
        cx, cy = q.popleft()
        if is_bg_pixel(cx, cy):
            px[cx, cy] = (0, 0, 0, 0)
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                    visited[ny][nx] = True
                    q.append((nx, ny))

    # Tight crop to visible alpha
    bbox = rgba.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    return rgba


def add_pixel_outline(img: Image.Image, outline_color=(14, 18, 30, 255)) -> Image.Image:
    """Adds a crisp 1px dark outline around non-transparent pixels."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    out = Image.new("RGBA", (w + 2, h + 2), (0, 0, 0, 0))
    src_px = rgba.load()
    dst_px = out.load()

    for y in range(h):
        for x in range(w):
            r, g, b, a = src_px[x, y]
            if a > 90:
                dst_px[x + 1, y + 1] = (r, g, b, 255)

    for y in range(1, h + 1):
        for x in range(1, w + 1):
            if dst_px[x, y][3] == 0:
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w + 2 and 0 <= ny < h + 2 and dst_px[nx, ny][3] > 200 and dst_px[nx, ny] != outline_color:
                        dst_px[x, y] = outline_color
                        break
    return out


# ---------------------------------------------------------------------------
# 3. Extract Portraits & Cut-In Banners for All 8 Powered Fighters
# ---------------------------------------------------------------------------
def extract_portraits_and_cutins() -> dict:
    PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
    CUTINS_DIR.mkdir(parents=True, exist_ok=True)

    orig_img = Image.open(AI_ORIG_SHEET).convert("RGBA") if AI_ORIG_SHEET.exists() else Image.new("RGBA", (1774, 887), (20, 25, 38, 255))
    ref_img = Image.open(AI_REF_SHEET).convert("RGBA") if AI_REF_SHEET.exists() else Image.new("RGBA", (1536, 1024), (20, 25, 38, 255))

    extracted = {}
    for hid, hdef in HERO_DEFS.items():
        if "orig_crop_full" in hdef:
            full_crop = orig_img.crop(hdef["orig_crop_full"])
            cutin_crop = orig_img.crop(hdef["orig_crop_cutin"])
        else:
            full_crop = ref_img.crop(hdef["ref_crop_full"])
            cutin_crop = ref_img.crop(hdef["ref_crop_cutin"])

        splash_path = PORTRAITS_DIR / f"{hid}_splash.png"
        cutin_path = CUTINS_DIR / f"{hid}_cutin.png"
        full_crop.save(splash_path, "PNG")
        cutin_crop.save(cutin_path, "PNG")
        extracted[hid] = {
            "full": full_crop,
            "cutin": cutin_crop,
            "segmented": segment_dark_background(full_crop),
        }
    return extracted


# ---------------------------------------------------------------------------
# 4. Build Custom Hybrid Sprite Sheets (600x400) & JSONs for All 8 Fighters
#    (SA-WP8: True SF-Native Pixel Rig + Head-Box Anchor + 3-Layer Pixel Smear)
# ---------------------------------------------------------------------------
SF_BLACK = (0, 0, 0, 255)
SF_SKIN = (255, 192, 160, 255)
SF_WHITE = (250, 250, 250, 255)

HERO_PIXEL_SPECS = {
    "solaria": {
        "shirt": (241, 230, 200, 255), "shirt2": (43, 179, 163, 255), "belt": (224, 165, 38, 255),
        "arm": None, "head_skin": (201, 142, 99, 255), "hair": ("long", (244, 244, 248, 255)),
        "glow": (255, 198, 52, 255), "core": (255, 255, 255, 255), "rim": (217, 107, 18, 255),
    },
    "atlas": {
        "shirt": (95, 143, 106, 255), "shirt2": (62, 100, 73, 255), "belt": (240, 122, 30, 255),
        "arm": (139, 151, 170, 255), "arm_hi": (95, 230, 255, 255), "head_skin": (122, 74, 46, 255),
        "hair": ("buzz", (27, 27, 27, 255)), "scarf": (240, 122, 30, 255),
        "glow": (255, 138, 42, 255), "core": (255, 255, 255, 255), "rim": (180, 62, 14, 255),
    },
    "shinobi": {
        "shirt": (42, 34, 56, 255), "shirt2": (91, 44, 138, 255), "belt": (155, 77, 255, 255),
        "arm": (59, 42, 85, 255), "head_skin": None, "hair": ("hood", (74, 37, 119, 255)),
        "eye": (182, 255, 58, 255), "scarf": (182, 255, 58, 255),
        "glow": (182, 255, 58, 255), "core": (255, 255, 255, 255), "rim": (155, 77, 255, 255),
    },
    "tideweaver": {
        "shirt": (34, 53, 94, 255), "shirt2": (241, 230, 200, 255), "belt": (138, 90, 50, 255),
        "arm": None, "head_skin": None, "hair": ("long", (208, 69, 42, 255)),
        "glow": (56, 200, 255, 255), "core": (255, 255, 255, 255), "rim": (24, 100, 184, 255),
    },
    "goku": {
        "shirt": (240, 122, 30, 255), "shirt2": (44, 74, 168, 255), "belt": (44, 74, 168, 255),
        "arm": None, "head_skin": None, "hair": ("spiky", (32, 38, 54, 255)),
        "glow": (95, 230, 255, 255), "core": (255, 255, 255, 255), "rim": (30, 120, 255, 255),
    },
    "luffy": {
        "shirt": (200, 40, 42, 255), "shirt2": None, "belt": (242, 194, 48, 255),
        "arm": None, "head_skin": None, "hair": ("strawhat", (232, 194, 90, 255)), "open_vest": True,
        "glow": (255, 74, 42, 255), "core": (255, 255, 255, 255), "rim": (138, 28, 36, 255),
    },
    "naruto": {
        "shirt": (242, 138, 30, 255), "shirt2": (29, 29, 43, 255), "belt": (29, 29, 43, 255),
        "arm": (242, 138, 30, 255), "head_skin": None, "hair": ("spiky", (255, 210, 58, 255)),
        "headband": True, "glow": (123, 232, 255, 255), "core": (255, 255, 255, 255), "rim": (42, 132, 255, 255),
    },
    "saitama": {
        "shirt": (244, 207, 42, 255), "shirt2": (217, 169, 15, 255), "belt": (27, 27, 27, 255),
        "arm": (216, 52, 44, 255), "head_skin": None, "hair": ("bald", None), "cape": (246, 246, 246, 255),
        "glow": (255, 242, 122, 255), "core": (255, 255, 255, 255), "rim": (255, 42, 42, 255),
    },
}


def _sf_set_px(px, w: int, h: int, x: int, y: int, c: tuple[int, int, int, int]) -> None:
    if 0 <= x < w and 0 <= y < h:
        px[x, y] = c


def _sf_outline_fill(img: Image.Image, mask: set[tuple[int, int]], fill: tuple[int, int, int, int]) -> None:
    px = img.load()
    w, h = img.size
    border = set()
    for (x, y) in mask:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) not in mask and 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] == 0:
                border.add((nx, ny))
    for (x, y) in mask:
        _sf_set_px(px, w, h, x, y, fill)
    for (x, y) in border:
        _sf_set_px(px, w, h, x, y, SF_BLACK)


def _sf_head_box(img: Image.Image):
    """Locate canonical 5px-wide SF forehead run (#sssss# above sunglasses). EC-32 safe."""
    px = img.load()
    w, h = img.size
    for y in range(h - 3):
        run = []
        for x in range(w):
            if px[x, y] == SF_SKIN:
                run.append(x)
            else:
                if len(run) >= 4:
                    break
                run = []
        if len(run) >= 4:
            sx0, sx1 = min(run), max(run)
            x0, x1 = sx0 - 1, sx1 + 1
            y0, bottom = y - 1, y + 3
            head_skin = {
                (xx, yy)
                for yy in range(y, y + 4)
                for xx in range(sx0 - 1, sx1 + 2)
                if 0 <= xx < w and 0 <= yy < h and px[xx, yy] == SF_SKIN
            }
            return x0, y0, x1, bottom, head_skin
    return None


def _sf_back_edge(px, w: int, h: int, y: int) -> int | None:
    if y < 0 or y >= h:
        return None
    for x in range(w):
        if px[x, y][3] > 0:
            return x
    return None


def _skin_sf_crop(frame: Image.Image, hid: str, is_arm_only: bool = False, is_ssj: bool = False) -> Image.Image:
    """Applies 1px-outlined SF-native outfit + Head-Box anchored hair/hat/cape/visor. EC-31 & EC-32 safe."""
    spec = HERO_PIXEL_SPECS[hid]
    img = frame.copy()
    px = img.load()
    w, h = img.size
    hb = None if is_arm_only else _sf_head_box(img)

    shirt = spec["shirt"]
    shirt2 = spec["shirt2"] if spec.get("shirt2") else shirt
    belt = spec["belt"]
    arm = spec.get("arm")
    head_skin = spec.get("head_skin")

    white_rows = [y for y in range(h) for x in range(w) if px[x, y] == SF_WHITE]
    belt_row = max(white_rows) if white_rows else -99
    white_cols = [x for y in range(h) for x in range(w) if px[x, y] == SF_WHITE]
    mid_col = (min(white_cols) + max(white_cols)) // 2 if white_cols else -99

    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if c[3] == 0 or c == SF_BLACK:
                # EC-31: Never overwrite 1px black outlines or sunglasses!
                continue
            if c == SF_WHITE:
                if y == belt_row:
                    px[x, y] = belt
                elif spec.get("open_vest") and x == mid_col:
                    px[x, y] = head_skin or SF_SKIN
                elif y >= belt_row - 1 and spec.get("shirt2"):
                    px[x, y] = shirt2 if hid in ("goku", "naruto", "solaria") else shirt
                else:
                    px[x, y] = shirt
            elif c == SF_SKIN:
                if is_arm_only or not hb or (x, y) not in hb[4]:
                    if arm:
                        px[x, y] = arm
                    elif head_skin:
                        px[x, y] = head_skin
                elif head_skin:
                    px[x, y] = head_skin

    if spec.get("arm_hi") and arm:
        for y in range(h):
            row = [x for x in range(w) if px[x, y] == arm]
            if row:
                px[max(row), y] = spec["arm_hi"]

    if hb and not is_arm_only:
        x0, y0, x1 = hb[0], hb[1], hb[2]
        kind, col = spec["hair"]
        if hid == "goku" and is_ssj:
            col = (255, 218, 44, 255)
        hw = x1 - x0 + 1

        if kind == "spiky":
            heights = [2, 3, 4, 3, 4, 2, 3, 1, 1]
            mask = set()
            for i in range(hw + 1):
                hgt = min(3, heights[i % len(heights)])
                xx = x0 - 1 + i
                for yy in range(max(1, y0 - hgt), y0 + 2):
                    mask.add((xx, yy))
            for k, yy in enumerate(range(y0 + 1, y0 + 4)):
                for xx in range(max(1, x0 - 2 - k), x0 + 1):
                    mask.add((xx, yy))
            mask = {(x, y) for (x, y) in mask if not (y >= y0 + 2 and x > x0 + 1)}
            _sf_outline_fill(img, mask, col)
            if hid == "goku" and not is_ssj:
                for (x, y) in mask:
                    if y <= y0 - 1 and (x + y) % 2 == 0:
                        _sf_set_px(px, w, h, x, y, (56, 68, 96, 255))
            if spec.get("headband"):
                for x in range(x0, x1 + 1):
                    _sf_set_px(px, w, h, x, y0 + 2, (42, 58, 106, 255))
                _sf_set_px(px, w, h, x1 - 2, y0 + 2, (201, 210, 224, 255))
                _sf_set_px(px, w, h, x1 - 1, y0 + 2, (201, 210, 224, 255))
                _sf_set_px(px, w, h, x0 - 2, y0 + 3, (42, 58, 106, 255))
        elif kind == "strawhat":
            mask = set()
            for x in range(max(1, x0 - 2), min(w - 1, x1 + 3)):
                mask.add((x, y0))
            for yy in range(max(1, y0 - 3), y0):
                for x in range(x0 + 1, x1):
                    mask.add((x, yy))
            _sf_outline_fill(img, mask, col)
            for x in range(x0 + 1, x1):
                _sf_set_px(px, w, h, x, max(1, y0 - 1), (200, 40, 42, 255))
        elif kind == "long":
            mask = set()
            for x in range(x0, x1 + 1):
                mask.add((x, y0))
                if y0 - 1 >= 1:
                    mask.add((x, y0 - 1))
            for x in range(x0, x0 + max(2, hw // 2)):
                mask.add((x, y0 + 1))
            for yy in range(y0 + 1, min(h - 1, y0 + 9)):
                if x0 - 1 >= 1:
                    mask.add((x0 - 1, yy))
                if yy < y0 + 6:
                    mask.add((x0, yy))
            _sf_outline_fill(img, mask, col)
        elif kind == "hood":
            mask = set()
            for yy in range(max(1, y0 - 1), y0 + 4):
                for x in range(x0, x1 + 1):
                    mask.add((x, yy))
            if y0 - 2 >= 1:
                mask.add((x0 + 1, y0 - 2))
                mask.add((x0, y0 - 2))
            for yy in range(y0 + 5, min(h - 1, y0 + 8)):
                for x in range(x0 + 2, min(w - 1, x1 + 1)):
                    if px[x, yy][3] > 0 and px[x, yy] != SF_BLACK:
                        mask.add((x, yy))
            _sf_outline_fill(img, mask, col)
            for x in range(x1 - 3, x1):
                _sf_set_px(px, w, h, x, y0 + 4, (26, 15, 42, 255))
            _sf_set_px(px, w, h, x1 - 1, y0 + 4, spec["eye"])
        elif kind == "buzz":
            for x in range(x0, x1 + 1):
                _sf_set_px(px, w, h, x, y0, SF_BLACK)
            for x in range(x0 + 1, x1):
                _sf_set_px(px, w, h, x, max(0, y0 - 1), SF_BLACK)
            for x in range(x1 - 4, x1 + 1):
                _sf_set_px(px, w, h, x, y0 + 3, (95, 230, 255, 255))
        elif kind == "bald":
            _sf_set_px(px, w, h, x0 + 2, y0 + 1, (255, 246, 238, 255))
            _sf_set_px(px, w, h, x0 + 3, y0 + 1, (255, 246, 238, 255))

        if spec.get("scarf"):
            ny = y0 + 9
            lx = _sf_back_edge(px, w, h, ny)
            if lx is not None and lx >= 4:
                smask = {(lx - 1, ny), (lx - 2, ny), (lx - 3, ny + 1)}
                _sf_outline_fill(img, {(x, y) for (x, y) in smask if 1 <= x < w - 1 and 1 <= y < h - 1 and px[x, y][3] == 0}, spec["scarf"])
        if spec.get("cape"):
            cmask = set()
            for k, yy in enumerate(range(y0 + 9, min(h - 1, y0 + 17))):
                lx = _sf_back_edge(px, w, h, yy)
                if lx is None:
                    continue
                for xx in range(max(1, lx - 1 - k // 3), lx):
                    cmask.add((xx, yy))
            _sf_outline_fill(img, {(x, y) for (x, y) in cmask if 1 <= x < w - 1 and 1 <= y < h - 1 and px[x, y][3] == 0}, spec["cape"])
    return img


def _compose_sf_skill_cell(base_sheet: Image.Image, rigs_data: dict, hid: str, pose_idx: int) -> Image.Image:
    """Composes a 28x24 pixel-art skill/combo cell from authentic SF anatomy + 3-layer pixel smear VFX."""
    cell = Image.new("RGBA", (28, 24), (0, 0, 0, 0))
    px = cell.load()
    w, h = cell.size
    spec = HERO_PIXEL_SPECS[hid]
    glow, core, rim = spec["glow"], spec["core"], spec["rim"]

    if pose_idx == 10:
        # 3-layer pixel projectile sprite (Black outline -> Rim -> Glow -> White core)
        cx, cy = 14, 12
        for yy in range(cy - 8, cy + 9):
            for xx in range(cx - 10, cx + 11):
                d2 = (xx - cx) ** 2 + ((yy - cy) * 1.2) ** 2
                if 64 < d2 <= 85:
                    _sf_set_px(px, w, h, xx, yy, SF_BLACK)
                elif 36 < d2 <= 64:
                    _sf_set_px(px, w, h, xx, yy, rim)
                elif 14 < d2 <= 36:
                    _sf_set_px(px, w, h, xx, yy, glow)
                elif d2 <= 14:
                    _sf_set_px(px, w, h, xx, yy, core)
        return cell

    # Pick real SF base pose according to skill/combo phase
    pose_map = {
        0: ("PUNCH_01", 0), 1: ("PUNCH_01", 1), 2: ("PUNCH_02", 1), 3: ("PUNCH_03", 1),
        4: ("RUN", 1),      5: ("PUNCH_01", 1), 6: ("SWORD_02", 1),
        7: ("PUNCH_02", 0), 8: ("PUNCH_03", 1), 9: ("PUNCH_01", 1),
        11: ("KICK", 0),    12: ("SWORD_03", 1), 13: ("PUNCH_03", 1),
        14: ("PUNCH_02", 0), 15: ("PUNCH_01", 1), 16: ("PUNCH_03", 1), 17: ("SWORD_02", 1),
    }
    st_name, kf_idx = pose_map.get(pose_idx, ("PUNCH_01", 1))
    st_frames = rigs_data["states"].get(st_name, {}).get("frames", [])
    if not st_frames:
        st_frames = rigs_data["states"]["IDLE"]["frames"]
    kf = st_frames[min(kf_idx, len(st_frames) - 1)]
    rx, ry, rw, rh = [int(round(v)) for v in kf["rect"]]
    top_pad = 4 if ry >= 4 else 0
    raw = base_sheet.crop((max(0, rx - 2), ry - top_pad, min(600, rx + rw + 2), min(400, ry + rh)))
    skinned = _skin_sf_crop(raw, hid, is_arm_only=False, is_ssj=(pose_idx >= 14 and hid == "goku"))

    # Paste skinned SF body on the left-center of the 28x24 cell so the right side holds the 3-layer pixel smear/effect
    paste_x = 1
    paste_y = max(0, 23 - skinned.height)
    cell.alpha_composite(skinned, (paste_x, paste_y))

    # Add crisp hero-specific 3-layer pixel smear / weapon / energy signature on the front side
    hx_x, hx_y = min(w - 7, paste_x + skinned.width - 3), max(7, paste_y + skinned.height // 2)
    is_ult = pose_idx >= 14
    if pose_idx in (0, 1, 2, 3):
        # 3-layer pixel crescent combo smear
        for dy in range(-5, 6):
            sx = min(w - 2, hx_x + 4 - (dy * dy) // 5)
            _sf_set_px(px, w, h, sx - 1, hx_y + dy, rim)
            _sf_set_px(px, w, h, sx, hx_y + dy, glow)
            _sf_set_px(px, w, h, min(w - 1, sx + 1), hx_y + dy, core)
    elif hid == "luffy":
        # Stretching rubber arm with 1px black outline + Haki / Red Roc fist
        end_x = min(w - 4, hx_x + (7 if is_ult else 5))
        for xx in range(hx_x - 2, end_x):
            _sf_set_px(px, w, h, xx, hx_y - 1, SF_BLACK)
            _sf_set_px(px, w, h, xx, hx_y, rim if is_ult else SF_SKIN)
            _sf_set_px(px, w, h, xx, hx_y + 1, SF_BLACK)
        rf = 3 if is_ult else 2
        fist_mask = {(end_x + dx0, hx_y + dy0) for dx0 in range(0, rf + 2) for dy0 in range(-rf, rf + 1)}
        _sf_outline_fill(cell, fist_mask, glow)
        _sf_set_px(px, w, h, min(w - 2, end_x + rf), hx_y, core)
    elif hid == "shinobi":
        # Neon green + purple X-cross slash smear
        for t in range(-5, 6):
            _sf_set_px(px, w, h, min(w - 2, hx_x + 3 + t), hx_y + t, core)
            _sf_set_px(px, w, h, min(w - 2, hx_x + 2 + t), hx_y + t, glow)
            _sf_set_px(px, w, h, min(w - 2, hx_x + 4 + t), hx_y + t, rim)
            _sf_set_px(px, w, h, min(w - 2, hx_x + 3 + t), hx_y - t, core)
            _sf_set_px(px, w, h, min(w - 2, hx_x + 2 + t), hx_y - t, glow)
    elif hid == "tideweaver":
        # S-curve 3-layer hydro whip
        for dx0 in range(0, min(10, w - hx_x - 1)):
            wy = int(round(hx_y + math.sin(dx0 * 0.55) * 3.0))
            _sf_set_px(px, w, h, hx_x + dx0, wy - 2, SF_BLACK)
            _sf_set_px(px, w, h, hx_x + dx0, wy - 1, core)
            _sf_set_px(px, w, h, hx_x + dx0, wy, glow)
            _sf_set_px(px, w, h, hx_x + dx0, wy + 1, rim)
            _sf_set_px(px, w, h, hx_x + dx0, wy + 2, SF_BLACK)
    elif hid == "saitama":
        # Serious Punch pressure wedge + shockwave
        for dx0 in range(1, min(10, w - hx_x)):
            half = 1 + dx0 // 2
            for dy0 in range(-half, half + 1):
                x, y = hx_x + dx0, hx_y + dy0
                if abs(dy0) == half:
                    _sf_set_px(px, w, h, x, y, rim)
                elif abs(dy0) == half - 1:
                    _sf_set_px(px, w, h, x, y, glow)
                elif dx0 % 2 == 0:
                    _sf_set_px(px, w, h, x, y, core)
    else:
        # 3-layer energy sphere + beam start (Goku, Naruto, Solaria, Atlas)
        r_max = 5 if is_ult else 4
        cx, cy = min(w - r_max - 1, hx_x + 3), hx_y
        for yy in range(cy - r_max, cy + r_max + 1):
            for xx in range(cx - r_max, cx + r_max + 1):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if r_max * r_max - 5 < d2 <= r_max * r_max:
                    _sf_set_px(px, w, h, xx, yy, SF_BLACK)
                elif (r_max - 1) ** 2 - 3 < d2 <= r_max * r_max - 5:
                    _sf_set_px(px, w, h, xx, yy, rim)
                elif d2 <= (r_max - 2) ** 2:
                    _sf_set_px(px, w, h, xx, yy, core)
                elif d2 <= (r_max - 1) ** 2:
                    _sf_set_px(px, w, h, xx, yy, glow)
    return cell


def build_all_hero_sheets_and_jsons() -> None:
    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    CUSTOM_FIGHTERS_DIR.mkdir(parents=True, exist_ok=True)

    base_sheet_path = SHEETS_DIR / "Bitmap 591.png"
    base_img = Image.open(base_sheet_path).convert("RGBA")
    rigs_data = json.loads((PROJECT_ROOT / "data" / "sf_compiled_rigs.json").read_text(encoding="utf-8"))

    # Collect all unique body/torso rects and weapon_arm/start_arm rects from sf_compiled_rigs.json
    body_rects: set[tuple[int, int, int, int]] = set()
    arm_rects: set[tuple[int, int, int, int]] = set()
    for _st_name, st_def in rigs_data.get("states", {}).items():
        for kf in (st_def.get("keyframes") or st_def.get("frames") or []):
            body_rects.add(tuple(int(round(v)) for v in kf["rect"]))
        if "torso" in st_def:
            for kf in (st_def["torso"].get("keyframes") or st_def["torso"].get("frames") or []):
                body_rects.add(tuple(int(round(v)) for v in kf["rect"]))
        for sub_k in ("weapon_arm", "start_arm"):
            if sub_k in st_def:
                for kf in (st_def[sub_k].get("keyframes") or st_def[sub_k].get("frames") or []):
                    arm_rects.add(tuple(int(round(v)) for v in kf["rect"]))

    for hid, hdef in HERO_DEFS.items():
        sheet = base_img.copy()
        w, h = sheet.size

        # 1. Skin all weapon/start arms first
        for (rx, ry, rw, rh) in sorted(arm_rects):
            crop = base_img.crop((rx, ry, rx + rw, ry + rh))
            skinned_arm = _skin_sf_crop(crop, hid, is_arm_only=True)
            sheet.paste(skinned_arm, (rx, ry))

        # 2. Skin all 72-state body & torso frames with 4px top headroom for spiky hair / straw hat / headband
        for (rx, ry, rw, rh) in sorted(body_rects):
            top_pad = 4 if (ry >= 4 and rh >= 15) else 0
            crop = base_img.crop((rx, ry - top_pad, rx + rw, ry + rh))
            skinned_body = _skin_sf_crop(crop, hid, is_arm_only=False)
            sheet.paste(skinned_body, (rx, ry - top_pad))

        # 2b. Fallback pass: tint any unreferenced SF_WHITE pixels in y < 260 so the entire sheet is visually uniform
        s_px = sheet.load()
        sh_col = HERO_PIXEL_SPECS[hid]["shirt"]
        for yy in range(min(260, h)):
            for xx in range(w):
                if s_px[xx, yy] == SF_WHITE:
                    s_px[xx, yy] = sh_col

        # 3. Clear custom frame region (y = 265..360) and stamp 18 authentic SF pixel-art skill/combo cells
        draw = ImageDraw.Draw(sheet)
        draw.rectangle([0, 265, w - 1, 360], fill=(0, 0, 0, 0))

        for idx in range(11):
            cell_x = 20 + idx * 32
            cell_y = 268
            cell_img = _compose_sf_skill_cell(base_img, rigs_data, hid, idx)
            sheet.paste(cell_img, (cell_x, cell_y))

        for idx in range(11, 18):
            cell_x = 20 + (idx - 11) * 32
            cell_y = 302
            cell_img = _compose_sf_skill_cell(base_img, rigs_data, hid, idx)
            sheet.paste(cell_img, (cell_x, cell_y))

        out_sheet_path = SHEETS_DIR / f"hero_{hid}_mugen.png"
        sheet.save(out_sheet_path, "PNG")

        # Build MUGEN states & JSON definition
        sk_kit = hdef["skill_kit"]

        def _make_state_frames(indices: list[int], row_y: int, base_idx_offset: int, hit_w: float = 24.0, hit_h: float = 14.0) -> list[dict]:
            frames = []
            for fnr, p_idx in enumerate(indices, start=1):
                cx = 20.0 + float(p_idx - base_idx_offset) * 32.0
                clsn1 = [[2.0, -18.0, hit_w, hit_h]] if fnr >= 2 else []
                frames.append({
                    "frame_nr": fnr,
                    "duration": 3 if fnr == 2 else 2,
                    "rect": [cx, float(row_y), 28.0, 24.0],
                    "pivot": [-9.0, -23.0],
                    "clsn2": [[-6.0, -18.0, 12.0, 18.0]],
                    "clsn1": clsn1,
                })
            return frames

        mugen_states = {
            "MUGEN_COMBO_1": {
                "type": "mugen_attack", "loop": False, "next_state": "IDLE",
                "damage": 7.0, "hit_force": 14.0, "range": 22.0, "step_vel_x": 1.3, "knockdown": False,
                "sfx": "punch_light",
                "frames": _make_state_frames([0, 0], 268, 0, 18.0, 10.0),
            },
            "MUGEN_COMBO_2": {
                "type": "mugen_attack", "loop": False, "next_state": "IDLE",
                "damage": 8.0, "hit_force": 16.0, "range": 23.0, "step_vel_x": 1.5, "knockdown": False,
                "sfx": "punch_light",
                "frames": _make_state_frames([1, 1], 268, 0, 20.0, 12.0),
            },
            "MUGEN_COMBO_3": {
                "type": "mugen_attack", "loop": False, "next_state": "IDLE",
                "damage": 10.0, "hit_force": 20.0, "range": 25.0, "step_vel_x": 1.8, "knockdown": False,
                "sfx": "punch_heavy",
                "frames": _make_state_frames([2, 2], 268, 0, 22.0, 12.0),
            },
            "MUGEN_COMBO_4": {
                "type": "mugen_attack", "loop": False, "next_state": "IDLE",
                "damage": 14.0, "hit_force": 30.0, "range": 28.0, "step_vel_x": 2.4, "knockdown": True,
                "sfx": "punch_heavy",
                "frames": _make_state_frames([3, 3, 3], 268, 0, 24.0, 14.0),
            },
            "SHUNPO_SLASH": {
                "type": "mugen_special", "loop": False, "next_state": "IDLE",
                "damage": float(sk_kit["skill_1"]["damage"]),
                "hit_force": float(sk_kit["skill_1"]["hit_force"]),
                "dash_speed_24hz": float(sk_kit["skill_1"].get("dash_speed_24hz", 7.5)),
                "knockdown": bool(sk_kit["skill_1"].get("knockdown", True)),
                "sfx": str(sk_kit["skill_1"].get("sfx", "swing_sword")),
                "frames": _make_state_frames([4, 5, 6], 268, 0, 32.0, 18.0),
            },
            "SKILL_1": {
                "type": "mugen_special", "loop": False, "next_state": "IDLE",
                "damage": float(sk_kit["skill_1"]["damage"]),
                "hit_force": float(sk_kit["skill_1"]["hit_force"]),
                "dash_speed_24hz": float(sk_kit["skill_1"].get("dash_speed_24hz", 6.5)),
                "knockdown": bool(sk_kit["skill_1"].get("knockdown", False)),
                "sfx": str(sk_kit["skill_1"].get("sfx", "punch_heavy")),
                "frames": _make_state_frames([4, 5, 6], 268, 0, 32.0, 18.0),
            },
            "CHAKRA_WAVE": {
                "type": "mugen_special", "loop": False, "next_state": "IDLE",
                "damage": float(sk_kit["skill_2"]["damage"]),
                "hit_force": float(sk_kit["skill_2"]["hit_force"]),
                "projectile_id": str(sk_kit["skill_2"].get("projectile_id", "CHAKRA_WAVE")),
                "projectile_speed_24hz": float(sk_kit["skill_2"].get("projectile_speed_24hz", 22.0)),
                "projectile_damage": float(sk_kit["skill_2"]["damage"]),
                "projectile_pushback": float(sk_kit["skill_2"]["hit_force"]),
                "spawn_frame": 2,
                "sfx": str(sk_kit["skill_2"].get("sfx", "swing_sword")),
                "frames": _make_state_frames([7, 8, 9], 268, 0, 28.0, 16.0),
            },
            "SKILL_2": {
                "type": "mugen_special", "loop": False, "next_state": "IDLE",
                "damage": float(sk_kit["skill_2"]["damage"]),
                "hit_force": float(sk_kit["skill_2"]["hit_force"]),
                "projectile_id": str(sk_kit["skill_2"].get("projectile_id", "")),
                "projectile_speed_24hz": float(sk_kit["skill_2"].get("projectile_speed_24hz", 22.0)),
                "projectile_damage": float(sk_kit["skill_2"]["damage"]),
                "projectile_pushback": float(sk_kit["skill_2"]["hit_force"]),
                "spawn_frame": 2,
                "knockdown": bool(sk_kit["skill_2"].get("knockdown", True)),
                "sfx": str(sk_kit["skill_2"].get("sfx", "swing_sword")),
                "frames": _make_state_frames([7, 8, 9], 268, 0, 34.0, 18.0),
            },
            "SKILL_3": {
                "type": "mugen_special", "loop": False, "next_state": "IDLE",
                "damage": float(sk_kit["skill_3"]["damage"]),
                "hit_force": float(sk_kit["skill_3"]["hit_force"]),
                "dash_speed_24hz": float(sk_kit["skill_3"].get("dash_speed_24hz", 7.5)),
                "knockdown": bool(sk_kit["skill_3"].get("knockdown", True)),
                "sfx": str(sk_kit["skill_3"].get("sfx", "punch_heavy")),
                "frames": _make_state_frames([11, 12, 13], 302, 11, 38.0, 20.0),
            },
            "SKILL_4": {
                "type": "mugen_special", "loop": False, "next_state": "IDLE",
                "damage": float(sk_kit["skill_4"]["damage"]),
                "hit_force": float(sk_kit["skill_4"]["hit_force"]),
                "dash_speed_24hz": float(sk_kit["skill_4"].get("dash_speed_24hz", 8.0)),
                "knockdown": True,
                "is_ultimate": True,
                "sfx": str(sk_kit["skill_4"].get("sfx", "explosion_large")),
                "frames": _make_state_frames([14, 15, 16, 17], 302, 11, 56.0, 24.0),
            },
        }

        special_moves = {
            "SHUNPO_SLASH": {
                "id": "SHUNPO_SLASH",
                "display_name": sk_kit["skill_1"]["name"],
                "state": sk_kit["skill_1"]["state"],
                "command": "U / Numpad 5 | D, DF, F + attack",
                "energy_cost": float(sk_kit["skill_1"]["resource_cost"]),
                "cooldown_sec": float(sk_kit["skill_1"]["cooldown_sec"]),
                "dash_speed_24hz": float(sk_kit["skill_1"].get("dash_speed_24hz", 7.5)),
                "dash_distance": float(sk_kit["skill_1"].get("dash_distance", 65.0)),
                "damage": float(sk_kit["skill_1"]["damage"]),
                "hit_force": float(sk_kit["skill_1"]["hit_force"]),
                "knockdown": bool(sk_kit["skill_1"].get("knockdown", True)),
                "sfx": str(sk_kit["skill_1"].get("sfx", "swing_sword")),
            },
            "CHAKRA_WAVE": {
                "id": "CHAKRA_WAVE",
                "display_name": sk_kit["skill_2"]["name"],
                "state": sk_kit["skill_2"]["state"],
                "command": "I / Numpad 6 | D, DB, B + attack",
                "energy_cost": float(sk_kit["skill_2"]["resource_cost"]),
                "cooldown_sec": float(sk_kit["skill_2"]["cooldown_sec"]),
                "projectile_id": "CHAKRA_WAVE",
                "projectile_speed_24hz": float(sk_kit["skill_2"].get("projectile_speed_24hz", 22.0)),
                "projectile_damage": float(sk_kit["skill_2"]["damage"]),
                "projectile_pushback": float(sk_kit["skill_2"]["hit_force"]),
                "projectile_rect": [340.0, 270.0, 28.0, 20.0],
                "sfx": str(sk_kit["skill_2"].get("sfx", "swing_sword")),
            },
            "SKILL_1": sk_kit["skill_1"],
            "SKILL_2": sk_kit["skill_2"],
            "SKILL_3": sk_kit["skill_3"],
            "SKILL_4": sk_kit["skill_4"],
        }

        hero_json = {
            "schema_version": "2.0.0",
            "format": "mugen_fighter_v2",
            "id": hid,
            "display_name": hdef["display_name"],
            "short_name": hdef["short_name"],
            "subtitle": hdef["subtitle"],
            "roster_category": hdef["roster_category"],
            "is_powered_fighter": True,
            "author": "HH Game Studio",
            "sheet_path": f"res://assets/sheets/hero_{hid}_mugen.png",
            "portrait_path": f"res://assets/sprites/portraits/{hid}_splash.png",
            "cutin_path": f"res://assets/sprites/cutins/{hid}_cutin.png",
            "sheet_size": [600, 400],
            "hp_mult": hdef["hp_mult"],
            "speed_mult": hdef["speed_mult"],
            "use_sf_split_rig_for_guns": True,
            "default_clsn2": [[-6.0, -18.0, 12.0, 18.0]],
            "resource_spec": hdef["resource_spec"],
            "skill_kit": sk_kit,
            "cancel_table": {
                "MUGEN_COMBO_1": ["MUGEN_COMBO_2", "SHUNPO_SLASH", "CHAKRA_WAVE", "SKILL_1", "SKILL_2", "SKILL_3", "SKILL_4"],
                "MUGEN_COMBO_2": ["MUGEN_COMBO_3", "SHUNPO_SLASH", "CHAKRA_WAVE", "SKILL_1", "SKILL_2", "SKILL_3", "SKILL_4"],
                "MUGEN_COMBO_3": ["MUGEN_COMBO_4", "SHUNPO_SLASH", "CHAKRA_WAVE", "SKILL_1", "SKILL_2", "SKILL_3", "SKILL_4"],
                "MUGEN_COMBO_4": ["SHUNPO_SLASH", "CHAKRA_WAVE", "SKILL_1", "SKILL_2", "SKILL_3", "SKILL_4"],
            },
            "special_moves": special_moves,
            "mugen_states": mugen_states,
        }

        json_path = CUSTOM_FIGHTERS_DIR / f"hero_{hid}_mugen.json"
        json_path.write_text(json.dumps(hero_json, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. Render Pipeline Visual Samples (Phương án A, B, C, D + Master 2x2)
# ---------------------------------------------------------------------------
def _draw_jus_pocket_sprite(hid: str, pose: str = "skill") -> Image.Image:
    """Generates a 36x36 Jump Ultimate Stars (JUS) 2.5-head pocket-anime pixel sprite with 1px dark outline."""
    canvas = Image.new("RGBA", (36, 36), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    pal = HERO_DEFS[hid]["palette"]
    prim = pal["primary"]
    sec = pal["secondary"]
    acc = pal["accent"]
    hair = pal["hair"]
    skin = pal["skin"]
    aura = pal["aura"]
    beam = pal["beam"]
    boots = pal["boots"]

    # Aura
    if pose in ("skill", "ult"):
        draw.ellipse([2, 2, 33, 34], fill=(aura[0], aura[1], aura[2], 95))

    # Cape / Scarf
    if hid in ("saitama", "atlas"):
        draw.polygon([(11, 16), (3, 30), (14, 31)], fill=sec)
    elif hid == "shinobi":
        draw.polygon([(10, 15), (2, 24), (12, 26)], fill=sec)

    # Legs (y = 24..33)
    draw.rectangle([11, 24, 15, 32], fill=sec)
    draw.rectangle([18, 24, 23, 32], fill=sec)
    draw.rectangle([10, 31, 15, 34], fill=boots)
    draw.rectangle([18, 31, 24, 34], fill=boots)

    # Torso (y = 15..24)
    draw.rectangle([11, 15, 22, 24], fill=prim)
    draw.rectangle([11, 21, 22, 23], fill=sec)

    # Expressive 2.5-Head JUS Anime Head (y = 4..15, 11px tall!)
    draw.rectangle([11, 6, 22, 15], fill=skin)
    # Expressive anime eyes (2x3 white + dark pupil)
    draw.rectangle([15, 10, 16, 12], fill=(255, 255, 255, 255))
    draw.point((16, 11), fill=(15, 20, 32, 255))
    draw.rectangle([19, 10, 20, 12], fill=(255, 255, 255, 255))
    draw.point((20, 11), fill=(15, 20, 32, 255))

    # Iconic Hair / Hat
    if hid == "goku":
        h_col = (255, 215, 35, 255) if pose == "ult" else hair
        draw.polygon([(8, 9), (12, 1), (16, 6), (20, 1), (26, 7), (22, 10), (11, 10)], fill=h_col)
    elif hid == "luffy":
        draw.ellipse([8, 3, 25, 9], fill=hair)
        draw.line([(9, 6), (24, 6)], fill=prim, width=2)
    elif hid == "naruto":
        draw.polygon([(9, 8), (12, 2), (16, 5), (20, 2), (24, 8)], fill=hair)
        draw.rectangle([11, 6, 22, 8], fill=(55, 70, 95, 255))
        draw.rectangle([14, 6, 19, 8], fill=(210, 220, 230, 255))
    elif hid == "saitama":
        draw.ellipse([11, 5, 22, 12], fill=skin)
        draw.rectangle([13, 6, 15, 7], fill=(255, 255, 255, 255))
    else:
        draw.polygon([(9, 9), (13, 2), (18, 4), (24, 8), (22, 10), (10, 10)], fill=hair)

    # Arms & Action VFX
    draw.rectangle([21, 16, 29, 20], fill=acc if hid in ("solaria", "atlas", "saitama") else skin)
    if pose in ("skill", "ult"):
        draw.ellipse([26, 12, 35, 23], fill=beam, outline=(255, 255, 255, 255))

    return add_pixel_outline(canvas)


def _load_arena_backdrop() -> Image.Image:
    bg_path = PROJECT_ROOT / "assets" / "maps" / "steel_harbor_bg.png"
    fg_path = PROJECT_ROOT / "assets" / "maps" / "steel_harbor_fg.png"
    canvas = Image.new("RGBA", (800, 450), (18, 24, 38, 255))
    if bg_path.exists():
        bg = Image.open(bg_path).convert("RGBA").resize((800, 450), Image.Resampling.NEAREST)
        canvas.alpha_composite(bg)
    if fg_path.exists():
        fg = Image.open(fg_path).convert("RGBA").resize((800, 450), Image.Resampling.NEAREST)
        canvas.alpha_composite(fg)
    return canvas


def _draw_sample_hud(draw: ImageDraw.ImageDraw, title: str, hero_name: str, res_label: str, res_color: tuple) -> None:
    title = title.replace("—", "-")
    hero_name = hero_name.replace("—", "-")
    # Top HUD bar
    draw.rectangle([0, 0, 800, 48], fill=(10, 14, 22, 230))
    draw.line([(0, 48), (800, 48)], fill=(65, 95, 140, 255), width=2)

    # P1 Card (Powered Fighter)
    draw.rectangle([12, 6, 290, 42], fill=(22, 28, 42, 245), outline=res_color)
    draw.text((20, 9), f"P1: {hero_name}", fill=(255, 245, 210, 255))
    # HP Bar
    draw.rectangle([135, 10, 280, 16], fill=(40, 15, 15, 255))
    draw.rectangle([135, 10, 265, 16], fill=(235, 55, 55, 255))
    # LoL Segmented Resource Bar
    draw.rectangle([135, 19, 280, 25], fill=(15, 20, 30, 255))
    draw.rectangle([135, 19, 255, 25], fill=res_color)
    for seg_x in (171, 207, 243):
        draw.line([(seg_x, 19), (seg_x, 25)], fill=(0, 0, 0, 220), width=1)
    draw.text((20, 25), f"{res_label} [LoL]", fill=res_color)

    # 4 Skill Icons (U / I / O / P)
    keys = ["U/5", "I/6", "O/7", "P/8"]
    for idx, k in enumerate(keys):
        ix = 135 + idx * 36
        iy = 28
        col = (255, 195, 40, 255) if idx == 3 else res_color
        draw.rectangle([ix, iy, ix + 31, iy + 12], fill=(28, 36, 54, 255), outline=col)
        draw.text((ix + 4, iy + 1), k, fill=(255, 255, 255, 255))

    # Center Title Banner
    draw.text((310, 16), title, fill=(130, 225, 255, 255))


def build_4_pipeline_showcase_images(extracted: dict) -> list[Path]:
    SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    hero_order = ["solaria", "atlas", "shinobi", "tideweaver", "goku", "luffy", "naruto", "saitama"]
    out_paths = []

    # -----------------------------------------------------------------------
    # PIPELINE A: Hybrid Split-Rig + Procedural Pixel-Art (22-26px) + VFX
    # -----------------------------------------------------------------------
    img_a = Image.new("RGBA", (1600, 900), (14, 18, 28, 255))
    draw_a = ImageDraw.Draw(img_a)
    draw_a.rectangle([0, 0, 1600, 56], fill=(22, 30, 48, 255))
    draw_a.text((24, 18), "PHUONG AN A (KHUYEN DUNG #1): HYBRID SPLIT-RIG PIXEL-ART (22-26px) + SHADER/CANVAS VFX + XOAY SUNG 360 DO", fill=(255, 220, 90, 255))

    # Left half: 8 Heroes at 7x Zoom showing Idle + Skill + Ultimate
    for i, hid in enumerate(hero_order):
        col = i % 2
        row = i // 2
        bx = 24 + col * 380
        by = 76 + row * 198
        pal = HERO_DEFS[hid]["palette"]
        clean_title = HERO_DEFS[hid]["display_name"].replace("—", "-")
        draw_a.rectangle([bx, by, bx + 364, by + 184], fill=(20, 26, 40, 255), outline=pal["accent"])
        draw_a.text((bx + 12, by + 8), f"{clean_title} [{HERO_DEFS[hid]['resource_spec']['display_label']}]", fill=pal["accent"])

        sheet = Image.open(SHEETS_DIR / f"hero_{hid}_mugen.png").convert("RGBA")
        # Crop Combo, Skill 1 (U), Skill 3 (O), Ultimate (P)
        poses = [
            ("COMBO", sheet.crop((20, 270, 48, 290))),
            ("SKILL U/5", sheet.crop((20 + 5 * 32, 270, 48 + 5 * 32, 290))),
            ("SKILL O/7", sheet.crop((20 + 1 * 32, 305, 48 + 1 * 32, 325))),
            ("ULT P/8", sheet.crop((20 + 5 * 32, 305, 48 + 5 * 32, 325))),
        ]
        for p_idx, (p_label, p_crop) in enumerate(poses):
            zoomed = p_crop.resize((28 * 4, 20 * 4), Image.Resampling.NEAREST)
            px_x = bx + 10 + p_idx * 88
            px_y = by + 42
            img_a.alpha_composite(zoomed, (px_x, px_y))
            draw_a.text((px_x + 12, by + 145), p_label, fill=(210, 220, 240, 255))

    # Right half: Actual 1x Steel Harbor Arena Context + 2x Zoom Action Box
    arena_a = _load_arena_backdrop()
    adraw_a = ImageDraw.Draw(arena_a)
    _draw_sample_hud(adraw_a, "PHUONG AN A - IN-GAME 1X", "GOKU vs SAITAMA", "SAIYAN KI", (56, 182, 255, 255))
    # Place Goku, Saitama, Solaria, Shinobi on the Steel Harbor platforms + Beam VFX
    for idx, (hid, ax, ay) in enumerate([("goku", 210, 232), ("saitama", 520, 232), ("solaria", 310, 122), ("shinobi", 450, 122)]):
        sh = Image.open(SHEETS_DIR / f"hero_{hid}_mugen.png").convert("RGBA")
        sp = sh.crop((20 + 5 * 32, 305, 48 + 5 * 32, 325))
        arena_a.alpha_composite(sp, (ax, ay))
        adraw_a.rectangle([ax + 2, ay - 6, ax + 24, ay - 4], fill=(235, 55, 55, 255))
        adraw_a.rectangle([ax + 2, ay - 3, ax + 24, ay - 1], fill=HERO_DEFS[hid]["palette"]["accent"])
    # Kamehameha vs Serious Punch clash in arena_a
    adraw_a.rectangle([236, 236, 380, 248], fill=(80, 225, 255, 210))
    adraw_a.rectangle([236, 239, 380, 245], fill=(255, 255, 255, 255))
    adraw_a.polygon([(520, 242), (380, 215), (380, 268)], fill=(255, 220, 70, 165))
    img_a.alpha_composite(arena_a, (790, 76))
    # 2x Zoomed crop of the arena clash below
    clash_zoom = arena_a.crop((180, 190, 580, 340)).resize((800, 300), Image.Resampling.NEAREST)
    img_a.alpha_composite(clash_zoom, (790, 560))
    draw_a.rectangle([790, 560, 1590, 860], outline=(80, 225, 255, 255), width=2)
    draw_a.text((805, 568), "PHONG DAI 2X SAN DAU STEEL HARBOR (DONG BO 100% VOI SUPERFIGHTERS + HIEU UNG CHUONG KAMEHAMEHA & SERIOUS PUNCH)", fill=(255, 255, 255, 255))

    path_a = SHOWCASE_DIR / "pipeline_A_sf_hybrid_sample.png"
    img_a.save(path_a, "PNG")
    out_paths.append(path_a)

    # -----------------------------------------------------------------------
    # PIPELINE B: MUGEN / JUS Pocket-Anime Sprite Style (32-36px, 2.5-3 Heads)
    # -----------------------------------------------------------------------
    img_b = Image.new("RGBA", (1600, 900), (14, 18, 28, 255))
    draw_b = ImageDraw.Draw(img_b)
    draw_b.rectangle([0, 0, 1600, 56], fill=(28, 22, 48, 255))
    draw_b.text((24, 18), "PHUONG AN B: MUGEN / JUS POCKET-ANIME SPRITE (32-36px, TY LE 2.5-3 DAU, VIEN DEN 1PX SAC NET, RO MAT & TOC ANIME)", fill=(120, 235, 255, 255))

    for i, hid in enumerate(hero_order):
        col = i % 2
        row = i // 2
        bx = 24 + col * 380
        by = 76 + row * 198
        pal = HERO_DEFS[hid]["palette"]
        clean_title = HERO_DEFS[hid]["display_name"].replace("—", "-")
        draw_b.rectangle([bx, by, bx + 364, by + 184], fill=(22, 24, 42, 255), outline=pal["accent"])
        draw_b.text((bx + 12, by + 8), f"{clean_title} (JUS 36px)", fill=pal["accent"])

        for p_idx, (p_label, p_mode) in enumerate([("IDLE 5X", "idle"), ("SKILL 5X", "skill"), ("ULTIMATE 5X", "ult")]):
            jus_sp = _draw_jus_pocket_sprite(hid, p_mode)
            jus_zoom = jus_sp.resize((36 * 3, 36 * 3), Image.Resampling.NEAREST)
            px_x = bx + 14 + p_idx * 114
            px_y = by + 34
            img_b.alpha_composite(jus_zoom, (px_x, px_y))
            draw_b.text((px_x + 18, by + 152), p_label, fill=(220, 230, 245, 255))

    arena_b = _load_arena_backdrop()
    adraw_b = ImageDraw.Draw(arena_b)
    _draw_sample_hud(adraw_b, "PHUONG AN B - JUS POCKET-ANIME", "NARUTO vs LUFFY", "CHAKRA + KURAMA", (0, 180, 216, 255))
    for hid, ax, ay in [("naruto", 220, 216), ("luffy", 490, 216), ("solaria", 310, 108), ("tideweaver", 455, 108)]:
        jus_sp = _draw_jus_pocket_sprite(hid, "ult")
        arena_b.alpha_composite(jus_sp, (ax, ay))
    img_b.alpha_composite(arena_b, (790, 76))
    clash_b = arena_b.crop((180, 175, 580, 325)).resize((800, 300), Image.Resampling.NEAREST)
    img_b.alpha_composite(clash_b, (790, 560))
    draw_b.rectangle([790, 560, 1590, 860], outline=(255, 180, 50, 255), width=2)
    draw_b.text((805, 568), "PHONG DAI 2X SAN DAU VOI SPRITE CHUAN JUS (NHAN VAT CAO ~34PX, NHIN RO MAT, MU ROM LUFFY & TOC NARUTO/GOKU)", fill=(255, 255, 255, 255))

    path_b = SHOWCASE_DIR / "pipeline_B_mugen_jus_sample.png"
    img_b.save(path_b, "PNG")
    out_paths.append(path_b)

    # -----------------------------------------------------------------------
    # PIPELINE C: High-Res AI Concept Art -> Auto Segmentation + Outlined Sprite + Ultimate Cut-In Banner
    # -----------------------------------------------------------------------
    img_c = Image.new("RGBA", (1600, 900), (14, 18, 28, 255))
    draw_c = ImageDraw.Draw(img_c)
    draw_c.rectangle([0, 0, 1600, 56], fill=(44, 24, 48, 255))
    draw_c.text((24, 18), "PHUONG AN C: TACH NEN TU ANH 1 CUA BAN -> SPRITE VIEN DEN TRONG TRAN + DAI BANG ULTIMATE CUT-IN TOAN MAN HINH!", fill=(255, 195, 255, 255))

    for i, hid in enumerate(hero_order):
        col = i % 2
        row = i // 2
        bx = 24 + col * 380
        by = 76 + row * 198
        pal = HERO_DEFS[hid]["palette"]
        clean_title = HERO_DEFS[hid]["display_name"].replace("—", "-")
        draw_c.rectangle([bx, by, bx + 364, by + 184], fill=(24, 22, 38, 255), outline=pal["accent"])
        draw_c.text((bx + 12, by + 8), f"{clean_title} (AI Segmented)", fill=pal["accent"])

        seg_img = extracted[hid]["segmented"]
        # 1) High-res Cutout preview (height 125px)
        ratio = max(1, seg_img.width) / max(1, seg_img.height)
        hd_h = 125
        hd_w = min(130, max(24, int(hd_h * ratio)))
        hd_thumb = seg_img.resize((hd_w, hd_h), Image.Resampling.LANCZOS)
        img_c.alpha_composite(hd_thumb, (bx + 12, by + 36))

        # 2) Pixel-Quantized Outlined 42px Arena Sprite zoomed 3x
        ar_h = 42
        ar_w = max(16, int(ar_h * ratio))
        small_sp = add_pixel_outline(seg_img.resize((ar_w, ar_h), Image.Resampling.BOX))
        zoom_sp = small_sp.resize((small_sp.width * 3, small_sp.height * 3), Image.Resampling.NEAREST)
        img_c.alpha_composite(zoom_sp, (bx + 145, by + 32))

        # 3) Ultimate Cut-In Banner Thumbnail
        cutin_thumb = extracted[hid]["cutin"].resize((112, 58), Image.Resampling.LANCZOS)
        img_c.alpha_composite(cutin_thumb, (bx + 242, by + 64))
        draw_c.rectangle([bx + 242, by + 64, bx + 354, by + 122], outline=pal["accent"], width=1)
        draw_c.text((bx + 244, by + 128), "ULT CUT-IN (P/8)", fill=(255, 230, 120, 255))

    arena_c = _load_arena_backdrop()
    adraw_c = ImageDraw.Draw(arena_c)
    _draw_sample_hud(adraw_c, "PHUONG AN C - AI SPRITE + ULTIMATE CUT-IN", "SOLARIA vs VOID SHINOBI", "SOLAR MANTRA", (255, 168, 34, 255))

    # Draw segmented outlined sprites in the arena
    for hid, ax, ay in [("solaria", 220, 206), ("shinobi", 495, 206), ("atlas", 305, 98), ("tideweaver", 455, 98)]:
        seg_img = extracted[hid]["segmented"]
        ratio = max(1, seg_img.width) / max(1, seg_img.height)
        sp_c = add_pixel_outline(seg_img.resize((max(18, int(44 * ratio)), 44), Image.Resampling.BOX))
        arena_c.alpha_composite(sp_c, (ax, ay))

    # Draw Dual Clash Full-Screen Ultimate Cut-In Banner across the Steel Harbor arena!
    adraw_c.rectangle([0, 88, 800, 178], fill=(8, 10, 18, 225))
    cut_left = extracted["solaria"]["cutin"].resize((220, 86), Image.Resampling.LANCZOS)
    cut_right = extracted["shinobi"]["cutin"].resize((220, 86), Image.Resampling.LANCZOS)
    arena_c.alpha_composite(cut_left, (12, 90))
    arena_c.alpha_composite(cut_right, (568, 90))
    for sl_y in range(94, 174, 10):
        adraw_c.line([(235, sl_y), (565, sl_y)], fill=(255, 220, 90, 130), width=1)
    adraw_c.line([(0, 88), (800, 88)], fill=(255, 195, 45, 255), width=3)
    adraw_c.line([(0, 178), (800, 178)], fill=(157, 78, 221, 255), width=3)
    adraw_c.text((255, 115), "ULTIMATE CLASH CUT-IN (0.35s)!", fill=(255, 240, 120, 255))
    adraw_c.text((248, 138), "SUPERNOVA BREAKER vs VOID EXECUTION", fill=(255, 255, 255, 255))

    img_c.alpha_composite(arena_c, (790, 76))
    clash_c = arena_c.crop((0, 75, 800, 315)).resize((800, 300), Image.Resampling.LANCZOS)
    img_c.alpha_composite(clash_c, (790, 560))
    draw_c.rectangle([790, 560, 1590, 860], outline=(255, 195, 45, 255), width=2)
    draw_c.text((805, 568), "CACH TAN DUNG ANH 1 TOT NHAT: VUA LAM ANH SPLASH CHON TUONG, VUA LAM DAI CUT-IN CHIEU CUOI P/8 CUC DEP!", fill=(255, 255, 255, 255))

    path_c = SHOWCASE_DIR / "pipeline_C_ai_cutout_and_cutin_sample.png"
    img_c.save(path_c, "PNG")
    out_paths.append(path_c)

    # -----------------------------------------------------------------------
    # PIPELINE D: Blender 5.2.3 3D (.glb / .blend) -> Orthographic Cel-Shaded 2D Sprite Sheet
    # -----------------------------------------------------------------------
    img_d = Image.new("RGBA", (1600, 900), (14, 18, 28, 255))
    draw_d = ImageDraw.Draw(img_d)
    draw_d.rectangle([0, 0, 1600, 56], fill=(20, 38, 38, 255))
    draw_d.text((24, 18), "PHUONG AN D: BLENDER 5.2.3 RENDER TU MODEL 3D (.GLB / .BLEND) VOI CEL-SHADER + FREESTYLE OUTLINE -> 2D SPRITE", fill=(130, 255, 195, 255))

    goku_3d_path = PREVIEW_DIR / "quality_study" / "blender_3d" / "A_Goku_NPR.png"
    v2_orig_path = PREVIEW_DIR / "v2" / "out" / "vault_fighters_v2_action_sheet.png"
    v3_ref_goku = PREVIEW_DIR / "v3" / "out" / "reference_goku_sheet.png"
    v3_ref_saitama = PREVIEW_DIR / "v3" / "out" / "reference_saitama_sheet.png"

    if goku_3d_path.exists():
        g3d = Image.open(goku_3d_path).convert("RGBA").resize((360, 360), Image.Resampling.LANCZOS)
        img_d.alpha_composite(g3d, (24, 80))
        draw_d.rectangle([24, 80, 384, 440], outline=(130, 255, 195, 255), width=2)
        draw_d.text((34, 90), "BLENDER 5.2.3 NPR CEL-SHADER (Goku_study.glb)", fill=(130, 255, 195, 255))

    if v2_orig_path.exists():
        vo2 = Image.open(v2_orig_path).convert("RGBA").resize((380, 360), Image.Resampling.LANCZOS)
        img_d.alpha_composite(vo2, (396, 80))
        draw_d.rectangle([396, 80, 776, 440], outline=(130, 255, 195, 255), width=2)
        draw_d.text((406, 90), "BLENDER 3D POSE SHEET (4 ORIGINAL ARCHETYPES)", fill=(130, 255, 195, 255))

    if v3_ref_goku.exists() and v3_ref_saitama.exists():
        rg = Image.open(v3_ref_goku).convert("RGBA").resize((752, 195), Image.Resampling.LANCZOS)
        rs = Image.open(v3_ref_saitama).convert("RGBA").resize((752, 195), Image.Resampling.LANCZOS)
        img_d.alpha_composite(rg, (24, 460))
        img_d.alpha_composite(rs, (24, 665))
        draw_d.rectangle([24, 460, 776, 860], outline=(130, 255, 195, 255), width=2)
        draw_d.text((34, 468), "BLENDER 3D POSE SHEETS (GOKU & SAITAMA 5-POSE 3D -> 2D SPRITE SHEET)", fill=(130, 255, 195, 255))

    arena_d = _load_arena_backdrop()
    adraw_d = ImageDraw.Draw(arena_d)
    _draw_sample_hud(adraw_d, "PHUONG AN D - BLENDER 3D TO 2D SPRITE", "3D CEL-SHADED FIGHTERS", "KI / HEAT", (130, 255, 195, 255))
    if goku_3d_path.exists():
        g3d_seg = segment_dark_background(Image.open(goku_3d_path).convert("RGBA"), threshold=32.0, trim_ground_ratio=0.95)
        g3d_sp = add_pixel_outline(g3d_seg.resize((36, 42), Image.Resampling.BOX))
        arena_d.alpha_composite(g3d_sp, (235, 208))
        arena_d.alpha_composite(g3d_sp.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (505, 208))
    img_d.alpha_composite(arena_d, (790, 76))
    clash_d = arena_d.crop((180, 170, 580, 320)).resize((800, 300), Image.Resampling.NEAREST)
    img_d.alpha_composite(clash_d, (790, 560))
    draw_d.rectangle([790, 560, 1590, 860], outline=(130, 255, 195, 255), width=2)
    draw_d.text((805, 568), "NHAN XET PHUONG AN D: CAN FILE 3D .VRM/.GLB CHI TIET CAO; NEU DUNG KHOI CAU/HINH NON THI KHI THU NHO SE CUNG DO.", fill=(255, 220, 180, 255))

    path_d = SHOWCASE_DIR / "pipeline_D_blender3d_glb_to_2d_sample.png"
    img_d.save(path_d, "PNG")
    out_paths.append(path_d)

    # -----------------------------------------------------------------------
    # MASTER 2x2 COMPARISON SHEET (All 4 Pipelines Side-by-Side)
    # -----------------------------------------------------------------------
    master = Image.new("RGBA", (1600, 960), (10, 12, 20, 255))
    mdraw = ImageDraw.Draw(master)
    mdraw.rectangle([0, 0, 1600, 52], fill=(24, 32, 54, 255))
    mdraw.text((24, 16), "BANG TONG HOP SO SANH TRUC QUAN CA 4 PHUONG AN TAO HINH NHAN VAT SIEU NANG LUC (A, B, C, D) TRONG SUPERAGENT", fill=(255, 230, 90, 255))

    quads = [
        (img_a, 12, 62),
        (img_b, 804, 62),
        (img_c, 12, 512),
        (img_d, 804, 512),
    ]
    for q_img, qx, qy in quads:
        thumb = q_img.resize((784, 438), Image.Resampling.LANCZOS)
        master.alpha_composite(thumb, (qx, qy))
        mdraw.rectangle([qx, qy, qx + 784, qy + 438], outline=(90, 140, 210, 255), width=2)

    path_master = SHOWCASE_DIR / "all_4_pipelines_master_comparison.png"
    master.save(path_master, "PNG")
    out_paths.append(path_master)

    # Copy all 5 showcase images into the conversation Artifact directory for embedding
    for p in out_paths:
        shutil.copy2(p, ARTIFACT_DIR / p.name)

    return out_paths


if __name__ == "__main__":
    print("[SA-WP1] Extracting 8 Splash Portraits & 8 Ultimate Cut-In Banners...")
    extracted_data = extract_portraits_and_cutins()
    print("[SA-WP1] Building 8 Custom Hybrid Sprite Sheets (600x400) & 8 LoL-Resource JSONs...")
    build_all_hero_sheets_and_jsons()
    print("[SA-WP1] Rendering 5 Showcase Comparison Sheets (Pipelines A, B, C, D + Master Grid)...")
    paths = build_4_pipeline_showcase_images(extracted_data)
    for p in paths:
        print(f"  -> Generated: {p}")
    print("[SA-WP1] Done!")

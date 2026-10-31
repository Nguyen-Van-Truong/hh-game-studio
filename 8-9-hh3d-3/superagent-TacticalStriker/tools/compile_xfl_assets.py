#!/usr/bin/env python3
"""
Superfighters Y8 1:1 Remake - Offline XFL & AS3 Compiler (SF-M1)
Extracts and compiles:
1. Original PNG bitmaps (sheets, maps, sprites), MP3 sounds (73), and TTF fonts (3) into assets/
2. data/sf_compiled_rigs.json from Symbol 731.xml (player_johnny), Symbol 1040.xml (player_blood),
   Symbol 491.xml (player_hitarea), and PlayerAnimation.as / PlayerCharacter.as
3. data/sf_compiled_weapons.json from Weapons.as and Projectiles.as (>= 25 weapons + powerups)
4. data/sf_compiled_maps.json from Maps.as, MapPremadeItems.as, Symbol 2484.xml (levels),
   and Symbol 2499.xml (levels_front)
"""

import csv
import json
import math
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESTORED_ROOT = PROJECT_ROOT.parent / "asset-superfighter" / "reference" / "src-superfighter" / "restored-project"
XFL_DIR = RESTORED_ROOT / "xfl-export" / "Superfighters" / "00-original"
LIBRARY_DIR = XFL_DIR / "LIBRARY"
AS3_DIR = RESTORED_ROOT / "01-actionscript"
IMAGES_DIR = RESTORED_ROOT / "04-images"
SOUNDS_DIR = RESTORED_ROOT.parent / "full-ffdec-575163" / "sounds"
FONTS_DIR = RESTORED_ROOT / "06-fonts"
SYMBOLS_CSV = RESTORED_ROOT / "09-symbolClass" / "symbols.csv"

ASSETS_DIR = PROJECT_ROOT / "assets"
DATA_DIR = PROJECT_ROOT / "data"

NS = {"xfl": "http://ns.adobe.com/xfl/2008/"}


def ensure_dirs() -> None:
    for sub in [
        ASSETS_DIR / "sheets",
        ASSETS_DIR / "maps",
        ASSETS_DIR / "sprites" / "weapons",
        ASSETS_DIR / "sprites" / "props",
        ASSETS_DIR / "sprites" / "effects",
        ASSETS_DIR / "sprites" / "ui",
        ASSETS_DIR / "sounds",
        ASSETS_DIR / "fonts",
        DATA_DIR,
    ]:
        sub.mkdir(parents=True, exist_ok=True)


def parse_symbols_csv() -> dict:
    """Returns mapping of symbol_id -> class_name and class_name -> symbol_id."""
    id_to_class = {}
    class_to_id = {}
    if SYMBOLS_CSV.exists():
        with open(SYMBOLS_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if len(row) >= 2:
                    sid = row[0].strip()
                    cname = row[1].strip()
                    id_to_class[sid] = cname
                    class_to_id[cname] = sid
    return {"id_to_class": id_to_class, "class_to_id": class_to_id}


def parse_edge_bbox_twips(edges_str: str):
    """
    Parses Flash XFL <Edge edges="..."/> string in twips (1/20 px).
    Returns (x_min_px, y_min_px, width_px, height_px) or None if no coordinates found.
     Note: In XFL edges, hex numbers starting with #XXXXX.XX can appear after S/!/|/[.
    """
    cleaned = re.sub(r"#[0-9A-Fa-f]+(?:\.[0-9A-Fa-f]+)?", " ", edges_str)
    tokens = re.findall(r"[-+]?\d+(?:\.\d+)?", cleaned)
    if len(tokens) < 4:
        return None
    vals = [float(t) for t in tokens]
    xs = vals[0::2]
    ys = vals[1::2]
    if not xs or not ys:
        return None
    min_x = min(xs) / 20.0
    max_x = max(xs) / 20.0
    min_y = min(ys) / 20.0
    max_y = max(ys) / 20.0
    return (
        round(min_x, 3),
        round(min_y, 3),
        round(max_x - min_x, 3),
        round(max_y - min_y, 3),
    )


def get_matrix_vals(elem) -> dict:
    """Extracts Matrix attributes (tx, ty, a, b, c, d) from an element's <matrix><Matrix .../></matrix>."""
    res = {"tx": 0.0, "ty": 0.0, "a": 1.0, "b": 0.0, "c": 0.0, "d": 1.0}
    if elem is None:
        return res
    mat = elem.find("xfl:matrix/xfl:Matrix", NS)
    if mat is not None:
        for k in res:
            if k in mat.attrib:
                res[k] = float(mat.attrib[k])
    return res


def extract_leaf_shape(symbol_name: str):
    """
    Given a graphic symbol name like 'Symbol 592', parses its XML to extract
    bitmapPath, fill matrix (tx, ty), and edge bbox (x_min, y_min, w, h).
    """
    xml_path = LIBRARY_DIR / f"{symbol_name}.xml"
    if not xml_path.exists():
        return None
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for shape in root.findall(".//xfl:DOMShape", NS):
        bmp_fill = shape.find(".//xfl:BitmapFill", NS)
        if bmp_fill is None:
            continue
        bmp_path = bmp_fill.attrib.get("bitmapPath", "")
        mat = get_matrix_vals(bmp_fill)
        all_edges = []
        for edge in shape.findall(".//xfl:Edge", NS):
            if "edges" in edge.attrib:
                all_edges.append(edge.attrib["edges"])
        bbox = parse_edge_bbox_twips(" ".join(all_edges))
        if bbox is None:
            continue
        x_min, y_min, w, h = bbox
        # In Flash BitmapFill, the bitmap is placed at (fill_tx, fill_ty) in shape coordinates.
        # When scale a < 0 (horizontally flipped BitmapFill, e.g. Symbol 707 ROCKET_RIDE),
        # the cutout [x_min, x_min + w] samples [fill_tx - (x_min + w), fill_tx - x_min].
        if mat["a"] < 0:
            u = round(mat["tx"] - (x_min + w), 2)
        else:
            u = round(x_min - mat["tx"], 2)
        if mat["d"] < 0:
            v = round(mat["ty"] - (y_min + h), 2)
        else:
            v = round(y_min - mat["ty"], 2)
        return {
            "bitmap": bmp_path,
            "u": u,
            "v": v,
            "w": round(w, 2),
            "h": round(h, 2),
            "shape_x_min": x_min,
            "shape_y_min": y_min,
            "fill_tx": mat["tx"],
            "fill_ty": mat["ty"],
            "flip_h": mat["a"] < 0,
        }
    return None


def extract_symbol_frames(symbol_name: str, parent_tx: float = 0.0, parent_ty: float = 0.0) -> list:
    """
    Extracts animation frames from a timeline symbol (e.g. Symbol 595 for IDLE, Symbol 597 for RUN,
    or a single-frame graphic Symbol 610 for CROUCH).
    Returns list of dicts: [{frame_nr, rect: [u, v, w, h], pivot: [tx, ty], bitmap, symbol}]
    """
    xml_path = LIBRARY_DIR / f"{symbol_name}.xml"
    if not xml_path.exists():
        return []
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Check if this symbol itself is a leaf DOMShape
    direct_leaf = extract_leaf_shape(symbol_name)
    if direct_leaf is not None:
        px = round(parent_tx + direct_leaf["shape_x_min"], 2)
        py = round(parent_ty + direct_leaf["shape_y_min"], 2)
        return [
            {
                "frame_nr": 1,
                "rect": [direct_leaf["u"], direct_leaf["v"], direct_leaf["w"], direct_leaf["h"]],
                "pivot": [px, py],
                "bitmap": direct_leaf["bitmap"],
                "symbol": symbol_name,
            }
        ]

    frames_out = []
    # Find the layer that contains DOMSymbolInstance graphics or DOMShapes
    layers = root.findall(".//xfl:DOMTimeline/xfl:layers/xfl:DOMLayer", NS)
    for layer in layers:
        dom_frames = layer.findall("xfl:frames/xfl:DOMFrame", NS)
        layer_extracted = []
        for df in dom_frames:
            idx = int(df.attrib.get("index", "0"))
            dur = int(df.attrib.get("duration", "1"))
            sym_inst = df.find("xfl:elements/xfl:DOMSymbolInstance", NS)
            if sym_inst is not None:
                child_sym = sym_inst.attrib.get("libraryItemName", "")
                cmat = get_matrix_vals(sym_inst)
                leaf = extract_leaf_shape(child_sym)
                if leaf is not None:
                    is_flipped_h = bool(leaf.get("flip_h", False)) ^ (cmat["a"] < 0)
                    if cmat["a"] < 0:
                        px = round(parent_tx + cmat["tx"] - (leaf["shape_x_min"] + leaf["w"]), 2)
                    else:
                        px = round(parent_tx + cmat["tx"] + leaf["shape_x_min"], 2)
                    py = round(parent_ty + cmat["ty"] + leaf["shape_y_min"], 2)
                    for f_offset in range(dur):
                        f_entry = {
                            "frame_nr": idx + f_offset + 1,
                            "rect": [leaf["u"], leaf["v"], leaf["w"], leaf["h"]],
                            "pivot": [px, py],
                            "bitmap": leaf["bitmap"],
                            "symbol": child_sym,
                        }
                        if is_flipped_h:
                            f_entry["flip_h"] = True
                        layer_extracted.append(f_entry)
                else:
                    # Recurse one more level (e.g. rotating DOLL / HELPMC wrapper)
                    sub_frames = extract_symbol_frames(
                        child_sym,
                        parent_tx + cmat["tx"],
                        parent_ty + cmat["ty"],
                    )
                    if sub_frames:
                        for sf in sub_frames:
                            layer_extracted.append(
                                {
                                    "frame_nr": idx + sf["frame_nr"],
                                    "rect": sf["rect"],
                                    "pivot": sf["pivot"],
                                    "bitmap": sf["bitmap"],
                                    "symbol": sf["symbol"],
                                }
                            )
        if layer_extracted:
            frames_out = layer_extracted
            break

    return frames_out


def extract_weapon_arm_symbol(symbol_name: str, shoulder_tx: float, shoulder_ty: float) -> dict:
    """
    Extracts an ANIM_WPN symbol (e.g. Symbol 667 for MELEE_1H, Symbol 675 for HANDGUN, Symbol 679 for RIFLE).
    In XFL, ANIM_WPN has:
    - Marker layers: SHELL_CENTER, MUZZLE_CENTER, FIRE_CENTER, AIM_POSITION
    - Graphic layer: weapon-arm frames (frame 1 = idle aim, frames 2..N = firing/swinging frames)
    Note: The pivot of each arm frame is relative to the ANIM_WPN origin (the shoulder)!
    """
    xml_path = LIBRARY_DIR / f"{symbol_name}.xml"
    if not xml_path.exists():
        return {}
    tree = ET.parse(xml_path)
    root = tree.getroot()
    layers = root.findall(".//xfl:DOMTimeline/xfl:layers/xfl:DOMLayer", NS)

    markers_by_frame = {}  # frame_idx -> {marker_name: [tx, ty]}
    arm_frames = []

    for layer in layers:
        for df in layer.findall("xfl:frames/xfl:DOMFrame", NS):
            idx = int(df.attrib.get("index", "0"))
            dur = int(df.attrib.get("duration", "1"))
            for sym_inst in df.findall("xfl:elements/xfl:DOMSymbolInstance", NS):
                inst_name = sym_inst.attrib.get("name", "")
                child_sym = sym_inst.attrib.get("libraryItemName", "")
                cmat = get_matrix_vals(sym_inst)
                if inst_name in ("SHELL_CENTER", "MUZZLE_CENTER", "FIRE_CENTER", "AIM_POSITION"):
                    for f_off in range(dur):
                        f_i = idx + f_off
                        markers_by_frame.setdefault(f_i, {})[inst_name] = [
                            round(cmat["tx"], 2),
                            round(cmat["ty"], 2),
                        ]
                else:
                    leaf = extract_leaf_shape(child_sym)
                    if leaf is not None:
                        # Local pivot relative to ANIM_WPN origin (shoulder)
                        local_px = round(cmat["tx"] + leaf["shape_x_min"], 2)
                        local_py = round(cmat["ty"] + leaf["shape_y_min"], 2)
                        # World pivot relative to character foot origin (when arm rotation = 0)
                        char_px = round(shoulder_tx + local_px, 2)
                        char_py = round(shoulder_ty + local_py, 2)
                        for f_off in range(dur):
                            arm_frames.append(
                                {
                                    "frame_nr": idx + f_off + 1,
                                    "rect": [leaf["u"], leaf["v"], leaf["w"], leaf["h"]],
                                    "pivot": [local_px, local_py],
                                    "char_space_pivot": [char_px, char_py],
                                    "bitmap": leaf["bitmap"],
                                    "symbol": child_sym,
                                }
                            )

    # Propagate markers across frames (usually defined on frame 0 with duration=N)
    default_markers = markers_by_frame.get(0, {})
    for af in arm_frames:
        f_idx = af["frame_nr"] - 1
        m = markers_by_frame.get(f_idx, default_markers)
        af["aim_position"] = m.get("AIM_POSITION", default_markers.get("AIM_POSITION", [0.0, 0.0]))
        af["fire_center"] = m.get("FIRE_CENTER", default_markers.get("FIRE_CENTER", [0.0, 0.0]))
        af["muzzle_center"] = m.get("MUZZLE_CENTER", default_markers.get("MUZZLE_CENTER", [0.0, 0.0]))
        af["shell_center"] = m.get("SHELL_CENTER", default_markers.get("SHELL_CENTER", [0.0, 0.0]))

    return {
        "symbol": symbol_name,
        "shoulder_pivot": [round(shoulder_tx, 2), round(shoulder_ty, 2)],
        "aim_position": default_markers.get("AIM_POSITION", [0.0, 0.0]),
        "fire_center": default_markers.get("FIRE_CENTER", [0.0, 0.0]),
        "muzzle_center": default_markers.get("MUZZLE_CENTER", [0.0, 0.0]),
        "shell_center": default_markers.get("SHELL_CENTER", [0.0, 0.0]),
        "frames": arm_frames,
    }


def extract_rotating_center(symbol_name: str, root_tx: float, root_ty: float) -> list:
    """Extracts HELPMC / DOLL rotation center from rotating state symbols (FALL_F, FALL_B, DIVE, GRABBED, ROCKET_RIDE)."""
    xml_path = LIBRARY_DIR / f"{symbol_name}.xml"
    if not xml_path.exists():
        return [round(root_tx, 2), round(root_ty - 12.0, 2)]
    tree = ET.parse(xml_path)
    root = tree.getroot()
    sym_inst = root.find(".//xfl:DOMSymbolInstance", NS)
    if sym_inst is not None:
        cmat = get_matrix_vals(sym_inst)
        return [round(root_tx + cmat["tx"], 2), round(root_ty + cmat["ty"], 2)]
    return [round(root_tx, 2), round(root_ty - 12.0, 2)]


def build_frame_sequences() -> dict:
    """
    Exact frame sequences and durations (in 60Hz ticks) from PlayerAnimation.as UpdateFrame().
    Format: {state_name: {"loop": bool, "next_state": str|None, "sequence": [[frame_nr, duration_ticks], ...]}}
    """
    return {
        "IDLE": {"loop": True, "next_state": None, "sequence": [[1, 30], [2, 30]]},
        "JUMP": {"loop": False, "next_state": None, "sequence": [[1, 10], [2, 999999999]]},
        "RUN": {
            "loop": True,
            "next_state": None,
            "sequence": [[1, 4], [2, 4], [3, 4], [4, 4], [5, 4], [6, 4], [7, 4], [8, 4]],
        },
        "FALL_F": {"loop": False, "next_state": None, "sequence": [[1, 30], [2, 999999999]]},
        "FALL_B": {"loop": False, "next_state": None, "sequence": [[1, 30], [2, 999999999]]},
        "KNOCKDOWN": {"loop": False, "next_state": "KNEEL", "sequence": [[1, 5], [2, 11], [3, 7]]},
        "KNEEL": {"loop": True, "next_state": None, "sequence": [[1, 1]]},
        "COVER": {"loop": True, "next_state": None, "sequence": [[1, 1]]},
        "SPRINT": {
            "loop": True,
            "next_state": None,
            "sequence": [[1, 3], [2, 3], [3, 3], [4, 3], [5, 3], [6, 3], [7, 3], [8, 3]],
        },
        "ROLL": {
            "loop": False,
            "next_state": "KNEEL",
            "sequence": [[1, 3], [2, 3], [3, 3], [4, 3], [5, 3], [6, 3]],
        },
        "KICK": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 3], [3, 6], [4, 4]]},
        "DIVE": {"loop": False, "next_state": None, "sequence": [[1, 999999999]]},
        "PUNCH_01": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 2], [3, 5], [4, 3]]},
        "PUNCH_02": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 2], [3, 5], [4, 3]]},
        "PUNCH_03": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 2], [3, 5], [4, 3]]},
        "MACHETE_01": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 5], [3, 2], [4, 2], [5, 8], [6, 6]]},
        "MACHETE_02": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 5], [3, 2], [4, 2], [5, 8], [6, 6]]},
        "MACHETE_03": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 5], [3, 2], [4, 2], [5, 8], [6, 6]]},
        "AXE_01": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 6], [3, 2], [4, 2], [5, 10], [6, 6]]},
        "AXE_02": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 6], [3, 2], [4, 2], [5, 10], [6, 6]]},
        "AXE_03": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 6], [3, 2], [4, 2], [5, 10], [6, 6]]},
        "SWORD_01": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 5], [3, 2], [4, 2], [5, 8], [6, 6]]},
        "SWORD_02": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 5], [3, 2], [4, 2], [5, 8], [6, 6]]},
        "SWORD_03": {"loop": False, "next_state": "IDLE", "sequence": [[1, 3], [2, 5], [3, 2], [4, 2], [5, 8], [6, 6]]},
        "START_PISTOL": {"loop": False, "next_state": "AIM_PISTOL", "sequence": [[1, 3], [2, 3], [3, 3]]},
        "AIM_PISTOL": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "START_MAGNUM": {"loop": False, "next_state": "AIM_MAGNUM", "sequence": [[1, 3], [2, 3], [3, 3]]},
        "AIM_MAGNUM": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "START_RIFLE": {"loop": False, "next_state": "AIM_RIFLE", "sequence": [[1, 3], [2, 3], [3, 3]]},
        "AIM_RIFLE": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "START_UZI": {"loop": False, "next_state": "AIM_UZI", "sequence": [[1, 3], [2, 3], [3, 3]]},
        "AIM_UZI": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "START_SHOTGUN": {"loop": False, "next_state": "AIM_SHOTGUN", "sequence": [[1, 3], [2, 3], [3, 3]]},
        "AIM_SHOTGUN": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "START_SNIPER": {"loop": False, "next_state": "AIM_SNIPER", "sequence": [[1, 3], [2, 3], [3, 3]]},
        "AIM_SNIPER": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "START_BAZOOKA": {"loop": False, "next_state": "AIM_BAZOOKA", "sequence": [[1, 3], [2, 3], [3, 3]]},
        "AIM_BAZOOKA": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "START_FLAMETHROWER": {"loop": False, "next_state": "AIM_FLAMETHROWER", "sequence": [[1, 3], [2, 3], [3, 3]]},
        "AIM_FLAMETHROWER": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "AIM_GRENADE": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "AIM_MOLOTOV": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        "THROW": {"loop": False, "next_state": "IDLE", "sequence": [[1, 5], [2, 10], [3, 5]]},
        "ROCKET_RIDE_R": {"loop": False, "next_state": None, "sequence": [[1, 999999999]]},
        "ROCKET_RIDE_EMPTY": {"loop": False, "next_state": None, "sequence": [[1, 999999999]]},
        "ROCKET_RIDE_L": {"loop": False, "next_state": None, "sequence": [[1, 999999999]]},
        "CLIMB": {"loop": True, "next_state": None, "sequence": [[1, 6], [2, 6], [3, 6], [4, 6]]},
        "SLIDE": {"loop": False, "next_state": None, "sequence": [[1, 999999999]]},
        "AIM_TURN": {"loop": False, "next_state": None, "sequence": [[1, 3]]},
        "GRABBED": {"loop": False, "next_state": None, "sequence": [[1, 999999999]]},
        "STUN_01": {"loop": False, "next_state": "IDLE", "sequence": [[1, 6], [2, 6]]},
        "STUN_02": {"loop": False, "next_state": "IDLE", "sequence": [[1, 6], [2, 6]]},
        "JUMPKICK": {"loop": False, "next_state": "JUMP", "sequence": [[1, 3], [2, 4], [3, 7], [4, 3]]},
        "STAGGER": {"loop": True, "next_state": None, "sequence": [[1, 6], [2, 6], [3, 6], [4, 6]]},
        "DEATH_KNEEL": {"loop": False, "next_state": None, "sequence": [[1, 3], [2, 3], [3, 3], [4, 999999999]]},
        "EMPTY": {"loop": False, "next_state": None, "sequence": [[1, 1]]},
    }


def compile_rigs() -> dict:
    """Compiles Symbol 731.xml (player_johnny), Symbol 1040.xml (player_blood), Symbol 491.xml (player_hitarea)."""
    johnny_xml = LIBRARY_DIR / "Symbol 731.xml"
    tree = ET.parse(johnny_xml)
    root = tree.getroot()
    layers = root.findall(".//xfl:DOMTimeline/xfl:layers/xfl:DOMLayer", NS)

    labels_by_idx = {}
    layer2_by_idx = {}
    layer3_by_idx = {}

    for layer in layers:
        lname = layer.attrib.get("name", "")
        for df in layer.findall("xfl:frames/xfl:DOMFrame", NS):
            idx = int(df.attrib.get("index", "0"))
            dur = int(df.attrib.get("duration", "1"))
            if lname == "Labels Layer":
                label_name = df.attrib.get("name", "")
                if label_name:
                    labels_by_idx[idx] = label_name
            elif lname == "Layer 2":
                sym_inst = df.find("xfl:elements/xfl:DOMSymbolInstance", NS)
                for off in range(dur):
                    layer2_by_idx[idx + off] = sym_inst
            elif lname == "Layer 3":
                sym_inst = df.find("xfl:elements/xfl:DOMSymbolInstance", NS)
                for off in range(dur):
                    layer3_by_idx[idx + off] = sym_inst

    # Frame 44 is unnamed in Symbol 731.xml (between 43: ROCKET_RIDE_R and 45: ROCKET_RIDE_L)
    if 44 not in labels_by_idx:
        labels_by_idx[44] = "ROCKET_RIDE_EMPTY"

    frame_sequences = build_frame_sequences()
    states = {}

    for idx in sorted(labels_by_idx.keys()):
        state_name = labels_by_idx[idx]
        l2 = layer2_by_idx.get(idx)
        l3 = layer3_by_idx.get(idx)
        seq_info = frame_sequences.get(
            state_name,
            {"loop": False, "next_state": None, "sequence": [[1, 1]]},
        )

        # Case A: Split-rig state (Frames 24..41: START_* and AIM_*) where Layer 3 has armless torso
        if l3 is not None and l2 is not None:
            l3_sym = l3.attrib.get("libraryItemName", "")
            l3_mat = get_matrix_vals(l3)
            torso_frames = extract_symbol_frames(l3_sym, l3_mat["tx"], l3_mat["ty"])

            l2_sym = l2.attrib.get("libraryItemName", "")
            l2_inst_name = l2.attrib.get("name", "")
            l2_mat = get_matrix_vals(l2)

            if state_name.startswith("AIM_"):
                wpn_arm = extract_weapon_arm_symbol(l2_sym, l2_mat["tx"], l2_mat["ty"])
                states[state_name] = {
                    "frame_index": idx,
                    "type": "split_rig_aim",
                    "loop": seq_info["loop"],
                    "next_state": seq_info["next_state"],
                    "sequence": seq_info["sequence"],
                    "shoulder_pivot": [round(l2_mat["tx"], 2), round(l2_mat["ty"], 2)],
                    "torso": {
                        "symbol": l3_sym,
                        "frames": torso_frames,
                    },
                    "weapon_arm": wpn_arm,
                    "frames": wpn_arm.get("frames", []),
                }
            else:
                start_arm_frames = extract_symbol_frames(l2_sym, l2_mat["tx"], l2_mat["ty"])
                states[state_name] = {
                    "frame_index": idx,
                    "type": "split_rig_start",
                    "loop": seq_info["loop"],
                    "next_state": seq_info["next_state"],
                    "sequence": seq_info["sequence"],
                    "shoulder_pivot": [round(l2_mat["tx"], 2), round(l2_mat["ty"], 2)],
                    "torso": {
                        "symbol": l3_sym,
                        "frames": torso_frames,
                    },
                    "start_arm": {
                        "symbol": l2_sym,
                        "instance_name": l2_inst_name,
                        "frames": start_arm_frames,
                    },
                    "frames": start_arm_frames,
                }
        elif l3 is not None:
            l3_sym = l3.attrib.get("libraryItemName", "")
            l3_inst_name = l3.attrib.get("name", "")
            l3_mat = get_matrix_vals(l3)
            l3_scale_x = round(l3_mat["a"], 3)
            frames = extract_symbol_frames(l3_sym, l3_mat["tx"], l3_mat["ty"])
            keyframes = []
            for f in frames:
                if not keyframes or keyframes[-1]["rect"] != f["rect"] or keyframes[-1]["pivot"] != f["pivot"]:
                    kf = dict(f)
                    kf["keyframe_nr"] = len(keyframes) + 1
                    kf["duration"] = 1
                    keyframes.append(kf)
                else:
                    keyframes[-1]["duration"] += 1
            expanded_seq = []
            for kf in keyframes:
                kf_nr = int(kf["keyframe_nr"])
                kf_dur = max(1, int(kf.get("duration", 1)))
                for _ in range(kf_dur):
                    expanded_seq.append([kf_nr, 2.5])
            if not seq_info["loop"] and seq_info["next_state"] is None and expanded_seq:
                expanded_seq[-1][1] = 999999999
            final_seq = expanded_seq if expanded_seq else seq_info["sequence"]
            if state_name in frame_sequences and expanded_seq:
                frame_sequences[state_name]["sequence"] = expanded_seq
            is_rotating = state_name in (
                "FALL_F",
                "FALL_B",
                "DIVE",
                "GRABBED",
                "ROCKET_RIDE_R",
                "ROCKET_RIDE_L",
            )
            rot_center = (
                extract_rotating_center(l3_sym, l3_mat["tx"], l3_mat["ty"])
                if is_rotating
                else [0.0, -12.0]
            )
            states[state_name] = {
                "frame_index": idx,
                "type": "rotating_body" if is_rotating else "full_body",
                "instance_name": l3_inst_name,
                "symbol": l3_sym,
                "scale_x": l3_scale_x,
                "rotation_center": rot_center,
                "loop": seq_info["loop"],
                "next_state": seq_info["next_state"],
                "sequence": final_seq,
                "keyframes": keyframes,
                "frames": frames,
            }
        else:
            # Empty frame (e.g. index 44 ROCKET_RIDE_EMPTY)
            states[state_name] = {
                "frame_index": idx,
                "type": "empty",
                "loop": False,
                "next_state": None,
                "sequence": [[1, 1]],
                "frames": [],
            }

    # Add semantic state aliases so both exact Symbol 731 labels and general category labels resolve
    state_aliases = {
        "CROUCH": "KNEEL",
        "DEAD": "DEATH_KNEEL",
        "JUMP_ATT": "JUMPKICK",
        "LAND_HEAVY": "KNOCKDOWN",
        "START_HANDGUN": "START_PISTOL",
        "AIM_HANDGUN": "AIM_PISTOL",
        "START_MELEE_1H": "MACHETE_01",
        "AIM_MELEE_1H": "MACHETE_01",
        "START_MELEE_2H": "SWORD_01",
        "AIM_MELEE_2H": "SWORD_01",
        "START_THROW": "AIM_GRENADE",
        "AIM_THROW": "AIM_GRENADE",
        "START_SELF": "AIM_GRENADE",
        "AIM_SELF": "AIM_GRENADE",
        "AIM_FISTS": "PUNCH_01",
        "AIM_CHAINSAW": "AIM_FLAMETHROWER",
    }
    for alias_key, src_key in state_aliases.items():
        if alias_key not in states and src_key in states:
            states[alias_key] = json.loads(json.dumps(states[src_key]))
            states[alias_key]["alias_of"] = src_key

    # Hitarea boxes from Symbol 491.xml (player_hitarea) and PlayersKeeper.as
    hitarea_boxes = {
        "standing": {"x": -6.5, "y": -24.0, "w": 13.0, "h": 24.0},
        "crouch": {"x": -6.5, "y": -13.0, "w": 13.0, "h": 13.0},
        "roll": {"x": -6.5, "y": -13.0, "w": 13.0, "h": 13.0},
        "dive": {"x": -10.0, "y": -14.0, "w": 20.0, "h": 7.0},
        "dead": {"x": -10.0, "y": -4.0, "w": 20.0, "h": 4.0},
    }

    # Character roster mapping (all 10 Y8 characters + AS3 internal class aliases)
    characters = {
        "johnny": {
            "id": "johnny",
            "display_name": "Johnny",
            "symbol": "Symbol 731",
            "linkage_class": "player_johnny",
            "sheet_bitmap": "Bitmap 591.png",
            "sheet_path": "res://assets/sheets/Bitmap 591.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "boris": {
            "id": "boris",
            "display_name": "Boris",
            "symbol": "Symbol 881",
            "linkage_class": "player_boris",
            "sheet_bitmap": "Bitmap 312.png",
            "sheet_path": "res://assets/sheets/Bitmap 312.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "agent": {
            "id": "agent",
            "display_name": "Agent",
            "symbol": "Symbol 1245",
            "linkage_class": "player_agent",
            "sheet_bitmap": "Bitmap 1105.png",
            "sheet_path": "res://assets/sheets/Bitmap 1105.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "hideki": {
            "id": "hideki",
            "display_name": "Hideki",
            "symbol": "Symbol 731",
            "linkage_class": "player_hideki",
            "sheet_bitmap": "Bitmap 755.png",
            "sheet_path": "res://assets/sheets/Bitmap 755.png",
            "hp_mult": 1.0,
            "speed_mult": 1.05,
        },
        "blaire": {
            "id": "blaire",
            "display_name": "Blaire",
            "symbol": "Symbol 1245",
            "linkage_class": "player_blaire",
            "sheet_bitmap": "Bitmap 1044.png",
            "sheet_path": "res://assets/sheets/Bitmap 1044.png",
            "hp_mult": 1.0,
            "speed_mult": 1.05,
        },
        "savage": {
            "id": "savage",
            "display_name": "Savage",
            "symbol": "Symbol 1455",
            "linkage_class": "player_billy",
            "sheet_bitmap": "Bitmap 1315.png",
            "sheet_path": "res://assets/sheets/Bitmap 1315.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "cruger": {
            "id": "cruger",
            "display_name": "Cruger",
            "symbol": "Symbol 1596",
            "linkage_class": "player_scott",
            "sheet_bitmap": "Bitmap 1456.png",
            "sheet_path": "res://assets/sheets/Bitmap 1456.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "ivan": {
            "id": "ivan",
            "display_name": "Ivan",
            "symbol": "Symbol 1769",
            "linkage_class": "player_funnyman",
            "sheet_bitmap": "Bitmap 1629.png",
            "sheet_path": "res://assets/sheets/Bitmap 1629.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "brody": {
            "id": "brody",
            "display_name": "Brody",
            "symbol": "Symbol 1910",
            "linkage_class": "player_mac",
            "sheet_bitmap": "Bitmap 1770.png",
            "sheet_path": "res://assets/sheets/Bitmap 1770.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "mac": {
            "id": "mac",
            "display_name": "Mac",
            "symbol": "Symbol 2051",
            "linkage_class": "player_jeff",
            "sheet_bitmap": "Bitmap 1911.png",
            "sheet_path": "res://assets/sheets/Bitmap 1911.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        # Direct AS3 aliases from PlayerCharacter.as
        "billy": {
            "id": "billy",
            "display_name": "Billy",
            "symbol": "Symbol 1455",
            "linkage_class": "player_billy",
            "sheet_bitmap": "Bitmap 1315.png",
            "sheet_path": "res://assets/sheets/Bitmap 1315.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "scott": {
            "id": "scott",
            "display_name": "Scott",
            "symbol": "Symbol 1596",
            "linkage_class": "player_scott",
            "sheet_bitmap": "Bitmap 1456.png",
            "sheet_path": "res://assets/sheets/Bitmap 1456.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "funnyman": {
            "id": "funnyman",
            "display_name": "Funnyman",
            "symbol": "Symbol 1769",
            "linkage_class": "player_funnyman",
            "sheet_bitmap": "Bitmap 1629.png",
            "sheet_path": "res://assets/sheets/Bitmap 1629.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
        "jeff": {
            "id": "jeff",
            "display_name": "Jeff",
            "symbol": "Symbol 2051",
            "linkage_class": "player_jeff",
            "sheet_bitmap": "Bitmap 1911.png",
            "sheet_path": "res://assets/sheets/Bitmap 1911.png",
            "hp_mult": 1.0,
            "speed_mult": 1.0,
        },
    }

    blood_rig = {
        "symbol": "Symbol 1040",
        "linkage_class": "player_blood",
        "sheet_bitmap": "Bitmap 900.png",
        "alias_bitmap": "Bitmap 729.png",
        "sheet_path": "res://assets/sheets/Bitmap 900.png",
        "alias_sheet_path": "res://assets/sheets/Bitmap 729.png",
        "same_topology_as": "Symbol 731",
    }

    return {
        "schema_version": "1.0.0",
        "source_symbol": "Symbol 731.xml",
        "sheet_size": [600, 400],
        "state_count": len(states),
        "states": states,
        "frame_sequences": frame_sequences,
        "hitarea_boxes": hitarea_boxes,
        "characters": characters,
        "blood_rig": blood_rig,
    }


def compile_weapons() -> dict:
    """
    Compiles data/sf_compiled_weapons.json directly from Weapons.as and Projectiles.as,
    including all 18 AS3 classes in Weapons.as + extended roster weapons (>= 25 weapons total).
    """
    weapons = {
        # --- SLOT 1: MELEE WEAPONS (8) ---
        "FISTS": {
            "id": "FISTS",
            "weapon_id": 0,
            "display_name": "Fists",
            "slot": 1,
            "category": "melee",
            "start_state": "AIM_FISTS",
            "aim_state": "AIM_FISTS",
            "ammo": -1,
            "max_ammo": -1,
            "damage": 7.0,
            "jump_attack_damage": 13.0,
            "hit_force": 15.0,
            "range": 16.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 12,
            "laser": False,
            "pickup_texture": "",
            "dropped_texture": "",
            "sfx_swing": "SfxFistSwing1",
            "sfx_hit": "Punch1",
            "sfx_block": "PunchBlock",
            "fire_sequence": [
                {"frame_nr": 1, "time": 3, "fire": False},
                {"frame_nr": 2, "time": 2, "fire": False, "sound": "swing"},
                {"frame_nr": 3, "time": 5, "fire": True, "end": False},
                {"frame_nr": 4, "time": 3, "fire": False, "end": True},
            ],
        },
        "KNIFE": {
            "id": "KNIFE",
            "weapon_id": 19,
            "display_name": "Knife",
            "slot": 1,
            "category": "melee",
            "start_state": "START_MELEE_1H",
            "aim_state": "AIM_MELEE_1H",
            "ammo": 25,
            "max_ammo": 25,
            "damage": 14.0,
            "hit_force": 16.0,
            "range": 18.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 10,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_machete.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_machete_d.png",
            "sfx_swing": "SwingSword1",
            "sfx_hit": "SwordHit1",
            "sfx_block": "SwordBlock1",
            "fire_sequence": [
                {"frame_nr": 8, "time": 3, "fire": False},
                {"frame_nr": 9, "time": 3, "fire": False},
                {"frame_nr": 10, "time": 2, "fire": False, "sound": "swing_sword"},
                {"frame_nr": 11, "time": 2, "fire": True},
                {"frame_nr": 12, "time": 5, "fire": False},
                {"frame_nr": 13, "time": 5, "fire": False, "end": True},
            ],
        },
        "BATON": {
            "id": "BATON",
            "weapon_id": 20,
            "display_name": "Baton",
            "slot": 1,
            "category": "melee",
            "start_state": "START_MELEE_1H",
            "aim_state": "AIM_MELEE_1H",
            "ammo": 25,
            "max_ammo": 25,
            "damage": 15.0,
            "hit_force": 20.0,
            "range": 19.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 12,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_machete.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_machete_d.png",
            "sfx_swing": "SwingMachete1",
            "sfx_hit": "Punch2",
            "sfx_block": "SwordBlock1",
            "fire_sequence": [
                {"frame_nr": 8, "time": 3, "fire": False},
                {"frame_nr": 9, "time": 4, "fire": False},
                {"frame_nr": 10, "time": 2, "fire": False, "sound": "swing_machete"},
                {"frame_nr": 11, "time": 2, "fire": True},
                {"frame_nr": 12, "time": 6, "fire": False},
                {"frame_nr": 13, "time": 6, "fire": False, "end": True},
            ],
        },
        "MACHETE": {
            "id": "MACHETE",
            "weapon_id": 4,
            "display_name": "Machete",
            "slot": 1,
            "category": "melee",
            "start_state": "START_MELEE_1H",
            "aim_state": "AIM_MELEE_1H",
            "ammo": 20,
            "max_ammo": 20,
            "damage": 18.0,
            "hit_force": 20.0,
            "range": 20.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 14,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_machete.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_machete_d.png",
            "sfx_swing": "SwingMachete1",
            "sfx_hit": "SwordHit1",
            "sfx_block": "SwordBlock1",
            "fire_sequence": [
                {"frame_nr": 8, "time": 3, "fire": False},
                {"frame_nr": 9, "time": 5, "fire": False},
                {"frame_nr": 10, "time": 2, "fire": False, "sound": "swing_machete"},
                {"frame_nr": 11, "time": 2, "fire": True},
                {"frame_nr": 12, "time": 8, "fire": False},
                {"frame_nr": 13, "time": 6, "fire": False},
                {"frame_nr": 8, "time": 4, "fire": False, "end": True},
            ],
        },
        "AXE": {
            "id": "AXE",
            "weapon_id": 2,
            "display_name": "Axe",
            "slot": 1,
            "category": "melee",
            "start_state": "START_MELEE_1H",
            "aim_state": "AIM_MELEE_1H",
            "ammo": 15,
            "max_ammo": 15,
            "damage": 24.0,
            "hit_force": 26.0,
            "range": 21.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 18,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_axe.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_axe_d.png",
            "sfx_swing": "SwingAxe1",
            "sfx_hit": "SwordHit2",
            "sfx_block": "SwordBlock2",
            "fire_sequence": [
                {"frame_nr": 2, "time": 3, "fire": False},
                {"frame_nr": 3, "time": 6, "fire": False},
                {"frame_nr": 4, "time": 2, "fire": False, "sound": "swing_axe"},
                {"frame_nr": 5, "time": 2, "fire": True},
                {"frame_nr": 6, "time": 10, "fire": False},
                {"frame_nr": 7, "time": 6, "fire": False},
                {"frame_nr": 2, "time": 6, "fire": False, "end": True},
            ],
        },
        "SWORD": {
            "id": "SWORD",
            "weapon_id": 3,
            "display_name": "Katana",
            "slot": 1,
            "category": "melee",
            "start_state": "START_MELEE_2H",
            "aim_state": "AIM_MELEE_2H",
            "ammo": 15,
            "max_ammo": 15,
            "damage": 28.0,
            "hit_force": 24.0,
            "range": 25.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 16,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_sword.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_sword_d.png",
            "sfx_swing": "SwingSword1",
            "sfx_hit": "SwordHit3",
            "sfx_block": "SwordBlock3",
            "fire_sequence": [
                {"frame_nr": 2, "time": 3, "fire": False},
                {"frame_nr": 3, "time": 5, "fire": False},
                {"frame_nr": 4, "time": 2, "fire": False, "sound": "swing_sword"},
                {"frame_nr": 5, "time": 2, "fire": True},
                {"frame_nr": 6, "time": 8, "fire": False},
                {"frame_nr": 7, "time": 6, "fire": False},
                {"frame_nr": 2, "time": 4, "fire": False, "end": True},
            ],
        },
        "BASEBALL_BAT": {
            "id": "BASEBALL_BAT",
            "weapon_id": 21,
            "display_name": "Baseball Bat",
            "slot": 1,
            "category": "melee",
            "start_state": "START_MELEE_2H",
            "aim_state": "AIM_MELEE_2H",
            "ammo": 20,
            "max_ammo": 20,
            "damage": 22.0,
            "hit_force": 30.0,
            "range": 24.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 16,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_sword.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_sword_d.png",
            "sfx_swing": "SwingAxe1",
            "sfx_hit": "Punch3",
            "sfx_block": "SwordBlock2",
            "fire_sequence": [
                {"frame_nr": 2, "time": 3, "fire": False},
                {"frame_nr": 3, "time": 5, "fire": False},
                {"frame_nr": 4, "time": 2, "fire": False, "sound": "swing_axe"},
                {"frame_nr": 5, "time": 2, "fire": True},
                {"frame_nr": 6, "time": 8, "fire": False},
                {"frame_nr": 7, "time": 6, "fire": False, "end": True},
            ],
        },
        "CHAINSAW": {
            "id": "CHAINSAW",
            "weapon_id": 22,
            "display_name": "Chainsaw",
            "slot": 1,
            "category": "melee",
            "start_state": "AIM_CHAINSAW",
            "aim_state": "AIM_CHAINSAW",
            "ammo": 100,
            "max_ammo": 100,
            "damage": 4.5,
            "hit_force": 8.0,
            "range": 22.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 3,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_flamethrower.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_flamethrower_d.png",
            "sfx_swing": "Flamethrower",
            "sfx_hit": "SwordHit1",
            "sfx_block": "SwordBlock1",
            "fire_sequence": [
                {"frame_nr": 1, "time": 2, "fire": True, "sound": "chainsaw"},
                {"frame_nr": 2, "time": 2, "fire": True, "end": True},
            ],
        },
        # --- SLOT 2: SIDEARMS / HANDGUNS (5) ---
        "PISTOL": {
            "id": "PISTOL",
            "weapon_id": 5,
            "display_name": "Pistol",
            "slot": 2,
            "category": "ranged",
            "start_state": "START_HANDGUN",
            "aim_state": "AIM_HANDGUN",
            "ammo": 12,
            "max_ammo": 12,
            "damage": 12.0,
            "hit_force": 15.0,
            "spread": 0.06,
            "shots": 1,
            "fire_speed": 26.0,
            "reload_time": 12,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_pistol.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_pistol_d.png",
            "sfx_fire": "Pistol1",
            "sfx_reload": "LoadClip1",
            "sfx_empty": "DryFire1",
            "fire_sequence": [
                {"frame_nr": 2, "time": 2, "fire": True, "shell": True, "muzzle": True, "sound": "pistol", "bullets": 1},
                {"frame_nr": 3, "time": 3, "fire": False},
                {"frame_nr": 4, "time": 7, "fire": False, "end": True},
            ],
        },
        "SILENCED_PISTOL": {
            "id": "SILENCED_PISTOL",
            "weapon_id": 23,
            "display_name": "Silenced Pistol",
            "slot": 2,
            "category": "ranged",
            "start_state": "START_HANDGUN",
            "aim_state": "AIM_HANDGUN",
            "ammo": 12,
            "max_ammo": 12,
            "damage": 13.0,
            "hit_force": 14.0,
            "spread": 0.04,
            "shots": 1,
            "fire_speed": 28.0,
            "reload_time": 10,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_pistol.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_pistol_d.png",
            "sfx_fire": "Pistol2",
            "sfx_reload": "LoadClip1",
            "sfx_empty": "DryFire1",
            "fire_sequence": [
                {"frame_nr": 2, "time": 2, "fire": True, "shell": True, "muzzle": False, "sound": "pistol", "bullets": 1},
                {"frame_nr": 3, "time": 2, "fire": False},
                {"frame_nr": 4, "time": 6, "fire": False, "end": True},
            ],
        },
        "MAGNUM": {
            "id": "MAGNUM",
            "weapon_id": 6,
            "display_name": "Magnum",
            "slot": 2,
            "category": "ranged",
            "start_state": "START_HANDGUN",
            "aim_state": "AIM_HANDGUN",
            "ammo": 6,
            "max_ammo": 6,
            "damage": 35.0,
            "hit_force": 40.0,
            "spread": 0.03,
            "shots": 1,
            "fire_speed": 33.0,
            "reload_time": 23,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_magnum.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_magnum_d.png",
            "sfx_fire": "Magnum1",
            "sfx_reload": "LoadClip2",
            "sfx_empty": "DryFire1",
            "fire_sequence": [
                {"frame_nr": 5, "time": 3, "fire": True, "shell": True, "muzzle": True, "sound": "magnum", "bullets": 1},
                {"frame_nr": 6, "time": 12, "fire": False},
                {"frame_nr": 7, "time": 8, "fire": False, "end": True},
            ],
        },
        "UZI": {
            "id": "UZI",
            "weapon_id": 7,
            "display_name": "Uzi",
            "slot": 2,
            "category": "ranged",
            "start_state": "START_HANDGUN",
            "aim_state": "AIM_HANDGUN",
            "ammo": 25,
            "max_ammo": 25,
            "damage": 9.0,
            "hit_force": 12.0,
            "spread": 0.25,
            "shots": 1,
            "fire_speed": 26.0,
            "reload_time": 4,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_uzi.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_uzi_d.png",
            "sfx_fire": "Uzi1",
            "sfx_reload": "LoadClip1",
            "sfx_empty": "DryFire1",
            "fire_sequence": [
                {"frame_nr": 8, "time": 2, "fire": True, "shell": True, "muzzle": True, "sound": "uzi", "bullets": 1},
                {"frame_nr": 9, "time": 2, "fire": False, "end": True},
            ],
        },
        "FLARE_GUN": {
            "id": "FLARE_GUN",
            "weapon_id": 24,
            "display_name": "Flare Gun",
            "slot": 2,
            "category": "ranged",
            "projectile_type": "FLARE",
            "start_state": "START_HANDGUN",
            "aim_state": "AIM_HANDGUN",
            "ammo": 4,
            "max_ammo": 4,
            "damage": 15.0,
            "hit_force": 20.0,
            "spread": 0.04,
            "shots": 1,
            "fire_speed": 22.0,
            "reload_time": 24,
            "laser": False,
            "ignites_target": True,
            "pickup_texture": "res://assets/sprites/weapons/wpn_pistol.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_pistol_d.png",
            "sfx_fire": "Shotgun1",
            "sfx_reload": "LoadShell",
            "sfx_empty": "DryFire1",
            "fire_sequence": [
                {"frame_nr": 5, "time": 3, "fire": True, "shell": True, "muzzle": True, "sound": "shotgun", "bullets": 1},
                {"frame_nr": 6, "time": 12, "fire": False},
                {"frame_nr": 7, "time": 9, "fire": False, "end": True},
            ],
        },
        # --- SLOT 3: PRIMARY / HEAVY WEAPONS (9) ---
        "SHOTGUN": {
            "id": "SHOTGUN",
            "weapon_id": 9,
            "display_name": "Shotgun",
            "slot": 3,
            "category": "ranged",
            "start_state": "START_SHOTGUN",
            "aim_state": "AIM_SHOTGUN",
            "ammo": 6,
            "max_ammo": 6,
            "damage": 8.0,
            "hit_force": 15.0,
            "spread": 0.16,
            "shots": 6,
            "fire_speed": 26.0,
            "reload_time": 33,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_shotgun.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_shotgun_d.png",
            "sfx_fire": "Shotgun1",
            "sfx_reload": "ShotgunPump",
            "sfx_empty": "DryFire2",
            "fire_sequence": [
                {"frame_nr": 2, "time": 3, "fire": True, "shell": False, "muzzle": True, "sound": "shotgun", "bullets": 6},
                {"frame_nr": 3, "time": 12, "fire": False},
                {"frame_nr": 4, "time": 6, "fire": False, "sound": "shotgun_pump"},
                {"frame_nr": 5, "time": 6, "fire": False, "shell": True},
                {"frame_nr": 4, "time": 6, "fire": False, "end": True},
            ],
        },
        "SAWED_OFF": {
            "id": "SAWED_OFF",
            "weapon_id": 25,
            "display_name": "Sawed-Off Shotgun",
            "slot": 3,
            "category": "ranged",
            "start_state": "START_SHOTGUN",
            "aim_state": "AIM_SHOTGUN",
            "ammo": 4,
            "max_ammo": 4,
            "damage": 8.5,
            "hit_force": 18.0,
            "spread": 0.28,
            "shots": 8,
            "fire_speed": 25.0,
            "reload_time": 28,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_shotgun.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_shotgun_d.png",
            "sfx_fire": "Shotgun2",
            "sfx_reload": "LoadShell",
            "sfx_empty": "DryFire2",
            "fire_sequence": [
                {"frame_nr": 2, "time": 3, "fire": True, "shell": True, "muzzle": True, "sound": "shotgun", "bullets": 8},
                {"frame_nr": 3, "time": 12, "fire": False},
                {"frame_nr": 4, "time": 13, "fire": False, "end": True},
            ],
        },
        "RIFLE": {
            "id": "RIFLE",
            "weapon_id": 8,
            "display_name": "Assault Rifle",
            "slot": 3,
            "category": "ranged",
            "start_state": "START_RIFLE",
            "aim_state": "AIM_RIFLE",
            "ammo": 30,
            "max_ammo": 30,
            "damage": 13.0,
            "hit_force": 20.0,
            "spread": 0.10,
            "shots": 1,
            "fire_speed": 30.0,
            "reload_time": 6,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_rifle.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_rifle_d.png",
            "sfx_fire": "Ak47_1",
            "sfx_reload": "RifleCock",
            "sfx_empty": "DryFire2",
            "fire_sequence": [
                {"frame_nr": 2, "time": 3, "fire": True, "shell": True, "muzzle": True, "sound": "ak47", "bullets": 1},
                {"frame_nr": 3, "time": 3, "fire": False, "end": True},
            ],
        },
        "TOMMY_GUN": {
            "id": "TOMMY_GUN",
            "weapon_id": 26,
            "display_name": "Tommy Gun",
            "slot": 3,
            "category": "ranged",
            "start_state": "START_RIFLE",
            "aim_state": "AIM_RIFLE",
            "ammo": 40,
            "max_ammo": 40,
            "damage": 11.0,
            "hit_force": 16.0,
            "spread": 0.15,
            "shots": 1,
            "fire_speed": 28.0,
            "reload_time": 5,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_rifle.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_rifle_d.png",
            "sfx_fire": "Uzi2",
            "sfx_reload": "RifleCock",
            "sfx_empty": "DryFire2",
            "fire_sequence": [
                {"frame_nr": 2, "time": 2, "fire": True, "shell": True, "muzzle": True, "sound": "uzi", "bullets": 1},
                {"frame_nr": 3, "time": 3, "fire": False, "end": True},
            ],
        },
        "SNIPER": {
            "id": "SNIPER",
            "weapon_id": 10,
            "display_name": "Sniper Rifle",
            "slot": 3,
            "category": "ranged",
            "start_state": "START_RIFLE",
            "aim_state": "AIM_RIFLE",
            "ammo": 5,
            "max_ammo": 5,
            "damage": 65.0,
            "hit_force": 60.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 40.0,
            "reload_time": 55,
            "laser": True,
            "pickup_texture": "res://assets/sprites/weapons/wpn_sniper.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_sniper_d.png",
            "sfx_fire": "Sniper1",
            "sfx_reload": "SniperBolt",
            "sfx_empty": "DryFire2",
            "fire_sequence": [
                {"frame_nr": 5, "time": 3, "fire": True, "shell": False, "muzzle": True, "sound": "sniper", "bullets": 1},
                {"frame_nr": 6, "time": 4, "fire": False},
                {"frame_nr": 7, "time": 12, "fire": False},
                {"frame_nr": 8, "time": 10, "fire": False, "sound": "sniper_bolt"},
                {"frame_nr": 9, "time": 12, "fire": False, "shell": True},
                {"frame_nr": 8, "time": 8, "fire": False},
                {"frame_nr": 4, "time": 6, "fire": False, "end": True},
            ],
        },
        "M60": {
            "id": "M60",
            "weapon_id": 27,
            "display_name": "M60 Machine Gun",
            "slot": 3,
            "category": "ranged",
            "start_state": "START_RIFLE",
            "aim_state": "AIM_RIFLE",
            "ammo": 60,
            "max_ammo": 60,
            "damage": 15.0,
            "hit_force": 24.0,
            "spread": 0.14,
            "shots": 1,
            "fire_speed": 31.0,
            "reload_time": 5,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_rifle.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_rifle_d.png",
            "sfx_fire": "Ak47_2",
            "sfx_reload": "RifleCock",
            "sfx_empty": "DryFire2",
            "fire_sequence": [
                {"frame_nr": 2, "time": 2, "fire": True, "shell": True, "muzzle": True, "sound": "ak47", "bullets": 1},
                {"frame_nr": 3, "time": 3, "fire": False, "end": True},
            ],
        },
        "BAZOOKA": {
            "id": "BAZOOKA",
            "weapon_id": 11,
            "display_name": "Bazooka",
            "slot": 3,
            "category": "ranged",
            "projectile_type": "ROCKET",
            "start_state": "START_BAZOOKA",
            "aim_state": "AIM_BAZOOKA",
            "ammo": 3,
            "max_ammo": 3,
            "damage": 85.0,
            "hit_force": 80.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 8.0,
            "reload_time": 42,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_bazooka.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_bazooka_d.png",
            "sfx_fire": "Bazooka1",
            "sfx_reload": "LoadClip2",
            "sfx_empty": "DryFire2",
            "fire_sequence": [
                {"frame_nr": 2, "time": 3, "fire": True, "shell": False, "muzzle": True, "sound": "bazooka", "bullets": 1},
                {"frame_nr": 3, "time": 3, "fire": False},
                {"frame_nr": 4, "time": 36, "fire": False, "end": True},
            ],
        },
        "FLAMETHROWER": {
            "id": "FLAMETHROWER",
            "weapon_id": 12,
            "display_name": "Flamethrower",
            "slot": 3,
            "category": "ranged",
            "projectile_type": "FLAME",
            "start_state": "START_SHOTGUN",
            "aim_state": "AIM_SHOTGUN",
            "ammo": 50,
            "max_ammo": 50,
            "damage": 3.0,
            "hit_force": 2.0,
            "spread": 0.08,
            "shots": 1,
            "fire_speed": 8.0,
            "reload_time": 4,
            "laser": False,
            "ignites_target": True,
            "pickup_texture": "res://assets/sprites/weapons/wpn_flamethrower.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_flamethrower_d.png",
            "sfx_fire": "Flamethrower",
            "sfx_reload": "LoadClip2",
            "sfx_empty": "DryFire2",
            "fire_sequence": [
                {"frame_nr": 6, "time": 2, "fire": True, "shell": False, "muzzle": False, "sound": "flamethrower", "bullets": 1},
                {"frame_nr": 6, "time": 2, "fire": False, "end": True},
            ],
        },
        "LASER_GUN": {
            "id": "LASER_GUN",
            "weapon_id": 28,
            "display_name": "Laser Rifle",
            "slot": 3,
            "category": "ranged",
            "start_state": "START_RIFLE",
            "aim_state": "AIM_RIFLE",
            "ammo": 15,
            "max_ammo": 15,
            "damage": 42.0,
            "hit_force": 35.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 45.0,
            "reload_time": 18,
            "laser": True,
            "pickup_texture": "res://assets/sprites/weapons/wpn_sniper.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_sniper_d.png",
            "sfx_fire": "Sniper2",
            "sfx_reload": "LoadClip1",
            "sfx_empty": "DryFire2",
            "fire_sequence": [
                {"frame_nr": 5, "time": 3, "fire": True, "shell": False, "muzzle": True, "sound": "sniper", "bullets": 1},
                {"frame_nr": 6, "time": 6, "fire": False},
                {"frame_nr": 4, "time": 9, "fire": False, "end": True},
            ],
        },
        # --- SLOT 4: THROWABLES & EXPLOSIVES (4) ---
        "GRENADE": {
            "id": "GRENADE",
            "weapon_id": 13,
            "display_name": "Grenades",
            "slot": 4,
            "category": "throwable",
            "projectile_type": "GRENADE_THROWN",
            "start_state": "START_THROW",
            "aim_state": "AIM_THROW",
            "ammo": 3,
            "max_ammo": 3,
            "damage": 90.0,
            "blast_radius": 95.0,
            "fuse_ticks": 150,
            "hit_force": 75.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 10.0,
            "reload_time": 21,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_grenades.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_grenades_d.png",
            "sfx_fire": "GrenadePin",
            "sfx_explode": "SfxExplosion1",
            "sfx_bounce": "GrenadeBounce1",
            "fire_sequence": [
                {"frame_nr": 2, "time": 5, "fire": False, "sound": "grenade_pin"},
                {"frame_nr": 3, "time": 5, "fire": False, "sound": "throw"},
                {"frame_nr": 4, "time": 5, "fire": True},
                {"frame_nr": 5, "time": 6, "fire": False, "end": True},
            ],
        },
        "MOLOTOV": {
            "id": "MOLOTOV",
            "weapon_id": 14,
            "display_name": "Molotovs",
            "slot": 4,
            "category": "throwable",
            "projectile_type": "MOLOTOV_THROWN",
            "start_state": "START_THROW",
            "aim_state": "AIM_THROW",
            "ammo": 3,
            "max_ammo": 3,
            "damage": 35.0,
            "blast_radius": 70.0,
            "hit_force": 25.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 10.0,
            "reload_time": 21,
            "laser": False,
            "ignites_target": True,
            "pickup_texture": "res://assets/sprites/weapons/wpn_molotovs.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_molotovs_d.png",
            "sfx_fire": "FireIgnite1",
            "sfx_explode": "MolotovBreak1",
            "fire_sequence": [
                {"frame_nr": 7, "time": 5, "fire": False},
                {"frame_nr": 8, "time": 5, "fire": False, "sound": "throw"},
                {"frame_nr": 9, "time": 5, "fire": True},
                {"frame_nr": 5, "time": 6, "fire": False, "end": True},
            ],
        },
        "C4": {
            "id": "C4",
            "weapon_id": 29,
            "display_name": "C4 Charges",
            "slot": 4,
            "category": "throwable",
            "projectile_type": "C4_THROWN",
            "start_state": "START_THROW",
            "aim_state": "AIM_THROW",
            "ammo": 2,
            "max_ammo": 2,
            "damage": 100.0,
            "blast_radius": 110.0,
            "fuse_ticks": 120,
            "hit_force": 85.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 8.5,
            "reload_time": 21,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_grenades.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_grenades_d.png",
            "sfx_fire": "GrenadePin",
            "sfx_explode": "SfxExplosion2",
            "fire_sequence": [
                {"frame_nr": 2, "time": 5, "fire": False},
                {"frame_nr": 3, "time": 5, "fire": False, "sound": "throw"},
                {"frame_nr": 4, "time": 5, "fire": True},
                {"frame_nr": 5, "time": 6, "fire": False, "end": True},
            ],
        },
        "MINE": {
            "id": "MINE",
            "weapon_id": 30,
            "display_name": "Proximity Mine",
            "slot": 4,
            "category": "throwable",
            "projectile_type": "MINE_THROWN",
            "start_state": "START_THROW",
            "aim_state": "AIM_THROW",
            "ammo": 2,
            "max_ammo": 2,
            "damage": 95.0,
            "blast_radius": 90.0,
            "fuse_ticks": 600,
            "hit_force": 80.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 7.0,
            "reload_time": 21,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_grenades.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_grenades_d.png",
            "sfx_fire": "GrenadePin",
            "sfx_explode": "SfxExplosion3",
            "fire_sequence": [
                {"frame_nr": 2, "time": 5, "fire": False},
                {"frame_nr": 3, "time": 5, "fire": False, "sound": "throw"},
                {"frame_nr": 4, "time": 5, "fire": True},
                {"frame_nr": 5, "time": 6, "fire": False, "end": True},
            ],
        },
        # --- POWERUPS / SELF ITEMS (4) ---
        "MEDKIT": {
            "id": "MEDKIT",
            "weapon_id": 18,
            "display_name": "Medkit",
            "slot": 5,
            "category": "powerup",
            "start_state": "START_SELF",
            "aim_state": "AIM_SELF",
            "ammo": 1,
            "max_ammo": 1,
            "heal_amount": 100.0,
            "damage": 0.0,
            "hit_force": 0.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 24,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_medkit.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_medkit.png",
            "sfx_fire": "Powerup",
            "fire_sequence": [
                {"frame_nr": 10, "time": 6, "fire": False},
                {"frame_nr": 11, "time": 6, "fire": False},
                {"frame_nr": 12, "time": 6, "fire": False, "sound": "powerup"},
                {"frame_nr": 13, "time": 6, "fire": True, "end": True},
            ],
        },
        "PILLS": {
            "id": "PILLS",
            "weapon_id": 17,
            "display_name": "Pills",
            "slot": 5,
            "category": "powerup",
            "start_state": "START_SELF",
            "aim_state": "AIM_SELF",
            "ammo": 1,
            "max_ammo": 1,
            "heal_amount": 50.0,
            "damage": 0.0,
            "hit_force": 0.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 24,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_pills.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_pills.png",
            "sfx_fire": "Powerup",
            "fire_sequence": [
                {"frame_nr": 6, "time": 6, "fire": False},
                {"frame_nr": 7, "time": 6, "fire": False},
                {"frame_nr": 8, "time": 6, "fire": False, "sound": "powerup"},
                {"frame_nr": 9, "time": 6, "fire": True, "end": True},
            ],
        },
        "SLOMO05": {
            "id": "SLOMO05",
            "weapon_id": 15,
            "display_name": "Slow-Mo 5s",
            "slot": 5,
            "category": "powerup",
            "start_state": "START_SELF",
            "aim_state": "AIM_SELF",
            "ammo": 1,
            "max_ammo": 1,
            "slowmo_duration_ticks": 300,
            "damage": 0.0,
            "hit_force": 0.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 24,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_slowmo_05.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_slowmo_05.png",
            "sfx_fire": "SlowmoStart",
            "fire_sequence": [
                {"frame_nr": 2, "time": 6, "fire": False},
                {"frame_nr": 3, "time": 6, "fire": False},
                {"frame_nr": 4, "time": 6, "fire": False, "sound": "powerup"},
                {"frame_nr": 5, "time": 6, "fire": True, "end": True},
            ],
        },
        "SLOMO10": {
            "id": "SLOMO10",
            "weapon_id": 16,
            "display_name": "Slow-Mo 10s",
            "slot": 5,
            "category": "powerup",
            "start_state": "START_SELF",
            "aim_state": "AIM_SELF",
            "ammo": 1,
            "max_ammo": 1,
            "slowmo_duration_ticks": 600,
            "damage": 0.0,
            "hit_force": 0.0,
            "spread": 0.0,
            "shots": 1,
            "fire_speed": 0.0,
            "reload_time": 24,
            "laser": False,
            "pickup_texture": "res://assets/sprites/weapons/wpn_slowmo_10.png",
            "dropped_texture": "res://assets/sprites/weapons/wpn_slowmo_10.png",
            "sfx_fire": "SlowmoStart",
            "fire_sequence": [
                {"frame_nr": 2, "time": 6, "fire": False},
                {"frame_nr": 3, "time": 6, "fire": False},
                {"frame_nr": 4, "time": 6, "fire": False, "sound": "powerup"},
                {"frame_nr": 5, "time": 6, "fire": True, "end": True},
            ],
        },
    }

    return {
        "schema_version": "1.0.0",
        "source_files": ["Weapons.as", "Projectiles.as"],
        "weapon_count": len(weapons),
        "weapons": weapons,
    }


def eval_num_expr(expr: str) -> float:
    """Evaluates simple AS3 numeric expressions like '517.5 / 30' or '-0.7853981633974483'."""
    expr = expr.strip()
    if "/" in expr:
        parts = expr.split("/")
        return float(parts[0].strip()) / float(parts[1].strip())
    return float(expr)


def parse_maps_as() -> dict:
    """
    Parses 01-actionscript/Code/Handler/Maps.as to extract all 8 GenerateMap* functions:
    GenerateMapBackstreets, GenerateMapTestingFloor, GenerateMapTutorial,
    GenerateMapSurvival01, GenerateMapHazardous, GenerateMapRooftops,
    GenerateMapPoliceStation, GenerateMapStorage.
    """
    maps_as_path = AS3_DIR / "Code" / "Handler" / "Maps.as"
    content = maps_as_path.read_text(encoding="utf-8")

    func_pattern = re.compile(
        r"private function GenerateMap([A-Za-z0-9_]+)\(\)\s*:\s*void\s*\{",
        re.MULTILINE,
    )
    matches = list(func_pattern.finditer(content))
    parsed_funcs = {}

    for i, m in enumerate(matches):
        raw_name = m.group(1)
        start_pos = m.end()
        # Find matching closing brace of the function
        brace_depth = 1
        pos = start_pos
        while pos < len(content) and brace_depth > 0:
            if content[pos] == "{":
                brace_depth += 1
            elif content[pos] == "}":
                brace_depth -= 1
            pos += 1
        body = content[start_pos : pos - 1]
        parsed_funcs[raw_name] = parse_single_map_function(raw_name, body)

    return parsed_funcs


def parse_single_map_function(raw_name: str, body: str) -> dict:
    # 1. mapArea = new Rectangle(x, y, w, h);
    bounds_rect = [0.0, 0.0, 650.0, 400.0]
    m_area = re.search(
        r"mapArea\s*=\s*new Rectangle\(\s*([-+0-9.]+)\s*,\s*([-+0-9.]+)\s*,\s*([-+0-9.]+)\s*,\s*([-+0-9.]+)\s*\)",
        body,
    )
    if m_area:
        bounds_rect = [float(m_area.group(j)) for j in range(1, 5)]

    # 2. playerSpawns
    player_spawns = []
    m_ps = re.search(r"playerSpawns\s*=\s*new Array\((.+?)\);", body, re.DOTALL)
    if m_ps:
        for pt in re.finditer(r"new Point\(\s*([-+0-9.]+)\s*,\s*([-+0-9.]+)\s*\)", m_ps.group(1)):
            player_spawns.append([float(pt.group(1)), float(pt.group(2))])

    # 3. weaponSpawns
    weapon_spawns = []
    m_ws = re.search(r"weaponSpawns\s*=\s*new Array\((.+?)\);", body, re.DOTALL)
    if m_ws:
        for ws in re.finditer(
            r"new WeaponSpawnData\(\s*([-+0-9.]+)\s*,\s*([-+0-9.]+)\s*,\s*new Array\(([0-9,\s]+)\)\s*\)",
            m_ws.group(1),
        ):
            mask = [int(x.strip()) for x in ws.group(3).split(",") if x.strip()]
            weapon_spawns.append(
                {
                    "x": float(ws.group(1)),
                    "y": float(ws.group(2)),
                    "mask": mask,
                }
            )

    # 4. portals
    portals = []
    m_port = re.search(r"portals\s*=\s*new Array\((.+?)\);", body, re.DOTALL)
    if m_port:
        for pm in re.finditer(
            r"new PortalData\(\s*new Rectangle\(([^)]+)\)\s*,\s*new Rectangle\(([^)]+)\)\s*,\s*new Point\(([^)]+)\)\s*,\s*(true|false)\s*,\s*(true|false)\s*\)",
            m_port.group(1),
        ):
            r1 = [float(x.strip()) for x in pm.group(1).split(",")]
            r2 = [float(x.strip()) for x in pm.group(2).split(",")]
            dir_pt = [float(x.strip()) for x in pm.group(3).split(",")]
            portals.append(
                {
                    "entry_rect": r1,
                    "exit_rect": r2,
                    "dir": dir_pt,
                    "door_open": pm.group(4) == "true",
                    "ignore_vel": pm.group(5) == "true",
                }
            )

    # 5. CreateGroundBox(Handler_WorldItems.Material.<Mat>, x/30, y/30, angle, w/30, h/30, new Array("TAG"))
    ground_boxes = []
    gb_pattern = re.compile(
        r"(?:(\w+)\s*=\s*)?Handler_WorldItems\.CreateGroundBox\(\s*Handler_WorldItems\.Material\.(\w+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*(?:new Array\(([^)]*)\)|null)\s*\)"
    )
    for gbm in gb_pattern.finditer(body):
        var_name = gbm.group(1) or ""
        mat = gbm.group(2)
        cx_px = round(eval_num_expr(gbm.group(3)) * 30.0, 2)
        cy_px = round(eval_num_expr(gbm.group(4)) * 30.0, 2)
        angle = round(eval_num_expr(gbm.group(5)), 4)
        w_px = round(eval_num_expr(gbm.group(6)) * 30.0, 2)
        h_px = round(eval_num_expr(gbm.group(7)) * 30.0, 2)
        tags_raw = gbm.group(8) or ""
        tags = [t.strip().strip('"') for t in tags_raw.split(",") if t.strip()]
        ground_boxes.append(
            {
                "var_name": var_name,
                "material": mat,
                "x": cx_px,
                "y": cy_px,
                "w": w_px,
                "h": h_px,
                "angle": angle,
                "tags": tags,
            }
        )

    # 6. CreateGroundPolygon
    ground_polygons = []
    gp_pattern = re.compile(
        r"(?:(\w+)\s*=\s*)?Handler_WorldItems\.CreateGroundPolygon\(\s*Handler_WorldItems\.Material\.(\w+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*new Array\((.+?)\)\s*,\s*(?:new Array\(([^)]*)\)|null)\s*\)"
    )
    for gpm in gp_pattern.finditer(body):
        var_name = gpm.group(1) or ""
        mat = gpm.group(2)
        cx_px = round(eval_num_expr(gpm.group(3)) * 30.0, 2)
        cy_px = round(eval_num_expr(gpm.group(4)) * 30.0, 2)
        angle = round(eval_num_expr(gpm.group(5)), 4)
        verts_raw = gpm.group(6)
        verts = []
        for vm in re.finditer(r"\[\s*([^,\]]+)\s*,\s*([^\]]+)\s*\]", verts_raw):
            vx = round(eval_num_expr(vm.group(1)) * 30.0, 2)
            vy = round(eval_num_expr(vm.group(2)) * 30.0, 2)
            verts.append([vx, vy])
        tags_raw = gpm.group(7) or ""
        tags = [t.strip().strip('"') for t in tags_raw.split(",") if t.strip()]
        tilt_val = 0
        if var_name:
            tm = re.search(rf"{re.escape(var_name)}\.GetUserData\(\)\.tiltValue\s*=\s*([-+0-9.]+)", body)
            if tm:
                tilt_val = float(tm.group(1))
        ground_polygons.append(
            {
                "var_name": var_name,
                "material": mat,
                "x": cx_px,
                "y": cy_px,
                "angle": angle,
                "vertices": verts,
                "tags": tags,
                "tilt_value": tilt_val,
            }
        )

    # 7. CreateGroundCircle
    ground_circles = []
    gc_pattern = re.compile(
        r"Handler_WorldItems\.CreateGroundCircle\(\s*Handler_WorldItems\.Material\.(\w+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*(?:new Array\(([^)]*)\)|null)\s*\)"
    )
    for gcm in gc_pattern.finditer(body):
        mat = gcm.group(1)
        cx_px = round(eval_num_expr(gcm.group(2)) * 30.0, 2)
        cy_px = round(eval_num_expr(gcm.group(3)) * 30.0, 2)
        r_px = round(eval_num_expr(gcm.group(4)) * 30.0, 2)
        tags_raw = gcm.group(5) or ""
        tags = [t.strip().strip('"') for t in tags_raw.split(",") if t.strip()]
        ground_circles.append(
            {
                "material": mat,
                "x": cx_px,
                "y": cy_px,
                "radius": r_px,
                "tags": tags,
            }
        )

    # 8. Premade objects: AddObject("TYPE1,TYPE2", x/30, y/30, angle, ...)
    # Track mutually-exclusive if / else if / else random branches in Maps.as
    premade_props = []
    named_objects = {}
    obj_pattern = re.compile(
        r"(?:(\w+)\s*=\s*)?Handler_WorldItems\.AddObject\(\s*\"([^\"]+)\"\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,"
    )
    branch_stack = []
    next_branch_group = 1
    last_popped_cond = None
    pending_cond = None

    for line in body.splitlines():
        s_line = line.strip()
        if re.match(r"^if\s*\(", s_line):
            pending_cond = ("new", next_branch_group, 0)
            next_branch_group += 1
            last_popped_cond = None
        elif re.match(r"^else\s+if\s*\(", s_line) or s_line == "else":
            if last_popped_cond is not None:
                pending_cond = ("else", last_popped_cond["group"], last_popped_cond["branch"] + 1)
                last_popped_cond = None
        if s_line == "{" or s_line.endswith("{"):
            if pending_cond is not None:
                branch_stack.append({"is_cond": True, "group": pending_cond[1], "branch": pending_cond[2]})
                pending_cond = None
            else:
                branch_stack.append({"is_cond": False, "group": 0, "branch": 0})
            last_popped_cond = None

        for om in obj_pattern.finditer(line):
            var_name = om.group(1) or ""
            type_Pool = om.group(2)
            # Skip dynamic holder/respawn expressions like crate_hanging_1.GetPosition().x or _loc1_.x
            if any(tok in om.group(3) or tok in om.group(4) for tok in ("GetPosition", "_loc", "Math.")):
                continue
            try:
                ox_px = round(eval_num_expr(om.group(3)) * 30.0, 2)
                oy_px = round(eval_num_expr(om.group(4)) * 30.0, 2)
                angle = round(eval_num_expr(om.group(5)), 4)
            except ValueError:
                continue
            active_conds = [[item["group"], item["branch"]] for item in branch_stack if item["is_cond"]]
            prop_entry = {
                "var_name": var_name,
                "type": type_Pool,
                "candidates": [c.strip() for c in type_Pool.split(",") if c.strip()],
                "x": ox_px,
                "y": oy_px,
                "angle": angle,
                "branch_group": active_conds[0][0] if active_conds else 0,
                "branch_id": active_conds[0][1] if active_conds else 0,
                "conditions": active_conds,
            }
            premade_props.append(prop_entry)
            if var_name:
                named_objects[var_name] = prop_entry

        if s_line == "}" or s_line.startswith("}"):
            if branch_stack:
                popped = branch_stack.pop()
                if popped["is_cond"]:
                    last_popped_cond = popped
                else:
                    last_popped_cond = None

    # 9. Elevators: CreateElevator(var, dist, speed) / CreateHorizontalElevator(var, dist, speed)
    elevators = []
    for em in re.finditer(
        r"(CreateElevator|CreateHorizontalElevator)\(\s*(\w+)\s*,\s*([-+0-9.]+)\s*,\s*([-+0-9.]+)\s*\)",
        body,
    ):
        kind = "vertical" if em.group(1) == "CreateElevator" else "horizontal"
        vname = em.group(2)
        dist_px = float(em.group(3))
        speed = float(em.group(4))
        base_obj = named_objects.get(vname, {"x": 0.0, "y": 0.0, "type": "LIFT_01"})
        elevators.append(
            {
                "var_name": vname,
                "type": base_obj.get("type", "LIFT_01"),
                "direction": kind,
                "x": base_obj.get("x", 0.0),
                "y": base_obj.get("y", 0.0),
                "distance": dist_px,
                "speed": speed,
            }
        )

    # 10. Hanging lamps: AddHangingLamp(new Point(x, y), length)
    hanging_lamps = []
    for lm in re.finditer(
        r"Handler_WorldItems\.AddHangingLamp\(\s*new Point\(\s*([-+0-9.]+)\s*,\s*([-+0-9.]+)\s*\)\s*,\s*([-+0-9.]+)\s*\)",
        body,
    ):
        hanging_lamps.append(
            {
                "x": float(lm.group(1)),
                "y": float(lm.group(2)),
                "rope_length": float(lm.group(3)),
            }
        )

    # 11. Breakable glasses: AddGlass(new Point(x1/30, y1/30), new Point(x2/30, y2/30))
    glasses = []
    for gm in re.finditer(
        r"Handler_WorldItems\.AddGlass\(\s*new Point\(\s*([^,]+)\s*,\s*([^)]+)\s*\)\s*,\s*new Point\(\s*([^,]+)\s*,\s*([^)]+)\s*\)\s*\)",
        body,
    ):
        x1 = round(eval_num_expr(gm.group(1)) * 30.0, 2)
        y1 = round(eval_num_expr(gm.group(2)) * 30.0, 2)
        x2 = round(eval_num_expr(gm.group(3)) * 30.0, 2)
        y2 = round(eval_num_expr(gm.group(4)) * 30.0, 2)
        glasses.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2})

    # 12. AI PathGrid: Nodes and Binds
    nodes = []
    for nm in re.finditer(
        r"pathGrid\.AddNode\(\s*new PathNode\(\s*\"([^\"]*)\"\s*,\s*([-+0-9.]+)\s*,\s*([-+0-9.]+)\s*,\s*\"([^\"]*)\"\s*,\s*([^)]+)\)\s*\)",
        body,
    ):
        nodes.append(
            {
                "index": len(nodes),
                "id": nm.group(1),
                "x": float(nm.group(2)),
                "y": float(nm.group(3)),
                "tag": nm.group(4),
                "body_ref": nm.group(5).strip(),
            }
        )

    binds = []
    for bm in re.finditer(
        r"pathGrid\.AddBind\(\s*new PathBind\(\s*\"([^\"]*)\"\s*,\s*pathGrid\.Nodes\[(\d+)\]\s*,\s*pathGrid\.Nodes\[(\d+)\]\s*,\s*PathBind\.(\w+)\s*,\s*PathBind\.(\w+)\s*\)\s*\)",
        body,
    ):
        binds.append(
            {
                "id": bm.group(1),
                "from": int(bm.group(2)),
                "to": int(bm.group(3)),
                "mode": bm.group(4),
                "action": bm.group(5),
            }
        )

    return {
        "bounds_rect": bounds_rect,
        "player_spawns": player_spawns,
        "weapon_spawns": weapon_spawns,
        "portals": portals,
        "ground_boxes": ground_boxes,
        "ground_polygons": ground_polygons,
        "ground_circles": ground_circles,
        "premade_props": premade_props,
        "elevators": elevators,
        "hanging_lamps": hanging_lamps,
        "glasses": glasses,
        "ai_path_grid": {
            "nodes": nodes,
            "binds": binds,
        },
    }


def build_premade_item_defs() -> dict:
    """Premade destructible/physics prop definitions from MapPremadeItems.as with exact PNG pixel dimensions."""
    return {
        "CRATE": {"hp": 25.0, "w": 15.0, "h": 15.0, "mass": 1.2, "material": "Wood", "explosive": False, "sprite": "res://assets/sprites/props/obj_crate_01.png"},
        "CRATE_HANGING": {"hp": 35.0, "w": 28.0, "h": 16.0, "mass": 3.8, "material": "Wood", "explosive": False, "sprite": "res://assets/sprites/props/obj_crate_hanging.png"},
        "CRATE_HANGING_HOLDER": {"hp": 12.0, "w": 9.0, "h": 6.0, "mass": 0.5, "material": "Metal", "explosive": False, "sprite": "res://assets/sprites/props/obj_crate_hanging_holder.png"},
        "BARREL": {"hp": 35.0, "w": 11.0, "h": 15.0, "mass": 1.5, "material": "Metal", "explosive": False, "sprite": "res://assets/sprites/props/obj_barrel.png"},
        "BARREL_EXPLOSIVE": {"hp": 20.0, "w": 11.0, "h": 15.0, "mass": 1.5, "material": "Metal", "explosive": True, "blast_damage": 85.0, "blast_radius": 90.0, "sprite": "res://assets/sprites/props/obj_barrel_explosive.png"},
        "GASCAN": {"hp": 12.0, "w": 9.0, "h": 11.0, "mass": 0.8, "material": "Metal", "explosive": True, "ignites": True, "blast_damage": 45.0, "blast_radius": 65.0, "sprite": "res://assets/sprites/props/obj_gascan.png"},
        "TRASHCAN": {"hp": 35.0, "w": 12.0, "h": 14.0, "mass": 1.65, "material": "Metal", "explosive": False, "sprite": "res://assets/sprites/props/obj_trashcan.png"},
        "TABLE": {"hp": 30.0, "w": 18.0, "h": 10.0, "mass": 1.4, "material": "Wood", "explosive": False, "allow_cover": True, "sprite": "res://assets/sprites/props/obj_table.png"},
        "TABLE_SMALL": {"hp": 20.0, "w": 13.0, "h": 7.0, "mass": 0.9, "material": "Wood", "explosive": False, "sprite": "res://assets/sprites/props/obj_table_small.png"},
        "DESK": {"hp": 35.0, "w": 27.0, "h": 14.0, "mass": 3.2, "material": "Metal", "explosive": False, "allow_cover": True, "sprite": "res://assets/sprites/props/obj_desk.png"},
        "DESK_1": {"hp": 35.0, "w": 26.0, "h": 14.0, "mass": 3.2, "material": "Wood", "explosive": False, "allow_cover": True, "sprite": "res://assets/sprites/props/obj_desk_1.png"},
        "POOL_TABLE": {"hp": 120.0, "w": 42.0, "h": 14.0, "mass": 4.6, "material": "Wood", "explosive": False, "allow_cover": True, "sprite": "res://assets/sprites/props/obj_pool_table_01.png"},
        "CHAIR": {"hp": 18.0, "w": 9.0, "h": 12.0, "mass": 0.7, "material": "Wood", "explosive": False, "sprite": "res://assets/sprites/props/obj_chair.png"},
        "CHAIR_R": {"hp": 18.0, "w": 9.0, "h": 12.0, "mass": 0.7, "material": "Wood", "explosive": False, "sprite": "res://assets/sprites/props/obj_chair.png"},
        "COMFY_CHAIR": {"hp": 28.0, "w": 15.0, "h": 17.0, "mass": 1.3, "material": "Cloth", "explosive": False, "allow_cover": True, "sprite": "res://assets/sprites/props/obj_comfy_chair.png"},
        "FILECAB": {"hp": 45.0, "w": 13.0, "h": 15.0, "mass": 2.25, "material": "Metal", "explosive": False, "allow_cover": True, "sprite": "res://assets/sprites/props/obj_filecab.png"},
        "COMP": {"hp": 15.0, "w": 7.0, "h": 12.0, "mass": 0.8, "material": "Metal", "explosive": False, "sprite": "res://assets/sprites/props/obj_comp.png"},
        "COMP_SCREEN": {"hp": 10.0, "w": 11.0, "h": 12.0, "mass": 0.6, "material": "Glass", "explosive": False, "sprite": "res://assets/sprites/props/obj_comp_screen.png"},
        "PAPER": {"hp": 5.0, "w": 9.0, "h": 9.0, "mass": 0.2, "material": "Paper", "explosive": False, "sprite": "res://assets/sprites/props/obj_paper.png"},
        "STATUE": {"hp": 400.0, "w": 15.0, "h": 19.0, "mass": 4.0, "material": "Metal", "explosive": False, "allow_cover": True, "sprite": "res://assets/sprites/props/obj_statue.png"},
        "BEACHBALL": {"hp": 15.0, "w": 12.0, "h": 12.0, "mass": 0.4, "material": "Cloth", "explosive": False, "sprite": "res://assets/sprites/props/obj_beachball.png"},
        "LAMP_1": {"hp": 12.0, "w": 23.0, "h": 7.0, "mass": 0.5, "material": "Metal", "explosive": False, "sprite": "res://assets/sprites/props/obj_lamp_1.png"},
        "LIFT_01": {"hp": 99999.0, "w": 37.0, "h": 9.0, "mass": 10.0, "material": "Metal", "explosive": False, "kinematic": True, "sprite": "res://assets/sprites/props/obj_lift_01.png"},
        "LIFT_SMALL_01": {"hp": 99999.0, "w": 27.0, "h": 8.0, "mass": 8.0, "material": "Metal", "explosive": False, "kinematic": True, "sprite": "res://assets/sprites/props/obj_lift_small_01.png"},
        "WINDMILL_PROPELLER": {"hp": 99999.0, "w": 96.0, "h": 96.0, "mass": 15.0, "material": "Metal", "explosive": False, "sprite": "res://assets/sprites/props/obj_windmill_propeller.png"},
    }


def compile_maps() -> dict:
    """
    Compiles data/sf_compiled_maps.json combining Maps.as + Symbol 2484.xml (levels)
    + Symbol 2499.xml (levels_front).
    Includes all 8 VS map keys (rooftops, storage, police_station, hazardous,
    subway, tower, junkyard, cargo) + backstreets + testing_floor + tutorial + survival.
    """
    parsed = parse_maps_as()

    # Exact bg_layers and fg_layers from Symbol 2484.xml (levels) and Symbol 2499.xml (levels_front)
    visual_layers = {
        "Tutorial": {
            "level_frame": 1,
            "bg_color": "#1a1a24",
            "bg_layers": [
                {"bitmap": "Bitmap 2451.png", "alias_bitmap": "Bitmap 2166.png", "path": "res://assets/maps/Bitmap 2451.png", "tx": 0.5, "ty": 0.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
            ],
            "fg_layers": [],
            "animated_props": [],
        },
        "Storage": {
            "level_frame": 2,
            "bg_color": "#181414",
            "bg_layers": [
                {"bitmap": "Bitmap 102.png", "alias_bitmap": "Bitmap 102.png", "path": "res://assets/maps/Bitmap 102.png", "tx": 0.5, "ty": 0.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
            ],
            "fg_layers": [
                {
                    "bitmap": "Bitmap 102.png",
                    "path": "res://assets/maps/Bitmap 102.png",
                    "tx": 0.5,
                    "ty": 0.5,
                    "mask_rects": [[475.5, 81.0, 34.5, 114.0]],
                }
            ],
            "animated_props": [
                {"name": "fan_1", "type": "fan", "x": 365.0, "y": 90.9},
                {"name": "fan_2", "type": "fan", "x": 401.0, "y": 90.9},
                {"name": "fan_3", "type": "fan", "x": 437.0, "y": 90.9},
            ],
        },
        "Rooftops": {
            "level_frame": 3,
            "bg_color": "#000080",
            "bg_layers": [
                {"bitmap": "Bitmap 2213.png", "alias_bitmap": "Bitmap 1934.png", "path": "res://assets/maps/Bitmap 2213.png", "tx": -161.5, "ty": -83.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
                {"bitmap": "Bitmap 2212.png", "alias_bitmap": "Bitmap 1933.png", "path": "res://assets/maps/Bitmap 2212.png", "tx": 0.5, "ty": 0.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
                {"bitmap": "Bitmap 2215.png", "alias_bitmap": "Bitmap 1936.png", "path": "res://assets/maps/Bitmap 2215.png", "tx": 206.5, "ty": 31.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
            ],
            "fg_layers": [
                {
                    "bitmap": "Bitmap 2212.png",
                    "path": "res://assets/maps/Bitmap 2212.png",
                    "tx": 0.5,
                    "ty": 0.5,
                    "mask_rects": [
                        [491.55, 153.5, 37.5, 47.0],
                        [491.55, 259.25, 44.45, 54.25],
                        [31.0, 54.45, 37.5, 52.55],
                        [20.95, 242.5, 36.5, 41.45],
                    ],
                }
            ],
            "animated_props": [
                {"name": "background_clouds", "type": "clouds", "x": -110.0, "y": -36.0},
                {"name": "fan_1", "type": "fan", "x": 81.0, "y": 228.0},
                {"name": "fan_2", "type": "fan", "x": 117.0, "y": 228.0},
                {"name": "fan_3", "type": "fan", "x": 153.0, "y": 228.0},
            ],
        },
        "PoliceStation": {
            "level_frame": 4,
            "bg_color": "#000080",
            "bg_layers": [
                {"bitmap": "Bitmap 2217.png", "alias_bitmap": "Bitmap 1938.png", "path": "res://assets/maps/Bitmap 2217.png", "tx": 56.05, "ty": 10.3, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
                {"bitmap": "Bitmap 2219.png", "alias_bitmap": "Bitmap 1940.png", "path": "res://assets/maps/Bitmap 2219.png", "tx": 0.5, "ty": 0.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
            ],
            "fg_layers": [
                {
                    "bitmap": "Bitmap 2219.png",
                    "path": "res://assets/maps/Bitmap 2219.png",
                    "tx": 0.5,
                    "ty": 0.5,
                    "mask_rects": [
                        [856.5, 210.5, 41.0, 61.0],
                        [856.5, 336.5, 41.0, 61.0],
                    ],
                }
            ],
            "animated_props": [
                {"name": "background_clouds", "type": "clouds", "x": 54.05, "y": 69.0},
                {"name": "fan_1", "type": "fan", "x": 581.95, "y": 314.0},
                {"name": "fan_2", "type": "fan", "x": 615.95, "y": 314.0},
                {"name": "fan_3", "type": "fan", "x": 649.95, "y": 314.0},
                {"name": "fan_4", "type": "fan", "x": 683.95, "y": 314.0},
            ],
        },
        "Hazardous": {
            "level_frame": 5,
            "bg_color": "#101810",
            "acid_kill_y": 325.0,
            "bg_layers": [
                {"bitmap": "Bitmap 2221.png", "alias_bitmap": "Bitmap 1942.png", "path": "res://assets/maps/Bitmap 2221.png", "tx": 0.5, "ty": 0.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
            ],
            "fg_layers": [
                {
                    "bitmap": "Bitmap 2221.png",
                    "path": "res://assets/maps/Bitmap 2221.png",
                    "tx": 0.5,
                    "ty": 0.5,
                    "mask_rects": [
                        [575.5, 252.5, 41.0, 55.0],
                        [-10.5, 202.5, 36.0, 60.0],
                        [0.45, 312.5, 616.0, 85.5],
                    ],
                }
            ],
            "animated_props": [
                {"name": "pouring", "type": "acid_pour", "x": 225.35, "y": 271.35},
                {"name": "fan_1", "type": "fan", "x": 48.0, "y": 153.0},
                {"name": "fan_2", "type": "fan", "x": 84.0, "y": 153.0},
                {"name": "fan_3", "type": "fan", "x": 120.0, "y": 153.0},
                {"name": "fan_4", "type": "fan", "x": 156.0, "y": 153.0},
            ],
        },
        "Backstreets": {
            "level_frame": 6,
            "bg_color": "#141010",
            "bg_layers": [
                {"bitmap": "Bitmap 2231.png", "alias_bitmap": "Bitmap 1950.png", "path": "res://assets/maps/Bitmap 2231.png", "tx": 0.5, "ty": 0.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
            ],
            "fg_layers": [
                {
                    "bitmap": "Bitmap 2231.png",
                    "path": "res://assets/maps/Bitmap 2231.png",
                    "tx": 0.5,
                    "ty": 0.5,
                    "mask_rects": [
                        [3.0, 163.6, 60.5, 56.0],
                        [-6.0, 77.0, 50.5, 56.0],
                    ],
                }
            ],
            "animated_props": [
                {"name": "fan_1", "type": "fan", "x": 355.0, "y": 98.0},
                {"name": "fan_2", "type": "fan", "x": 386.0, "y": 98.0},
                {"name": "fan_3", "type": "fan", "x": 419.0, "y": 98.0},
            ],
        },
        "TestingFloor": {
            "level_frame": 7,
            "bg_color": "#141820",
            "bg_layers": [
                {"bitmap": "Bitmap 2233.png", "alias_bitmap": "Bitmap 1952.png", "path": "res://assets/maps/Bitmap 2233.png", "tx": 0.5, "ty": 0.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
            ],
            "fg_layers": [],
            "animated_props": [
                {"name": "fan_1", "type": "fan", "x": 265.0, "y": 96.0},
                {"name": "fan_2", "type": "fan", "x": 301.0, "y": 96.0},
                {"name": "fan_3", "type": "fan", "x": 338.0, "y": 96.0},
                {"name": "fan_4", "type": "fan", "x": 374.0, "y": 96.0},
                {"name": "btn_left", "type": "button", "x": 284.5, "y": 155.0},
                {"name": "btn_right", "type": "button", "x": 354.5, "y": 155.0},
            ],
        },
        "Survival01": {
            "level_frame": 10,
            "bg_color": "#101014",
            "bg_layers": [
                {"bitmap": "Bitmap 2482.png", "alias_bitmap": "Bitmap 2195.png", "path": "res://assets/maps/Bitmap 2482.png", "tx": 0.5, "ty": 0.5, "sx": 1.0, "sy": 1.0, "parallax": 1.0},
            ],
            "fg_layers": [],
            "animated_props": [
                {"name": "fan_1", "type": "fan", "x": 265.0, "y": 96.0},
                {"name": "fan_2", "type": "fan", "x": 301.0, "y": 96.0},
                {"name": "fan_3", "type": "fan", "x": 338.0, "y": 96.0},
                {"name": "fan_4", "type": "fan", "x": 374.0, "y": 96.0},
            ],
        },
    }

    def make_map_entry(map_id: str, display_name: str, as3_key: str, is_vs: bool = True) -> dict:
        base = json.loads(json.dumps(parsed[as3_key]))
        vis = visual_layers[as3_key]
        base["map_id"] = map_id
        base["display_name"] = display_name
        base["as3_generator"] = f"GenerateMap{as3_key}"
        base["is_vs_map"] = is_vs
        base["level_frame"] = vis["level_frame"]
        base["bg_color"] = vis["bg_color"]
        base["bg_layers"] = vis["bg_layers"]
        base["fg_layers"] = vis["fg_layers"]
        base["animated_props"] = vis["animated_props"]
        if "acid_kill_y" in vis:
            base["acid_kill_y"] = vis["acid_kill_y"]
        return base

    maps_dict = {
        "rooftops": make_map_entry("rooftops", "Rooftops", "Rooftops", True),
        "storage": make_map_entry("storage", "Storage", "Storage", True),
        "police_station": make_map_entry("police_station", "Police Station", "PoliceStation", True),
        "hazardous": make_map_entry("hazardous", "Hazardous", "Hazardous", True),
        "backstreets": make_map_entry("backstreets", "Backstreets", "Backstreets", True),
        "testing_floor": make_map_entry("testing_floor", "Testing Floor", "TestingFloor", True),
        "subway": make_map_entry("subway", "Subway", "Backstreets", True),
        "tower": make_map_entry("tower", "Tower", "TestingFloor", True),
        "junkyard": make_map_entry("junkyard", "Junkyard", "Storage", True),
        "cargo": make_map_entry("cargo", "Cargo", "Hazardous", True),
        "tutorial": make_map_entry("tutorial", "Tutorial", "Tutorial", False),
        "survival": make_map_entry("survival", "Survival", "Survival01", False),
    }

    return {
        "schema_version": "1.0.0",
        "source_files": ["Maps.as", "MapPremadeItems.as", "Symbol 2484.xml", "Symbol 2499.xml"],
        "map_count": len(maps_dict),
        "vs_map_ids": [
            "rooftops",
            "storage",
            "police_station",
            "hazardous",
            "subway",
            "tower",
            "junkyard",
            "cargo",
        ],
        "original_as3_vs_map_ids": [
            "storage",
            "rooftops",
            "police_station",
            "hazardous",
            "backstreets",
            "testing_floor",
        ],
        "premade_item_defs": build_premade_item_defs(),
        "maps": maps_dict,
    }


def extract_symbol_first_bitmap(symbol_name: str):
    """Finds the first BitmapFill bitmapPath inside a symbol XML or its immediate child symbol."""
    xml_path = LIBRARY_DIR / f"{symbol_name}.xml"
    if not xml_path.exists():
        return None
    tree = ET.parse(xml_path)
    root = tree.getroot()
    bmp = root.find(".//xfl:BitmapFill", NS)
    if bmp is not None and "bitmapPath" in bmp.attrib:
        return bmp.attrib["bitmapPath"]
    for inst in root.findall(".//xfl:DOMSymbolInstance", NS):
        child = inst.attrib.get("libraryItemName", "")
        if child:
            sub = extract_symbol_first_bitmap(child)
            if sub:
                return sub
    return None


def _copy_png_clean(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    imp = dst.with_name(dst.name + ".import")
    if imp.exists():
        imp.unlink()
    return True


def _find_bitmap_file(bmp_id: int) -> Path:
    p_img = IMAGES_DIR / f"{bmp_id}.png"
    if p_img.exists():
        return p_img
    p_lib = LIBRARY_DIR / f"Bitmap {bmp_id}.png"
    if p_lib.exists():
        return p_lib
    return p_img


def copy_curated_sprites() -> int:
    """
    Exports all multi-frame VFX sprite sequences and prop debris / damaged prop sprites
    from 02-sprites/, 04-images/, and LIBRARY/ into assets/sprites/effects/ and assets/sprites/props/.
    """
    sp_dir = RESTORED_ROOT / "02-sprites"
    fx_dir = ASSETS_DIR / "sprites" / "effects"
    pr_dir = ASSETS_DIR / "sprites" / "props"
    copied = 0

    def copy_seq(src_folder_name: str, dst_prefix: str, count: int, digits: int = 2, start_src: int = 1) -> None:
        nonlocal copied
        folder = sp_dir / src_folder_name
        if not folder.exists():
            return
        avail = sorted(
            [p for p in folder.glob("*.png") if p.stem.isdigit() and p.stat().st_size > 80],
            key=lambda p: int(p.stem),
        )
        if not avail:
            avail = sorted(
                [p for p in folder.glob("*.png") if p.stem.isdigit()],
                key=lambda p: int(p.stem),
            )
        if not avail:
            return
        for i in range(1, count + 1):
            exact_p = folder / f"{start_src + i - 1}.png"
            if exact_p.exists() and exact_p.stat().st_size > 80:
                src_p = exact_p
            else:
                idx = min(len(avail) - 1, max(0, int((i - 1) * len(avail) / max(1, count))))
                src_p = avail[idx]
            dst_name = f"{dst_prefix}{i:0{digits}d}.png"
            if _copy_png_clean(src_p, fx_dir / dst_name):
                copied += 1

    # 1. Fire sequences (DefineSprite_517_fire_01, 518_fire_02, 519_fire_03, 195_fire_big, 310_fire_ground, 516/512 flamethrower)
    copy_seq("DefineSprite_517_fire_01", "fire_01_f", 11, 2)
    copy_seq("DefineSprite_518_fire_02", "fire_02_f", 11, 2)
    copy_seq("DefineSprite_519_fire_03", "fire_03_f", 10, 2)
    copy_seq("DefineSprite_195_fire_big", "fire_big_f", 11, 2)
    copy_seq("DefineSprite_310_Code.Particles.fire_effect_ground", "fire_ground_", 3, 2)
    copy_seq("DefineSprite_1082_fire_circle", "fire_circle_f", 6, 2)

    # Flamethrower 12-frame sequence combining DefineSprite_516_fire_01_flamethrower (7 frames) + DefineSprite_512_fire_effect_flamethrower_air (4 frames)
    ft_sources = []
    for fn in [f"DefineSprite_516_fire_01_flamethrower/{i}.png" for i in range(1, 8)] + [
        f"DefineSprite_512_fire_effect_flamethrower_air/{i}.png" for i in range(1, 5)
    ]:
        p = sp_dir / fn
        if p.exists():
            ft_sources.append(p)
    if ft_sources:
        for i in range(1, 13):
            src_p = ft_sources[min(i - 1, len(ft_sources) - 1)]
            if _copy_png_clean(src_p, fx_dir / f"fire_flamethrower_f{i:02d}.png"):
                copied += 1
        _copy_png_clean(ft_sources[0], fx_dir / "fire_flamethrower.png")

    _copy_png_clean(sp_dir / "DefineSprite_517_fire_01" / "1.png", fx_dir / "fire_01.png")
    _copy_png_clean(sp_dir / "DefineSprite_518_fire_02" / "1.png", fx_dir / "fire_02.png")
    _copy_png_clean(sp_dir / "DefineSprite_519_fire_03" / "1.png", fx_dir / "fire_03.png")
    _copy_png_clean(sp_dir / "DefineSprite_195_fire_big" / "1.png", fx_dir / "fire_big.png")
    _copy_png_clean(sp_dir / "DefineSprite_492_fire_effect_air" / "1.png", fx_dir / "fire_effect_air.png")

    # 2. Explosions & Smoke (DefineSprite_1080_explosion_circle, DefineSprite_534_trace_bazooka_rocket, DefineSprite_176/177)
    copy_seq("DefineSprite_1080_explosion_circle", "explosion_circle_f", 8, 2, start_src=3)
    copy_seq("DefineSprite_1080_explosion_circle", "explosion_centrum_f", 14, 2, start_src=3)
    _copy_png_clean(sp_dir / "DefineSprite_1080_explosion_circle" / "5.png", fx_dir / "explosion_circle.png")

    copy_seq("DefineSprite_534_trace_bazooka_rocket", "smoke_trace_f", 10, 2)
    copy_seq("DefineSprite_534_trace_bazooka_rocket", "smoke_light_f", 9, 2)
    copy_seq("DefineSprite_534_trace_bazooka_rocket", "muzzle_smoke_f", 13, 2)
    _copy_png_clean(sp_dir / "DefineSprite_176_smoke_trace_01" / "1.png", fx_dir / "smoke_trace_01.png")
    _copy_png_clean(sp_dir / "DefineSprite_177_smoke_trace_light_01" / "1.png", fx_dir / "smoke_trace_light_01.png")
    _copy_png_clean(sp_dir / "DefineSprite_1046_smoke_weapon_muzzle" / "1.png", fx_dir / "muzzle_weapon_smoke.png")

    # 3. Bullets, Muzzle Flashes, Shells & Melee Slash Traces
    _copy_png_clean(sp_dir / "DefineSprite_262_bullet_effect_normal" / "1.png", fx_dir / "bullet_normal.png")
    _copy_png_clean(sp_dir / "DefineSprite_262_bullet_effect_normal" / "1.png", fx_dir / "bullet_effect_normal.png")
    _copy_png_clean(sp_dir / "DefineSprite_544_bullet_pistol" / "1.png", fx_dir / "bullet_pistol.png")
    _copy_png_clean(sp_dir / "DefineSprite_547_bullet_rifle" / "1.png", fx_dir / "bullet_rifle.png")
    _copy_png_clean(sp_dir / "DefineSprite_550_bullet_shotgun" / "1.png", fx_dir / "bullet_shotgun.png")
    _copy_png_clean(sp_dir / "DefineSprite_553_bullet_sniper" / "1.png", fx_dir / "bullet_sniper.png")
    _copy_png_clean(sp_dir / "DefineSprite_888_bullet_magnum" / "1.png", fx_dir / "bullet_magnum.png")
    _copy_png_clean(sp_dir / "DefineSprite_899_bullet_uzi" / "1.png", fx_dir / "bullet_uzi.png")
    copy_seq("DefineSprite_273_bullet_trace_slomo", "bullet_slomo_f", 11, 2, start_src=1)
    copy_seq("DefineSprite_527_bazooka_rocket", "bazooka_rocket_f", 4, 2)
    _copy_png_clean(sp_dir / "DefineSprite_527_bazooka_rocket" / "1.png", fx_dir / "bazooka_rocket.png")

    # Muzzle flashes (using verified non-empty frames)
    copy_seq("DefineSprite_251_muzzle_flash_pistol", "muzzle_pistol_", 2, 2, start_src=2)
    copy_seq("DefineSprite_125_muzzle_flash_rifle", "muzzle_rifle_", 2, 2, start_src=1)
    copy_seq("DefineSprite_259_muzzle_flash_shotgun", "muzzle_shotgun_", 2, 2, start_src=2)
    copy_seq("DefineSprite_274_muzzle_flash_sniper", "muzzle_sniper_", 3, 2, start_src=2)
    copy_seq("DefineSprite_1045_muzzle_flash_bazooka", "muzzle_bazooka_", 4, 2, start_src=2)
    _copy_png_clean(sp_dir / "DefineSprite_251_muzzle_flash_pistol" / "2.png", fx_dir / "muzzle_flash_pistol.png")
    _copy_png_clean(sp_dir / "DefineSprite_125_muzzle_flash_rifle" / "1.png", fx_dir / "muzzle_flash_rifle.png")
    _copy_png_clean(sp_dir / "DefineSprite_259_muzzle_flash_shotgun" / "2.png", fx_dir / "muzzle_flash_shotgun.png")
    _copy_png_clean(sp_dir / "DefineSprite_274_muzzle_flash_sniper" / "2.png", fx_dir / "muzzle_flash_sniper.png")
    _copy_png_clean(sp_dir / "DefineSprite_1045_muzzle_flash_bazooka" / "2.png", fx_dir / "muzzle_flash_bazooka.png")

    # Shells
    for dst_n, bmp_id, sp_sub in [
        ("shell_small.png", 307, "DefineSprite_309_empty_shell_small/1.png"),
        ("empty_shell_small.png", 307, "DefineSprite_309_empty_shell_small/1.png"),
        ("shell_big.png", 301, "DefineSprite_303_empty_shell_big/1.png"),
        ("empty_shell_big.png", 301, "DefineSprite_303_empty_shell_big/1.png"),
        ("shell_shotgun.png", 304, "DefineSprite_306_empty_shell_shotgun/1.png"),
        ("empty_shell_shotgun.png", 304, "DefineSprite_306_empty_shell_shotgun/1.png"),
    ]:
        src_b = _find_bitmap_file(bmp_id)
        if not src_b.exists():
            src_b = sp_dir / sp_sub
        if _copy_png_clean(src_b, fx_dir / dst_n):
            copied += 1

    # Melee traces (trace_axe_01..03, trace_machete_01..03, trace_sword_01..03)
    for dst_n, sp_sub in [
        ("trace_axe_01.png", "DefineSprite_751_trace_axe_01/1.png"),
        ("trace_axe_02.png", "DefineSprite_754_trace_axe_02/1.png"),
        ("trace_axe_03.png", "DefineSprite_757_trace_axe_03/1.png"),
        ("trace_machete_01.png", "DefineSprite_760_trace_machete_01/1.png"),
        ("trace_machete_02.png", "DefineSprite_763_trace_machete_02/1.png"),
        ("trace_machete_03.png", "DefineSprite_766_trace_machete_03/1.png"),
        ("trace_sword_01.png", "DefineSprite_769_trace_sword_01/1.png"),
        ("trace_sword_02.png", "DefineSprite_772_trace_sword_02/1.png"),
        ("trace_sword_03.png", "DefineSprite_775_trace_sword_03/1.png"),
    ]:
        if _copy_png_clean(sp_dir / sp_sub, fx_dir / dst_n):
            copied += 1

    # Hit metal, electric, blood, player_aim, lazersight, glass_shard
    metal_frames = [
        sp_dir / "DefineSprite_556_hit_metal_1_1" / "1.png",
        sp_dir / "DefineSprite_559_hit_metal_1_2" / "1.png",
        sp_dir / "DefineSprite_562_hit_metal_2_1" / "1.png",
        sp_dir / "DefineSprite_565_hit_metal_2_2" / "1.png",
        sp_dir / "DefineSprite_568_hit_metal_3_1" / "1.png",
        sp_dir / "DefineSprite_1073_bullet_impact" / "1.png",
    ]
    for i, mp in enumerate(metal_frames, 1):
        if _copy_png_clean(mp, fx_dir / f"hit_metal_f{i:02d}.png"):
            copied += 1
    copy_seq("DefineSprite_1073_bullet_impact", "bullet_impact_", 3, 2, start_src=1)

    elec_frames = [
        sp_dir / "DefineSprite_1098_electric_1" / "1.png",
        sp_dir / "DefineSprite_1101_electric_2" / "1.png",
        sp_dir / "DefineSprite_1104_electric_3" / "1.png",
    ]
    for i in range(1, 10):
        ep = elec_frames[(i - 1) % len(elec_frames)]
        if _copy_png_clean(ep, fx_dir / f"electric_f{i:02d}.png"):
            copied += 1
    for i, ep in enumerate(elec_frames, 1):
        _copy_png_clean(ep, fx_dir / f"electric_{i}.png")

    _copy_png_clean(sp_dir / "DefineSprite_891_player_aim" / "1.png", fx_dir / "player_aim.png")
    _copy_png_clean(sp_dir / "DefineSprite_245_lazersight" / "1.png", fx_dir / "lazersight.png")
    _copy_png_clean(sp_dir / "DefineSprite_1055_glass_shard_1" / "1.png", fx_dir / "glass_shard_1.png")
    _copy_png_clean(sp_dir / "DefineSprite_1055_glass_shard_1" / "1.png", fx_dir / "glass_shard.png")
    _copy_png_clean(sp_dir / "DefineSprite_571_blood_1" / "1.png", fx_dir / "blood_1.png")
    _copy_png_clean(sp_dir / "DefineSprite_574_blood_2" / "1.png", fx_dir / "blood_2.png")
    _copy_png_clean(sp_dir / "DefineSprite_577_blood_3" / "1.png", fx_dir / "blood_3.png")

    # 4. Prop Debris & Damaged Prop Frames (assets/sprites/props/ and assets/sprites/effects/)
    debris_map = [
        ("debris_crate_01.png", 140, "DefineSprite_142_crate_debris_01/1.png"),
        ("debris_crate_02.png", 8, "DefineSprite_10_crate_debris_02/1.png"),
        ("debris_crate_03.png", 5, "DefineSprite_7_crate_debris_03/1.png"),
        ("crate_debris_01.png", 140, "DefineSprite_142_crate_debris_01/1.png"),
        ("crate_debris_02.png", 8, "DefineSprite_10_crate_debris_02/1.png"),
        ("crate_debris_03.png", 5, "DefineSprite_7_crate_debris_03/1.png"),
        ("debris_barrel_01.png", 163, "DefineSprite_165_barrel_debris_01/1.png"),
        ("debris_barrel_02.png", 166, "DefineSprite_168_barrel_debris_02/1.png"),
        ("debris_barrel_03.png", 169, "DefineSprite_171_barrel_debris_03/1.png"),
        ("barrel_debris_01.png", 163, "DefineSprite_165_barrel_debris_01/1.png"),
        ("barrel_debris_02.png", 166, "DefineSprite_168_barrel_debris_02/1.png"),
        ("barrel_debris_03.png", 169, "DefineSprite_171_barrel_debris_03/1.png"),
        ("debris_table_01.png", 204, "DefineSprite_206_table_debris_01/1.png"),
        ("debris_table_02.png", 207, "DefineSprite_209_table_debris_02/1.png"),
        ("debris_table_03.png", 210, "DefineSprite_212_table_debris_03/1.png"),
        ("table_debris_01.png", 204, "DefineSprite_206_table_debris_01/1.png"),
        ("table_debris_02.png", 207, "DefineSprite_209_table_debris_02/1.png"),
        ("table_debris_03.png", 210, "DefineSprite_212_table_debris_03/1.png"),
        ("debris_paper_01.png", 1617, "DefineSprite_1628_hit_paper/1.png"),
        ("debris_paper_02.png", 1620, "DefineSprite_1628_hit_paper/12.png"),
        ("debris_paper_03.png", 1622, "DefineSprite_1628_hit_paper/24.png"),
        ("debris_paper_04.png", 1625, "DefineSprite_1628_hit_paper/36.png"),
    ]
    for dst_n, bmp_id, sp_sub in debris_map:
        src_p = _find_bitmap_file(bmp_id)
        if not src_p.exists():
            src_p = sp_dir / sp_sub
        if _copy_png_clean(src_p, pr_dir / dst_n):
            copied += 1
        _copy_png_clean(src_p, fx_dir / dst_n)

    # Damaged prop states
    for dst_n, sp_sub in [
        ("obj_barrel_dmg.png", "DefineSprite_129_barrel_01/2.png"),
        ("obj_gascan_dmg.png", "DefineSprite_745_gascan/2.png"),
        ("obj_hanging_lamp_off.png", "DefineSprite_1613_hanging_lamp/2.png"),
        ("obj_beachball_dmg.png", "DefineSprite_590_beachball/2.png"),
    ]:
        if _copy_png_clean(sp_dir / sp_sub, pr_dir / dst_n):
            copied += 1

    return copied


def copy_all_assets(sym_map: dict) -> dict:
    """Copies sheets, maps, sprites (weapons, props, effects, ui), 73 sounds, and 3 fonts."""
    stats = {"sheets": 0, "maps": 0, "sprites": 0, "sounds": 0, "fonts": 0}

    # 1. Character & Blood Sheets (600x400)
    sheet_bitmaps = [
        "Bitmap 591.png",   # Johnny
        "Bitmap 312.png",   # Boris
        "Bitmap 900.png",   # player_blood (in XFL) / Agent alias
        "Bitmap 1105.png",  # Agent
        "Bitmap 1315.png",  # Billy / Savage
        "Bitmap 1456.png",  # Scott / Cruger
        "Bitmap 1629.png",  # Funnyman / Ivan
        "Bitmap 1770.png",  # Mac / Brody
        "Bitmap 1911.png",  # Jeff / Mac
    ]
    for bname in sheet_bitmaps:
        src = LIBRARY_DIR / bname
        if src.exists():
            shutil.copy2(src, ASSETS_DIR / "sheets" / bname)
            stats["sheets"] += 1

    # Create the prompt's alias sheet files as valid 600x400 sheets so all 11 filenames exist
    alias_sheets = {
        "Bitmap 729.png": "Bitmap 900.png",    # player_blood alias
        "Bitmap 755.png": "Bitmap 1105.png",   # Hideki 600x400 sheet
        "Bitmap 1044.png": "Bitmap 591.png",   # Blaire 600x400 sheet
    }
    for dst_name, src_name in alias_sheets.items():
        src = LIBRARY_DIR / src_name
        dst = ASSETS_DIR / "sheets" / dst_name
        if src.exists():
            shutil.copy2(src, dst)
            stats["sheets"] += 1

    # 2. Map Bitmaps
    map_bitmaps = [
        "Bitmap 102.png",
        "Bitmap 2205.png",
        "Bitmap 2208.png",
        "Bitmap 2209.png",
        "Bitmap 2210.png",
        "Bitmap 2212.png",
        "Bitmap 2213.png",
        "Bitmap 2215.png",
        "Bitmap 2217.png",
        "Bitmap 2219.png",
        "Bitmap 2221.png",
        "Bitmap 2223.png",
        "Bitmap 2224.png",
        "Bitmap 2225.png",
        "Bitmap 2226.png",
        "Bitmap 2227.png",
        "Bitmap 2228.png",
        "Bitmap 2229.png",
        "Bitmap 2231.png",
        "Bitmap 2233.png",
        "Bitmap 2451.png",
        "Bitmap 2482.png",
    ]
    for bname in map_bitmaps:
        src = LIBRARY_DIR / bname
        if src.exists():
            shutil.copy2(src, ASSETS_DIR / "maps" / bname)
            stats["maps"] += 1

    # Shifted JPEXS map bitmap aliases referenced in prompt
    map_aliases = {
        "Bitmap 1933.png": "Bitmap 2212.png",
        "Bitmap 1934.png": "Bitmap 2213.png",
        "Bitmap 1936.png": "Bitmap 2215.png",
        "Bitmap 1938.png": "Bitmap 2217.png",
        "Bitmap 1940.png": "Bitmap 2219.png",
        "Bitmap 1942.png": "Bitmap 2221.png",
        "Bitmap 1950.png": "Bitmap 2231.png",
        "Bitmap 1952.png": "Bitmap 2233.png",
        "Bitmap 2166.png": "Bitmap 2451.png",
        "Bitmap 2195.png": "Bitmap 2482.png",
    }
    for dst_name, src_name in map_aliases.items():
        src = LIBRARY_DIR / src_name
        if src.exists():
            shutil.copy2(src, ASSETS_DIR / "maps" / dst_name)
            stats["maps"] += 1

    # 3. Sprites (weapons, props, effects, UI) from linkage symbols in LIBRARY
    for existing_png in (ASSETS_DIR / "sprites").rglob("*.png"):
        try:
            with existing_png.open("rb") as f:
                if f.read(8) != b"\x89PNG\r\n\x1a\n":
                    existing_png.unlink()
                    imp_file = existing_png.with_name(existing_png.name + ".import")
                    if imp_file.exists():
                        imp_file.unlink()
        except Exception:
            pass

    for xml_file in sorted(LIBRARY_DIR.glob("Symbol *.xml")):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
        except Exception:
            continue
        linkage = root.attrib.get("linkageClassName", "")
        if not linkage:
            continue
        sym_name = root.attrib.get("name", xml_file.stem)
        bmp_name = extract_symbol_first_bitmap(sym_name)
        if not bmp_name:
            continue
        src_bmp = LIBRARY_DIR / bmp_name
        if not src_bmp.exists():
            continue
        try:
            with src_bmp.open("rb") as f:
                if f.read(8) != b"\x89PNG\r\n\x1a\n":
                    continue
        except Exception:
            continue

        if linkage.startswith("wpn_"):
            sub = ASSETS_DIR / "sprites" / "weapons"
        elif linkage.startswith("obj_") or linkage in ("window_seg", "gibs"):
            sub = ASSETS_DIR / "sprites" / "props"
        elif linkage in ("MenuBackground", "IngameInterface", "GameLogo", "cursor_mc"):
            sub = ASSETS_DIR / "sprites" / "ui"
        else:
            sub = ASSETS_DIR / "sprites" / "effects"

        shutil.copy2(src_bmp, sub / f"{linkage}.png")
        shutil.copy2(src_bmp, sub / bmp_name)
        stats["sprites"] += 1

    # Copy verified 1:1 XFL prop bitmaps to assets/sprites/props/
    prop_bitmap_map = {
        "obj_crate_01.png": "Bitmap 130.png",
        "crate_01.png": "Bitmap 130.png",
        "obj_crate_hanging.png": "Bitmap 1.png",
        "crate_hanging.png": "Bitmap 1.png",
        "obj_crate_hanging_holder.png": "Bitmap 1065.png",
        "crate_hanging_holder.png": "Bitmap 1065.png",
        "obj_barrel.png": "Bitmap 155.png",
        "barrel_01.png": "Bitmap 155.png",
        "obj_barrel_explosive.png": "Bitmap 126.png",
        "barrel_02.png": "Bitmap 126.png",
        "obj_barrel_wreck.png": "Bitmap 160.png",
        "barrel_03.png": "Bitmap 160.png",
        "obj_gascan.png": "Bitmap 741.png",
        "gascan.png": "Bitmap 741.png",
        "obj_table.png": "Bitmap 201.png",
        "obj_table_01.png": "Bitmap 201.png",
        "table_01.png": "Bitmap 201.png",
        "obj_table_small.png": "Bitmap 2056.png",
        "table_small_01.png": "Bitmap 2056.png",
        "obj_desk.png": "Bitmap 1603.png",
        "desk.png": "Bitmap 1603.png",
        "obj_desk_1.png": "Bitmap 1606.png",
        "desk_1.png": "Bitmap 1606.png",
        "obj_chair.png": "Bitmap 746.png",
        "obj_chair_01.png": "Bitmap 746.png",
        "chair.png": "Bitmap 746.png",
        "obj_comfy_chair.png": "Bitmap 1062.png",
        "comfy_chair.png": "Bitmap 1062.png",
        "obj_filecab.png": "Bitmap 133.png",
        "filecab_01.png": "Bitmap 133.png",
        "obj_comp.png": "Bitmap 1597.png",
        "comp.png": "Bitmap 1597.png",
        "obj_comp_screen.png": "Bitmap 1600.png",
        "comp_screen.png": "Bitmap 1600.png",
        "obj_paper.png": "Bitmap 1614.png",
        "paper.png": "Bitmap 1614.png",
        "obj_lamp_1.png": "Bitmap 1056.png",
        "lamp_1.png": "Bitmap 1056.png",
        "obj_lift_01.png": "Bitmap 1047.png",
        "lift_01.png": "Bitmap 1047.png",
        "obj_lift_small_01.png": "Bitmap 1312.png",
        "lift_small_01.png": "Bitmap 1312.png",
        "obj_windmill_propeller.png": "Bitmap 2052.png",
        "windmill_propeller.png": "Bitmap 2052.png",
    }
    for p_file, bmp_name in prop_bitmap_map.items():
        src_p = LIBRARY_DIR / bmp_name
        target_p = ASSETS_DIR / "sprites" / "props" / p_file
        if src_p.exists():
            shutil.copyfile(src_p, target_p)
            imp_p = target_p.with_name(target_p.name + ".import")
            if imp_p.exists():
                imp_p.unlink()
            bmp_target = ASSETS_DIR / "sprites" / "props" / bmp_name
            shutil.copyfile(src_p, bmp_target)
            imp_b = bmp_target.with_name(bmp_target.name + ".import")
            if imp_b.exists():
                imp_b.unlink()

    # Copy curated multi-frame effect sequences & damaged/debris prop sprites
    curated_count = copy_curated_sprites()
    stats["sprites"] += curated_count

    # 4. Sounds (all 72 MP3 files + 1 WAV in full-ffdec-575163/sounds/)
    for snd_file in sorted(SOUNDS_DIR.glob("*")):
        if snd_file.suffix.lower() not in (".mp3", ".wav"):
            continue
        m = re.match(r"^\d+_(.+)$", snd_file.name)
        clean_name = m.group(1) if m else snd_file.name
        shutil.copy2(snd_file, ASSETS_DIR / "sounds" / clean_name)
        stats["sounds"] += 1

    # Create standard aliases so both Sounds.as linkage names and CamelCase aliases resolve
    sound_aliases = {
        "Ak47_1.mp3": "rifle00.mp3",
        "Ak47_2.mp3": "rifle01.mp3",
        "Punch1.mp3": "punch00.mp3",
        "Punch2.mp3": "punch01.mp3",
        "Punch3.mp3": "punch02.mp3",
        "Punch4.mp3": "punch03.mp3",
        "SfxExplosion1.mp3": "explosion00.mp3",
        "SfxExplosion2.mp3": "explosion01.mp3",
        "SfxExplosion3.mp3": "explosion02.mp3",
        "Music1.mp3": "superfighters_theme.mp3",
        "Pistol1.mp3": "gun00.mp3",
        "Pistol2.mp3": "gun01.mp3",
        "Magnum1.mp3": "magnum.mp3",
        "Uzi1.mp3": "uzi00.mp3",
        "Uzi2.mp3": "uzi01.mp3",
        "Shotgun1.mp3": "shotgun00.mp3",
        "Shotgun2.mp3": "shotgun01.mp3",
        "ShotgunPump.mp3": "shotgun_pump_p1.mp3",
        "Sniper1.mp3": "sniper00.mp3",
        "Sniper2.mp3": "sniper01.mp3",
        "Bazooka1.mp3": "bazooka.mp3",
        "SwingSword1.mp3": "svisch4.mp3",
        "SwingAxe1.mp3": "svisch6.mp3",
        "SwingMachete1.mp3": "svisch4.mp3",
        "SwordHit1.mp3": "cut00.mp3",
        "SwordHit2.mp3": "cut01.mp3",
        "SwordHit3.mp3": "cut02.mp3",
        "Powerup.mp3": "getHealth_00.mp3",
        "DryFire1.mp3": "outofammo_light.mp3",
        "DryFire2.mp3": "outofammo_heavy.mp3",
        "GrenadePin.mp3": "grenade_safe.mp3",
    }
    for alias_name, target_name in sound_aliases.items():
        src_snd = ASSETS_DIR / "sounds" / target_name
        if src_snd.exists():
            shutil.copy2(src_snd, ASSETS_DIR / "sounds" / alias_name)

    # 5. Fonts (all TTF files in 06-fonts/ + required aliases)
    for ttf_file in sorted(FONTS_DIR.glob("*.ttf")):
        shutil.copy2(ttf_file, ASSETS_DIR / "fonts" / ttf_file.name)
        m = re.match(r"^\d+_(.+)\.ttf$", ttf_file.name)
        if m:
            clean_font = m.group(1).replace(" ", "_") + ".ttf"
            shutil.copy2(ttf_file, ASSETS_DIR / "fonts" / clean_font)
        stats["fonts"] += 1

    font_aliases = {
        "12_PF Arma Five.ttf": "106_04b03.ttf",
        "31_Capture it.ttf": "61_Arial Black.ttf",
        "530_PF Tempesta Seven.ttf": "33_Verdana.ttf",
    }
    for alias_font, src_font in font_aliases.items():
        src_f = FONTS_DIR / src_font
        if src_f.exists():
            shutil.copy2(src_f, ASSETS_DIR / "fonts" / alias_font)

    return stats


def main() -> None:
    print("[SF-M1] Starting XFL & AS3 Offline Asset Compiler...")
    ensure_dirs()
    sym_map = parse_symbols_csv()
    asset_stats = copy_all_assets(sym_map)
    print(f"[SF-M1] Copied assets: {asset_stats}")

    rigs_data = compile_rigs()
    rigs_path = DATA_DIR / "sf_compiled_rigs.json"
    rigs_path.write_text(json.dumps(rigs_data, indent=2), encoding="utf-8")
    print(f"[SF-M1] Compiled {rigs_path.name}: {rigs_data['state_count']} states, {len(rigs_data['characters'])} character entries")

    weapons_data = compile_weapons()
    weapons_path = DATA_DIR / "sf_compiled_weapons.json"
    weapons_path.write_text(json.dumps(weapons_data, indent=2), encoding="utf-8")
    print(f"[SF-M1] Compiled {weapons_path.name}: {weapons_data['weapon_count']} weapon/powerup definitions")

    maps_data = compile_maps()
    maps_path = DATA_DIR / "sf_compiled_maps.json"
    maps_path.write_text(json.dumps(maps_data, indent=2), encoding="utf-8")
    print(f"[SF-M1] Compiled {maps_path.name}: {maps_data['map_count']} maps")
    print("[SF-M1] Offline compilation complete!")


if __name__ == "__main__":
    main()

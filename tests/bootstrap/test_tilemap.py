#!/usr/bin/env python3
"""R5-WP2: TileSet/TileMapLayer/terrain workflow.

Does not tick the 20-8 plan. G2 is not involved. Pin missing is a hard FAIL.
No skip-PASS. No dummy screenshot PNG. Do not paper-ACK play.start.
Do not raw-edit .tscn cell bytes. Plugin is the only writer.

Verify (encoded here; this file is the official harness):
  - create scene + TileSet + atlas source + TileMapLayer
  - paint / fill / stamp with engine get_cell_source_id / get_cell_atlas_coords
  - 100x100 via chunks + paged query (never 10k cells in one after)
  - one UndoRedo stroke (fill/stamp/cell-chunk), Agent: prefix
  - save/reopen hash
  - terrain.connect via TileMapLayer.set_cells_terrain_connect
  - collision shapes readable in editor (TileData polygons), not Play

Honest Alternative: PlaceholderTexture2D / generated atlas stands in for
missing painted tile art. Collision playtest is editor-side layer/shape
readback, not a Play process. screenshots=SKIP.

Generated plugin-validator.json / mcp-tools.json are coordinator-owned
(`npm run generate`). This WP registers verbs in actions.json + the live
TypeScript catalog. No extra codegen pipeline.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r5w2"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
SCREENSHOTS = "SKIP"
TILEMAP_MUTATES = (
    "tilemap.tileset",
    "tilemap.source",
    "tilemap.terrain",
    "tilemap.layer",
    "tilemap.cell",
    "tilemap.fill",
    "tilemap.stamp",
)
TILEMAP_VERBS = ("tileset", "source", "terrain", "layer", "cell", "fill", "stamp", "query")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R5-WP2 [ ] while unticked; after coordinator tick allow R5-WP3+."""
    errors: list[str] = []
    current = ""
    wp2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R5-WP2\b", stripped):
            wp2 = stripped
    if wp2 is None:
        return ["plan missing R5-WP2 heading"]
    ticked = bool(re.search(r"\[x\]", wp2, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp2:
            errors.append("R5-WP2 heading must keep [ ] until coordinator tick")
        if current != "R5-WP2":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP2 while WP2 is unticked)")
    elif not re.match(r"^R5-WP([3-9]|\d{2,})$|^R[6-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP3+ after R5-WP2 tick)")
    return errors


def cleanup_temp() -> None:
    if TEMP_DIR.is_dir():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass


def variant(typ: str, value) -> dict:
    return {"schema": SCHEMA, "type": typ, "value": value}


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png)", self_text):
        errors.append("official test writes a .tscn/.tres/.png path directly")
    if re.search(r"\.write_bytes\(|Image\.new\b", self_text):
        errors.append("official test must not bless dummy screenshot PNGs")
    if "screenshots=SKIP" not in self_text and 'SCREENSHOTS = "SKIP"' not in self_text:
        errors.append("official test must record screenshots=SKIP")
    if "Alternative" not in self_text:
        errors.append("official test must record PlaceholderTexture2D / Play Alternatives honestly")
    if "play.start" in self_text and "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK play.start")
    if "get_cell_source_id" not in self_text or "get_cell_atlas_coords" not in self_text:
        errors.append("official test must encode engine cell readback")
    if "PlaceholderTexture2D" not in self_text:
        errors.append("official test must name PlaceholderTexture2D as the missing-art Alternative")
    if "set_cells_terrain_connect" not in self_text:
        errors.append("official test must encode terrain.connect")
    if "100x100" not in self_text and "w=100" not in self_text:
        errors.append("official test must encode 100x100 paging")
    if "g2_" + "signed" in self_text or "G2" + " VISIBLE" in self_text:
        errors.append("official test must stay independent of the visible gate")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_tilemap_adapter" not in router:
        errors.append("router must dispatch through hh_tilemap_adapter")
    if "godot.tilemap" not in router:
        errors.append("router must name godot.tilemap")
    if 'action == "query"' not in router:
        errors.append("router must keep tilemap.query on the read adapter")

    adapter = ADDON / "core" / "hh_tilemap_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_tilemap_adapter.gd")
    else:
        text = adapter.read_text(encoding="utf-8")
        if "get_cell_source_id" not in text or "get_cell_atlas_coords" not in text:
            errors.append("tilemap adapter must use engine get_cell_source_id/get_cell_atlas_coords")
        if "TileMapLayer" not in text or "TileSetAtlasSource" not in text:
            errors.append("tilemap adapter must use TileMapLayer / TileSetAtlasSource")
        if "create_tile" not in text or "texture_region_size" not in text:
            errors.append("tilemap adapter must use TileSetAtlasSource.create_tile / texture_region_size")
        if "set_cells_terrain_connect" not in text:
            errors.append("tilemap adapter must implement terrain connect")
        if "UNDO_ACTION_PREFIX" not in text or "create_action" not in text:
            errors.append("tilemap adapter must use one Agent UndoRedo action per stroke")
        if re.search(r"\bcallv\b", text) or "Object.call" in text or "evaluate_expression" in text:
            errors.append("tilemap adapter has a generic invoke path")
        if "Vector2(32, 32)" in text:
            errors.append("tilemap adapter must not invent a 32px box")
        if "plugin-validator" not in text and "coordinator" not in text:
            errors.append("tilemap adapter must note coordinator-owned generated catalog")

    reads = (ADDON / "core" / "hh_read_adapters.gd").read_text(encoding="utf-8")
    if "func _tilemap_query" not in reads:
        errors.append("tilemap.query read adapter missing")
    if "get_cell_source_id" not in reads or "get_cell_atlas_coords" not in reads:
        errors.append("tilemap.query must keep engine cell readback")
    if "tilemap region exceeds one page" not in reads:
        errors.append("tilemap.query must still refuse an unpaged 100x100 dump")

    if not ACTIONS_JSON.is_file():
        errors.append("missing actions.json")
    else:
        catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8"))
        actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
        for action_id, method, verb in (
            ("tilemap.tileset", "godot.tilemap", "tileset"),
            ("tilemap.source", "godot.tilemap", "source"),
            ("tilemap.terrain", "godot.tilemap", "terrain"),
            ("tilemap.layer", "godot.tilemap", "layer"),
            ("tilemap.cell", "godot.tilemap", "cell"),
            ("tilemap.fill", "godot.tilemap", "fill"),
            ("tilemap.stamp", "godot.tilemap", "stamp"),
            ("tilemap.query", "godot.tilemap", "query"),
        ):
            spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
            if spec.get("method") != method or spec.get("verb") != verb:
                errors.append(f"actions.json missing {action_id}")

    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "TILEMAP_APPLY" not in lifecycle or "isTilemapApply" not in lifecycle:
        errors.append("scene_lifecycle must export TILEMAP_APPLY / isTilemapApply")
    if "isTilemapApply(actionId)" not in lifecycle:
        errors.append("isProvenEditorApply must include isTilemapApply")
    for action_id in TILEMAP_MUTATES:
        if action_id not in lifecycle:
            errors.append(f"isProvenEditorApply must list {action_id}")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function tilemapApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check tilemap apply")
    if "const tilemapFail = tilemapApplyOk" not in execute:
        errors.append("execute.ts must call tilemapApplyOk from applyMutateOnce")
    if "tilemap node_path bind mismatch" not in execute:
        errors.append("execute.ts must bind tilemap node_path")
    if "tilemap.cell atlas bind mismatch" not in execute:
        errors.append("execute.ts must bind cell source_id/atlas")
    if "tilemap.fill cell count mismatch" not in execute:
        errors.append("execute.ts must bind fill item counts")
    if "more than one page of cells" not in execute:
        errors.append("execute.ts must reject a 10k-cell after payload")

    resources = (BRIDGE / "src" / "resources" / "mcp_resources.ts").read_text(encoding="utf-8")
    if 'isTilemapApply(def.id)' not in resources or '"tilemap"' not in resources:
        errors.append("mcp_resources.ts must label tilemap apply as the tilemap adapter")

    validator = json.loads((BRIDGE / "generated" / "plugin-validator.json").read_text(encoding="utf-8"))
    validator_actions = validator.get("actions") if isinstance(validator.get("actions"), dict) else {}
    for action_id, method, verb in (
        ("tilemap.tileset", "godot.tilemap", "tileset"),
        ("tilemap.source", "godot.tilemap", "source"),
        ("tilemap.terrain", "godot.tilemap", "terrain"),
        ("tilemap.layer", "godot.tilemap", "layer"),
        ("tilemap.cell", "godot.tilemap", "cell"),
        ("tilemap.fill", "godot.tilemap", "fill"),
        ("tilemap.stamp", "godot.tilemap", "stamp"),
        ("tilemap.query", "godot.tilemap", "query"),
    ):
        spec = validator_actions.get(action_id) if isinstance(validator_actions.get(action_id), dict) else {}
        if spec.get("method") != method or spec.get("verb") != verb:
            errors.append(f"plugin-validator.json missing dotted id {action_id}")

    mcp_tools = json.loads((BRIDGE / "generated" / "mcp-tools.json").read_text(encoding="utf-8"))
    tool_enums: dict[str, list[str]] = {}
    for tool in mcp_tools.get("tools") if isinstance(mcp_tools.get("tools"), list) else []:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "")
        schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        action = props.get("action") if isinstance(props.get("action"), dict) else {}
        enum = action.get("enum") if isinstance(action.get("enum"), list) else []
        tool_enums[name] = [str(item) for item in enum]
    domain = tool_enums.get("godot.tilemap", [])
    for verb in TILEMAP_VERBS:
        if verb not in domain:
            errors.append(f"mcp-tools.json godot.tilemap must enum {verb}")
    if "godot.tilemap" not in tool_enums:
        errors.append("mcp-tools.json must expose godot.tilemap as a domain tool")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if re.search(r"\bcallv\b", blob) or "evaluate_expression" in blob:
            errors.append(f"{posix} has a generic invoke path")
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 45.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 45.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(proc, req_id, method, {"action": action, "params": params, "command_id": cid}, timeout)
    return req_id + 1, body_of(resp)


def ack_ok(body: dict, errors: list[str], verb: str) -> bool:
    if body.get("ok") is not True:
        errors.append(f"{verb} must ACK: {body}")
        return False
    post = body.get("postcondition") or {}
    if post.get("verified") is not True or not post.get("checks"):
        errors.append(f"{verb} paper postcondition: {body}")
        return False
    return True


def expect_unverified(body: dict, errors: list[str], label: str) -> None:
    got = str((body.get("error") or {}).get("code") or "")
    if body.get("ok") is True or got != "E_UNVERIFIED":
        errors.append(f"{label} expected E_UNVERIFIED, got {body}")


def cell_of(query_body: dict, x: int, y: int) -> dict | None:
    cells = (query_body.get("after") or {}).get("cells")
    if not isinstance(cells, list):
        return None
    for item in cells:
        if isinstance(item, dict) and int(item.get("x", -1)) == x and int(item.get("y", -1)) == y:
            return item
    return None


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    scene = "res://r5w2/level.tscn"
    tileset = "res://r5w2/tiles.tres"
    tex = "res://r5w2/atlas_tex.tres"
    req_id = 2
    # Honest Alternative: missing painted tile art uses PlaceholderTexture2D.
    # Collision playtest is editor TileData polygon readback, not Play.
    # screenshots=SKIP — do not write a fake PNG. Do not paper-ACK play.start.
    _screenshots = SCREENSHOTS
    try:
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = life.start_godot(exe)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors

        req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
        if not ack_ok(created, errors, "scene.create"):
            return errors

        req_id, ground = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "TileMapLayer", "name": "Ground"},
        )
        if not ack_ok(ground, errors, "node.add Ground TileMapLayer"):
            return errors

        req_id, tex_created = tool_call(
            proc, req_id, "godot.resource", "create", {"path": tex, "class_name": "PlaceholderTexture2D"}
        )
        if not ack_ok(tex_created, errors, "resource.create PlaceholderTexture2D"):
            return errors
        req_id, tex_sized = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {"path": tex, "property": "size", "value": variant("Vector2", {"x": 32, "y": 16})},
        )
        if not ack_ok(tex_sized, errors, "resource.edit PlaceholderTexture2D.size"):
            return errors

        req_id, set_created = tool_call(
            proc, req_id, "godot.resource", "create", {"path": tileset, "class_name": "TileSet"}
        )
        if not ack_ok(set_created, errors, "resource.create TileSet"):
            return errors

        req_id, sourced = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "source",
            {
                "tileset": tileset,
                "source_id": 0,
                "texture": tex,
                "op": "add",
                "texture_region_size": 16,
                "create_tiles": True,
                "collision": True,
            },
        )
        if not ack_ok(sourced, errors, "tilemap.source"):
            return errors
        src_after = sourced.get("after") or {}
        if src_after.get("has_source") is not True or int(src_after.get("tile_count") or 0) < 1:
            errors.append(f"tilemap.source tile_count/has_source: {src_after}")
        if src_after.get("source_id") != 0:
            errors.append(f"tilemap.source source_id bind: {src_after}")
        collision = src_after.get("collision") if isinstance(src_after.get("collision"), dict) else {}
        if collision.get("invented_box") is True:
            errors.append(f"collision invented a box: {collision}")
        if collision.get("size_source") not in ("texture_region_size", "tile_size"):
            errors.append(f"collision size_source must be engine tile size: {collision}")
        tiles = collision.get("tiles") if isinstance(collision.get("tiles"), list) else []
        if not tiles or int((tiles[0] or {}).get("polygon_count") or 0) < 1:
            errors.append(f"editor collision polygons missing: {collision}")
        if len((tiles[0] or {}).get("points") or []) < 3:
            errors.append(f"editor collision polygon points missing: {collision}")

        req_id, assigned = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "tileset",
            {
                "scene": scene,
                "node_path": "Ground",
                "tileset": tileset,
                "op": "assign",
                "tile_size": 16,
                "physics_layers": 1,
                "navigation_layers": 1,
                "occlusion_layers": 1,
            },
        )
        if not ack_ok(assigned, errors, "tilemap.tileset"):
            return errors
        set_after = assigned.get("after") or {}
        if set_after.get("node_path") != "Ground" or set_after.get("tileset") != tileset:
            errors.append(f"tilemap.tileset bind: {set_after}")
        if int(set_after.get("physics_layers") or 0) < 1:
            errors.append(f"physics layer missing: {set_after}")

        req_id, configured = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "layer",
            {"scene": scene, "node_path": "Ground", "enabled": True, "op": "configure"},
        )
        if not ack_ok(configured, errors, "tilemap.layer configure"):
            return errors
        if (configured.get("after") or {}).get("class_name") != "TileMapLayer":
            errors.append(f"tilemap.layer class: {configured}")

        req_id, overlay = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "layer",
            {
                "scene": scene,
                "node_path": "Walls",
                "enabled": True,
                "op": "add",
                "name": "Walls",
                "parent": ".",
            },
        )
        if not ack_ok(overlay, errors, "tilemap.layer add"):
            return errors
        req_id, reordered = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "layer",
            {"scene": scene, "node_path": "Walls", "enabled": True, "op": "reorder", "index": 0},
        )
        if not ack_ok(reordered, errors, "tilemap.layer reorder"):
            errors.append(f"tilemap.layer reorder: {reordered}")

        req_id, painted = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "cell",
            {
                "scene": scene,
                "node_path": "Ground",
                "x": 1,
                "y": 1,
                "source_id": 0,
                "atlas_x": 0,
                "atlas_y": 0,
            },
        )
        if not ack_ok(painted, errors, "tilemap.cell"):
            return errors
        cell_after = painted.get("after") or {}
        if cell_after.get("readback_equals") is not True:
            errors.append(f"tilemap.cell readback: {cell_after}")
        if cell_after.get("source_id") != 0 or cell_after.get("atlas_x") != 0:
            errors.append(f"tilemap.cell atlas bind: {cell_after}")
        if not str(painted.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"tilemap.cell missing Agent undo: {painted}")

        req_id, filled = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "fill",
            {
                "scene": scene,
                "node_path": "Ground",
                "x": 0,
                "y": 0,
                "w": 8,
                "h": 8,
                "source_id": 0,
                "atlas_x": 0,
                "atlas_y": 0,
            },
        )
        if not ack_ok(filled, errors, "tilemap.fill 8x8"):
            return errors
        fill_after = filled.get("after") or {}
        if fill_after.get("cell_count") != 64 or fill_after.get("compact") is not True:
            errors.append(f"tilemap.fill compact payload: {fill_after}")
        if isinstance(fill_after.get("cells"), list) and len(fill_after["cells"]) > 16:
            errors.append("tilemap.fill after must not dump the full region")
        if "tilemap.fill" not in str(filled.get("undo_action") or ""):
            errors.append(f"fill must be one Agent UndoRedo: {filled}")

        req_id, stamped = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "stamp",
            {
                "scene": scene,
                "node_path": "Ground",
                "x": 2,
                "y": 2,
                "pattern": "tree_clump",
                "source_id": 0,
                "atlas_x": 1,
                "atlas_y": 0,
            },
        )
        if not ack_ok(stamped, errors, "tilemap.stamp tree_clump"):
            return errors
        stamp_after = stamped.get("after") or {}
        if stamp_after.get("pattern") != "tree_clump" or int(stamp_after.get("cell_count") or 0) < 4:
            errors.append(f"tilemap.stamp item count: {stamp_after}")

        req_id, q8 = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 0, "y": 0, "w": 8, "h": 8},
        )
        if not ack_ok(q8, errors, "tilemap.query 8x8"):
            return errors
        if len(((q8.get("after") or {}).get("cells") or [])) != 64:
            errors.append(f"tilemap.query 8x8 cell count: {q8}")
        painted_cell = cell_of(q8, 2, 2)
        if painted_cell is None or int((painted_cell.get("atlas") or {}).get("x") or -1) != 1:
            errors.append(f"stamp readback via get_cell_atlas_coords: {painted_cell}")

        req_id, big = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "fill",
            {
                "scene": scene,
                "node_path": "Ground",
                "x": 0,
                "y": 0,
                "w": 100,
                "h": 100,
                "source_id": 0,
                "atlas_x": 0,
                "atlas_y": 0,
            },
            45.0,
        )
        if not ack_ok(big, errors, "tilemap.fill 100x100"):
            return errors
        big_after = big.get("after") or {}
        if big_after.get("cell_count") != 10000 or big_after.get("compact") is not True:
            errors.append(f"100x100 fill must stay compact: {big_after}")
        if isinstance(big_after.get("cells"), list):
            errors.append("100x100 fill after must not include a cells array")
        if len(json.dumps(big_after.get("samples") or [])) > 4000:
            errors.append("100x100 fill samples payload too large")

        req_id, unpaged = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 0, "y": 0, "w": 100, "h": 100},
        )
        expect_unverified(unpaged, errors, "100x100 query without page")

        req_id, page0 = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {
                "scene": scene,
                "node_path": "Ground",
                "x": 0,
                "y": 0,
                "w": 100,
                "h": 100,
                "offset": 0,
                "limit": 100,
            },
        )
        if not ack_ok(page0, errors, "tilemap.query 100x100 page 0"):
            return errors
        page_after = page0.get("after") or {}
        if len(page_after.get("cells") or []) != 100:
            errors.append(f"paged query must return one page: {page_after}")
        if page_after.get("total") != 10000 or page_after.get("truncated") is not True:
            errors.append(f"paged query must report total 10000: {page_after}")
        if int(page_after.get("next_offset") or 0) != 100:
            errors.append(f"paged query next_offset: {page_after}")

        req_id, corner = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 99, "y": 99, "w": 1, "h": 1},
        )
        if ack_ok(corner, errors, "tilemap.query 99,99"):
            far = cell_of(corner, 99, 99)
            if far is None or int(far.get("source_id", -2)) != 0:
                errors.append(f"100x100 corner engine readback: {corner}")

        req_id, undone = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(undone, errors, "node.undo after 100x100 fill"):
            errors.append(f"one-undo after fill must ACK: {undone}")
        req_id, after_undo = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 50, "y": 50, "w": 1, "h": 1},
        )
        if ack_ok(after_undo, errors, "query 50,50 after undo"):
            mid = cell_of(after_undo, 50, 50)
            if mid is None or int(mid.get("source_id") or 0) != -1:
                errors.append(f"one UndoRedo fill undo did not restore empty cell: {after_undo}")
        req_id, stamp_back = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 2, "y": 2, "w": 1, "h": 1},
        )
        if ack_ok(stamp_back, errors, "query stamp after undo"):
            back = cell_of(stamp_back, 2, 2)
            if back is None or int((back.get("atlas") or {}).get("x") or -1) != 1:
                errors.append(f"undo restored stamp via get_cell_atlas_coords: {stamp_back}")
        req_id, redone = tool_call(proc, req_id, "godot.node", "redo", {"scene": scene, "count": 1})
        if not ack_ok(redone, errors, "node.redo after 100x100 fill undo"):
            errors.append(f"one-redo after fill undo must ACK: {redone}")
        req_id, after_redo = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 99, "y": 99, "w": 1, "h": 1},
        )
        if ack_ok(after_redo, errors, "query 99,99 after redo"):
            far_redo = cell_of(after_redo, 99, 99)
            if far_redo is None or int(far_redo.get("source_id", -2)) != 0:
                errors.append(f"one UndoRedo fill redo did not restore 100x100 corner: {after_redo}")
        req_id, undone_again = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(undone_again, errors, "node.undo after redo to restore 8x8 level"):
            errors.append(f"second undo after redo must ACK: {undone_again}")

        req_id, terrain = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "terrain",
            {"tileset": tileset, "terrain_name": "dirt", "op": "add"},
        )
        if not ack_ok(terrain, errors, "tilemap.terrain add"):
            return errors
        if (terrain.get("after") or {}).get("terrain_name") != "dirt":
            errors.append(f"terrain name bind: {terrain}")

        req_id, connected = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "terrain",
            {
                "tileset": tileset,
                "terrain_name": "dirt",
                "op": "connect",
                "scene": scene,
                "node_path": "Ground",
                "cells": [{"x": 4, "y": 4}, {"x": 5, "y": 4}, {"x": 6, "y": 4}],
            },
        )
        if not ack_ok(connected, errors, "tilemap.terrain connect"):
            return errors
        conn_after = connected.get("after") or {}
        if int(conn_after.get("cell_count") or 0) != 3:
            errors.append(f"terrain connect cell count: {conn_after}")
        if conn_after.get("connected") is not True:
            errors.append(f"terrain continuity via set_cells_terrain_connect: {conn_after}")
        req_id, tq = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 4, "y": 4, "w": 3, "h": 1},
        )
        if ack_ok(tq, errors, "query terrain line"):
            for x in (4, 5, 6):
                item = cell_of(tq, x, 4)
                if item is None or int(item.get("source_id", -2)) < 0:
                    errors.append(f"terrain cell {x},4 empty after connect: {tq}")
                    break

        req_id, colq = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {
                "scene": scene,
                "node_path": "Ground",
                "x": 0,
                "y": 0,
                "w": 1,
                "h": 1,
                "include_collision": True,
            },
        )
        if not ack_ok(colq, errors, "tilemap.query include_collision"):
            return errors
        col = ((colq.get("after") or {}).get("collision") or {})
        if col.get("ok") is not True or col.get("invented_box") is True:
            errors.append(f"editor collision readback: {col}")
        if int(col.get("physics_layers") or 0) < 1:
            errors.append(f"physics layers not readable in editor: {col}")
        col_tiles = col.get("tiles") if isinstance(col.get("tiles"), list) else []
        if not col_tiles or int((col_tiles[0] or {}).get("polygon_count") or 0) < 1:
            errors.append(f"TileData collision polygons missing: {col}")
        if (col_tiles[0] or {}).get("size_source") not in ("texture_region_size", "tile_size"):
            errors.append(f"collision polygon must use engine tile size: {col}")

        req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved, errors, "scene.save"):
            return errors
        hash_before = str((saved.get("after") or {}).get("disk_hash") or "")
        if len(hash_before) < 16:
            errors.append(f"scene.save missing disk_hash: {saved}")
        req_id, q_before = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 2, "y": 2, "w": 4, "h": 2},
        )
        if not ack_ok(q_before, errors, "query before reload"):
            return errors
        cells_before = (q_before.get("after") or {}).get("cells")

        req_id, reloaded = tool_call(proc, req_id, "godot.scene", "reload", {"path": scene})
        if not ack_ok(reloaded, errors, "scene.reload"):
            return errors
        hash_after = str((reloaded.get("after") or {}).get("disk_hash") or "")
        if hash_before and hash_after and hash_before != hash_after:
            errors.append(f"save/reopen disk_hash drifted: {hash_before} -> {hash_after}")
        req_id, q_after = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 2, "y": 2, "w": 4, "h": 2},
        )
        if not ack_ok(q_after, errors, "query after reload"):
            return errors
        if (q_after.get("after") or {}).get("cells") != cells_before:
            errors.append(f"save/reopen cell hash mismatch: {q_before} vs {q_after}")

        req_id, removed = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "layer",
            {"scene": scene, "node_path": "Walls", "enabled": True, "op": "remove"},
        )
        if not ack_ok(removed, errors, "tilemap.layer remove"):
            errors.append(f"tilemap.layer remove: {removed}")

        if _screenshots != "SKIP":
            errors.append("tilemap screenshot Alternative must stay screenshots=SKIP")
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live tilemap failed: {type(exc).__name__}: {exc}", secret))
    finally:
        life.stop_proc(godot)
        life.stop_proc(proc)
        if desc_path and desc_path.is_file():
            try:
                desc_path.unlink()
            except OSError:
                pass
        cleanup_temp()
    return errors


def main() -> int:
    errors: list[str] = []
    if not PLAN.is_file():
        print("FAIL: missing authoritative 20-8 plan", file=sys.stderr)
        return 1
    errors.extend(plan_errors(PLAN.read_text(encoding="utf-8")))
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())

    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot required (no skip-PASS): {pin_reason}")
        print("FAIL: tilemap", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    built = subprocess.run(
        [sess.npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")

    if not errors:
        errors.extend(live_errors(exe))

    if errors:
        print("FAIL: tilemap", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: TileSet/TileMapLayer/terrain adapters; paint/fill/stamp, 100x100 paged, "
        f"one-undo stroke, editor collision, save/reopen; screenshots={SCREENSHOTS} Alternative; "
        "plan progress consistent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

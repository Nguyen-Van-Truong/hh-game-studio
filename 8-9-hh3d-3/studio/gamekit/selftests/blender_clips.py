"""Quick Blender 5.2 regression: multiple clips on one skinned armature."""

from __future__ import annotations

import json

from .. import blender_recipe as B
from . import Ctx
from .w8_blender import _glb_document


def run(ctx: Ctx) -> None:
    steps = [
        {"op": "clear"},
        {"op": "primitive", "type": "cube", "name": "Body", "size": 1.0,
         "location": [0, 0, 0.5]},
        {"op": "armature", "name": "Rig", "bones": [
            {"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 0.5]},
            {"name": "Top", "head": [0, 0, 0.5], "tail": [0, 0, 1], "parent": "Root"}]},
        {"op": "skin", "mesh": "Body", "armature": "Rig"},
    ]
    # Re-enter Idle after Walk to cover both a new Action and rebinding an
    # existing Action's slot.  Each clip has a different range and two bones.
    for action, bone, start, end, angle in (
        ("Idle", "Root", 1, 12, 5), ("Walk", "Root", 20, 32, 20),
        ("Idle", "Top", 1, 12, -5), ("Walk", "Top", 20, 32, -20),
    ):
        steps.append({"op": "keyframes", "object": "Rig", "bone": bone, "action": action,
                      "fps": 24, "interpolation": "LINEAR", "keys": [
                          {"frame": start, "rotation_deg": [0, 0, 0]},
                          {"frame": end, "rotation_deg": [angle, 0, 0]}]})
    steps.append({"op": "export_gltf", "out": "multi.glb", "animations": True})
    steps.extend([
        {"op": "primitive", "type": "cube", "name": "Badge", "size": 0.1,
         "location": [0, 0, 1.2]},
        {"op": "primitive", "type": "cube", "name": "Other", "size": 0.2,
         "location": [5, 0, 0]},
        {"op": "keyframes", "object": "Other", "action": "OtherMove", "fps": 24,
         "interpolation": "LINEAR", "keys": [
             {"frame": 1, "location": [5, 0, 0]}, {"frame": 12, "location": [6, 0, 0]}]},
        {"op": "export_gltf", "out": "selected.glb", "objects": ["Body", "Badge"], "animations": True},
    ])
    recipe = ctx.root / "multi.json"
    recipe.write_text(json.dumps({"schema": B.SCHEMA, "name": "multi", "steps": steps}), encoding="utf-8")
    out = ctx.root / "out"
    result = ctx.guard("run multi-clip recipe", lambda: B.run_recipe(recipe, out, timeout=90))
    if not isinstance(result, dict):
        return
    _, version, doc = _glb_document(out / "multi.glb")
    clips = {anim.get("name"): anim for anim in doc.get("animations", [])}
    stats = result.get("manifest", {}).get("stats", {})
    ranges = {a.get("name"): [a.get("frame_start"), a.get("frame_end")] for a in stats.get("actions", [])}
    ctx.check("multi-clip recipe exits cleanly", result.get("ok") is True
              and result.get("process", {}).get("exit_code") == 0, process=result.get("process"))
    ctx.check("both clips survive in one skinned GLB", version == 2 and set(clips) == {"Idle", "Walk"}
              and len(doc.get("skins", [])) == 1, clips=sorted(clips), skins=len(doc.get("skins", [])))
    ctx.check("each clip contains tracks for both authored bones", all(
        len({channel.get("target", {}).get("node") for channel in clips.get(name, {}).get("channels", [])
             if channel.get("target", {}).get("path") == "rotation"}) >= 2 for name in ("Idle", "Walk")))
    ctx.check("rebinding preserves separate frame ranges", ranges.get("Idle") == [1, 12]
              and ranges.get("Walk") == [20, 32], ranges=ranges)
    _, _, chosen = _glb_document(out / "selected.glb")
    node_names = {node.get("name") for node in chosen.get("nodes", [])}
    selected_clips = {anim.get("name") for anim in chosen.get("animations", [])}
    ctx.check("selected export includes companion mesh and automatic armature", {"Body", "Badge", "Rig"} <= node_names
              and "Other" not in node_names and len(chosen.get("skins", [])) == 1, nodes=sorted(node_names))
    ctx.check("selected export validates only exported clip owners", selected_clips == {"Idle", "Walk"}, clips=sorted(selected_clips))

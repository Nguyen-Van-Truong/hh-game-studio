"""Native smoke for synthetic WAV readback and vfx packed scenes.

``selftest.py`` exposes this as the opt-in ``effects`` smoke. Importing it does
not start Godot. ``run`` does, through ``scene.apply`` and ``scene.inspect``,
so it remains separate from the historical long matrix.
"""

from __future__ import annotations

from .. import scene as S
from .. import sfx
from .. import vfx
from . import Ctx

_SCENES = (
    ("sparks_2d", "res://effects/sparks_2d.tscn", "fx.sparks2d.1", "Sparks", True, 1002),
    ("smoke_2d", "res://effects/smoke_2d.tscn", "fx.smoke2d.1", "Smoke", False, 1003),
    ("sparks_3d", "res://effects/sparks_3d.tscn", "fx.sparks3d.1", "Sparks", True, 3002),
    ("smoke_3d", "res://effects/smoke_3d.tscn", "fx.smoke3d.1", "Smoke", False, 3003),
)


def run(ctx: Ctx) -> None:
    out_dir = ctx.root / "sfx-out"
    out_dir.mkdir()
    first = ctx.guard("write impact wav", lambda: sfx.generate(out_dir / "impact-a.wav", "impact", seed=4))
    second = ctx.guard("write impact wav again", lambda: sfx.generate(out_dir / "impact-b.wav", "impact", seed=4))
    if isinstance(first, dict) and isinstance(second, dict):
        same_bytes = (out_dir / "impact-a.wav").read_bytes() == (out_dir / "impact-b.wav").read_bytes()
        ctx.check(
            "same seed writes the same wav",
            same_bytes and first.get("sha256") == second.get("sha256") and first.get("checks", {}).get("clipping") is False,
            sha=first.get("sha256"),
        )

    project = ctx.project(
        "gk-fx",
        settings='[rendering]\nrenderer/rendering_method="forward_plus"\n',
    )
    ctx.expect_error(
        "wav is not written into the project",
        "FORBIDDEN_PATH",
        lambda: sfx.generate(project.root / "jump.wav", "jump"),
    )
    ctx.check("project wav was not created", not (project.root / "jump.wav").exists())

    for preset, scene, command_id, node, one_shot, seed in _SCENES:
        receipt = ctx.guard(
            f"create {preset}",
            lambda preset=preset, scene=scene, command_id=command_id, seed=seed: vfx.create(
                project, scene, preset, command_id, seed=seed
            ),
        )
        if not isinstance(receipt, dict):
            continue
        ctx.check(
            f"{preset} committed",
            receipt.get("ok") is True and receipt.get("readback") == "FRESH_PROCESS_MATCH",
            status=receipt.get("status"),
        )
        replay = ctx.guard(
            f"retry {preset}",
            lambda preset=preset, scene=scene, command_id=command_id, seed=seed: vfx.create(
                project, scene, preset, command_id, seed=seed
            ),
        )
        if isinstance(replay, dict):
            ctx.check(f"{preset} retry replays", replay.get("replayed") is True, kind=replay.get("kind"))
        view = ctx.guard(f"inspect {preset}", lambda scene=scene: S.inspect(project, scene))
        if not isinstance(view, dict):
            continue
        nodes = {item["path"]: item for item in view.get("nodes", [])}
        props = nodes.get(node, {}).get("props", {})
        ctx.check(
            f"{preset} process material",
            props.get("process_material", {}).get("$type") == "ParticleProcessMaterial",
        )
        amount = props.get("amount")
        ctx.check(f"{preset} count capped", isinstance(amount, int) and 1 <= amount <= 96, amount=amount)
        # Godot omits a property whose value equals its engine default. A
        # missing one_shot is therefore the persisted representation of false.
        persisted_one_shot = props.get("one_shot", False)
        ctx.check(f"{preset} one_shot", persisted_one_shot is one_shot, one_shot=persisted_one_shot)
        ctx.check(
            f"{preset} fixed seed",
            props.get("use_fixed_seed") is True and props.get("seed") == seed,
            use_fixed_seed=props.get("use_fixed_seed"),
            seed=props.get("seed"),
        )
        camera_props = nodes.get("PreviewCamera", {}).get("props", {})
        camera_key = "enabled" if preset.endswith("_2d") else "current"
        # Camera2D.enabled defaults to true and Godot may omit that default from
        # the serialized scene; Camera3D.current is explicitly read back.
        camera_value = camera_props.get(camera_key, True) if camera_key == "enabled" else camera_props.get(camera_key)
        ctx.check(f"{preset} preview camera", camera_value is True, camera_key=camera_key)
        ctx.check(f"{preset} group", "hh_vfx" in nodes.get(node, {}).get("groups", []))
        if preset.endswith("_3d"):
            draw = props.get("draw_pass_1", {})
            ctx.check(f"{preset} quad", draw.get("$type") == "QuadMesh", draw=str(draw)[:240])
            material = (draw.get("props") or {}).get("material", {})
            ctx.check(f"{preset} unshaded quad material", material.get("$type") == "StandardMaterial3D")
        else:
            ctx.check(f"{preset} gradient texture", props.get("texture", {}).get("$type") == "GradientTexture2D")

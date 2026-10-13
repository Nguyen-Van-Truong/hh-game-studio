"""Native quality smoke. Not registered in selftest.py; call run(ctx) from a scheduled check.

Uses a temp project only. It does not register or edit a real game.
"""

from __future__ import annotations

from .. import project_config as PC
from .. import quality as Q
from . import Ctx

_SETTINGS = """
[display]
window/size/viewport_width=1280

[internationalization]
locale/fallback="vi"

[rendering]
renderer/rendering_method.web="gl_compatibility"
anti_aliasing/quality/use_taa=true
environment/ssao/quality=1

[hh_game]
custom/data={
"title": "Lang Viet",
"coords": [1, 2, 3]
}
"""


def run(ctx: Ctx) -> None:
    catalog = Q.list_profiles()
    names = [item["name"] for item in catalog["profiles"]]
    ctx.check(
        "three conservative profiles",
        names == ["compatibility", "mobile", "desktop"]
        and catalog.get("beauty_guarantee") is False
        and all(item.get("beauty_guarantee") is False and item.get("costly_effects_enabled") is False for item in catalog["profiles"]),
        names=names,
    )
    project = ctx.project("quality", {"extra.gd": "extends Node\n"}, settings=_SETTINGS)
    path = project.root / "project.godot"
    before = path.read_bytes()
    owned = set(Q.MANAGED_KEYS)
    dry = ctx.guard("dry-run", lambda: Q.apply_profile(project, "compatibility", "quality.smoke.dry", dry_run=True))
    ctx.check(
        "dry-run reports compatibility and does not write",
        isinstance(dry, dict)
        and dry.get("status") == "DRY_RUN"
        and dry.get("beauty_guarantee") is False
        and dry.get("renderer") == "gl_compatibility"
        and path.read_bytes() == before
        and not (project.state / "journal.jsonl").exists(),
        dry=None if not isinstance(dry, dict) else {"status": dry.get("status"), "renderer": dry.get("renderer")},
    )
    applied = ctx.guard("apply compatibility", lambda: Q.apply_profile(project, "compatibility", "quality.smoke.1"))
    compat = path.read_bytes()
    ctx.check(
        "compatibility committed and read back",
        isinstance(applied, dict)
        and applied.get("status") == "COMMITTED"
        and applied.get("readback") == "FRESH_PROCESS_MATCH"
        and applied.get("renderer") == "gl_compatibility"
        and applied.get("mobile_renderer") == "gl_compatibility"
        and applied.get("beauty_guarantee") is False
        and applied.get("settings") == Q.PROFILES["compatibility"]["settings"],
        applied=None if not isinstance(applied, dict) else {"status": applied.get("status"), "readback": applied.get("readback"), "renderer": applied.get("renderer")},
    )
    ctx.check(
        "unrelated source preserved and web override kept",
        PC.preserved_entries(before, owned) == PC.preserved_entries(compat, owned)
        and b'renderer/rendering_method.web="gl_compatibility"' in compat
        and b"environment/ssao/quality=1" in compat
        and b'locale/fallback="vi"' in compat
        and b'"title": "Lang Viet"' in compat
        and b"use_taa=true" not in compat,
    )
    replay = ctx.guard("retry", lambda: Q.apply_profile(project, "compatibility", "quality.smoke.1"))
    ctx.check(
        "retry replays without rewriting",
        isinstance(replay, dict) and replay.get("replayed") is True and path.read_bytes() == compat,
        replayed=None if not isinstance(replay, dict) else replay.get("replayed"),
    )
    ctx.expect_error("changed payload conflicts", "CONFLICT", Q.apply_profile, project, "desktop", "quality.smoke.1")
    ctx.check("conflict keeps the committed bytes", path.read_bytes() == compat)
    mobile = ctx.guard("apply mobile", lambda: Q.apply_profile(project, "mobile", "quality.smoke.2"))
    ctx.check(
        "mobile override follows the mobile profile",
        isinstance(mobile, dict)
        and mobile.get("status") == "COMMITTED"
        and mobile.get("readback") == "FRESH_PROCESS_MATCH"
        and mobile.get("renderer") == "mobile"
        and mobile.get("mobile_renderer") == "mobile"
        and PC.preserved_entries(before, owned) == PC.preserved_entries(path.read_bytes(), owned),
        mobile=None if not isinstance(mobile, dict) else {"renderer": mobile.get("renderer"), "mobile_renderer": mobile.get("mobile_renderer")},
    )
    inspected = ctx.guard("inspect", lambda: Q.inspect_quality(project))
    ctx.check(
        "inspect matches mobile from a fresh process",
        isinstance(inspected, dict)
        and inspected.get("matched_profile") == "mobile"
        and inspected.get("renderer") == "mobile"
        and inspected.get("web_renderer") == "gl_compatibility"
        and inspected.get("readback") == "FRESH_PROCESS_MATCH"
        and inspected.get("beauty_guarantee") is False,
        inspected=None if not isinstance(inspected, dict) else {"matched_profile": inspected.get("matched_profile"), "web_renderer": inspected.get("web_renderer")},
    )

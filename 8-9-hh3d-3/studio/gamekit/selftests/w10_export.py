"""W10 selftest: install pinned export templates and export Windows, Web and Linux."""

from __future__ import annotations

import time

from .. import export as E
from . import Ctx

MAIN_GD = """extends Node


func _process(_delta: float) -> void:
	if Engine.get_process_frames() >= 30:
		get_tree().quit(0)
"""

MAIN_TSCN = """[gd_scene load_steps=2 format=3 uid="uid://bhhw10export1"]

[ext_resource type="Script" path="res://main.gd" id="1_main"]

[node name="Main" type="Node"]
script = ExtResource("1_main")
"""

RENDERING = """
[application]

config/features=PackedStringArray("4.7", "GL Compatibility")

[rendering]

renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
"""

USER_PRESET = """[preset.0]

name="Player Build"
platform="Windows Desktop"
runnable=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="keep/player.exe"

[preset.0.options]

custom_template/debug="C:/do-not-touch"
binary_format/embed_pck=true
"""


def _by_name(receipt: dict) -> dict:
    return {item["name"]: item for item in receipt.get("files", [])}


def _preset_text(project) -> str:
    return (project.root / "export_presets.cfg").read_bytes().decode("utf-8")


def run(ctx: Ctx) -> None:
    installed = ctx.guard("install templates", lambda: E.templates(install=True, platform="all"))
    if not isinstance(installed, dict):
        return
    ctx.check(
        "templates installed",
        installed.get("ok") is True and installed.get("installed") is True and installed.get("version") == "4.7.2.stable",
        seconds=installed.get("seconds"),
        verify_seconds=installed.get("verify_seconds"),
        extract_seconds=installed.get("extract_seconds"),
        extracted=installed.get("extracted"),
        archive_cached=installed.get("archive_cached"),
    )
    if not installed.get("installed"):
        return

    started = time.monotonic()
    status = ctx.guard("template status", lambda: E.templates(install=False, platform="all"))
    elapsed = time.monotonic() - started
    if not isinstance(status, dict):
        return
    ctx.check(
        "second status fast and installed",
        status.get("installed") is True and status.get("archive_cached") is True and elapsed < 5,
        seconds=round(elapsed, 3),
        verify_seconds=status.get("verify_seconds"),
    )

    project = ctx.project(
        "gkexport",
        {"main.gd": MAIN_GD, "main.tscn": MAIN_TSCN, "export_presets.cfg": USER_PRESET},
        main_scene="res://main.tscn",
        settings=RENDERING,
    )
    original = (project.root / "export_presets.cfg").read_bytes()
    out_win = ctx.root / "out-win"
    win = ctx.guard(
        "export windows",
        lambda: E.export_run(project, "windows", out_win, "w10.win.1", name="Game"),
    )
    if isinstance(win, dict):
        files = _by_name(win)
        ctx.check(
            "windows exe and pck",
            "Game.exe" in files and files["Game.exe"]["bytes"] > 1_000_000
            and "Game.pck" in files and files["Game.pck"]["bytes"] > 64
            and (out_win / "Game.exe").is_file(),
            exe_bytes=files.get("Game.exe", {}).get("bytes"),
            pck_bytes=files.get("Game.pck", {}).get("bytes"),
        )
        ctx.check(
            "windows smoke exit 0",
            (win.get("smoke") or {}).get("exit_code") == 0 and win.get("status") == "COMMITTED",
            smoke=win.get("smoke"),
        )
        ctx.check(
            "windows output hashes",
            all(len(item.get("sha256", "")) == 64 for item in win.get("files", [])),
        )
        before_replay = (project.root / "export_presets.cfg").read_bytes()
        replay = ctx.guard(
            "replay windows",
            lambda: E.export_run(project, "windows", out_win, "w10.win.1", name="Game"),
        )
        if isinstance(replay, dict):
            ctx.check(
                "same command_id replays",
                replay.get("replayed") is True and replay.get("files") == win.get("files")
                and (project.root / "export_presets.cfg").read_bytes() == before_replay,
            )

    out_web = ctx.root / "out-web"
    web = ctx.guard(
        "export web",
        lambda: E.export_run(project, "web", out_web, "w10.web.1", name="Game"),
    )
    if isinstance(web, dict):
        files = _by_name(web)
        ctx.check(
            "web index.html wasm pck js",
            all((out_web / name).is_file() and files.get(name, {}).get("bytes", 0) > 64 for name in
                ("index.html", "index.js", "index.wasm", "index.pck"))
            and files.get("index.wasm", {}).get("bytes", 0) > 100_000,
            bytes={name: files.get(name, {}).get("bytes") for name in ("index.html", "index.js", "index.wasm", "index.pck")},
        )

    out_linux = ctx.root / "out-linux"
    linux = ctx.guard(
        "export linux",
        lambda: E.export_run(project, "linux", out_linux, "w10.linux.1", name="Game"),
    )
    if isinstance(linux, dict):
        files = _by_name(linux)
        pck = next((item for name, item in files.items() if name.endswith(".pck")), None)
        ctx.check(
            "linux binary and pck",
            "Game.x86_64" in files and files["Game.x86_64"]["bytes"] > 1_000_000
            and pck is not None and pck["bytes"] > 64
            and (out_linux / "Game.x86_64").is_file(),
            binary_bytes=files.get("Game.x86_64", {}).get("bytes"),
            pck=None if pck is None else {"name": pck["name"], "bytes": pck["bytes"]},
        )

    text = _preset_text(project)
    ctx.check(
        "user preset bytes preserved",
        (project.root / "export_presets.cfg").read_bytes().startswith(original)
        and 'custom_template/debug="C:/do-not-touch"' in text,
    )
    ctx.check(
        "hh presets present and web threads off",
        text.count('name="HH Windows"') == 1 and text.count('name="HH Linux"') == 1
        and text.count('name="HH Web"') == 1 and "variant/thread_support=false" in text,
    )
    before_refuse = (project.root / "export_presets.cfg").read_bytes()
    ctx.expect_error(
        "out-dir inside the project refused",
        "FORBIDDEN_PATH",
        lambda: E.export_run(project, "windows", project.root / "inside", "w10.inside.1"),
    )
    ctx.check(
        "refused export left presets unchanged",
        (project.root / "export_presets.cfg").read_bytes() == before_refuse,
    )

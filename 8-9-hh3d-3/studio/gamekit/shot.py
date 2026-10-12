"""hh shot: windowed screenshot of a registered Godot project, plus hh vcheck.

The capture runs the pinned Godot with a visible window (headless has no
framebuffer). ``--out`` is an absolute png outside the project. ``--baseline``
either copies that png into the project (missing file or ``--update-baseline``,
status BASELINE_WRITTEN, ``--command-id`` required) or compares it with vcheck
(PASS / FAIL). A baseline write follows the mutating contract: journal, lock,
editor check, checkpoint, atomic replace, byte readback.
"""

from __future__ import annotations

import argparse
import math
import os
import re
from pathlib import Path
from typing import Any

from . import common as C
from . import pngio
from . import scene as scene_mod
from . import vcheck

MAX_FRAME = 600
_RES_RE = re.compile(r"^(\d+)x(\d+)$")
_ACTION_RE = re.compile(r"^[A-Za-z0-9_./+-]{1,64}$")
_MAIN_SCENE_RE = re.compile(r'^[ \t]*run/main_scene="([^"]+)"', re.M)


def parse_resolution(text: str) -> tuple[int, int]:
    match = _RES_RE.match(text.strip())
    if not match:
        raise C.GamekitError("BAD_REQUEST", "resolution must look like 640x360")
    width, height = int(match.group(1)), int(match.group(2))
    return _check_resolution((width, height))


def _check_resolution(resolution: tuple[int, int]) -> tuple[int, int]:
    if not isinstance(resolution, tuple) or len(resolution) != 2:
        raise C.GamekitError("BAD_REQUEST", "resolution must be (width, height)")
    width, height = resolution
    if isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, int) or not isinstance(height, int):
        raise C.GamekitError("BAD_REQUEST", "resolution must be (width, height)")
    if not (16 <= width <= 4096 and 16 <= height <= 4096):
        raise C.GamekitError("BAD_REQUEST", "resolution out of range 16..4096")
    return width, height


def parse_frames(frames: int) -> int:
    if isinstance(frames, bool) or not isinstance(frames, int) or not 1 <= frames <= MAX_FRAME:
        raise C.GamekitError("BAD_REQUEST", f"--frames must be an integer 1..{MAX_FRAME}")
    return frames


def parse_at(text: str) -> list[int]:
    frames: list[int] = []
    for part in text.split(","):
        piece = part.strip()
        if not piece.isdigit():
            raise C.GamekitError("BAD_REQUEST", f"bad frame {piece!r} in --at")
        frame = int(piece)
        if frame > MAX_FRAME:
            raise C.GamekitError("BAD_REQUEST", f"frame {frame} out of range 0..{MAX_FRAME}")
        frames.append(frame)
    if not frames:
        raise C.GamekitError("BAD_REQUEST", "--at is empty")
    if len(frames) > 32:
        raise C.GamekitError("BAD_REQUEST", "at most 32 capture frames")
    if len(set(frames)) != len(frames):
        raise C.GamekitError("BAD_REQUEST", "duplicate frame in --at")
    return frames


def parse_expect(text: str) -> list[str]:
    parts = [part.strip() for part in text.split(",")]
    if not parts or any(part == "" for part in parts):
        raise C.GamekitError("BAD_REQUEST", "empty name in --expect")
    out: list[str] = []
    for path in parts:
        if len(path) > 240 or "\\" in path or path.startswith("/"):
            raise C.GamekitError("VALIDATION_FAILED", f"bad node path {path!r}")
        if path != ".":
            segments = path.split("/")
            if any(seg in ("", ".", "..") for seg in segments):
                raise C.GamekitError("VALIDATION_FAILED", f"bad node path {path!r}")
        out.append(path)
    return out


def validate_trace(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise C.GamekitError("VALIDATION_FAILED", "trace must be an object")
    fps = data.get("fps", 60)
    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 240:
        raise C.GamekitError("VALIDATION_FAILED", "trace fps must be an integer 1..240")
    events = data.get("events", [])
    if not isinstance(events, list) or len(events) > 10000:
        raise C.GamekitError("VALIDATION_FAILED", "trace events must be a list of at most 10000")
    clean: list[dict[str, Any]] = []
    allowed = {"frame", "action", "pressed", "strength"}
    for i, event in enumerate(events):
        if not isinstance(event, dict):
            raise C.GamekitError("VALIDATION_FAILED", f"events[{i}] must be an object")
        extra = set(event) - allowed
        if extra:
            raise C.GamekitError("VALIDATION_FAILED", f"events[{i}] unknown fields {sorted(extra)}")
        frame = event.get("frame")
        action = event.get("action")
        pressed = event.get("pressed")
        if isinstance(frame, bool) or not isinstance(frame, int) or not 0 <= frame <= MAX_FRAME:
            raise C.GamekitError("VALIDATION_FAILED", f"events[{i}].frame out of range")
        if not isinstance(action, str) or not _ACTION_RE.match(action):
            raise C.GamekitError("VALIDATION_FAILED", f"events[{i}].action is not a safe action name")
        if not isinstance(pressed, bool):
            raise C.GamekitError("VALIDATION_FAILED", f"events[{i}].pressed must be a bool")
        row: dict[str, Any] = {"frame": frame, "action": action, "pressed": pressed}
        if "strength" in event:
            strength = event["strength"]
            if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not math.isfinite(float(strength)):
                raise C.GamekitError("VALIDATION_FAILED", f"events[{i}].strength must be a finite number")
            if not 0.0 <= float(strength) <= 1.0:
                raise C.GamekitError("VALIDATION_FAILED", f"events[{i}].strength must be 0..1")
            row["strength"] = float(strength)
        clean.append(row)
    return {"fps": fps, "events": clean}


def _load_trace(path: str) -> dict[str, Any]:
    file = Path(path)
    if not file.is_absolute():
        file = Path.cwd() / file
    file = Path(os.path.abspath(str(file)))
    if file.name.lower() == "private.raw":
        raise C.GamekitError("FORBIDDEN_PATH", "refusing private.raw")
    if C.is_within(file, C.STUDIO_DIR / ".local"):
        raise C.GamekitError("FORBIDDEN_PATH", "refusing studio/.local")
    reason = C.forbidden_reason(file)
    if reason:
        raise C.GamekitError("FORBIDDEN_PATH", reason)
    return validate_trace(C.read_json(file))


def _main_scene(project: C.Project) -> str:
    text = (project.root / "project.godot").read_text(encoding="utf-8")
    match = _MAIN_SCENE_RE.search(text)
    if not match:
        raise C.GamekitError("BAD_REQUEST", "no --scene and the project has no main scene")
    scene = match.group(1)
    if scene.startswith("uid://"):
        raise C.GamekitError("BAD_REQUEST", "main scene is a uid; pass --scene res://...")
    return scene


def _check_scene(project: C.Project, scene: str) -> str:
    if not (scene.endswith(".tscn") or scene.endswith(".scn")):
        raise C.GamekitError("BAD_PATH", "scene must be a .tscn or .scn")
    project.res_to_path(scene, must_exist=True)
    return scene


def _external_png(project: C.Project, raw: str | Path, what: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        raise C.GamekitError("BAD_PATH", f"{what} must be an absolute path")
    path = Path(os.path.abspath(str(path)))
    if path.suffix.lower() != ".png":
        raise C.GamekitError("BAD_PATH", f"{what} must be a .png file")
    if path.name.lower() == "private.raw":
        raise C.GamekitError("FORBIDDEN_PATH", "refusing private.raw")
    if C.is_within(path, project.root):
        raise C.GamekitError("FORBIDDEN_PATH", f"{what} must be outside the project; use --baseline to store a png inside it")
    if C.is_within(path, C.STUDIO_DIR / ".local"):
        raise C.GamekitError("FORBIDDEN_PATH", "refusing to write under studio/.local")
    reason = C.forbidden_reason(path)
    if reason:
        raise C.GamekitError("FORBIDDEN_PATH", reason)
    if path.exists() and not path.is_file():
        raise C.GamekitError("BAD_PATH", f"{what} exists and is not a file")
    if path.is_symlink():
        raise C.GamekitError("FORBIDDEN_PATH", f"{what} is a symlink")
    return path


def frame_paths(out: Path, frames: list[int], use_at: bool) -> dict[int, Path]:
    """Map capture frame -> absolute png. ``--at`` writes ``<stem>_f<frame>.png``."""
    paths: dict[int, Path] = {}
    for frame in frames:
        path = out.with_name(f"{out.stem}_f{frame}{out.suffix}") if use_at else out
        paths[frame] = path
    return paths


def _check_seed(seed: int | None) -> int | None:
    if seed is None:
        return None
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
        raise C.GamekitError("BAD_REQUEST", "seed must be an integer 0..4294967295")
    return seed


def _request_obj(
    *,
    scene: str,
    out: Path,
    frames: int,
    at: list[int] | None,
    resolution: tuple[int, int],
    seed: int | None,
    trace: dict[str, Any] | None,
    expect: list[str],
    baseline: str | None,
    threshold: float,
    pixel_tolerance: int,
    update_baseline: bool,
    diff_out: str | None,
) -> dict[str, Any]:
    return {
        "kind": "shot",
        "scene": scene,
        "out": str(out),
        "frames": frames,
        "at": at,
        "resolution": [resolution[0], resolution[1]],
        "seed": seed,
        "trace": trace,
        "expect": expect,
        "baseline": baseline,
        "threshold": threshold,
        "pixel_tolerance": pixel_tolerance,
        "update_baseline": update_baseline,
        "diff_out": diff_out,
    }


def _num(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise C.GamekitError("GODOT_FAILED", "bad number in shot result")
    return float(value)


def _screen_rect(value: Any) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4:
        raise C.GamekitError("GODOT_FAILED", "screen_rect must be [x, y, w, h] or null")
    return [_num(item) for item in value]


def _presence(raw: Any, expect: list[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) != len(expect):
        raise C.GamekitError("GODOT_FAILED", "presence result does not match --expect")
    out: list[dict[str, Any]] = []
    for want, row in zip(expect, raw):
        if not isinstance(row, dict) or row.get("path") != want:
            raise C.GamekitError("GODOT_FAILED", f"presence row for {want!r} is missing")
        for key in ("exists", "visible_in_tree", "on_screen"):
            if not isinstance(row.get(key), bool):
                raise C.GamekitError("GODOT_FAILED", f"presence.{key} missing for {want}")
        cleaned: dict[str, Any] = {
            "path": want,
            "exists": row["exists"],
            "visible_in_tree": row["visible_in_tree"],
            "on_screen": row["on_screen"],
            "screen_rect": _screen_rect(row.get("screen_rect")),
        }
        if "emitting" in row:
            if not isinstance(row["emitting"], bool):
                raise C.GamekitError("GODOT_FAILED", f"presence.emitting is not a bool for {want}")
            cleaned["emitting"] = row["emitting"]
        if "class" in row:
            if not isinstance(row["class"], str):
                raise C.GamekitError("GODOT_FAILED", f"presence.class is not a string for {want}")
            cleaned["class"] = row["class"]
        out.append(cleaned)
    return out


def _decode_capture(path: Path, reported_w: int, reported_h: int) -> tuple[bytes, pngio.Image]:
    if not path.is_file():
        raise C.GamekitError("GODOT_FAILED", f"shot did not write {path}")
    data = path.read_bytes()
    try:
        image = pngio.decode(data)
    except pngio.PngError as exc:
        raise C.GamekitError("READBACK_MISMATCH", f"screenshot is not a readable png: {exc}") from exc
    if image.width != reported_w or image.height != reported_h:
        raise C.GamekitError(
            "READBACK_MISMATCH",
            f"{path.name} decoded {image.width}x{image.height}, Godot reported {reported_w}x{reported_h}",
        )
    return data, image


def _commit_baseline(
    project: C.Project,
    command_id: str,
    request_digest: str,
    baseline_res: str,
    png_bytes: bytes,
    image: pngio.Image,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    path = project.res_to_path(baseline_res)
    before = path.read_bytes() if path.is_file() else None
    receipt["baseline"] = baseline_res
    receipt["before_sha256"] = C.sha256_bytes(before) if before is not None else None
    receipt["status"] = "BASELINE_WRITTEN"
    receipt["ok"] = True
    receipt["readback"] = "BYTES_AND_PNG_DECODE"
    C.checkpoint(project, command_id, [path])
    try:
        C.atomic_write_bytes(path, png_bytes)
        written = path.read_bytes()
        if written != png_bytes:
            raise C.GamekitError("READBACK_MISMATCH", "baseline bytes differ after write")
        try:
            back = pngio.decode(written)
        except pngio.PngError as exc:
            raise C.GamekitError("READBACK_MISMATCH", f"baseline png does not decode: {exc}") from exc
        if (back.width, back.height, back.mode, back.pixels) != (image.width, image.height, image.mode, image.pixels):
            raise C.GamekitError("READBACK_MISMATCH", "baseline pixels differ after write")
        receipt["after_sha256"] = C.sha256_bytes(written)
        C.Journal(project).append(command_id, request_digest, receipt)
    except Exception:
        try:
            C.restore_checkpoint(project, command_id)
        except Exception as restore_exc:
            raise C.GamekitError("STATE_CORRUPT", f"restore failed: {restore_exc}") from restore_exc
        raise
    return receipt


def capture(
    project: C.Project,
    out: str | Path,
    *,
    scene: str | None = None,
    frames: int = 10,
    at: list[int] | None = None,
    resolution: tuple[int, int] = (640, 360),
    seed: int | None = None,
    trace: dict[str, Any] | None = None,
    expect: list[str] | None = None,
    baseline: str | None = None,
    threshold: float = 0.01,
    pixel_tolerance: int = 8,
    update_baseline: bool = False,
    command_id: str | None = None,
    diff_out: str | Path | None = None,
    allow_open_editor: bool = False,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Capture a windowed shot. Writes a baseline only when asked; otherwise returns PASS/FAIL/CAPTURED."""
    frames = parse_frames(frames)
    width, height = _check_resolution(resolution)
    threshold, pixel_tolerance = vcheck.validate_thresholds(threshold, pixel_tolerance)
    seed = _check_seed(seed)
    if trace is not None:
        trace = validate_trace(trace)
    expect_paths = list(expect or [])
    for path in expect_paths:
        if not isinstance(path, str) or "," in path or parse_expect(path) != [path]:
            raise C.GamekitError("VALIDATION_FAILED", f"bad node path {path!r}")
    scene_res = _check_scene(project, scene) if scene else _check_scene(project, _main_scene(project))
    out_path = _external_png(project, out, "--out")
    use_at = at is not None
    capture_at = list(at) if at is not None else [frames]
    if at is not None:
        if not at:
            raise C.GamekitError("BAD_REQUEST", "--at is empty")
        if any(isinstance(frame, bool) or not isinstance(frame, int) or not 0 <= frame <= MAX_FRAME for frame in at):
            raise C.GamekitError("BAD_REQUEST", f"--at frames must be integers 0..{MAX_FRAME}")
        if len(set(at)) != len(at):
            raise C.GamekitError("BAD_REQUEST", "duplicate frame in --at")
    paths = frame_paths(out_path, capture_at, use_at)
    for path in paths.values():
        _external_png(project, path, "--out")
    diff_text = str(Path(os.path.abspath(str(diff_out)))) if diff_out else None
    if diff_text:
        _external_png(project, diff_text, "--diff-out")
    baseline_res = baseline
    if baseline_res is not None:
        if not baseline_res.endswith(".png"):
            raise C.GamekitError("BAD_PATH", "baseline must be a res:// .png path")
        project.res_to_path(baseline_res)
    if command_id is not None:
        command_id = C.validate_command_id(command_id)
    if update_baseline and baseline_res is None:
        raise C.GamekitError("BAD_REQUEST", "--update-baseline requires --baseline")
    request_obj = _request_obj(
        scene=scene_res,
        out=out_path,
        frames=frames,
        at=list(at) if at is not None else None,
        resolution=(width, height),
        seed=seed,
        trace=trace,
        expect=expect_paths,
        baseline=baseline_res,
        threshold=threshold,
        pixel_tolerance=pixel_tolerance,
        update_baseline=update_baseline,
        diff_out=diff_text,
    )
    request_digest = C.digest(request_obj)
    last_frame = max(capture_at)
    run_timeout = timeout if timeout is not None else max(90.0, 40.0 + last_frame)
    fps = int(trace["fps"]) if trace else 60
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    with C.project_lock(project, "shot", wait_seconds=30):
        if command_id is not None:
            prior = C.Journal(project).replay_or_conflict(command_id, request_digest)
            if prior is not None:
                return prior
        writing = False
        if baseline_res is not None:
            baseline_path = project.res_to_path(baseline_res)
            writing = update_baseline or not baseline_path.is_file()
            if writing and command_id is None:
                raise C.GamekitError("BAD_REQUEST", "--command-id is required to write a baseline")
        C.refuse_if_editor_open(project, allow_open_editor)
        if not project.root.is_dir():
            raise C.GamekitError("NOT_FOUND", f"project directory is missing: {project.root}")
        try:
            imported = scene_mod.refresh_import(project.root)
        except OSError as exc:
            raise C.GamekitError("GODOT_FAILED", f"could not start the import pass: {exc}") from exc
        godot_request = {
            "scene": scene_res,
            "width": width,
            "height": height,
            "expect": expect_paths,
            "captures": [{"frame": frame, "path": str(paths[frame])} for frame in sorted(paths)],
            "trace": trace or {"fps": fps, "events": []},
        }
        if seed is not None:
            godot_request["seed"] = seed
        try:
            run = C.run_godot_tool(
                project.root,
                "shot_runner.gd",
                godot_request,
                headless=False,
                windowed=True,
                resolution=(width, height),
                fixed_fps=fps,
                timeout=run_timeout,
            )
        except OSError as exc:
            raise C.GamekitError("GODOT_FAILED", f"could not start Godot: {exc}") from exc
        result = C.require_result(run, "shot")
        got = result.get("files")
        if not isinstance(got, list) or len(got) != len(paths):
            raise C.GamekitError("GODOT_FAILED", "shot file list does not match the request", process=run.summary())
        files: list[dict[str, Any]] = []
        decoded: dict[int, tuple[bytes, pngio.Image]] = {}
        for row in got:
            if not isinstance(row, dict) or "frame" not in row:
                raise C.GamekitError("GODOT_FAILED", "shot file row is malformed", process=run.summary())
            frame = row["frame"]
            if isinstance(frame, bool) or not isinstance(frame, int) or frame not in paths:
                raise C.GamekitError("GODOT_FAILED", f"unexpected capture frame {frame!r}", process=run.summary())
            if str(row.get("path")) != str(paths[frame]):
                raise C.GamekitError("GODOT_FAILED", "shot wrote an unexpected path", process=run.summary())
            data, image = _decode_capture(paths[frame], int(row["width"]), int(row["height"]))
            decoded[frame] = (data, image)
            files.append({
                "path": str(paths[frame]),
                "frame": frame,
                "width": image.width,
                "height": image.height,
                "bytes": len(data),
                "sha256": C.sha256_bytes(data),
            })
        files.sort(key=lambda item: int(item["frame"]))
        primary_frame = max(paths)
        primary_bytes, primary_image = decoded[primary_frame]
        blank_info = vcheck.blank(primary_image)
        for row in files:
            if row["frame"] == primary_frame:
                row["blank"] = blank_info["blank"]
        presence = _presence(result.get("presence"), expect_paths)
        receipt: dict[str, Any] = {
            "ok": True,
            "status": "CAPTURED",
            "kind": "shot",
            "project": project.project_id,
            "scene": scene_res,
            "candidate": str(paths[primary_frame]),
            "files": files,
            "size": [primary_image.width, primary_image.height],
            "requested_resolution": [width, height],
            "blank": blank_info["blank"],
            "blank_metrics": {
                "luminance_stddev": blank_info["luminance_stddev"],
                "dominant_ratio": blank_info["dominant_ratio"],
            },
            "presence": presence,
            "import": imported,
            "errors": list(run.errors[:20]),
            "process": run.summary(),
            "at": C.now_iso(),
        }
        if run.errors:
            receipt["ok"] = False
        if command_id is not None:
            receipt["command_id"] = command_id
        if writing:
            if command_id is None or baseline_res is None:
                raise C.GamekitError("BAD_REQUEST", "--command-id is required to write a baseline")
            if run.errors:
                raise C.GamekitError("GODOT_FAILED", "script errors during capture; baseline not written",
                                     errors=run.errors[:20])
            return _commit_baseline(project, command_id, request_digest, baseline_res, primary_bytes, primary_image, receipt)
        if baseline_res is not None:
            baseline_path = project.res_to_path(baseline_res, must_exist=True)
            diff_target = Path(diff_text) if diff_text else paths[primary_frame].with_name(
                paths[primary_frame].stem + "_diff" + paths[primary_frame].suffix
            )
            compared = vcheck.compare_files(
                paths[primary_frame],
                baseline_path,
                threshold=threshold,
                pixel_tolerance=pixel_tolerance,
                diff_out=diff_target,
                diff_when="always" if diff_text else "fail",
            )
            receipt["baseline"] = baseline_res
            receipt["compare"] = compared
            receipt["status"] = compared["status"]
            receipt["ok"] = bool(compared["ok"]) and not run.errors
            if compared.get("diff"):
                receipt["diff"] = compared["diff"]
        return receipt


def _cmd_shot(args: argparse.Namespace) -> dict[str, Any]:
    return capture(
        C.get_project(args.project),
        args.out,
        scene=args.scene,
        frames=args.frames,
        at=parse_at(args.at) if args.at else None,
        resolution=parse_resolution(args.resolution),
        seed=args.seed,
        trace=_load_trace(args.trace) if args.trace else None,
        expect=parse_expect(args.expect) if args.expect else None,
        baseline=args.baseline,
        threshold=args.threshold,
        pixel_tolerance=args.pixel_tolerance,
        update_baseline=args.update_baseline,
        command_id=args.command_id,
        diff_out=args.diff_out,
        allow_open_editor=args.allow_open_editor,
    )


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("shot", help="capture a windowed screenshot and optionally diff a baseline")
    parser.add_argument("project")
    parser.add_argument("--scene", default=None, help="res:// scene; default is the project main scene")
    parser.add_argument("--out", required=True, help="absolute png path outside the project")
    parser.add_argument("--frames", type=int, default=10, help="wait this many frames, then capture --out")
    parser.add_argument("--at", default=None, help="comma-separated frames saved as <out stem>_f<frame>.png")
    parser.add_argument("--resolution", default="640x360")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--trace", default=None, help="json file {fps, events:[{frame, action, pressed}]}")
    parser.add_argument("--expect", default=None, help="comma-separated node paths relative to the scene root")
    parser.add_argument("--baseline", default=None, help="res:// png inside the project")
    parser.add_argument("--threshold", type=float, default=0.01)
    parser.add_argument("--pixel-tolerance", dest="pixel_tolerance", type=int, default=8)
    parser.add_argument("--update-baseline", dest="update_baseline", action="store_true")
    parser.add_argument("--command-id", dest="command_id", default=None)
    parser.add_argument("--diff-out", dest="diff_out", default=None, help="absolute diff png; default on FAIL is <candidate>_diff.png")
    parser.add_argument("--allow-open-editor", dest="allow_open_editor", action="store_true")
    parser.set_defaults(func=_cmd_shot)
    vcheck.register(sub)

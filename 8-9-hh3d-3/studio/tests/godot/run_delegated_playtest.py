"""Bounded host runner for delegated fixture lifecycle sessions.

The child is an observation source only.  This module owns the run directory,
Godot pin, deadline, process identity, Windows Job, process tree and handle
observations.  It never edits a frozen script to add capture hooks and never
turns a child summary field into an acceptance decision.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import math
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
RAW_ROOT = STUDIO / ".local" / "reviews"
TOOLCHAIN_LOCK = STUDIO / "toolchain.lock.json"
RUN_RE = re.compile(r"gt09-playtest-[0-9]{8}-[0-9]{2}\Z")
GODOT_PIN = "4.7.2-stable"
DEFAULT_DEADLINE_SECONDS = 960.0
DEFAULT_FFMPEG = Path(os.environ.get("USERPROFILE", "C:/Users/truon")) / ".codex" / "gif-banner-tools" / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v7.1.exe"
MAX_LOG_BYTES = 8 * 1024 * 1024
FIXTURES = {
    "arena": {
        "source": STUDIO / "tests" / "godot" / "gameplay_fixture" / "arena_physics.gd",
        "project_source": STUDIO / ".local" / "reviews" /
        "o2-publication-gt09-arena-effects-20261007-18" / "gameplay-owner-4c042d76775349b7881dd19f5c1361e8" /
        "revisions" / "4634eb15a8a382d14db183d8aee0ef17249882ac1a01d4b55f60e3ee608b046e" / "project",
        "title": "HH Fixture Arena - delegated playtest",
    },
    "room": {
        "source": STUDIO / "tests" / "godot" / "gameplay_fixture" / "room3d_native.gd",
        "project_source": STUDIO / ".local" / "reviews" /
        "o2-publication-gt09-room-effects-20261007-19" / "gameplay-owner-4c95441b5e114a5fbd451b264937bcd5" /
        "revisions" / "57ed8422bc1d73a27a1e17b365370937e04d88098f82dee7e1de50212c4c6e92" / "project",
        "title": "HH Fixture Room - delegated playtest",
    },
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _upsert_project_sections(raw: str, sections: dict[str, dict[str, str]]) -> str:
    """Replace each named section exactly once while preserving other config."""
    lines = raw.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            starts.append((index, line[1:-1]))
    replacements = {
        name: [f"[{name}]", *[f"{key}={value}" for key, value in values.items()]]
        for name, values in sections.items()
    }
    output: list[str] = []
    consumed: set[str] = set()
    index = 0
    while index < len(lines):
        matching = [section for start, section in starts if start == index]
        if not matching:
            output.append(lines[index])
            index += 1
            continue
        name = matching[0]
        end = next((start for start, _ in starts if start > index), len(lines))
        if name in replacements:
            if name not in consumed:
                output.extend(replacements[name])
                consumed.add(name)
        else:
            output.extend(lines[index:end])
        index = end
    for name, replacement in replacements.items():
        if name not in consumed:
            if output and output[-1] != "":
                output.append("")
            output.extend(replacement)
    return "\n".join(output).rstrip() + "\n"


def _source_files(project: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(project.rglob("*")):
        info = path.lstat()
        if path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
            raise ValueError("SOURCE_REPARSE_OR_SYMLINK")
        if not path.is_file():
            continue
        relative = path.relative_to(project).as_posix()
        if relative.startswith(".godot/") or relative.endswith((".uid", ".import")):
            continue
        files[relative] = sha(path)
    return files


def _closure_sha(files: dict[str, str]) -> str:
    return hashlib.sha256(_canonical(files)).hexdigest()


def _toolchain() -> dict[str, Any]:
    try:
        value = json.loads(TOOLCHAIN_LOCK.read_bytes())
        godot = value["godot"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError("GODOT_TOOLCHAIN_LOCK_INVALID") from error
    if godot.get("version") != GODOT_PIN or godot.get("source_tag") != GODOT_PIN:
        raise RuntimeError("GODOT_PIN_MISMATCH")
    if godot.get("console_executable") != "Godot_v4.7.2-stable_win64_console.exe":
        raise RuntimeError("GODOT_CONSOLE_PIN_MISMATCH")
    return godot


def pinned_godot(candidate: Path | None = None) -> Path:
    expected_name = str(_toolchain()["console_executable"])
    pin_root = STUDIO / ".local" / "tooling" / f"godot-{GODOT_PIN}"
    default = pin_root / expected_name
    path = (candidate or default).expanduser().resolve()
    if path.name.casefold() != expected_name.casefold():
        raise ValueError("GODOT_EXECUTABLE_NOT_PINNED")
    try:
        path.relative_to(pin_root.resolve())
    except ValueError as error:
        raise ValueError("GODOT_EXECUTABLE_OUTSIDE_PIN_ROOT") from error
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha(path) != _toolchain().get("console_sha256"):
        raise ValueError("GODOT_EXECUTABLE_HASH_MISMATCH")
    gui = path.with_name(str(_toolchain()["gui_executable"]))
    if not gui.is_file() or sha(gui) != _toolchain().get("gui_sha256"):
        raise ValueError("GODOT_GUI_HASH_MISMATCH")
    return path


def _host_sources() -> dict[str, str]:
    paths = {Path(__file__), Path(__file__).with_name("fixture_lifecycle_manifest.py"), TOOLCHAIN_LOCK}
    for directory in ("host", "protocol", "pipeline", "tests/replay", "godot-addon"):
        paths.update(path for path in (STUDIO / directory).rglob("*.py") if "__pycache__" not in path.parts)
    return {path.relative_to(STUDIO).as_posix(): sha(path) for path in sorted(paths)}


def _binary_pins() -> dict[str, str]:
    binary = pinned_godot()
    gui = binary.with_name(str(_toolchain()["gui_executable"]))
    if not DEFAULT_FFMPEG.is_file():
        raise FileNotFoundError(DEFAULT_FFMPEG)
    return {"godot_console": sha(binary), "godot_gui": sha(gui), "ffmpeg": sha(DEFAULT_FFMPEG)}


def _full_closure(project_files: dict[str, str], host_files: dict[str, str], pins: dict[str, str]) -> str:
    return hashlib.sha256(_canonical({"project": project_files, "host": host_files, "binaries": pins})).hexdigest()


def _metadata_path(run_id: str, fixture: str) -> Path:
    if not isinstance(run_id, str) or not RUN_RE.fullmatch(run_id):
        raise ValueError("invalid run id")
    if fixture not in FIXTURES:
        raise ValueError("invalid fixture")
    return RAW_ROOT / run_id / fixture / "metadata.json"


def _safe_publication_root(value: Path) -> Path:
    """Resolve a publication directory while keeping it below review roots."""
    root = Path(value).expanduser().resolve()
    try:
        root.relative_to(RAW_ROOT.resolve())
    except ValueError as error:
        raise ValueError("PUBLICATION_ROOT_OUTSIDE_REVIEWS") from error
    if not root.is_dir():
        raise FileNotFoundError(root)
    return root


def _json_object(path: Path, error: str) -> dict[str, Any]:
    try:
        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in items:
                if key in result:
                    raise ValueError("duplicate_key")
                result[key] = item
            return result
        value = json.loads(path.read_bytes(), object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(error) from exc
    if type(value) is not dict:
        raise ValueError(error)
    return value


def _relative_publication_path(raw: Any) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise ValueError("NATIVE_PATH_INVALID")
    parts = [part for part in raw.replace("\\", "/").split("/") if part]
    if not parts or any(part in (".", "..") for part in parts):
        raise ValueError("NATIVE_PATH_TRAVERSAL")
    return Path(*parts)


def _publication_project(publication_root: Path, fixture: str) -> tuple[Path, dict[str, Any]]:
    """Select and verify the immutable project snapshot used by native Godot."""
    root = _safe_publication_root(publication_root)
    publication = _json_object(root / "result.json", "PUBLICATION_RESULT_INVALID")
    observation = _json_object(root / "native-observation.json", "PUBLICATION_OBSERVATION_INVALID")
    try:
        expected_case = {"arena": "gameplay_arena_physics", "room": "gameplay_source_room_3d_native"}[fixture]
    except KeyError as error:
        raise ValueError("FIXTURE") from error
    if observation.get("case_name") != expected_case:
        raise ValueError("PUBLICATION_FIXTURE_MISMATCH")
    if publication.get("status") != "DIAGNOSTIC_PASS" or publication.get("authority") != 0:
        raise ValueError("PUBLICATION_NOT_DIAGNOSTIC_PASS")
    if publication.get("native_fixture_observed") is not True or publication.get("source_unchanged") is not True:
        raise ValueError("PUBLICATION_NATIVE_OBSERVATION_MISSING")
    if observation.get("fixture_observed") is not True or observation.get("source_closure_sha256") != publication.get("source_closure_sha256"):
        raise ValueError("PUBLICATION_OBSERVATION_BINDING")
    native_paths = publication.get("native_paths")
    if publication.get("native_run_count") != 1 or type(native_paths) is not list or len(native_paths) != 1:
        raise ValueError("PUBLICATION_NATIVE_PATH_COUNT")
    run_relative = _relative_publication_path(native_paths[0])
    run_root = (root / run_relative).resolve()
    try:
        run_root.relative_to(root)
    except ValueError as error:
        raise ValueError("NATIVE_PATH_TRAVERSAL") from error
    run_result = _json_object(run_root / "result.json", "NATIVE_RESULT_INVALID")
    if run_result.get("schema") != "hh-gt03-linux-diagnostic-1" or run_result.get("snapshot_unchanged") is not True:
        raise ValueError("NATIVE_SNAPSHOT_UNVERIFIED")
    receipt = publication.get("receipt") if type(publication.get("receipt")) is dict else {}
    if receipt.get("native_run_id") != run_result.get("run_id"):
        raise ValueError("NATIVE_RUN_BINDING")
    expected = run_result.get("snapshot_hashes_after")
    if type(expected) is not dict or not expected:
        raise ValueError("NATIVE_SNAPSHOT_HASHES_MISSING")
    snapshot = run_root / "snapshot"
    if not snapshot.is_dir():
        raise ValueError("NATIVE_SNAPSHOT_MISSING")
    actual = _source_files(snapshot)
    normalized_expected = {str(key).replace("\\", "/"): value for key, value in expected.items()}
    if actual != normalized_expected:
        raise ValueError("NATIVE_SNAPSHOT_HASH_MISMATCH")
    dependency = observation.get("dependency_observation")
    nodes = dependency.get("observation", {}).get("nodes") if type(dependency) is dict else None
    if isinstance(nodes, list):
        observed_files = {
            item.get("path"): item.get("sha256")
            for item in nodes if type(item) is dict and isinstance(item.get("path"), str)
        }
        if observed_files != {key: value for key, value in actual.items() if key != "project.godot"}:
            raise ValueError("NATIVE_DEPENDENCY_SNAPSHOT_MISMATCH")
    actor_hash = observation.get("fixture_script_sha256")
    if actor_hash != actual.get("scripts/fixture_actor.gd"):
        raise ValueError("NATIVE_FIXTURE_SCRIPT_BINDING")
    if not (snapshot / "scripts" / "fixture_lifecycle.gd").is_file():
        raise ValueError("PUBLICATION_LIFECYCLE_MISSING")
    selected = publication.get("selected") if type(publication.get("selected")) is dict else {}
    selected_files = selected.get("files") if type(selected.get("files")) is dict else {}
    selected_hashes = {}
    for key, value in selected_files.items():
        if type(value) is dict:
            value = value.get("sha256")
        if isinstance(value, str):
            selected_hashes[str(key).replace("\\", "/")] = value
    comparable_snapshot = {key: value for key, value in actual.items() if key != "project.godot"}
    provenance = {
        "publication_root": str(root),
        "native_run_root": str(run_root),
        "executed_snapshot": str(snapshot),
        "executed_snapshot_files": actual,
        "executed_snapshot_closure_sha256": _closure_sha(actual),
        "executed_fixture_script_sha256": actor_hash,
        "selected_revision": selected.get("selected_revision"),
        "selected_source_sha256": selected.get("source_sha256"),
        "selected_matches_executed_snapshot": selected_hashes == comparable_snapshot,
        "publication_run_id": publication.get("run_id"),
        "native_run_id": run_result.get("run_id"),
    }
    return snapshot, provenance


def prepare(run_id: str, fixture: str, project_source: Path | None = None,
            publication_root: Path | None = None) -> dict[str, Any]:
    """Create one immutable run copy and record its complete source closure."""
    metadata_path = _metadata_path(run_id, fixture)
    spec = FIXTURES[fixture]
    if publication_root is not None and project_source is not None:
        raise ValueError("PUBLICATION_AND_PROJECT_SOURCE_MUTUALLY_EXCLUSIVE")
    provenance: dict[str, Any] | None = None
    legacy_copy_mode = publication_root is None
    if publication_root is not None:
        source_project, provenance = _publication_project(publication_root, fixture)
    else:
        source_project = (project_source.resolve() if project_source is not None
                          else spec["project_source"])
    if not source_project.is_dir():
        raise FileNotFoundError(source_project)
    root = metadata_path.parent
    if root.exists():
        raise FileExistsError(root)
    project = root / "project"
    video_dir = root / "video"
    shutil.copytree(source_project, project)
    video_dir.mkdir()

    if legacy_copy_mode:
        # Compatibility diagnostic only.  These writes sever catalog
        # provenance and are explicitly marked unaccepted in metadata.
        _write(project / "scripts" / "fixture_actor.gd", spec["source"].read_bytes())
        lifecycle = STUDIO / "tests" / "godot" / "gameplay_fixture" / "fixture_lifecycle.gd"
        _write(project / "scripts" / "fixture_lifecycle.gd", lifecycle.read_bytes())
        deps = STUDIO / "tests" / "godot" / "gameplay_fixture" / "fixture_dependencies.gd"
        _write(project / "scripts" / "fixture_dependencies.gd", deps.read_bytes())
        if fixture == "arena":
            projectile = STUDIO / "tests" / "godot" / "gameplay_fixture" / "projectile.tscn"
            if projectile.is_file():
                _write(project / "scenes" / "projectile.tscn", projectile.read_bytes())

        project_file = project / "project.godot"
        config = _upsert_project_sections(project_file.read_text(encoding="utf-8"), {
            "display": {
                "window/size/viewport_width": "960",
                "window/size/viewport_height": "540",
                "window/size/window_width_override": "960",
                "window/size/window_height_override": "540",
                "window/stretch/mode": '"canvas_items"',
            },
            "application": {"config/name": json.dumps(spec["title"]),
                            "run/main_scene": '"res://scenes/fixture.tscn"'},
        })
        project_file.write_text(config, encoding="utf-8", newline="\n")
    files = _source_files(project)
    host_files, pins = _host_sources(), _binary_pins()
    metadata = {
        "schema": "hh-gt09-delegated-playtest-2", "run_id": run_id,
        "fixture": fixture, "performed_by": "agent", "delegated_by": "owner",
        "duration_target_seconds": 900, "deadline_seconds": 960.0,
        "godot_pin": GODOT_PIN, "source_files": files,
        "host_files": host_files, "binary_pins": pins,
        "source_closure_sha256": _full_closure(files, host_files, pins), "project": str(project),
        "video_dir": str(video_dir), "created_unix": time.time(), "authority": 0,
        "acceptance": False, "playtest_claim": False,
        "source_mode": "legacy-copy" if legacy_copy_mode else "native-publication-snapshot",
        "legacy_unaccepted": legacy_copy_mode,
        "publication_provenance": provenance,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8", newline="\n")
    return metadata


def _load_metadata(metadata: dict[str, Any]) -> tuple[Path, Path]:
    if type(metadata) is not dict or metadata.get("schema") != "hh-gt09-delegated-playtest-2":
        raise ValueError("METADATA_SCHEMA")
    run_id, fixture = metadata.get("run_id"), metadata.get("fixture")
    if not isinstance(run_id, str) or not RUN_RE.fullmatch(run_id):
        raise ValueError("RUN_ID")
    if fixture not in FIXTURES:
        raise ValueError("FIXTURE")
    if metadata.get("godot_pin") != GODOT_PIN or metadata.get("authority") != 0:
        raise ValueError("METADATA_AUTHORITY_OR_PIN")
    project = Path(metadata.get("project", "")).expanduser().resolve()
    root = RAW_ROOT / run_id / fixture
    try:
        project.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("PROJECT_PATH_TRAVERSAL") from error
    if not project.is_dir():
        raise FileNotFoundError(project)
    files = _source_files(project)
    if metadata.get("source_files") != files:
        raise ValueError("SOURCE_CLOSURE_CHANGED")
    source_mode = metadata.get("source_mode")
    if source_mode not in (None, "legacy-copy", "native-publication-snapshot"):
        raise ValueError("SOURCE_MODE_INVALID")
    if source_mode == "legacy-copy" and metadata.get("legacy_unaccepted") is not True:
        raise ValueError("LEGACY_COPY_MUST_BE_UNACCEPTED")
    if source_mode == "native-publication-snapshot":
        provenance = metadata.get("publication_provenance")
        if type(provenance) is not dict or provenance.get("executed_snapshot_files") != files:
            raise ValueError("PUBLICATION_PROVENANCE_CHANGED")
        snapshot = Path(provenance.get("executed_snapshot", "")).expanduser().resolve()
        try:
            snapshot.relative_to(RAW_ROOT.resolve())
        except ValueError as error:
            raise ValueError("PUBLICATION_PROVENANCE_PATH") from error
    host_files, pins = _host_sources(), _binary_pins()
    if metadata.get("host_files") != host_files or metadata.get("binary_pins") != pins:
        raise ValueError("HOST_SOURCE_OR_BINARY_CHANGED")
    if metadata.get("source_closure_sha256") != _full_closure(files, host_files, pins):
        raise ValueError("SOURCE_CLOSURE_HASH")
    return root, project


def _process_start_filetime(process: subprocess.Popen[Any]) -> int | None:
    if os.name != "nt":
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.GetProcessTimes.restype = wintypes.BOOL
    values = [wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(int(process._handle), *(ctypes.byref(value) for value in values)):
        raise OSError(ctypes.get_last_error(), "GetProcessTimes")
    return (int(values[0].dwHighDateTime) << 32) | int(values[0].dwLowDateTime)


def _handle_count(process: subprocess.Popen[Any]) -> int | None:
    if os.name != "nt" or process.poll() is not None:
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessHandleCount.restype = wintypes.BOOL
    count = wintypes.DWORD()
    if not kernel.GetProcessHandleCount(int(process._handle), ctypes.byref(count)):
        raise OSError(ctypes.get_last_error(), "GetProcessHandleCount")
    return int(count.value)


def _job_process_ids(owner: Any) -> list[int]:
    """Read the owned Job's process list; a PID alone is never used to kill."""
    if os.name != "nt" or owner is None or owner._handle is None:
        return []
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                                wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    size = 4096
    for _ in range(5):
        buffer = ctypes.create_string_buffer(size)
        returned = wintypes.DWORD()
        if kernel.QueryInformationJobObject(owner._handle, 3, buffer, size, ctypes.byref(returned)):
            assigned = int.from_bytes(buffer.raw[:4], "little")
            count = int.from_bytes(buffer.raw[4:8], "little")
            word = ctypes.sizeof(ctypes.c_size_t)
            if count > assigned or 8 + count * word > size:
                raise RuntimeError("JOB_PROCESS_LIST_INVALID")
            return [int.from_bytes(buffer.raw[8 + i * word:8 + (i + 1) * word], "little")
                    for i in range(count)]
        if ctypes.get_last_error() != 234:
            raise OSError(ctypes.get_last_error(), "QueryInformationJobObject")
        size *= 4
    raise RuntimeError("JOB_PROCESS_LIST_TOO_LARGE")


DRY_RUN_SCHEMA = "hh-gt09-delegated-playtest-dry-run-2"
ENGINE_LOG_FAILURE = re.compile(r"(?im)^(?:ERROR|WARNING|SCRIPT ERROR|USER ERROR):|ObjectDB instances leaked")


def _resolve_deadline(deadline_seconds: float | None, mode: str) -> float:
    if mode not in ("scripted", "smoke"):
        raise ValueError("MODE")
    value = 960.0 if deadline_seconds is None and mode == "scripted" else \
        30.0 if deadline_seconds is None else float(deadline_seconds)
    if not 1 <= value <= 960 or not math.isfinite(value):
        raise ValueError("DEADLINE_OUT_OF_RANGE")
    return value


def _fixture_argv(binary: Path, project: str | Path, mode: str) -> list[str]:
    if mode not in ("scripted", "smoke"):
        raise ValueError("MODE")
    return [str(binary), "--path", str(project), "--position", "100,100", "--resolution", "960x540",
            "--rendering-method", "gl_compatibility", "--audio-driver", "Dummy",
            "res://scenes/fixture.tscn", "--", "--fixture-lifecycle-" + mode]


def _import_argv(binary: Path, project: str | Path) -> list[str]:
    return [str(binary), "--headless", "--editor", "--path", str(project), "--import", "--quit"]


def _engine_log_failure(directory: Path) -> str | None:
    """Return the first engine error/warning observed in bounded native logs."""
    for name in ("stdout.txt", "stderr.txt"):
        path = directory / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = ENGINE_LOG_FAILURE.search(text)
        if match:
            line = text[match.start():].splitlines()[0].strip()
            return line[:512]
    return None


def _import_cache(project: Path, *, required: tuple[str, ...] = ("avatar.glb", "sprite_sheet.png")) -> dict[str, Any]:
    imported = project / ".godot" / "imported"
    if not imported.is_dir():
        raise RuntimeError("GODOT_IMPORT_CACHE_MISSING")
    files: dict[str, str] = {}
    for path in sorted(imported.rglob("*")):
        info = path.lstat()
        if path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
            raise RuntimeError("GODOT_IMPORT_CACHE_REPARSE")
        if path.is_file():
            files[path.relative_to(imported).as_posix()] = sha(path)
    if not files:
        raise RuntimeError("GODOT_IMPORT_CACHE_EMPTY")
    for asset in required:
        if not any(name.startswith(asset + "-") for name in files):
            raise RuntimeError("GODOT_IMPORT_CACHE_ASSET_MISSING:" + asset)
    return {"root": str(imported), "files": files, "sha256": _closure_sha(files)}


def _run_import(root: Path, project: Path, metadata: dict[str, Any], binary: Path,
                deadline: float) -> dict[str, Any]:
    """Import authored assets in a separate, owned Godot process before Play."""
    from studio.tests.replay.benchmark_job import BenchmarkProcess
    output = root / "import"
    argv = _import_argv(binary, project)
    owner = BenchmarkProcess(argv, cwd=project, output=output, source_root=project,
        source_files=metadata["source_files"], binary_sha256=metadata["binary_pins"]["godot_console"])
    started = time.monotonic()
    capture = None
    try:
        while owner.tick() is None:
            failure = _engine_log_failure(output)
            if failure is not None:
                raise RuntimeError("ENGINE_LOG_FAILURE:" + failure)
            if time.monotonic() - started >= min(deadline, 120.0):
                raise RuntimeError("GODOT_IMPORT_TIMEOUT")
            time.sleep(0.1)
        capture = owner.finish()
        failure = _engine_log_failure(output)
        if failure is not None:
            raise RuntimeError("ENGINE_LOG_FAILURE:" + failure)
        cache = _import_cache(project)
    finally:
        if not owner.closed:
            owner.close()
    return {"argv": argv, "capture": capture,
            "capture_path": str(output / "capture.json"),
            "capture_sha256": sha(output / "capture.json"), "cache": cache}


def dry_run(metadata: dict[str, Any], godot: Path | None = None, *,
            deadline_seconds: float | None = None, mode: str = "scripted") -> dict[str, Any]:
    root, _ = _load_metadata(metadata)
    binary = pinned_godot(godot)
    deadline = _resolve_deadline(deadline_seconds, mode)
    project = metadata["project"]
    receipt = {
        "schema": DRY_RUN_SCHEMA, "run_id": metadata["run_id"],
        "fixture": metadata["fixture"], "dry_run": True, "native_run_performed": False,
        "authority": 0, "source_closure_sha256": metadata["source_closure_sha256"],
        "godot_pin": GODOT_PIN, "godot": str(binary), "godot_sha256": sha(binary),
        "mode": mode, "deadline_seconds": deadline,
        "argv": _fixture_argv(binary, project, mode),
        "import_argv": _import_argv(binary, project),
        "created_unix": time.time(),
    }
    (root / "dry-run.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8", newline="\n")
    return receipt


def _require_dry_run(metadata: dict[str, Any], godot: Path, root: Path, *,
                     mode: str, deadline: float, argv: list[str],
                     import_argv: list[str]) -> None:
    path = root / "dry-run.json"
    if not path.is_file():
        raise RuntimeError("DRY_RUN_REQUIRED")
    try:
        receipt = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        raise RuntimeError("DRY_RUN_INVALID") from error
    if type(receipt) is not dict:
        raise RuntimeError("DRY_RUN_INVALID")
    if (receipt.get("schema") != DRY_RUN_SCHEMA
            or receipt.get("dry_run") is not True
            or receipt.get("native_run_performed") is not False
            or receipt.get("run_id") != metadata["run_id"]
            or receipt.get("fixture") != metadata["fixture"]
            or receipt.get("source_closure_sha256") != metadata["source_closure_sha256"]
            or receipt.get("godot") != str(godot)
            or receipt.get("godot_sha256") != sha(godot)
            or receipt.get("mode") != mode
            or receipt.get("deadline_seconds") != deadline
            or receipt.get("argv") != argv
            or receipt.get("import_argv") != import_argv):
        raise RuntimeError("DRY_RUN_INVALID")


def _close_process_handle(process: Any) -> dict[str, Any]:
    from studio.tests.replay.benchmark_job import close_process_handle_native
    state = {"required": True, "closed": False, "close_uncertain": False, "handle_retained": True}
    handle = process._handle
    if handle.closed:
        raise RuntimeError("PROCESS_HANDLE_ALREADY_CLOSED_UNOBSERVED")
    if type(process.returncode) is not int:
        raise RuntimeError("PROCESS_HANDLE_LIVE")
    state["close_uncertain"] = True
    handle.closed = True
    if not close_process_handle_native(int(handle)):
        handle.closed = False
        raise RuntimeError("PROCESS_HANDLE_CLOSE_FAILED")
    return {"required": True, "closed": True, "close_uncertain": False, "handle_retained": False}


class _Recorder:
    """Gated real-time ffmpeg capture; checked native cleanup remains owned."""
    def __init__(self, root: Path, video: Path, seconds: float):
        from studio.host.blender.ui_host import HELPER, cli_job
        self.root, self.process, self.job = root, None, None
        self.closed, self.errors, self.started = False, [], time.monotonic()
        self.stdout = (root / "ffmpeg.stdout.log").open("xb")
        self.stderr = (root / "ffmpeg.stderr.log").open("xb")
        self.capture = None
        self.handle = None
        self.argv = [str(DEFAULT_FFMPEG), "-hide_banner", "-nostdin", "-f", "gdigrab",
                     "-framerate", "10", "-draw_mouse", "0", "-offset_x", "100", "-offset_y", "100",
                     "-video_size", "960x540", "-i", "desktop", "-t", str(seconds),
                     "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                     "-pix_fmt", "yuv420p", "-y", str(video)]
        try:
            cli_job.require_no_holds()
            self.process = subprocess.Popen([sys.executable, "-B", "-c", HELPER,
                str(root / "recorder-process"), *self.argv], cwd=root, stdin=subprocess.PIPE,
                stdout=self.stdout, stderr=self.stderr, creationflags=subprocess.CREATE_NO_WINDOW)
            self.job = cli_job.create(self.process)
            self.process.stdin.write(b"{}\n")
            self.process.stdin.close()
        except BaseException:
            self.close()
            raise

    def tick(self) -> int | None:
        if (self.root / "ffmpeg.stderr.log").stat().st_size > MAX_LOG_BYTES:
            raise RuntimeError("RECORDER_LOG_LIMIT")
        if (self.root / "ffmpeg.stdout.log").stat().st_size > MAX_LOG_BYTES:
            raise RuntimeError("RECORDER_LOG_LIMIT")
        return self.process.poll()

    def finish(self) -> dict[str, Any]:
        if self.tick() != 0:
            raise RuntimeError("RECORDER_ACTUAL_EXIT")
        active = self.job.active_count()
        if active != 0:
            settle = time.monotonic() + 0.5
            while active and time.monotonic() < settle:
                time.sleep(0.01)
                active = self.job.active_count()
        if active != 0:
            raise RuntimeError("RECORDER_TREE_REMAINED")
        launched = json.loads((self.root / "recorder-process-start.json").read_bytes())
        exited = json.loads((self.root / "recorder-process-exit.json").read_bytes())
        if type(exited.get("exit_code")) is not int or exited["exit_code"] != 0 or launched.get("pid") != exited.get("pid"):
            raise RuntimeError("RECORDER_EXIT_BINDING")
        self.close()
        self.capture = {"argv": self.argv, "actual_exit": exited, "natural_tree_exit": True,
                        "job": self.job.snapshot(), "process_handle": self.handle,
                        "duration_seconds": time.monotonic() - self.started,
                        "artifacts": {name: sha(self.root / name) for name in
                            ("ffmpeg.stdout.log", "ffmpeg.stderr.log", "recorder-process-start.json", "recorder-process-exit.json")}}
        (self.root / "recorder-result.json").write_text(json.dumps(self.capture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return self.capture

    def close(self) -> None:
        if self.closed:
            return
        from studio.host.blender.ui_host import cli_job
        if self.job is None and self.process is not None:
            self.job = cli_job.owner_for_process(self.process)
        if self.job is not None:
            self.job.close()
        elif self.process is not None and self.process.poll() is None:
            self.process.kill()  # Exact unreleased helper, never a PID lookup.
        if self.process is not None:
            self.process.wait(timeout=5)
            if self.process.stdin and not self.process.stdin.closed:
                self.process.stdin.close()
            self.handle = _close_process_handle(self.process)
        self.stdout.close()
        self.stderr.close()
        self.closed = True


def _media_duration(text: str) -> float:
    match = re.search(r"Duration: ([0-9]+):([0-9]+):([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        raise RuntimeError("VIDEO_DURATION_MISSING")
    return int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])


def _decode_video(root: Path, project: Path, metadata: dict[str, Any], video: Path) -> dict[str, Any]:
    from studio.tests.replay.benchmark_job import BenchmarkProcess
    argv = [str(DEFAULT_FFMPEG), "-hide_banner", "-nostdin", "-i", str(video),
            "-map", "0:v:0", "-f", "null", "NUL"]
    owner = None
    before = sha(video)
    try:
        owner = BenchmarkProcess(argv, cwd=root, output=root / "video-verify", source_root=project,
            source_files=metadata["source_files"], binary_sha256=metadata["binary_pins"]["ffmpeg"])
        deadline = time.monotonic() + 90.0
        while owner.tick() is None:
            if time.monotonic() >= deadline:
                raise RuntimeError("VIDEO_DECODE_TIMEOUT")
            time.sleep(0.25)
        capture = owner.finish()
    finally:
        if owner is not None and not owner.closed:
            owner.close()
    text = (root / "video-verify" / "stderr.txt").read_text(encoding="utf-8", errors="replace")
    seconds = _media_duration(text)
    frames = re.findall(r"frame=\s*([0-9]+)", text)
    if not frames or int(frames[-1]) < 1 or sha(video) != before:
        raise RuntimeError("VIDEO_DECODE_OR_HASH_FAILED")
    return {"status": "decoded", "path": str(video), "sha256": before, "bytes": video.stat().st_size,
            "duration_seconds": seconds, "decoded_frames": int(frames[-1]),
            "capture_sha256": sha(root / "video-verify" / "capture.json"), "capture": capture}


def host(metadata: dict[str, Any], godot: Path | None = None, *,
         deadline_seconds: float | None = None, video_path: Path | None = None,
         mode: str = "scripted") -> int:
    """Run one fixture and recorder using existing gated Windows native owners."""
    root, project = _load_metadata(metadata)
    binary = pinned_godot(godot)
    if os.name != "nt":
        raise RuntimeError("WINDOWS_REQUIRED")
    deadline = _resolve_deadline(deadline_seconds, mode)
    argv = _fixture_argv(binary, project, mode)
    import_argv = _import_argv(binary, project)
    _require_dry_run(metadata, binary, root, mode=mode, deadline=deadline,
                     argv=argv, import_argv=import_argv)
    if video_path is not None and video_path.resolve() != (root / "video" / "capture.mkv").resolve():
        raise ValueError("VIDEO_PATH_MUST_MATCH_RUN")
    video = root / "video" / "capture.mkv"
    if (root / "host-result.json").exists() or (root / "import").exists() \
            or (root / "native").exists() or video.exists():
        raise FileExistsError("RUN_ID_CONSUMED")
    sys.path.insert(0, str(STUDIO.parent))
    from studio.tests.replay.benchmark_job import BenchmarkProcess
    from studio.host.replay.process_probe import ProcessProbe, ProbeError
    from studio.tests.replay.measure_window import measurement_window
    from studio.tests.replay.benchmark_environment import KeepAwake
    result: dict[str, Any] = {
        "schema": "hh-gt09-delegated-playtest-host-2", "run_id": metadata["run_id"],
        "fixture": metadata["fixture"], "authority": 0, "acceptance": False,
        "performed_by": "agent", "delegated_by": "owner", "mode": mode,
        "source_closure_sha256": metadata["source_closure_sha256"], "godot_pin": GODOT_PIN,
        "argv": argv, "import_argv": import_argv, "import": None,
        "actual_process_exit": None, "wrapper_exit_code": None,
        "engine_exit_observation": None, "timed_out": False, "deadline_seconds": deadline,
        "started_unix": time.time(), "finished_unix": None, "duration_seconds": None,
        "handle_samples": [], "tree": {"verified": False}, "job": None,
        "process_handle": None, "probe_closed": False, "errors": [], "video": None,
        "status": "HOST_RUN_INCOMPLETE",
    }
    owner = recorder = probe = None
    native_capture = None
    started = time.monotonic()
    safely_closed = lambda: (owner is None or owner.closed) and (recorder is None or recorder.closed) and (probe is None or probe.handle is None)
    with measurement_window(metadata["run_id"], "GT09 delegated fixture " + metadata["fixture"], safe_to_release=safely_closed):
        with KeepAwake():
            try:
                _load_metadata(metadata)  # Same closure immediately before the gate release.
                result["import"] = _run_import(root, project, metadata, binary, deadline)
                if time.monotonic() - started >= deadline:
                    result["timed_out"] = True
                    raise RuntimeError("HOST_DEADLINE")
                recorder = _Recorder(root, video, 910 if mode == "scripted" else 12)
                owner = BenchmarkProcess(argv, cwd=project, output=root / "native", source_root=project,
                    source_files=metadata["source_files"], binary_sha256=metadata["binary_pins"]["godot_console"])
                seen: set[int] = set()
                gui = binary.with_name(str(_toolchain()["gui_executable"]))
                while True:
                    code = owner.tick()
                    failure = _engine_log_failure(root / "native")
                    if failure is not None:
                        raise RuntimeError("ENGINE_LOG_FAILURE:" + failure)
                    if probe is None:
                        for pid in _job_process_ids(owner.job):
                            if pid in seen:
                                continue
                            try:
                                probe = ProcessProbe(pid, gui)
                            except ProbeError as error:
                                if str(error) == "PROBE_IMAGE_IDENTITY":
                                    seen.add(pid)
                                    continue
                                raise
                            result["engine_identity"] = {"pid": pid, "process_start": probe.process_start, "image": str(gui)}
                            break
                    if probe is not None:
                        sample = probe.sample_with_handle_count()
                        if sample is not None:
                            result["handle_samples"].append(sample)
                        else:
                            result["engine_exit_observation"] = probe.exit_observation()
                    if recorder.tick() is not None and code is None:
                        raise RuntimeError("RECORDER_ENDED_BEFORE_ENGINE")
                    if code is not None:
                        break
                    if time.monotonic() - started >= deadline:
                        result["timed_out"] = True
                        raise RuntimeError("HOST_DEADLINE")
                    time.sleep(0.25)
                native_capture = owner.finish()
                failure = _engine_log_failure(root / "native")
                if failure is not None:
                    raise RuntimeError("ENGINE_LOG_FAILURE:" + failure)
                result["native_capture"] = {"path": str(root / "native" / "capture.json"),
                                            "sha256": sha(root / "native" / "capture.json")}
                result["wrapper_exit_code"] = native_capture["wrapper_exit_code"]
                if probe is None:
                    raise RuntimeError("ENGINE_IDENTITY_UNPROVEN")
                observed = probe.exit_observation()
                if observed is None:
                    raise RuntimeError("ENGINE_EXIT_UNPROVEN")
                result["engine_exit_observation"] = observed
                result["actual_process_exit"] = observed["exit_code"]
                result["duration_seconds"] = time.monotonic() - started
                result["job"] = native_capture["job"]
                result["process_handle"] = native_capture["wrapper_process_handle"]
                result["tree"] = {"verified": True, "active_before_close": native_capture["active_before_cleanup"],
                                  "active_after_close": native_capture["job"]["active_count"]}
                probe.close()
                result["probe_closed"] = probe.handle is None
                while recorder.tick() is None:
                    if time.monotonic() - started >= deadline + 20:
                        raise RuntimeError("RECORDER_DEADLINE")
                    time.sleep(0.25)
                result["recorder"] = recorder.finish()
                result["video"] = _decode_video(root, project, metadata, video)
                _load_metadata(metadata)
                result["source_unchanged"] = True
            except Exception as error:
                result["errors"].append(f"{type(error).__name__}:{error}")
            finally:
                for resource, name in ((probe, "probe"), (owner, "native"), (recorder, "recorder")):
                    if resource is None:
                        continue
                    try:
                        if name == "probe":
                            resource.close()
                            result["probe_closed"] = resource.handle is None
                        elif not resource.closed:
                            resource.close()
                    except Exception as error:
                        result["errors"].append(f"{name}_cleanup:{type(error).__name__}:{error}")
                result["finished_unix"] = time.time()
                if result["duration_seconds"] is None:
                    result["duration_seconds"] = time.monotonic() - started
    for filename, source in (("godot.stdout.log", "stdout.txt"), ("godot.stderr.log", "stderr.txt")):
        path = root / "native" / source
        if path.is_file():
            _write(root / filename, path.read_bytes())
    result["stdout_sha256"] = sha(root / "godot.stdout.log") if (root / "godot.stdout.log").is_file() else None
    result["stderr_sha256"] = sha(root / "godot.stderr.log") if (root / "godot.stderr.log").is_file() else None
    result["status"] = "HOST_RUN_CAPTURED" if not result["errors"] and not result["timed_out"] and result["actual_process_exit"] == 0 and result["video"] is not None else "HOST_RUN_INCOMPLETE"
    (root / "host-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["status"] == "HOST_RUN_CAPTURED" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--fixture", choices=sorted(FIXTURES), required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--host", action="store_true")
    parser.add_argument("--godot", type=Path)
    parser.add_argument("--deadline-seconds", type=float)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--mode", choices=("scripted", "smoke"), default="scripted")
    parser.add_argument("--project-source", type=Path,
                        help="legacy diagnostic project copy (unaccepted; use --publication-root)")
    parser.add_argument("--publication-root", type=Path,
                        help="publication evidence root whose native snapshot is consumed verbatim")
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare(args.run_id, args.fixture, args.project_source, args.publication_root),
                         indent=2, sort_keys=True))
        return 0
    metadata = json.loads(_metadata_path(args.run_id, args.fixture).read_bytes())
    if args.dry_run:
        print(json.dumps(dry_run(metadata, args.godot, deadline_seconds=args.deadline_seconds,
                                  mode=args.mode), indent=2, sort_keys=True))
        return 0
    return host(metadata, args.godot, deadline_seconds=args.deadline_seconds,
                video_path=args.video, mode=args.mode)


if __name__ == "__main__":
    raise SystemExit(main())

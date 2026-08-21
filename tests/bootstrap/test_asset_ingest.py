#!/usr/bin/env python3
"""R3-WP6: asset ingest/import/reimport/move/delete + quarantine.

Does not tick the 20-8 plan. Does not start R3-WP7.
Pin missing is a hard FAIL. No skip-PASS.
Python generates the source PNG outside the project; asset.import copies it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
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
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r3w6"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
MAX_BYTES = 8388608


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R3-WP6 [ ] while unticked; after coordinator tick allow R3-WP7+."""
    errors: list[str] = []
    current = ""
    wp6 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R3-WP6\b", stripped):
            wp6 = stripped
    if wp6 is None:
        return ["plan missing R3-WP6 heading"]
    ticked = bool(re.search(r"\[x\]", wp6, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp6:
            errors.append("R3-WP6 heading must keep [ ] until coordinator tick")
        if current != "R3-WP6":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP6 while WP6 is unticked)")
    elif not re.match(r"^R3-WP([7-9]|\d{2,})$|^R[4-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP7+ after R3-WP6 tick)")
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
    for sub in ("staging", "quarantine"):
        folder = agent / sub
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)


def tiny_png() -> bytes:
    """1x1 RGB PNG generated in the official test, never written to dest res://."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\x00\x00"
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*.ts"):
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if re.search(r"writeFile(?:Sync)?\([^)]*\.(?:png|jpg|jpeg|webp|ogg|wav)", text):
            errors.append(f"{posix} writes an imported asset from the sidecar")
        if "ResourceSaver" in text:
            errors.append(f"{posix} uses ResourceSaver")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append(f"{posix} has a generic invoke path")
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"life\.res_to_abs\([^\n]*\)\.write", self_text):
        errors.append("official test writes a dest res:// file directly")
    if "tiny_png" not in self_text or "mkdtemp" not in self_text:
        errors.append("official test must generate the source PNG in a TEMP outside the project")
    if "asset.import" not in self_text:
        errors.append("official test must call asset.import")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_asset_adapter" not in router:
        errors.append("router must dispatch the asset adapter")
    if "project.settings must stay" not in router:
        errors.append("unproven-mutate sentinel must stay on project.settings")
    if "4.7.2" in router:
        errors.append("router mentions 4.7.2")
    asset = ADDON / "core" / "hh_asset_adapter.gd"
    if not asset.is_file():
        errors.append("missing asset adapter")
    else:
        text = asset.read_text(encoding="utf-8")
        if "_stage_and_sniff" not in text or "_sniff" not in text:
            errors.append("asset adapter must stage and sniff magic")
        if "_is_polyglot" not in text or "_png_iend_end" not in text:
            errors.append("asset adapter must reject polyglot/trailing PNG payloads")
        if "MAX_BYTES" not in text:
            errors.append("asset adapter must cap source size")
        if "_promote" not in text or "rename_absolute" not in text:
            errors.append("asset adapter must atomic-promote via tmp+rename")
        if "_wait_import" not in text or "reimport_files" not in text:
            errors.append("asset adapter must wait for EditorFileSystem import")
        if "_import_busy" not in text or "_job_token" not in text:
            errors.append("asset adapter must guard reentrancy and late import jobs")
        if "_quarantine_path" not in text:
            errors.append("asset adapter must quarantine instead of hard-delete")
        delete_fn = re.search(r"func _delete\b.*?func _move\b", text, re.S)
        if delete_fn is None:
            errors.append("missing _delete")
        else:
            body = delete_fn.group(0)
            if "DirAccess.remove" in body or "remove_absolute" in body:
                errors.append("_delete must not DirAccess.remove the live dest")
            if "E_CONFLICT" not in body:
                errors.append("_delete must E_CONFLICT when the asset is still referenced")
        promote_fn = re.search(r"func _promote\b.*?func _wait_import\b", text, re.S)
        if promote_fn is None:
            errors.append("missing _promote")
        else:
            atom = promote_fn.group(0)
            if "FileAccess.open(dest, FileAccess.WRITE)" in atom:
                errors.append("promote must not FileAccess.WRITE the live dest")
            if ".tmp" not in atom or "rename_absolute" not in atom:
                errors.append("promote must write dest.tmp then rename")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append("asset adapter has a generic invoke path")
        if "addons/hh_agent" in text and "_jail_dest" not in text:
            errors.append("asset adapter must jail dest paths")
    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "if _busy:" not in plugin:
        errors.append("plugin must skip queue drain while a command is busy (import reentrancy)")
    life_ts = BRIDGE / "src" / "ledger" / "scene_lifecycle.ts"
    if life_ts.is_file():
        life_text = life_ts.read_text(encoding="utf-8")
        if "asset.import" not in life_text or "isAssetIngestApply" not in life_text:
            errors.append("sidecar must treat asset.import as a proven apply verb")
    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "import_sidecar" not in execute or "late import" not in execute:
        errors.append("ledger must verify import sidecar and reject a late old job")
    actions_ts = (BRIDGE / "src" / "registry" / "actions.ts").read_text(encoding="utf-8")
    if "OS_SOURCE" not in actions_ts:
        errors.append("asset.import must accept an external OS_SOURCE")
    if '"project.settings"' not in actions_ts:
        errors.append("catalog must keep project.settings")
    for path in ADDON.rglob("*.gd"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append(f"{rel(path)} has a generic invoke path")
            break
    return errors


def variant(typ: str, value) -> dict:
    return {"schema": SCHEMA, "type": typ, "value": value}


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 40.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    tool: str,
    action: str,
    params: dict,
    timeout: float = 40.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(proc, req_id, tool, {"action": action, "params": params, "command_id": cid}, timeout)
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


def expect_code(body: dict, codes: tuple[str, ...], errors: list[str], label: str) -> None:
    got = str((body.get("error") or {}).get("code") or "")
    if body.get("ok") is True or got not in codes:
        errors.append(f"{label} expected {codes}, got {body}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def try_junction_escape() -> str | None:
    outside = Path(tempfile.mkdtemp(prefix="hh-r3w6-link-"))
    link = TEMP_DIR / "outlink"
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            done = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                check=False,
                capture_output=True,
                text=True,
            )
            if done.returncode != 0 or not link.exists():
                shutil.rmtree(outside, ignore_errors=True)
                return None
        else:
            link.symlink_to(outside, target_is_directory=True)
        return "res://r3w6/outlink/escaped.png"
    except OSError:
        shutil.rmtree(outside, ignore_errors=True)
        return None


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    outside = Path(tempfile.mkdtemp(prefix="hh-r3w6-src-"))
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    dest = "res://r3w6/floor.png"
    dest_abs = life.res_to_abs(dest)
    other = "res://r3w6/spare.png"
    other_abs = life.res_to_abs(other)
    corrupt_dest = "res://r3w6/corrupt.png"
    poly_dest = "res://r3w6/polyglot.png"
    huge_dest = "res://r3w6/huge.png"
    scene = "res://r3w6/main.tscn"
    req_id = 2
    try:
        src_png = outside / "tiny.png"
        src_png.write_bytes(tiny_png())
        src_other = outside / "spare.png"
        src_other.write_bytes(tiny_png())
        src_corrupt = outside / "corrupt.png"
        src_corrupt.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-png")
        src_poly = outside / "poly.png"
        src_poly.write_bytes(tiny_png() + b"PK\x03\x04junk")
        src_huge = outside / "huge.png"
        src_huge.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_BYTES + 1))

        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = life.start_godot(exe)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors

        if dest_abs.is_file():
            errors.append("dest res:// file existed before asset.import")
            return errors

        req_id, ingested = tool_call(
            proc,
            req_id,
            "godot.asset",
            "import",
            {"path": dest, "source": str(src_png), "license": "test-fixture"},
        )
        if not ack_ok(ingested, errors, "asset.import tiny PNG"):
            return errors
        if not dest_abs.is_file():
            errors.append("asset.import did not promote dest under res://")
            return errors
        sidecar = dest_abs.with_name(dest_abs.name + ".import")
        if not sidecar.is_file():
            errors.append("asset.import ACK without a .import sidecar")
            return errors
        if dest_abs.read_bytes() != src_png.read_bytes():
            errors.append("promoted dest bytes != source PNG")
        after = ingested.get("after") or {}
        if after.get("import_sidecar") is not True or after.get("resource_exists") is not True:
            errors.append(f"import postcondition flags missing: {ingested}")
        if str(after.get("job") or "") != str(ingested.get("command_id") or after.get("job") or ""):
            if str(after.get("job") or "") == "":
                errors.append("import after.job missing")
        if str(after.get("disk_hash") or "") != sha256_file(dest_abs):
            errors.append(f"import disk SHA mismatch: {ingested}")

        req_id, collision = tool_call(
            proc,
            req_id,
            "godot.asset",
            "import",
            {"path": dest, "source": str(src_other)},
        )
        expect_code(collision, ("E_CONFLICT",), errors, "same-name collision")

        req_id, reimported = tool_call(proc, req_id, "godot.asset", "reimport", {"path": dest})
        if not ack_ok(reimported, errors, "asset.reimport"):
            return errors

        req_id, bad = tool_call(
            proc,
            req_id,
            "godot.asset",
            "import",
            {"path": corrupt_dest, "source": str(src_corrupt)},
        )
        expect_code(bad, ("E_INVALID_TYPE",), errors, "corrupt bytes")
        if life.res_to_abs(corrupt_dest).is_file():
            errors.append("corrupt ingest left a dest file")

        req_id, poly = tool_call(
            proc,
            req_id,
            "godot.asset",
            "import",
            {"path": poly_dest, "source": str(src_poly)},
        )
        expect_code(poly, ("E_INVALID_TYPE",), errors, "polyglot PNG")
        if life.res_to_abs(poly_dest).is_file():
            errors.append("polyglot ingest left a dest file")

        req_id, huge = tool_call(
            proc,
            req_id,
            "godot.asset",
            "import",
            {"path": huge_dest, "source": str(src_huge)},
        )
        expect_code(huge, ("E_OUT_OF_BOUNDS", "E_INVALID_TYPE"), errors, "huge source")
        if life.res_to_abs(huge_dest).is_file():
            errors.append("huge ingest left a dest file")

        jail = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.asset",
                {
                    "action": "import",
                    "params": {"path": "res://../escape.png", "source": str(src_png)},
                    "command_id": life.new_ulid(),
                },
            )
        )
        req_id += 1
        expect_code(jail, ("E_PATH",), errors, "path with ..")

        addon_dest = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.asset",
                {
                    "action": "import",
                    "params": {"path": "res://addons/hh_agent/r3w6_attack.png", "source": str(src_png)},
                    "command_id": life.new_ulid(),
                },
            )
        )
        req_id += 1
        expect_code(addon_dest, ("E_PATH", "E_OUT_OF_BOUNDS"), errors, "import into addons/hh_agent")
        attack_abs = ADDON / "r3w6_attack.png"
        if attack_abs.is_file():
            errors.append("asset.import into addons/hh_agent created a file")
            try:
                attack_abs.unlink()
            except OSError:
                pass

        linked = try_junction_escape()
        if linked:
            req_id, escaped = tool_call(
                proc,
                req_id,
                "godot.asset",
                "import",
                {"path": linked, "source": str(src_png)},
            )
            expect_code(escaped, ("E_PATH",), errors, "symlink/junction escape")
            escaped_abs = PLUGIN_PROJECT / "r3w6" / "outlink" / "escaped.png"
            if escaped_abs.is_file():
                errors.append("symlink escape wrote a dest outside the jail")

        req_id, spare = tool_call(
            proc,
            req_id,
            "godot.asset",
            "import",
            {"path": other, "source": str(src_other)},
        )
        if not ack_ok(spare, errors, "asset.import spare PNG"):
            return errors

        req_id, scene_body = tool_call(
            proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"}
        )
        if not ack_ok(scene_body, errors, "scene.create"):
            return errors
        req_id, added = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Sprite2D", "name": "Sprite"},
        )
        if not ack_ok(added, errors, "node.add Sprite"):
            return errors
        req_id, assigned = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "Sprite", "property": "texture", "resource": dest},
        )
        if not ack_ok(assigned, errors, "resource.assign texture"):
            return errors
        req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved, errors, "scene.save"):
            return errors

        req_id, del_ref = tool_call(proc, req_id, "godot.asset", "delete", {"path": dest})
        expect_code(del_ref, ("E_CONFLICT",), errors, "delete referenced")
        if not dest_abs.is_file():
            errors.append("referenced delete silently removed the dest")

        req_id, del_spare = tool_call(proc, req_id, "godot.asset", "delete", {"path": other})
        if not ack_ok(del_spare, errors, "delete unreferenced"):
            return errors
        if other_abs.is_file():
            errors.append("unreferenced delete left the dest in res://")
        qpath = str((del_spare.get("after") or {}).get("quarantine_path") or "")
        if (del_spare.get("after") or {}).get("quarantined") is not True:
            errors.append(f"unreferenced delete must quarantine: {del_spare}")
        if qpath and not Path(qpath).is_file():
            errors.append(f"quarantine path missing: {qpath}")

        req_id, deps = tool_call(proc, req_id, "godot.asset", "dependencies", {"path": dest})
        if not ack_ok(deps, errors, "asset.dependencies"):
            return errors

        req_id, settings = tool_call(
            proc,
            req_id,
            "godot.project",
            "settings",
            {
                "key": "application/config/name",
                "value": {"schema": "hh-godot-variant/1", "type": "int", "value": 1},
            },
        )
        expect_code(settings, ("E_UNVERIFIED",), errors, "unproven project.settings")

        paused = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused.get("ok") is not True:
            errors.append(f"hh.pause failed: {paused}")
        req_id, paused_import = tool_call(
            proc,
            req_id,
            "godot.asset",
            "import",
            {"path": "res://r3w6/paused.png", "source": str(src_png)},
        )
        expect_code(paused_import, ("E_PAUSED",), errors, "paused asset.import")
        if life.res_to_abs("res://r3w6/paused.png").is_file():
            errors.append("paused import wrote dest")

        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live asset ingest failed: {type(exc).__name__}: {exc}", secret))
    finally:
        life.stop_proc(godot)
        life.stop_proc(proc)
        if desc_path and desc_path.is_file():
            try:
                desc_path.unlink()
            except OSError:
                pass
        shutil.rmtree(outside, ignore_errors=True)
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
        print("FAIL: asset ingest", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    gen = subprocess.run(
        [sess.npm(), "run", "generate"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if gen.returncode != 0:
        errors.append(f"npm run generate failed:\n{gen.stdout}\n{gen.stderr}")
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
        print("FAIL: asset ingest", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: asset ingest/import wait + .import sidecar; corrupt/polyglot/huge typed fail; "
        "path jail; collision; referenced delete E_CONFLICT; unreferenced quarantine; Pause."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

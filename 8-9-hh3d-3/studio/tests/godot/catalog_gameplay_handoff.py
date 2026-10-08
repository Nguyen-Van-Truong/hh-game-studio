"""Read-only binding of catalog-native scenes into gameplay publication.

This module consumes historical diagnostic evidence only.  It never runs Godot,
replays a builder, rewrites a scene, or grants publication authority.  The
optional mount helper copies the already verified scene bytes verbatim; it does
not synthesize or relabel a TSCN.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import os
import re
import stat
import sys
import tempfile
from typing import Any, Mapping


STUDIO = Path(__file__).resolve().parents[2]
ARENA_FIXTURE = "gameplay_arena_physics"
SCHEMA = "hh-catalog-gameplay-handoff-1"
MAX_SCENE_BYTES = 1_048_576
_SHA = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")
_ID = re.compile(r"[a-z][a-z0-9._-]{0,127}\Z")


class CatalogGameplayHandoffError(ValueError):
    """Fail-closed error raised for stale, unbound, or malformed evidence."""


def _need(condition: object, code: str) -> None:
    if not condition:
        raise CatalogGameplayHandoffError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_sha(value: Mapping[str, Any]) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _json(path: Path, *, maximum: int = 8 * 1024 * 1024) -> tuple[dict[str, Any], bytes]:
    raw = _read_file(path, maximum=maximum)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise CatalogGameplayHandoffError("CATALOG_HANDOFF_JSON") from exc
    _need(type(value) is dict, "CATALOG_HANDOFF_OBJECT")
    return value, raw


def _read_file(path: Path, *, maximum: int = MAX_SCENE_BYTES) -> bytes:
    """Read one regular, non-reparse file with a stable metadata check."""
    path = Path(path)
    _need(path.is_absolute(), "CATALOG_HANDOFF_ABSOLUTE_PATH")
    try:
        for parent in (path, *path.parents):
            info = parent.lstat()
            _need(not stat.S_ISLNK(info.st_mode)
                  and not getattr(info, "st_file_attributes", 0) & 0x400,
                  "CATALOG_HANDOFF_REPARSE")
        before = path.stat()
        _need(stat.S_ISREG(before.st_mode) and before.st_size <= maximum,
              "CATALOG_HANDOFF_FILE")
        raw = path.read_bytes()
        after = path.stat()
    except (FileNotFoundError, OSError) as exc:
        raise CatalogGameplayHandoffError("CATALOG_HANDOFF_FILE") from exc
    _need((before.st_size, before.st_mtime_ns, before.st_ino) ==
          (after.st_size, after.st_mtime_ns, after.st_ino)
          and len(raw) <= maximum, "CATALOG_HANDOFF_FILE_CHANGED")
    return raw


def _root(value: Path | str, code: str) -> Path:
    root = Path(value).expanduser().absolute()
    _need(root.is_dir(), code)
    _need(not root.is_symlink() and not getattr(root.stat(), "st_file_attributes", 0) & 0x400,
          code)
    return root


def _load_native_host():
    """Load the producer verifier without importing or executing its evidence."""
    path = STUDIO / "godot-addon" / "catalog_native_host.py"
    key = "_hh_catalog_native_host_" + _sha(path.read_bytes())
    loaded = sys.modules.get(key)
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location(key, path)
    _need(spec is not None and spec.loader is not None, "CATALOG_NATIVE_VERIFIER")
    # catalog_native_host imports the studio package; expose its parent only.
    parent = str(STUDIO.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(key, None)
        raise
    return module


def _verified_native(catalog_root: Path) -> dict[str, Any]:
    """Ask the existing native verifier to validate historical producer bytes."""
    native = _load_native_host()
    try:
        # Absolute root matters: the historical invocation records an absolute
        # project cwd.  ``require_current_source=False`` deliberately permits
        # an old producer closure while still checking every evidence hash.
        result = native.verify_native(catalog_root, require_current_source=False)
    except CatalogGameplayHandoffError:
        raise
    except Exception as exc:
        code = str(exc)
        raise CatalogGameplayHandoffError(
            code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "CATALOG_NATIVE_VERIFY") from exc
    _need(result.get("status") == "DIAGNOSTIC_PASS"
          and result.get("authority") == 0 and result.get("public_ack") is False,
          "CATALOG_NATIVE_RESULT")
    return result


def _hex(value: Any, code: str = "CATALOG_HANDOFF_HASH") -> str:
    _need(type(value) is str and _SHA.fullmatch(value), code)
    return value.removeprefix("sha256:")


def _same_hash(value: Any, raw: bytes, code: str) -> None:
    _need(_hex(value, code) == _sha(raw), code)


def _transaction_identity(catalog_root: Path) -> tuple[dict[str, Any], bytes]:
    data, raw = _json(catalog_root / "project" / "catalog-input.json")
    transaction = data.get("transaction")
    _need(type(transaction) is dict, "CATALOG_TRANSACTION_BINDING")
    _need(type(transaction.get("transaction_digest")) is str
          and type(transaction.get("command_ids")) is list
          and transaction.get("command_ids")
          and all(type(value) is str and _ID.fullmatch(value) for value in transaction["command_ids"]),
          "CATALOG_TRANSACTION_BINDING")
    return transaction, raw


def _registered_envelope(registered_root: Path, *, fixture: str = "arena") -> tuple[dict[str, Any], bytes]:
    result, raw = _json(registered_root / "registered-owner-result.json",
                        maximum=32 * 1024 * 1024)
    _need(result.get("schema") == "hh-godot-registered-authoring-owner-1"
          and result.get("status") == "DIAGNOSTIC_PASS"
          and result.get("authority") == 0 and result.get("public_ack") is False,
          "REGISTERED_OWNER_RESULT")
    _need(result.get("fixture") == fixture and result.get("profile")
          and result.get("native_run_id"), "REGISTERED_OWNER_RESULT")
    _need(result.get("run_id") == registered_root.name, "REGISTERED_OWNER_RUN_BINDING")
    envelope = dict(result)
    envelope_hash = envelope.pop("envelope_sha256", None)
    _need(type(envelope_hash) is str and envelope_hash == _canonical_sha(envelope),
          "REGISTERED_OWNER_ENVELOPE_HASH")
    receipt = result.get("receipt")
    _need(type(receipt) is dict, "REGISTERED_OWNER_RECEIPT")
    return result, raw


@dataclass(frozen=True, slots=True)
class CatalogArenaHandoff:
    """Verified immutable scene bytes and producer provenance."""

    scene_bytes: bytes
    scene_sha256: str
    catalog_root: str
    registered_root: str
    native_run_id: str
    transaction_digest: str
    command_ids: tuple[str, ...]
    source_closure_sha256: str
    provenance: Mapping[str, Any]
    authority: int = 0
    public_ack: bool = False
    scene_path: str = "scenes/arena.tscn"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "scene_path": self.scene_path,
            "scene_sha256": self.scene_sha256,
            "scene_size_bytes": len(self.scene_bytes),
            "catalog_root": self.catalog_root,
            "registered_root": self.registered_root,
            "native_run_id": self.native_run_id,
            "transaction_digest": self.transaction_digest,
            "command_ids": list(self.command_ids),
            "source_closure_sha256": self.source_closure_sha256,
            "provenance": dict(self.provenance),
            "authority": self.authority,
            "public_ack": self.public_ack,
        }


def verify_catalog_arena_handoff(catalog_root: Path | str,
                                 registered_root: Path | str) -> CatalogArenaHandoff:
    """Verify the catalog arena and registered-owner evidence as one chain.

    The producer verifier is explicitly historical (`require_current_source=False`).
    A successful return is still diagnostic, AUTHORITY=0 evidence and carries no
    publication ACK.
    """
    catalog = _root(catalog_root, "CATALOG_ROOT")
    registered = _root(registered_root, "REGISTERED_ROOT")
    result = _verified_native(catalog)
    binding, _binding_raw = _json(catalog / "binding.json")
    receipt_file = catalog / "registered-owner-receipt.json"
    receipt, receipt_raw = _json(receipt_file, maximum=32 * 1024 * 1024)
    owner_result, owner_raw = _registered_envelope(registered)
    owner_receipt = owner_result["receipt"]
    _need(receipt == owner_receipt, "REGISTERED_RECEIPT_MISMATCH")
    _need(_sha(receipt_raw) == _sha((catalog / "registered-owner-receipt.json").read_bytes()),
          "REGISTERED_RECEIPT_READBACK")
    _need(owner_result.get("native_run_id") == catalog.name
          and receipt.get("native_run_id") == catalog.name,
          "REGISTERED_NATIVE_RUN_BINDING")
    _need(owner_result.get("fixture") == "arena", "REGISTERED_FIXTURE_BINDING")
    _need(receipt.get("schema") == "hh-godot-registered-authoring-owner-1"
          and receipt.get("state_kind") == "NATIVE_OBSERVED_AUTHORITY0"
          and receipt.get("authority") == 0 and receipt.get("public_ack") is False,
          "REGISTERED_RECEIPT_AUTHORITY")
    admission = receipt.get("admission")
    _need(type(admission) is dict and admission == owner_result.get("admission"),
          "REGISTERED_ADMISSION_BINDING")

    scene = _read_file(catalog / "project" / "scenes" / "authored.tscn")
    _need(scene.startswith(b"[gd_scene "), "CATALOG_SCENE_FORMAT")
    scene_hash = _sha(scene)
    _need(result.get("artifacts", {}).get("project/scenes/authored.tscn") == scene_hash,
          "CATALOG_SCENE_ARTIFACT")
    _need(receipt.get("native_scene_sha256") == scene_hash,
          "REGISTERED_SCENE_BINDING")

    transaction, input_raw = _transaction_identity(catalog)
    _need(receipt.get("transaction_digest") == transaction.get("transaction_digest")
          and owner_result.get("transaction", {}).get("transaction_digest") == transaction.get("transaction_digest"),
          "REGISTERED_TRANSACTION_BINDING")
    _need(transaction.get("project_id") == admission.get("project_id")
          and transaction.get("lease_id") == admission.get("lease_id")
          and transaction.get("fencing_epoch") == admission.get("fencing_epoch")
          and transaction.get("expected_revision") == admission.get("revision")
          and transaction.get("generation") == admission.get("generation")
          and transaction.get("project_revision") == admission.get("project_revision"),
          "REGISTERED_ADMISSION_BINDING")
    ids = tuple(transaction["command_ids"])
    _need(tuple(receipt.get("command_ids", ())) == ids
          and tuple(owner_result.get("transaction", {}).get("command_ids", ())) == ids,
          "REGISTERED_COMMAND_BINDING")
    _need(receipt.get("readback_ack") is True and receipt.get("native_observed") is True
          and receipt.get("editor_diagnostic_pass") is True,
          "REGISTERED_READBACK")
    process = receipt.get("native_process")
    _need(type(process) is dict and process.get("exit_code") == 0
          and type(process.get("pid")) is int and process["pid"] > 0,
          "REGISTERED_PROCESS_EXIT")
    # Keep explicit byte checks separate so the producer-to-receipt link is
    # checked against the actual bytes on disk.
    native_result_raw = _read_file(catalog / "result.json")
    observation_raw = _read_file(catalog / "native-observation.json")
    _need(receipt.get("native_result_sha256") == _sha(native_result_raw)
          and receipt.get("native_observation_sha256") == _sha(observation_raw),
          "REGISTERED_RESULT_BINDING")
    _need(receipt.get("source_closure_sha256") == binding.get("source_closure_sha256")
          == owner_result.get("source_closure_sha256"),
          "REGISTERED_SOURCE_CLOSURE")
    _need(type(input_raw) is bytes and result.get("binding_sha256") == _sha(_read_file(catalog / "binding.json")),
          "CATALOG_BINDING_HASH")
    _need(receipt.get("blender_handoff") == binding.get("blender_handoff"),
          "REGISTERED_BLENDER_BINDING")
    provenance = {
        "catalog_result_sha256": _sha(native_result_raw),
        "catalog_observation_sha256": _sha(observation_raw),
        "catalog_binding_sha256": _sha(_read_file(catalog / "binding.json")),
        "registered_result_sha256": _sha(owner_raw),
        "registered_receipt_sha256": _sha(receipt_raw),
        "transaction_digest": transaction["transaction_digest"],
        "admission": admission,
        "source_closure_sha256": receipt["source_closure_sha256"],
        "blender_handoff": receipt.get("blender_handoff"),
        "authority": 0,
        "public_ack": False,
    }
    return CatalogArenaHandoff(scene, scene_hash, str(catalog), str(registered),
                               catalog.name, transaction["transaction_digest"], ids,
                               receipt["source_closure_sha256"], provenance)


def verify_catalog_room_handoff(catalog_root: Path | str,
                                registered_root: Path | str) -> CatalogArenaHandoff:
    """Bind the 3D room catalog run using the same receipt chain as arena.

    The dataclass name is retained for wire compatibility with the first
    arena bridge; ``scene_path`` identifies the room asset explicitly.
    """
    catalog = _root(catalog_root, "CATALOG_ROOT")
    registered = _root(registered_root, "REGISTERED_ROOT")
    result = _verified_native(catalog)
    binding, _binding_raw = _json(catalog / "binding.json")
    receipt_file = catalog / "registered-owner-receipt.json"
    receipt, receipt_raw = _json(receipt_file, maximum=32 * 1024 * 1024)
    owner_result, owner_raw = _registered_envelope(registered, fixture="room")
    owner_receipt = owner_result["receipt"]
    _need(receipt == owner_receipt, "REGISTERED_RECEIPT_MISMATCH")
    _need(owner_result.get("native_run_id") == catalog.name
          and receipt.get("native_run_id") == catalog.name
          and owner_result.get("fixture") == "room", "REGISTERED_FIXTURE_BINDING")
    scene = _read_file(catalog / "project" / "scenes" / "authored.tscn")
    _need(scene.startswith(b"[gd_scene "), "CATALOG_SCENE_FORMAT")
    scene_hash = _sha(scene)
    _need(result.get("artifacts", {}).get("project/scenes/authored.tscn") == scene_hash
          and receipt.get("native_scene_sha256") == scene_hash,
          "REGISTERED_SCENE_BINDING")
    transaction, input_raw = _transaction_identity(catalog)
    _need(receipt.get("transaction_digest") == transaction.get("transaction_digest")
          and owner_result.get("transaction", {}).get("transaction_digest") == transaction.get("transaction_digest"),
          "REGISTERED_TRANSACTION_BINDING")
    ids = tuple(transaction["command_ids"])
    _need(tuple(receipt.get("command_ids", ())) == ids
          and tuple(owner_result.get("transaction", {}).get("command_ids", ())) == ids,
          "REGISTERED_COMMAND_BINDING")
    _need(receipt.get("readback_ack") is True and receipt.get("native_observed") is True
          and receipt.get("editor_diagnostic_pass") is True,
          "REGISTERED_READBACK")
    process = receipt.get("native_process")
    _need(type(process) is dict and process.get("exit_code") == 0
          and type(process.get("pid")) is int and process["pid"] > 0,
          "REGISTERED_PROCESS_EXIT")
    native_result_raw = _read_file(catalog / "result.json")
    observation_raw = _read_file(catalog / "native-observation.json")
    _need(receipt.get("native_result_sha256") == _sha(native_result_raw)
          and receipt.get("native_observation_sha256") == _sha(observation_raw),
          "REGISTERED_RESULT_BINDING")
    _need(receipt.get("source_closure_sha256") == binding.get("source_closure_sha256")
          == owner_result.get("source_closure_sha256"), "REGISTERED_SOURCE_CLOSURE")
    _need(type(input_raw) is bytes
          and result.get("binding_sha256") == _sha(_read_file(catalog / "binding.json")),
          "CATALOG_BINDING_HASH")
    _need(receipt.get("blender_handoff") == binding.get("blender_handoff"),
          "REGISTERED_BLENDER_BINDING")
    provenance = {
        "catalog_result_sha256": _sha(native_result_raw),
        "catalog_observation_sha256": _sha(observation_raw),
        "catalog_binding_sha256": _sha(_read_file(catalog / "binding.json")),
        "registered_result_sha256": _sha(owner_raw),
        "registered_receipt_sha256": _sha(receipt_raw),
        "transaction_digest": transaction["transaction_digest"],
        "source_closure_sha256": receipt["source_closure_sha256"],
        "blender_handoff": receipt.get("blender_handoff"),
        "authority": 0, "public_ack": False,
    }
    return CatalogArenaHandoff(scene, scene_hash, str(catalog), str(registered),
                               catalog.name, transaction["transaction_digest"], ids,
                               receipt["source_closure_sha256"], provenance,
                               scene_path="scenes/room.tscn")


def mount_catalog_arena(handoff: CatalogArenaHandoff, project_root: Path | str,
                        *, relative_path: str = "scenes/arena.tscn") -> Path:
    """Copy verified arena bytes exactly once into a caller-owned project.

    This is an explicit materialization step for the gameplay runner.  It uses
    temp+replace, refuses traversal/reparse paths and rejects an existing file;
    the source bytes and hash are unchanged.
    """
    _need(isinstance(handoff, CatalogArenaHandoff)
          and handoff.authority == 0 and handoff.public_ack is False,
          "CATALOG_HANDOFF_CONTEXT")
    _need(_sha(handoff.scene_bytes) == handoff.scene_sha256,
          "CATALOG_HANDOFF_SCENE_HASH")
    root = _root(project_root, "GAMEPLAY_PROJECT_ROOT")
    _need(type(relative_path) is str and relative_path == "scenes/arena.tscn",
          "CATALOG_ARENA_DESTINATION")
    destination = root / relative_path
    _need(destination.parent.resolve().is_relative_to(root.resolve()),
          "CATALOG_ARENA_DESTINATION")
    _need(not destination.exists(), "CATALOG_ARENA_EXISTS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    for parent in (destination.parent, *destination.parent.parents):
        info = parent.lstat()
        _need(not stat.S_ISLNK(info.st_mode)
              and not getattr(info, "st_file_attributes", 0) & 0x400,
              "CATALOG_ARENA_REPARSE")
    _need(not destination.is_symlink(), "CATALOG_ARENA_REPARSE")
    fd, temporary = tempfile.mkstemp(prefix=".arena.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(handoff.scene_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    _need(_read_file(destination) == handoff.scene_bytes
          and _sha(_read_file(destination)) == handoff.scene_sha256,
          "CATALOG_ARENA_MOUNT_READBACK")
    return destination


def inspect_blender_content_publication(publication_root: Path | str,
                                        handoff: CatalogArenaHandoff) -> dict[str, Any]:
    """Read and bind the protected Blender fixture publication, without launch."""
    _need(isinstance(handoff, CatalogArenaHandoff), "CATALOG_HANDOFF_CONTEXT")
    root = _root(publication_root, "BLENDER_PUBLICATION_ROOT")
    # Import through the studio package because the job uses package-relative
    # imports.  Importing it performs no native work; inspect_publication is a
    # protected, read-only file check.
    parent = str(STUDIO.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    try:
        import importlib
        module = importlib.import_module("studio.host.blender.fixture_content_job")
        observed = module.inspect_publication(root)
    except CatalogGameplayHandoffError:
        raise
    except Exception as exc:
        raise CatalogGameplayHandoffError("BLENDER_PUBLICATION_VERIFY") from exc
    bound = handoff.provenance.get("blender_handoff")
    _need(type(bound) is dict, "BLENDER_HANDOFF_BINDING")
    publication = observed.get("manifest", {}).get("run_id")
    files = observed.get("files", {})
    _need(observed.get("public_ack") is False
          and bound.get("published_root") == str(root)
          and bound.get("command_id") == publication
          and bound.get("glb_sha256") == files.get("scene.glb", {}).get("sha256")
          and bound.get("sprite_sha256") == files.get("sprite_sheet.png", {}).get("sha256")
          and bound.get("manifest_sha256") == _sha(_read_file(root / "manifest.json")),
          "BLENDER_HANDOFF_BINDING")
    return {"schema": "hh-catalog-blender-content-binding-1", "read_only": True,
            "authority": 0, "public_ack": False, "publication": observed,
            "handoff": dict(bound)}


def read_blender_content_artifacts(publication_root: Path | str,
                                   handoff: CatalogArenaHandoff) -> dict[str, Any]:
    """Return exact protected GLB/PNG bytes after a read-only inspection.

    The publication is inspected first, then reopened using its recorded root
    identity.  Gameplay callers may mount the returned bytes into a candidate
    project, but this helper itself performs no writes and emits no ACK.
    """
    checked = inspect_blender_content_publication(publication_root, handoff)
    manifest = checked["publication"].get("manifest", {})
    root = _root(publication_root, "BLENDER_PUBLICATION_ROOT")
    _need(manifest.get("protected_root_identity") is not None,
          "BLENDER_ROOT_IDENTITY")
    parent = str(STUDIO.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    try:
        from studio.host.core.custody import identity_from
        from studio.host.core.safe_replace import ProtectedFileRoot
        protected = ProtectedFileRoot.reopen_readonly(
            root, identity_from(manifest["protected_root_identity"]))
    except Exception as exc:
        raise CatalogGameplayHandoffError("BLENDER_ROOT_REOPEN") from exc
    try:
        versions: dict[str, Any] = {}
        raw_files: dict[str, bytes] = {}
        for name in ("scene.glb", "sprite_sheet.png", "manifest.json"):
            version, raw = protected.read(name)
            versions[name] = version
            raw_files[name] = raw
    except Exception as exc:
        raise CatalogGameplayHandoffError("BLENDER_ARTIFACT_READBACK") from exc
    finally:
        protected.close()
    files = checked["publication"].get("files", {})
    _need(_sha(raw_files["scene.glb"]) == files.get("scene.glb", {}).get("sha256")
          and _sha(raw_files["sprite_sheet.png"]) == files.get("sprite_sheet.png", {}).get("sha256")
          and _sha(raw_files["manifest.json"]) == checked["handoff"].get("manifest_sha256"),
          "BLENDER_ARTIFACT_BINDING")
    return {
        "schema": "hh-catalog-blender-content-artifacts-1",
        "scene_glb_bytes": raw_files["scene.glb"],
        "sprite_sheet_bytes": raw_files["sprite_sheet.png"],
        "manifest_sha256": _sha(raw_files["manifest.json"]),
        "artifact_sha256": {
            "scene.glb": _sha(raw_files["scene.glb"]),
            "sprite_sheet.png": _sha(raw_files["sprite_sheet.png"]),
        },
        "published_root": str(root),
        "protected_root_identity": manifest["protected_root_identity"],
        "authority": 0,
        "public_ack": False,
    }


def room_runtime_gap() -> dict[str, Any]:
    """Describe the minimum adapter work needed for the current native room.

    The catalog room TSCN is a static topology (avatar, platform, trigger,
    camera).  ``room3d_native.gd`` currently builds a different world in
    ``_ready`` and owns the gameplay lifecycle.  This report is intentionally
    declarative so callers can plan the adapter without mutating that script.
    """
    return {
        "schema": "hh-catalog-room-runtime-gap-1",
        "fixture": "gameplay_source_room_3d_native",
        "current_scene": "scenes/authored.tscn",
        "current_builder": "tests/godot/gameplay_fixture/room3d_native.gd",
        "authority": 0,
        "public_ack": False,
        "smallest_runtime_changes": [
            "Mount authored.tscn as the gameplay world and bind Avatar, Platform, Trigger, and Camera by stable ids.",
            "Move the existing lifecycle/physics callbacks into a thin catalog-room adapter; do not call the dynamic _ready world builder.",
            "Add the missing Pickup Area3D and HUD/Status nodes (or bind equivalent authored nodes) because authored.tscn has neither.",
            "Copy the protected Blender scene.glb and sprite_sheet.png into assets/ and perform import/readback from the adapter.",
            "Keep asset paths literal and retain the existing 60 Hz trace, interaction, replay, checkpoint, and perf assertions.",
        ],
        "current_scene_gaps": {
            "script": True,
            "pickup": True,
            "hud": True,
            "asset_ext_resources": True,
            "avatar": False,
            "platform": False,
            "trigger": False,
            "camera": False,
        },
        "residual": "Until that adapter exists and runs, room catalog evidence remains topology/readback evidence and cannot claim gameplay publication.",
    }


# Descriptive aliases for callers that refer to the handoff generically.
verify_catalog_gameplay_handoff = verify_catalog_arena_handoff
mount_native_arena = mount_catalog_arena


__all__ = ["SCHEMA", "CatalogGameplayHandoffError", "CatalogArenaHandoff",
           "verify_catalog_arena_handoff", "mount_catalog_arena",
           "verify_catalog_room_handoff",
           "verify_catalog_gameplay_handoff", "mount_native_arena",
           "inspect_blender_content_publication", "read_blender_content_artifacts",
           "room_runtime_gap"]

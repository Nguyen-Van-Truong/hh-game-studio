"""Host-owned GT-09 Blender producer and protected handoff.

The runner deliberately does not use a caller supplied Blend or command. It
validates the fixed content recipe, launches one pinned Blender process behind
the existing ``cli_job`` Job and records the real child exit. A caller must
provide an existing fenced lease and checker; this module never mints a
synthetic lease or turns child JSON into a receipt. The final files are copied
through the existing PrivateBlobStore and ProtectedFileRoot primitives.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.custody import identity_value, identity_from
from studio.host.core.private_store import PrivateBlobStore, MAX_BLOB_BYTES
from studio.host.core.safe_replace import ProtectedFileRoot
from . import fixture_content as content
from .export_job import configure_limits
from .ui_host import BLENDER_SHA256, HELPER, STUDIO, cli_job, need

WALL_SECONDS = 20
LOG_BYTES = 262144
MAX_TOTAL = 6 * 1024 * 1024
ARTIFACTS = ("scene.glb", "sprite_sheet.png", "checkpoint.blend", "transcript.json")


@dataclass(frozen=True)
class ContentPublication:
    run_id: str
    published_root: str
    root_identity: dict
    manifest_sha256: str
    artifact_sha256: dict[str, str]
    source_closure_sha256: str
    binary_sha256: str = BLENDER_SHA256
    public_ack: bool = False
    # Keep the exact protected owners alive for the handoff lifetime. They are
    # intentionally omitted from the wire descriptor and are closed by the
    # coordinator after its consumer has independently read the handoff.
    files: object = None
    store: object = None

    def close(self) -> None:
        """Close both protected owners after the consumer has read the handoff.

        The native producer returns a private handoff object to its coordinator;
        dropping that object without an explicit close would leave Windows
        directory/blob handles alive and make the next measurement unsafe.
        Close in reverse creation order and preserve the first failure.
        """
        failure = None
        for resource in (self.store, self.files):
            if resource is None:
                continue
            try:
                resource.close()
            except BaseException as exc:
                if failure is None:
                    failure = exc
        if failure is not None:
            raise failure

    def as_dict(self):
        return {"schema": content.SCHEMA, "run_id": self.run_id,
                "published_root": self.published_root, "root_identity": self.root_identity,
                "manifest_sha256": self.manifest_sha256, "artifact_sha256": self.artifact_sha256,
                "source_closure_sha256": self.source_closure_sha256,
                "binary_sha256": self.binary_sha256, "public_ack": self.public_ack}


class ContentJobError(RuntimeError):
    def __init__(self, code, *, raw=None, cleanup_owner=None):
        self.code = code
        self.raw = raw
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _sources(root: Path) -> dict[str, str]:
    # The producer imports several host helpers lazily (the UI host loads the
    # recovery/export paths only after the child starts).  A hand-maintained
    # list therefore creates a false sense of a complete closure whenever a
    # helper adds one more local import.  Bind the whole bounded local runtime
    # packages instead.  This is deliberately conservative: unrelated files
    # can invalidate a publication, but an omitted executable dependency can
    # never silently pass the handoff.
    names = {
        path.relative_to(root).as_posix()
        for folder in ("host/blender", "host/core", "protocol", "blender-addon")
        for path in (root / folder).rglob("*.py")
        if path.is_file()
    }
    names.update(("tests/blender/sprite_sheet_pixels.py", "toolchain.lock.json"))
    return {name: _sha((root / name).read_bytes()) for name in sorted(names)}


def _read_logs(directory: Path):
    rows = {}
    for name in ("stdout.txt", "stderr.txt"):
        path = directory / name
        rows[name] = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    return rows


def _drain(path: Path, pipe, overflow: threading.Event):
    count = 0
    try:
        with path.open("xb") as output:
            while True:
                raw = pipe.read(4096)
                if not raw:
                    return
                count += len(raw)
                if count > LOG_BYTES:
                    overflow.set()
                    output.write(raw[:max(0, LOG_BYTES - (count - len(raw)))])
                else:
                    output.write(raw)
                output.flush()
    finally:
        pipe.close()


def _fixed_binary(binary: Path):
    binary = binary.resolve(strict=True)
    need(binary.name.lower() == "blender.exe" and _sha(binary.read_bytes()) == BLENDER_SHA256,
         "CONTENT_BINARY_PIN")
    return binary


def _lease_check(lease, checker):
    # Lease is intentionally duck-checked only for immutable shape here; the
    # existing journal remains the authority for ownership/fence validation.
    need(type(lease).__name__ == "Lease" and type(lease.fencing_epoch) is int
         and lease.fencing_epoch > 0 and type(lease.expires_ms) is int, "CONTENT_LEASE_REQUIRED")
    need(callable(checker), "CONTENT_LEASE_CHECKER_REQUIRED")
    checker(lease)


def _protected_publish(parent: Path, run_id: str, temp: Path, *, source_closure_sha256: str,
                       binary_sha256: str, lease, native, logs):
    file_root = store = None
    try:
        file_root = ProtectedFileRoot.create(parent)
        store = PrivateBlobStore.create(parent)
        artifact_sha = {}
        blob_rows = {}
        for name in ARTIFACTS:
            raw = (temp / name).read_bytes()
            need(type(raw) is bytes and 0 < len(raw) <= MAX_BLOB_BYTES, "CONTENT_ARTIFACT_CAP")
            blob = store.put_bytes(raw)
            need(store.read_blob(blob) == raw, "CONTENT_BLOB_READBACK")
            version = file_root.create_new(name, raw)
            observed, readback = file_root.read(name)
            need(observed == version and readback == raw, "CONTENT_PROTECTED_READBACK")
            artifact_sha[name] = _sha(raw)
            blob_rows[name] = {"object_id": blob.object_id, "sha256": blob.sha256,
                               "size_bytes": len(raw), "file_id": blob.identity.file_id,
                               "volume": str(blob.identity.volume),
                               "file_version": {"sha256": version.sha256,
                                                "file_id": version.identity.file_id,
                                                "volume": str(version.identity.volume),
                                                "size": version.identity.size}}
        manifest = {"schema": content.SCHEMA, "run_id": run_id, "profile": content.PROFILE,
                    "authority": 0, "license": "original-fixture", "external_inputs": [],
                    "binary_sha256": binary_sha256, "source_closure_sha256": source_closure_sha256,
                    "lease": {"fencing_epoch": lease.fencing_epoch, "expires_ms": lease.expires_ms},
                    "native": native, "artifacts": artifact_sha, "blobs": blob_rows,
                    "logs": logs, "protected_root_identity": identity_value(file_root.root_identity),
                    "public_ack": False}
        manifest["manifest_body_sha256"] = _sha(canonical_bytes(manifest))
        raw_manifest = canonical_bytes(manifest)
        version = file_root.create_new("manifest.json", raw_manifest)
        observed, readback = file_root.read("manifest.json")
        need(observed == version and readback == raw_manifest, "CONTENT_MANIFEST_READBACK")
        return ContentPublication(run_id, str(file_root.root), identity_value(file_root.root_identity),
                                  _sha(raw_manifest), artifact_sha, source_closure_sha256,
                                  files=file_root, store=store)
    except BaseException:
        for resource in (store, file_root):
            if resource is not None:
                try:
                    resource.close()
                except BaseException:
                    pass
        raise
    finally:
        # Ownership is transferred to the caller only through the root path;
        # retain the protected root open until publication inspection finishes.
        pass


def run_content(*, run_id: str, binary: Path, parent: Path, lease, lease_checker,
                source_root: Path = STUDIO, timeout: int = WALL_SECONDS) -> dict:
    """Run one bounded producer and return an internal handoff descriptor.

    ``lease_checker`` must call the existing journal's ``check_lease``. The
    function does not start a second Blender worker if the same path is active;
    the caller owns serialization around one invocation.
    """
    need(type(run_id) is str and run_id.startswith("gt09-content-") and len(run_id) <= 64,
         "CONTENT_RUN_ID")
    # ``Path`` resolves to ``WindowsPath`` on the pinned Windows host.  A
    # strict ``type(...) is Path`` check rejects valid paths before any native
    # work starts, so accept the concrete platform subclasses while retaining
    # the absolute/root checks below.
    need(isinstance(parent, Path) and parent.is_absolute() and parent.is_dir(), "CONTENT_PARENT")
    need(isinstance(source_root, Path) and source_root.is_dir(), "CONTENT_SOURCE_ROOT")
    need(5 <= int(timeout) <= WALL_SECONDS, "CONTENT_TIMEOUT")
    _lease_check(lease, lease_checker)
    binary = _fixed_binary(binary)
    recipe = content.recipe()
    recipe_check = content.validate_recipe(recipe)
    source_files = _sources(source_root)
    source_closure = content.digest(source_files)
    run_dir = parent / ("content-" + run_id)
    need(not run_dir.exists(), "CONTENT_RUN_EXISTS")
    run_dir.mkdir()
    native_output = run_dir / "native"
    native_output.mkdir()
    args = [str(binary), "--factory-startup", "--disable-autoexec", "--offline-mode", "--threads", "1",
            "--python-exit-code", "17", "--python", str(source_root / "host/blender/fixture_content_native.py"),
            "--", "--output", str(native_output), "--recipe-sha256", recipe_check["recipe_sha256"]]
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith(("PYTHON", "BLENDER_", "HH_BLENDER_"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in ("TEMP", "TMP"):
        path = run_dir / key.lower()
        path.mkdir()
        env[key] = str(path)
    launch = {"schema": "HH-BLENDER-CONTENT-LAUNCH-1", "argv": args,
              "source_files": source_files, "source_closure_sha256": source_closure,
              "binary_sha256": BLENDER_SHA256, "public_ack": False}
    (run_dir / "launch.json").write_bytes(canonical_bytes(launch))
    process = subprocess.Popen([sys.executable, "-B", "-c", HELPER, str(run_dir / "process"), *args],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=run_dir, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    job = None
    overflow = threading.Event()
    threads = []
    started = time.monotonic()
    publication = None
    handed_off = False
    try:
        def configure(owner):
            configure_limits(owner)
        job = cli_job.create(process, before_assign=configure)
        process.stdin.write(b"{}\n")
        process.stdin.close()
        for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
            thread = threading.Thread(target=_drain, args=(run_dir / (name + ".txt"), pipe, overflow), daemon=True)
            threads.append(thread)
            thread.start()
        while process.poll() is None:
            _lease_check(lease, lease_checker)
            if overflow.is_set() or time.monotonic() - started > timeout:
                raise ContentJobError("CONTENT_DEADLINE_OR_LOG_CAP")
            if sum(path.stat().st_size for path in run_dir.rglob("*") if path.is_file()) > MAX_TOTAL:
                raise ContentJobError("CONTENT_WORKSPACE_CAP")
            time.sleep(0.02)
        for thread in threads:
            thread.join(2)
            need(not thread.is_alive(), "CONTENT_LOG_DRAIN")
        actual = parse_json((run_dir / "process-exit.json").read_bytes()) if (run_dir / "process-exit.json").is_file() else None
        if process.returncode != 0 or not actual or actual.get("exit_code") != process.returncode:
            raise ContentJobError("CONTENT_NATIVE_EXIT", raw={"wrapper_exit": process.returncode, "actual": actual,
                                                               "logs": _read_logs(run_dir)})
        # Close the owned Job before constructing the publication manifest.
        # The pre-close snapshot only proves that a handle was assigned; it
        # cannot support a clean-handoff claim.  ``Owner.close`` performs the
        # final active-count query and checked handle close, so the snapshot
        # below is the durable postcondition consumed by the inspector.
        job.close()
        job_snapshot = job.snapshot()
        need(job_snapshot.get("closed") is True
             and job_snapshot.get("handle_retained") is False
             and job_snapshot.get("zero_observed") is True
             and job_snapshot.get("active_count") == 0
             and job_snapshot.get("failed_operations") == [], "CONTENT_JOB_CLEANUP")
        _lease_check(lease, lease_checker)
        transcript = parse_json((native_output / "transcript.json").read_bytes())
        need(transcript.get("public_ack") is False and transcript.get("native_finished") is True,
             "CONTENT_NATIVE_TRANSCRIPT")
        for name in ARTIFACTS:
            need((native_output / name).is_file(), "CONTENT_ARTIFACT_MISSING")
        png = content.inspect_png((native_output / "sprite_sheet.png").read_bytes())
        glb = content.inspect_glb((native_output / "scene.glb").read_bytes())
        need(transcript["sprite"]["sha256"] == png["sha256"] and transcript["glb_sha256"] == glb["sha256"],
             "CONTENT_TRANSCRIPT_ARTIFACT_BINDING")
        _lease_check(lease, lease_checker)
        native = {"process_exit": actual, "wrapper_exit_code": process.returncode,
                  "job": job_snapshot, "transcript": transcript, "png": png, "glb": glb,
                  "public_ack": False, "readback": True}
        publication = _protected_publish(parent, run_id, native_output,
                                          source_closure_sha256=source_closure,
                                          binary_sha256=BLENDER_SHA256, lease=lease,
                                          native=native, logs=_read_logs(run_dir))
        result = {"schema": content.SCHEMA, "run_id": run_id, "authority": 0,
                  "recipe": recipe_check, "source_files": source_files,
                  "source_closure_sha256": source_closure, "binary_sha256": BLENDER_SHA256,
                  "publication": publication.as_dict(), "native": native, "public_ack": False}
        # The descriptor is the wire-safe portion.  The private handle is
        # deliberately kept out of JSON and must be closed by the caller after
        # inspect_publication/consumer readback.
        result["_publication_handle"] = publication
        wire_result = {key: value for key, value in result.items()
                       if key != "_publication_handle"}
        (run_dir / "result.json").write_bytes(canonical_bytes(wire_result))
        handed_off = True
        return result
    except BaseException as error:
        if isinstance(error, ContentJobError):
            raise
        raise ContentJobError("CONTENT_JOB_FAILED", raw={"error": type(error).__name__,
                                                          "message": str(error), "logs": _read_logs(run_dir)}) from error
    finally:
        if publication is not None and not handed_off:
            try:
                publication.close()
            except BaseException:
                pass
        if job is not None:
            try:
                if process.poll() is None:
                    job.terminate()
                process.wait(timeout=3)
                job.close()
            except BaseException as error:
                # Existing cli_job retains the owner on uncertain close. Do
                # not discard it or claim that a child was cleaned up.
                if not isinstance(error, ContentJobError):
                    error.cleanup_owner = job
        elif process.poll() is None:
            process.kill()
            process.wait(timeout=3)


def inspect_publication(publication_root: Path) -> dict:
    """Read-only handoff verification for the Godot consumer.

    All bytes are read through the protected primitive's exact identity and
    manifest hashes. This function does not reopen a native process or publish
    an ACK.
    """
    owner = publication_root if isinstance(publication_root, ContentPublication) else None
    candidate = Path(owner.published_root if owner is not None else publication_root)
    need(candidate.is_absolute(), "CONTENT_PUBLICATION_ROOT")
    # Check the lexical path before resolving it.  Resolving first would make
    # a junction/symlink indistinguishable from the broker-owned directory.
    for part in (candidate, *candidate.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        need(not part.is_symlink()
             and not getattr(info, "st_file_attributes", 0) & 0x400,
             "CONTENT_PUBLICATION_ROOT")
    root = candidate.resolve(strict=True)
    need(root.is_dir() and root.name.startswith("hh-files-"), "CONTENT_PUBLICATION_ROOT")
    # Reopen through the protected primitive so the handoff is checked against
    # the broker-owned directory identity and every file version, rather than
    # trusting a resolved path and ordinary reads.
    manifest_path = root / "manifest.json"
    if owner is not None:
        _manifest_version, manifest_raw = owner.files.read("manifest.json")
        manifest = parse_json(manifest_raw)
    else:
        manifest_raw = manifest_path.read_bytes()
        manifest = parse_json(manifest_raw)
    need(manifest.get("schema") == content.SCHEMA and manifest.get("public_ack") is False,
         "CONTENT_PUBLICATION_MANIFEST")
    protected = owner.files if owner is not None else ProtectedFileRoot.reopen_readonly(
        root, identity_from(manifest.get("protected_root_identity")))
    raw_files = {}
    try:
        files = {}
        for name in (*ARTIFACTS, "manifest.json"):
            version, raw = protected.read(name)
            raw_files[name] = raw
            files[name] = {"sha256": _sha(raw), "size_bytes": len(raw),
                           "file_id": version.identity.file_id,
                           "volume": str(version.identity.volume),
                           "version_sha256": version.sha256}
    finally:
        if owner is None:
            protected.close()
    # The protected read is the authoritative second read.  Requiring the
    # bytes and version identity to match the first read closes a race where a
    # replaced manifest could otherwise be paired with old artifact metadata.
    need(raw_files["manifest.json"] == manifest_raw,
         "CONTENT_PUBLICATION_MANIFEST_CHANGED")
    need(manifest["artifacts"] == {name: files[name]["sha256"] for name in ARTIFACTS},
         "CONTENT_PUBLICATION_HASHES")
    manifest_body = dict(manifest)
    body_digest = manifest_body.pop("manifest_body_sha256", None)
    need(type(body_digest) is str and body_digest == _sha(canonical_bytes(manifest_body)),
         "CONTENT_PUBLICATION_MANIFEST_HASH")
    png = content.inspect_png(raw_files["sprite_sheet.png"])
    glb = content.inspect_glb(raw_files["scene.glb"])
    transcript = parse_json(raw_files["transcript.json"])
    need(transcript.get("public_ack") is False and transcript.get("native_finished") is True,
         "CONTENT_PUBLICATION_TRANSCRIPT")
    need(transcript.get("sprite", {}).get("sha256") == files["sprite_sheet.png"]["sha256"]
         and transcript.get("glb_sha256") == files["scene.glb"]["sha256"]
         and transcript.get("checkpoint_sha256") == files["checkpoint.blend"]["sha256"],
         "CONTENT_TRANSCRIPT_ARTIFACT_BINDING")
    return {"schema": content.SCHEMA, "published_root": str(root), "manifest": manifest,
            "files": files, "png": png, "glb": glb, "transcript": transcript,
            "public_ack": False, "read_only": True}


__all__ = ["ContentPublication", "ContentJobError", "run_content", "inspect_publication"]

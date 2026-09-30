"""Owned gameplay-source publication candidate.

This is the first real adapter for the O2 gameplay-source profile.  It binds
the validated source envelope to the existing Godot grant/lease lifecycle,
runs the pinned Linux executor before publication, and publishes an immutable
revision through an atomic selector.  The returned receipt is a readback ACK
for this candidate only; it never grants public capability or GT06 authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, asdict
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import threading
import uuid

from studio.host.core.transport import epoch_ms
from studio.host.core.limits import SafetyViolation
from studio.protocol.core import SAFE_INTEGER, canonical_bytes, parse_json

HERE = Path(__file__).resolve().parent
ENTRYPOINT = "scripts/fixture_actor.gd"
PROFILE = "hh-godot-gameplay-source-1"
JOURNAL_SCHEMA = "hh-gameplay-source-journal-1"
MAX_JOURNAL_BYTES = 512 * 1024
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_RUNTIME_FILES = (
    "godot-addon/gameplay_source_owner.py",
    "godot-addon/gameplay_source_profile.py",
    "godot-addon/linux_executor.py",
    "godot-addon/gameplay_sandbox.py",
    "godot-addon/publication_session.py",
    "godot-addon/contract.py",
    "godot-addon/operations.json",
    "protocol/core.py",
    "host/core/transport.py",
    "host/core/limits.py",
    "build/bootstrap/run_fixture.py",
    "godot-addon/validator-toolchain.lock.json",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def runtime_source_closure() -> tuple[dict[str, str], str]:
    """Hash the exact adapter/executor inputs before a run is admitted."""
    studio = HERE.parent
    files = {}
    for relative in _RUNTIME_FILES:
        path = studio / relative
        _need(path.is_file() and not path.is_symlink(), "GAMEPLAY_OWNER_SOURCE_MISSING")
        files[relative] = _sha(path.read_bytes())
    return files, _sha(canonical_bytes(files))


def _load(name: str):
    path = HERE / (name + ".py")
    raw = path.read_bytes()
    key = "_hh_gameplay_owner_" + _sha(str(path).encode() + b"\0" + raw)
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            exec(compile(raw, str(path), "exec"), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


class GameplaySourceOwnerError(SafetyViolation):
    pass


def _need(condition: object, code: str) -> None:
    if not condition:
        raise GameplaySourceOwnerError(code)


def _copy_source_bundle(profile, source_files, *, entrypoint: str):
    """Validate a bounded private mapping of immutable source bytes."""
    if (not isinstance(source_files, Mapping) or not source_files
            or len(source_files) > profile.MAX_FILES):
        raise profile.GameplaySourceError("GAMEPLAY_DEPENDENCY_SHAPE")
    candidate = {}
    for index, (name, raw) in enumerate(source_files.items()):
        if index >= profile.MAX_FILES:
            raise profile.GameplaySourceError("GAMEPLAY_DEPENDENCY_SHAPE")
        if type(name) is not str or type(raw) is not bytes:
            raise profile.GameplaySourceError("GAMEPLAY_DEPENDENCY_FILE")
        if name in candidate:
            raise profile.GameplaySourceError("GAMEPLAY_DEPENDENCY_DUPLICATE")
        candidate[name] = raw
    checked = profile.validate_source_bundle(candidate, entrypoint=entrypoint)
    return candidate, checked


def _request_digest(*, project_id: str, command_id: str, entrypoint: str,
                    expected_project_revision: str, source_files) -> str:
    _need(type(project_id) is str and _ID.fullmatch(project_id), "GAMEPLAY_OWNER_PROJECT")
    _need(type(command_id) is str and _ID.fullmatch(command_id), "GAMEPLAY_OWNER_COMMAND")
    _need(type(expected_project_revision) is str
          and expected_project_revision.startswith("sha256:")
          and _HEX.fullmatch(expected_project_revision[7:]), "GAMEPLAY_OWNER_REVISION")
    body = {"schema": "hh-gameplay-source-request-1", "project_id": project_id,
            "profile": PROFILE, "command_id": command_id, "entrypoint": entrypoint,
            "expected_project_revision": expected_project_revision,
            "files": {name: {"sha256": _sha(raw), "size_bytes": len(raw)}
                      for name, raw in sorted(source_files.items())}}
    return "sha256:" + _sha(canonical_bytes(body))


def request_digest(*, project_id: str, command_id: str, entrypoint: str,
                   expected_project_revision: str, source_files) -> str:
    """Derive retry identity from the validated, byte-exact source request."""
    candidate, _ = _copy_source_bundle(_load("gameplay_source_profile"), source_files,
                                       entrypoint=entrypoint)
    return _request_digest(project_id=project_id, command_id=command_id, entrypoint=entrypoint,
                           expected_project_revision=expected_project_revision,
                           source_files=candidate)


@dataclass(frozen=True, slots=True)
class ReadbackAck:
    command_id: str
    request_digest: str
    project_revision: str
    source_sha256: str
    native_run_id: str
    selected_revision: str
    generation: int
    readback_sha256: str
    readback_ack: bool = True
    public_ack: bool = False


class GameplaySourcePublicationOwner:
    """Single-writer source publication over the existing session contract.

    The profile currently admits the fixed fixture scene entrypoint because
    the pinned executor's driver is deliberately closed over that fixture. A
    future profile revision may widen this after its driver and lock hashes are
    updated; silently remapping arbitrary entrypoints would be unsafe.
    """

    def __init__(self):
        raise TypeError("use create or reopen")

    @classmethod
    def create(cls, parent: Path, *, project_id: str, source_files, entrypoint: str,
               source_closure_sha256: str, runner=None):
        profile = _load("gameplay_source_profile")
        session_model = _load("publication_session")
        contract = _load("contract")
        executor = _load("linux_executor")
        _need(isinstance(parent, Path) and parent.is_absolute() and parent.is_dir(),
              "GAMEPLAY_OWNER_PARENT_REQUIRED")
        executor._no_links(parent)
        _need(type(project_id) is str and _ID.fullmatch(project_id), "GAMEPLAY_OWNER_PROJECT")
        _need(entrypoint == ENTRYPOINT, "GAMEPLAY_OWNER_ENTRYPOINT_PIN")
        _need(type(source_closure_sha256) is str and _HEX.fullmatch(source_closure_sha256),
              "GAMEPLAY_OWNER_CLOSURE")
        _need(runtime_source_closure()[1] == source_closure_sha256,
              "GAMEPLAY_OWNER_SOURCE_CLOSURE_MISMATCH")
        candidate, checked = _copy_source_bundle(profile, source_files, entrypoint=entrypoint)
        owner = object.__new__(cls)
        owner._lock = threading.RLock()
        owner._work = threading.Lock()
        owner._closed = False
        owner._held = False
        owner._jobs = {}
        owner._profile = profile
        owner._executor = executor
        owner._session_model = session_model
        owner._contract = contract
        owner._runner = runner or executor.run
        owner.project_id = project_id
        owner.entrypoint = entrypoint
        owner.source_closure_sha256 = source_closure_sha256
        owner._root = parent / ("gameplay-owner-" + uuid.uuid4().hex)
        owner._revisions = owner._root / "revisions"
        owner._runs = owner._root / "runs"
        owner._selector = owner._root / "CURRENT"
        owner._journal = owner._root / "journal.jsonl"
        owner._root.mkdir()
        owner._revisions.mkdir()
        owner._runs.mkdir()
        owner._session = session_model.PublicationSession(project_id, owner._root,
                                                           contract.CATALOG_DIGEST)
        owner._files = candidate
        owner._profile_observation = checked
        owner._generation = 1
        owner._project_revision = owner._revision(owner._files)
        owner._materialize(owner._project_revision, owner._files)
        owner._atomic_select(owner._project_revision, owner._generation)
        owner._append({"schema": JOURNAL_SCHEMA, "kind": "INITIAL",
                       "project_id": project_id, "profile": PROFILE, "entrypoint": ENTRYPOINT,
                       "source_closure_sha256": source_closure_sha256,
                       "generation": owner._generation,
                       "project_revision": owner._project_revision,
                       "source_sha256": owner._source_hash(owner._files),
                       "fencing_epoch": 0, "observed_ms": epoch_ms()})
        return owner

    @classmethod
    def reopen(cls, root: Path, *, project_id: str, source_closure_sha256: str,
                runner=None):
        """Reopen only the durable selected revision; no old lease survives."""
        profile = _load("gameplay_source_profile")
        session_model = _load("publication_session")
        contract = _load("contract")
        executor = _load("linux_executor")
        _need(isinstance(root, Path) and root.is_absolute() and root.is_dir(),
              "GAMEPLAY_OWNER_ROOT_REQUIRED")
        executor._no_links(root)
        _need(type(project_id) is str and _ID.fullmatch(project_id), "GAMEPLAY_OWNER_PROJECT")
        _need(type(source_closure_sha256) is str and _HEX.fullmatch(source_closure_sha256),
              "GAMEPLAY_OWNER_CLOSURE")
        _need(runtime_source_closure()[1] == source_closure_sha256,
              "GAMEPLAY_OWNER_SOURCE_CLOSURE_MISMATCH")
        rows = []
        journal = root / "journal.jsonl"
        _need(journal.is_file(), "GAMEPLAY_OWNER_JOURNAL_MISSING")
        raw = executor._read_file(journal, MAX_JOURNAL_BYTES)
        _need(raw.endswith(b'\n'), "GAMEPLAY_OWNER_JOURNAL_TRUNCATED")
        for line in raw.splitlines():
            value = parse_json(line)
            _need(type(value) is dict and value.get("kind") in ("INITIAL", "COMMITTED"),
                  "GAMEPLAY_OWNER_JOURNAL_ROW")
            _need(canonical_bytes(value) == line, "GAMEPLAY_OWNER_JOURNAL_ENCODING")
            rows.append(value)
        _need(rows, "GAMEPLAY_OWNER_JOURNAL_EMPTY")
        _need(len(rows) <= session_model.MAX_COMMANDS + 1, "GAMEPLAY_OWNER_JOURNAL_LIMIT")
        last = rows[-1]
        owner = object.__new__(cls)
        owner._lock = threading.RLock()
        owner._work = threading.Lock()
        owner._closed = False
        owner._held = False
        owner._jobs = {}
        owner._profile = profile
        owner._executor = executor
        owner._session_model = session_model
        owner._contract = contract
        owner._runner = runner or executor.run
        owner.project_id = project_id
        owner.entrypoint = ENTRYPOINT
        owner.source_closure_sha256 = source_closure_sha256
        owner._root = root
        owner._revisions = root / "revisions"
        owner._runs = root / "runs"
        owner._selector = root / "CURRENT"
        owner._journal = journal
        # Rebuild only a fully validated terminal history. Selector mismatch
        # is reconciled only after the journal and selected revision have been
        # fully checked; malformed or truncated durable state still fails closed.
        initial = rows[0]
        _need(set(initial) == {"schema", "kind", "project_id", "profile", "entrypoint",
              "source_closure_sha256", "generation", "project_revision", "source_sha256",
              "fencing_epoch", "observed_ms"} and initial["kind"] == "INITIAL"
              and initial["schema"] == JOURNAL_SCHEMA, "GAMEPLAY_OWNER_JOURNAL_INITIAL")
        _need(initial["project_id"] == project_id and initial["profile"] == PROFILE
              and initial["entrypoint"] == ENTRYPOINT
              and initial["source_closure_sha256"] == source_closure_sha256,
              "GAMEPLAY_OWNER_JOURNAL_BINDING")
        _need(type(initial["generation"]) is int and initial["generation"] == 1
              and type(initial["fencing_epoch"]) is int and initial["fencing_epoch"] == 0
              and type(initial["observed_ms"]) is int
              and 0 <= initial["observed_ms"] <= SAFE_INTEGER,
              "GAMEPLAY_OWNER_JOURNAL_INITIAL")
        files = owner._read_revision(initial["project_revision"])
        _need(initial["source_sha256"] == owner._source_hash(files),
              "GAMEPLAY_OWNER_JOURNAL_SOURCE")
        terminal_keys = {"schema", "project_id", "profile", "entrypoint",
                         "source_closure_sha256", "kind", "command_id", "request_digest", "project_revision",
                         "source_sha256", "native_run_id", "selected_revision", "generation",
                         "readback_sha256", "readback_ack", "public_ack", "fencing_epoch",
                         "observed_ms"}
        previous_row = initial
        for row in rows[1:]:
            _need(set(row) == terminal_keys and row["schema"] == JOURNAL_SCHEMA
                  and row["project_id"] == project_id and row["profile"] == PROFILE
                  and row["entrypoint"] == ENTRYPOINT
                  and row["source_closure_sha256"] == source_closure_sha256
                  and row["kind"] == "COMMITTED",
                  "GAMEPLAY_OWNER_JOURNAL_COMMITTED_SHAPE")
            receipt = ReadbackAck(**{name: row[name] for name in terminal_keys
                                     if name in ReadbackAck.__dataclass_fields__})
            _need(receipt.readback_ack is True and receipt.public_ack is False
                  and type(receipt.generation) is int
                  and receipt.generation == previous_row["generation"] + 1
                  and type(row["fencing_epoch"]) is int
                  and max(1, previous_row["fencing_epoch"]) <= row["fencing_epoch"] < SAFE_INTEGER
                  and type(row["observed_ms"]) is int and 0 <= row["observed_ms"] <= SAFE_INTEGER
                  and type(receipt.command_id) is str and _ID.fullmatch(receipt.command_id)
                  and type(receipt.native_run_id) is str
                  and _ID.fullmatch(receipt.native_run_id.replace("-", ".")),
                  "GAMEPLAY_OWNER_JOURNAL_COMMITTED_VALUE")
            _need(receipt.command_id not in owner._jobs,
                  "GAMEPLAY_OWNER_JOURNAL_COMMAND_CONFLICT")
            files = owner._read_revision(receipt.project_revision)
            expected_digest = _request_digest(project_id=project_id, command_id=receipt.command_id,
                entrypoint=ENTRYPOINT, expected_project_revision=previous_row["project_revision"],
                source_files=files)
            _need(receipt.request_digest == expected_digest
                  and receipt.source_sha256 == owner._source_hash(files)
                  and receipt.selected_revision == receipt.project_revision
                  and receipt.readback_sha256 == _sha(canonical_bytes(owner._readback(
                      files, receipt.project_revision, receipt.generation))),
                  "GAMEPLAY_OWNER_JOURNAL_RECEIPT_BINDING")
            rebuilt = {"status": "READBACK_ACK", **asdict(receipt)}
            owner._jobs[receipt.command_id] = rebuilt
            previous_row = row
        owner._generation = last["generation"]
        owner._project_revision = last["project_revision"]
        owner._files = files
        owner._profile_observation = profile.validate_source_bundle(files, entrypoint=ENTRYPOINT)
        selector = parse_json(executor._read_file(owner._selector, 4096))
        _need(type(selector) is dict and set(selector) == {"schema", "revision", "generation"}
              and selector.get("schema") == "hh-gameplay-selector-1"
              and type(selector.get("revision")) is str
              and selector["revision"].startswith("sha256:")
              and _HEX.fullmatch(selector["revision"][7:])
              and type(selector.get("generation")) is int and selector["generation"] > 0,
              "GAMEPLAY_OWNER_SELECTOR_SHAPE")
        expected_selector = {"schema": "hh-gameplay-selector-1",
                             "revision": owner._project_revision,
                             "generation": owner._generation}
        if selector != expected_selector:
            # Journal validation above proves the durable target first; only
            # then may recovery repair the pointer file.
            owner._atomic_select(owner._project_revision, owner._generation)
        owner._check_selected()
        owner._session = session_model.PublicationSession(project_id, root,
            contract.CATALOG_DIGEST, minimum_fencing_epoch=last["fencing_epoch"])
        return owner

    @staticmethod
    def _source_hash(files) -> str:
        return _sha(canonical_bytes({name: _sha(files[name]) for name in sorted(files)}))

    @staticmethod
    def _revision(files) -> str:
        body = {"profile": PROFILE, "entrypoint": ENTRYPOINT,
                "files": {name: _sha(files[name]) for name in sorted(files)}}
        return "sha256:" + _sha(canonical_bytes(body))

    def _safe_revision(self, revision: str) -> Path:
        _need(type(revision) is str and revision.startswith("sha256:")
              and _HEX.fullmatch(revision[7:]), "GAMEPLAY_OWNER_REVISION")
        return self._revisions / revision[7:]

    def _materialize(self, revision: str, files) -> None:
        target = self._safe_revision(revision)
        _need(not target.exists(), "GAMEPLAY_OWNER_REVISION_EXISTS")
        target.mkdir()
        try:
            project = target / "project"
            project.mkdir()
            (project / "project.godot").write_bytes(self._profile.PROJECT_TEMPLATE.encode())
            for name, raw in sorted(files.items()):
                path = project / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(raw)
            manifest = {"schema": "hh-gameplay-source-revision-1", "profile": PROFILE,
                        "entrypoint": ENTRYPOINT,
                        "files": {name: {"sha256": _sha(files[name]), "size_bytes": len(files[name])}
                                  for name in sorted(files)},
                        "project_godot_sha256": _sha(self._profile.PROJECT_TEMPLATE.encode()),
                        "project_revision": revision}
            (target / "manifest.json").write_bytes(canonical_bytes(manifest))
        except BaseException:
            # Keep a failed revision out of the selector; it is evidence for
            # inspection, but never a publishable candidate.
            raise

    def _read_revision(self, revision: str):
        target = self._safe_revision(revision)
        manifest = parse_json(self._executor._read_file(target / "manifest.json", 65536))
        _need(type(manifest) is dict and set(manifest) == {
              "schema", "profile", "entrypoint", "files", "project_godot_sha256", "project_revision"}
              and manifest["schema"] == "hh-gameplay-source-revision-1"
              and manifest["profile"] == PROFILE
              and manifest["project_revision"] == revision and manifest["entrypoint"] == ENTRYPOINT,
              "GAMEPLAY_OWNER_MANIFEST")
        inventory = manifest["files"]
        _need(type(inventory) is dict and 1 <= len(inventory) <= self._profile.MAX_FILES,
              "GAMEPLAY_OWNER_MANIFEST_FILES")
        # Validate every path/size before any project file is read. Reuse the
        # profile's platform-aware path rules and the executor's bounded,
        # no-link reader; a manifest cannot introduce an external file.
        for name, row in inventory.items():
            _need(self._profile._path(name) and type(row) is dict
                  and set(row) == {"sha256", "size_bytes"}
                  and type(row["sha256"]) is str and _HEX.fullmatch(row["sha256"])
                  and type(row["size_bytes"]) is int
                  and 1 <= row["size_bytes"] <= self._profile.MAX_BYTES,
                  "GAMEPLAY_OWNER_MANIFEST_FILE")
        _need(sum(row["size_bytes"] for row in inventory.values()) <= self._profile.MAX_TOTAL_BYTES,
              "GAMEPLAY_OWNER_MANIFEST_FILES")
        files = {}
        for name, row in inventory.items():
            raw = self._executor._read_file(target / "project" / name, row["size_bytes"])
            _need(_sha(raw) == row.get("sha256") and len(raw) == row.get("size_bytes"),
                  "GAMEPLAY_OWNER_READBACK_HASH")
            files[name] = raw
        _need(self._revision(files) == revision, "GAMEPLAY_OWNER_REVISION_MISMATCH")
        self._profile.validate_source_bundle(files, entrypoint=ENTRYPOINT)
        project = self._executor._read_file(target / "project/project.godot", 65536)
        _need(project == self._profile.PROJECT_TEMPLATE.encode()
              and _sha(project) == manifest["project_godot_sha256"], "GAMEPLAY_OWNER_PROJECT_HASH")
        return files

    def _atomic_select(self, revision: str, generation: int) -> None:
        payload = canonical_bytes({"schema": "hh-gameplay-selector-1",
                                   "revision": revision, "generation": generation})
        temp = self._selector.with_name("CURRENT." + uuid.uuid4().hex + ".tmp")
        with temp.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self._selector)

    def _check_selected(self):
        selector = parse_json(self._executor._read_file(self._selector, 4096))
        _need(type(selector) is dict and set(selector) == {"schema", "revision", "generation"}
              and selector["schema"] == "hh-gameplay-selector-1"
              and selector["revision"] == self._project_revision
              and type(selector["generation"]) is int
              and selector["generation"] == self._generation, "GAMEPLAY_OWNER_SELECTOR")
        files = self._read_revision(selector["revision"])
        _need(files == self._files, "GAMEPLAY_OWNER_SELECTED_FILES")

    def _append(self, value: dict) -> None:
        raw = canonical_bytes(value) + b"\n"
        with self._journal.open("ab") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())

    def issue(self, *, operations=None, ttl_ms=120_000):
        if operations is None:
            operations = frozenset({"scene.save", "control.lookup", "control.stop"})
        return self._session.issue(operations=operations, ttl_ms=ttl_ms)

    def authorize(self, authorization: str, operation: str):
        return self._session.authorize(authorization, operation,
                                       project_id=self.project_id,
                                       catalog_digest=self._contract.CATALOG_DIGEST)

    def lease(self, grant, *, ttl_ms=90_000):
        return self._session.lease(grant, ttl_ms=ttl_ms)

    def inspect(self) -> dict:
        with self._lock:
            _need(not self._closed and not self._held, "GAMEPLAY_OWNER_CLOSED")
            self._check_selected()
            return self._readback(self._files, self._project_revision, self._generation)

    def _readback(self, files, revision, generation) -> dict:
        return {"schema": "hh-gameplay-source-readback-1", "profile": PROFILE,
                    "project_id": self.project_id, "entrypoint": ENTRYPOINT,
                    "generation": generation, "project_revision": revision,
                    "selected_revision": revision,
                    "source_sha256": self._source_hash(files),
                    "files": {name: _sha(raw) for name, raw in sorted(files.items())},
                    "public_ack": False}

    def _phase(self, grant, lease, command_id, digest, deadline_ms, phase, effect):
        permit = self._session.reserve_phase(grant, lease, command_id=command_id, digest=digest,
                                             phase=phase, deadline_ms=deadline_ms,
                                             operation="scene.save")
        started = False
        try:
            self._session.start_effect(permit)
            started = True
            value = effect()
        except BaseException:
            if started:
                self._session.finish_effect(permit, known=False)
                self._held = True
            else:
                self._session.cancel_reserved(permit)
            raise
        self._session.finish_effect(permit, known=True)
        return value

    @staticmethod
    def _validate_native(result: dict, *, expected_input_hashes) -> None:
        _need(type(result) is dict and result.get("schema") == "hh-gt03-linux-diagnostic-1",
              "GAMEPLAY_OWNER_NATIVE_SCHEMA")
        _need(result.get("mode") == "gameplay-source" and result.get("public_ack") is False,
              "GAMEPLAY_OWNER_NATIVE_MODE")
        _need(result.get("gameplay_source_envelope_checked") is True
              and result.get("gameplay_profile") == PROFILE
              and result.get("gameplay_profile_unchanged") is True
              and result.get("diagnostic_process_clean") is True
              and result.get("owned_removed") is True
              and result.get("input_unchanged") is True and result.get("snapshot_unchanged") is True
              and result.get("binary_unchanged") is True
              and result.get("log_clean") is True
              and result.get("owner_record_retained") is False
              and result.get("errors") == [],
              "GAMEPLAY_OWNER_NATIVE_NOT_CLEAN")
        state = result.get("state")
        _need(type(state) is dict and state.get("Running") is False and state.get("Pid") == 0
              and state.get("ExitCode") == 0 and state.get("OOMKilled") is False
              and result.get("docker_wait_exit") == 0, "GAMEPLAY_OWNER_NATIVE_EXIT")
        host = result.get("commandhost") or result.get("command_host")
        _need(type(host) is dict and host.get("exit_code") == 0
              and host.get("timed_out") is False and host.get("stream_cap_exceeded") is False
              and host.get("readers_stopped") is True and host.get("job_active_count") == 0,
              "GAMEPLAY_OWNER_NATIVE_HOST")
        job = host.get("job_owner")
        _need(type(job) is dict and job.get("configured") is True and job.get("assigned") is True
              and job.get("closed") is True and job.get("zero_observed") is True
              and job.get("active_count") == 0 and job.get("tainted") is False
              and job.get("handle_retained") is False and job.get("failed_operations") == [],
              "GAMEPLAY_OWNER_NATIVE_JOB")
        _need(type(result.get("run_id")) is str and _ID.fullmatch(result["run_id"].replace("-", ".")),
              "GAMEPLAY_OWNER_NATIVE_RUN_ID")
        for field in ("input_hashes_before", "input_hashes_after", "snapshot_hashes_after"):
            _need(result.get(field) == expected_input_hashes,
                  "GAMEPLAY_OWNER_NATIVE_INPUT_BINDING")

    def publish(self, request: dict, *, grant, lease, deadline_ms: int) -> dict:
        # Serialize complete publication, including validation, native work and
        # selector/journal updates. The short lifecycle lock remains available
        # to close/Stop while the executor is running. A competing writer must
        # retry from a fresh observation, not wait with a stale revision/lease.
        _need(self._work.acquire(blocking=False), "GAMEPLAY_OWNER_BUSY")
        try:
            return self._publish_owned(request, grant=grant, lease=lease, deadline_ms=deadline_ms)
        finally:
            self._work.release()

    def _publish_owned(self, request: dict, *, grant, lease, deadline_ms: int) -> dict:
        _need(type(request) is dict and set(request) ==
              {"command_id", "digest", "expected_project_revision", "source_files", "entrypoint"},
              "GAMEPLAY_OWNER_REQUEST")
        command_id, digest = request["command_id"], request["digest"]
        entrypoint = request["entrypoint"]
        expected_revision = request["expected_project_revision"]
        _need(type(command_id) is str and _ID.fullmatch(command_id), "GAMEPLAY_OWNER_COMMAND")
        _need(type(digest) is str and digest.startswith("sha256:") and _HEX.fullmatch(digest[7:]),
              "GAMEPLAY_OWNER_DIGEST")
        candidate, checked = _copy_source_bundle(self._profile, request["source_files"],
                                                  entrypoint=entrypoint)
        derived_digest = _request_digest(project_id=self.project_id, command_id=command_id,
            entrypoint=entrypoint, expected_project_revision=expected_revision,
            source_files=candidate)
        _need(digest == derived_digest, "GAMEPLAY_OWNER_DIGEST_MISMATCH")
        _need(entrypoint == ENTRYPOINT, "GAMEPLAY_OWNER_ENTRYPOINT_PIN")
        self._session.validate_public_identifier(command_id)
        with self._lock:
            _need(not self._closed and not self._held, "GAMEPLAY_OWNER_CLOSED")
            # A cached receipt is still private project data. Retry identity
            # does not authorize an expired/revoked grant or a fenced lease.
            self._session.check(grant, lease, deadline_ms=deadline_ms, operation="scene.save")
            previous = self._jobs.get(command_id)
            if previous is not None:
                _need(previous["request_digest"] == digest, "GAMEPLAY_OWNER_COMMAND_CONFLICT")
                return dict(previous)
            _need(len(self._jobs) < self._session_model.MAX_COMMANDS,
                  "GAMEPLAY_OWNER_JOURNAL_LIMIT")
        candidate_revision = self._revision(candidate)
        _need(expected_revision == self._project_revision,
              "GAMEPLAY_OWNER_STALE_PROJECT")
        _need(self._session.check(grant, lease, deadline_ms=deadline_ms, operation="scene.save") is None,
              "GAMEPLAY_OWNER_LEASE")
        self._phase(grant, lease, command_id, digest, deadline_ms, "capture",
                    lambda: self.inspect())
        run_dir = self._runs / command_id
        stage_dir = self._runs / (command_id + ".stage")
        _need(not run_dir.exists() and not stage_dir.exists(), "GAMEPLAY_OWNER_COMMAND_REUSED")
        stage_dir.mkdir()
        try:
            if not self._safe_revision(candidate_revision).exists():
                self._materialize(candidate_revision, candidate)
            # The revision is not selected yet. Running against this immutable
            # directory exercises the real Docker/Godot executor before ACK.
            result = self._phase(grant, lease, command_id, digest, deadline_ms, "stage",
                lambda: self._runner(self._safe_revision(candidate_revision) / "project",
                                      mode="gameplay-source", output=run_dir, timeout_seconds=20))
            expected_native_inputs = {
                "project.godot": _sha(self._profile.PROJECT_TEMPLATE.encode()),
                **{name: _sha(raw) for name, raw in sorted(candidate.items())},
            }
            self._validate_native(result, expected_input_hashes=expected_native_inputs)
            native_run_id = result["run_id"]
            # Once selection starts, keep the lifecycle lock through the
            # durable journal commit.  Stop/close may still interrupt the
            # native runner above, but cannot leave CURRENT ahead of the last
            # committed journal row and make reopen observe a split state.
            with self._lock:
                ack = self._phase(grant, lease, command_id, digest, deadline_ms, "adopt", lambda: self._adopt(
                    candidate_revision, candidate, command_id, digest, checked, native_run_id))
                committed = self._phase(grant, lease, command_id, digest, deadline_ms, "commit",
                                        lambda: self._commit(ack, lease.fencing_epoch))
                self._jobs[command_id] = committed
            return dict(committed)
        finally:
            if stage_dir.exists():
                # No selector ever points to this directory. Keep the final
                # revision and executor evidence; remove only the empty marker.
                try:
                    stage_dir.rmdir()
                except OSError:
                    pass

    def _adopt(self, revision, candidate, command_id, digest, checked, native_run_id):
        self._atomic_select(revision, self._generation + 1)
        self._files = candidate
        self._profile_observation = checked
        self._generation += 1
        self._project_revision = revision
        self._check_selected()
        readback = self.inspect()
        return {"command_id": command_id, "request_digest": digest,
                "project_revision": revision, "source_sha256": readback["source_sha256"],
                "native_run_id": native_run_id, "selected_revision": revision,
                "generation": self._generation,
                "readback_sha256": _sha(canonical_bytes(readback)),
                "readback_ack": True, "public_ack": False}

    def _commit(self, ack, fencing_epoch):
        receipt = ReadbackAck(**ack)
        raw_rows = self._executor._read_file(self._journal, MAX_JOURNAL_BYTES)
        prior = parse_json(raw_rows.splitlines()[-1])
        _need(prior.get("kind") in ("INITIAL", "COMMITTED"),
              "GAMEPLAY_OWNER_JOURNAL_ROW")
        _need(receipt.request_digest == _request_digest(
              project_id=self.project_id, command_id=receipt.command_id,
              entrypoint=ENTRYPOINT, expected_project_revision=prior["project_revision"],
              source_files=self._files), "GAMEPLAY_OWNER_COMMIT_DIGEST")
        row = {"schema": JOURNAL_SCHEMA, "project_id": self.project_id,
               "profile": PROFILE, "entrypoint": ENTRYPOINT,
               "source_closure_sha256": self.source_closure_sha256,
               "kind": "COMMITTED", **asdict(receipt), "fencing_epoch": fencing_epoch,
               "observed_ms": epoch_ms()}
        self._append(row)
        self._check_selected()
        _need(self.inspect()["project_revision"] == receipt.project_revision,
              "GAMEPLAY_OWNER_COMMIT_READBACK")
        return {"status": "READBACK_ACK", **asdict(receipt)}

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._session.halt()

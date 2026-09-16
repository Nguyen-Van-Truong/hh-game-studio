"""Owned Linux fixture validation; a registered observation is not a save ACK.

Only validate() launches the fixed executor and can register a receipt. The
pure evaluator accepts recorded facts for testing, never minting authority.
The trusted installed host/release is outside the candidate threat boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import threading
import uuid

from studio.protocol.core import canonical_bytes, parse_json

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parent
MAX_RUNS = 4
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024  # Per attempt; at most four per owner.
_COMMAND = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_SOURCE_SUFFIXES = {'.py', '.gd', '.uid', '.cfg', '.godot', '.json'}


class ValidationOwnerError(ValueError):
    def __init__(self, code, *, cleanup_owner=None):
        self.code = code
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


def _need(value, code):
    if not value:
        raise ValidationOwnerError(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _load(name):
    path = HERE / (name + '.py')
    raw = path.read_bytes()
    key = '_hh_validation_owner_' + _sha(str(path).encode() + b'\0' + raw)
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        module._validation_source = _sha(raw)
        sys.modules[key] = module
        try:
            exec(compile(raw, str(path), 'exec'), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    module = sys.modules[key]
    _need(module.__file__ == str(path) and module._validation_source == _sha(raw),
          'VALIDATION_MODULE_SOURCE_CHANGED')
    return module


def _regular(path):
    info = path.stat(follow_symlinks=False)
    _need(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
          'VALIDATION_REPARSE_FORBIDDEN')
    return info


def source_release():
    """Bound the installed runtime inputs, not a caller-provided release hash."""
    paths = [STUDIO / 'toolchain.lock.json', STUDIO / 'build/bootstrap/run_fixture.py']
    for directory in (HERE, STUDIO / 'host/core', STUDIO / 'protocol'):
        # No imported-cache or arbitrary runtime output belongs to the release.
        stack = [directory]
        while stack:
            current = stack.pop()
            _regular(current)
            for path in sorted(current.iterdir()):
                if path.name == '__pycache__':
                    continue
                _regular(path)
                if path.is_dir():
                    stack.append(path)
                elif path.suffix in _SOURCE_SUFFIXES:
                    paths.append(path)
                _need(len(paths) + len(stack) <= 256, 'VALIDATION_RELEASE_LIMIT')
    files, total = {}, 0
    for path in sorted(paths):
        before = _regular(path)
        _need(before.st_size <= 2 * 1024 * 1024, 'VALIDATION_RELEASE_LIMIT')
        raw = path.read_bytes()
        after = _regular(path)
        _need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
              == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
              and len(raw) == after.st_size, 'VALIDATION_RELEASE_CHANGED')
        total += len(raw)
        _need(total <= 16 * 1024 * 1024, 'VALIDATION_RELEASE_LIMIT')
        files[path.relative_to(STUDIO).as_posix()] = _sha(raw)
    return files, _sha(canonical_bytes(files))


# Pin before any source-bound addon cache is consulted. An owner cannot adopt
# a newer on-disk release while this interpreter retains old dependency code.
_IMPORT_RELEASE = source_release()
comparator = _load('profile_readback')
factory = comparator.factory
bundle_codec = factory.bundle_codec
executor = _load('linux_executor')
_need(source_release() == _IMPORT_RELEASE, 'VALIDATION_IMPORT_RELEASE_CHANGED')


def _loaded_release():
    files, _ = _IMPORT_RELEASE
    bindings = {
        'profile_readback.py': comparator._validation_source,
        'fixture_profile.py': _sha(comparator._raw),
        'bundle_staging.py': factory.staging._fixture_source_sha256,
        'bundle_v2.py': bundle_codec._bundle_source_sha256,
        'linux_executor.py': executor._validation_source,
    }
    for name, digest in bindings.items():
        _need(files.get('godot-addon/' + name) == digest, 'VALIDATION_LOADED_DEPENDENCY_CHANGED')
    # Pin the dynamically loaded profiles too; their cache keys bind their
    # own bytes, while the scene profile additionally pins its script grammar.
    scene = factory._sibling('scene_profile')
    script = factory._sibling('script_profile')
    _need(scene._fixture_source_sha256 == files['godot-addon/scene_profile.py']
          and script._fixture_source_sha256 == files['godot-addon/script_profile.py']
          and scene.SCRIPT_PROFILE_SHA256 == files['godot-addon/script_profile.py'],
          'VALIDATION_LOADED_DEPENDENCY_CHANGED')
    cli = executor._cli_jobs()
    path = STUDIO / 'godot-addon/cli_job.py'
    raw = path.read_bytes()
    _need(_sha(raw) == files['godot-addon/cli_job.py']
          and cli.__file__ == str(path)
          and cli.__name__ == '_hh_linux_cli_job_' + _sha(str(path).encode() + b'\0' + raw),
          'VALIDATION_LOADED_DEPENDENCY_CHANGED')


_loaded_release()


def evaluate_run(result, stdout: str, stderr: str, bundle):
    """Pure raw-fact checks. Success here cannot create a registered receipt."""
    _need(type(result) is dict and type(stdout) is str and type(stderr) is str,
          'VALIDATION_RAW_TYPES')
    factory.qualify(bundle)
    _need(bundle.engine_sha256 == executor.BINARY_SHA256, 'VALIDATION_ENGINE_PIN')
    phases = [item for phase in ('parse', 'import', 'readback')
              for item in ('HH_PROFILE_PHASE_BEGIN ' + phase, 'HH_PROFILE_PHASE_END ' + phase + ' 0')]
    ordered = [line if line.startswith('HH_PROFILE_PHASE_') else 'HH_PROFILE_READBACK'
               for line in stdout.splitlines()
               if line.startswith(('HH_PROFILE_PHASE_', 'HH_PROFILE_READBACK '))]
    markers = [line.removeprefix('HH_PROFILE_READBACK ') for line in stdout.splitlines()
               if line.startswith('HH_PROFILE_READBACK ')]
    _need(ordered == phases[:-1] + ['HH_PROFILE_READBACK', phases[-1]] and len(markers) == 1,
          'VALIDATION_PHASE_ORDER')
    _need(re.search(r'(?m)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked',
                    stdout + '\n' + stderr) is None, 'VALIDATION_LOG_ERROR')
    integer = lambda value, expected: type(value) is int and value == expected
    _need(result.get('schema') == 'hh-gt03-linux-diagnostic-1'
          and result.get('mode') == 'profile-validate', 'VALIDATION_MODE')
    for key in ('diagnostic_process_clean', 'profile_eligible', 'profile_harness_unchanged',
                'owned_removed', 'input_unchanged', 'snapshot_unchanged', 'binary_unchanged', 'log_clean'):
        _need(result.get(key) is True, 'VALIDATION_OWNED_RUN_NOT_CLEAN')
    _need(result.get('errors') == [] and result.get('owner_record_retained') is False,
          'VALIDATION_OWNED_RUN_NOT_CLEAN')
    _need(result.get('profile_harness_sha256') == _sha(executor._profile_harness()),
          'VALIDATION_HARNESS_CHANGED')
    admission = result.get('admission', {})
    _need(admission.get('acquired') is True and admission.get('released') is True
          and integer(admission.get('maximum_active'), 1), 'VALIDATION_ADMISSION')
    state = result.get('container_state', {})
    _need(state == result.get('state') and integer(state.get('ExitCode'), 0)
          and state.get('Running') is False and integer(state.get('Pid'), 0)
          and state.get('OOMKilled') is False and integer(result.get('docker_wait_exit'), 0),
          'VALIDATION_NATIVE_EXIT')
    host = result.get('command_host', {})
    _need(host == result.get('commandhost') and executor._cli_clean(host), 'VALIDATION_HOST_OWNERSHIP')
    eof = host.get('stream_reader_eof')
    _need(type(eof) is list and len(eof) == 2 and all(value is True for value in eof),
          'VALIDATION_STREAM_EOF')
    expected = {name: _sha(raw) for name, raw in bundle.files.items()}
    _need(all(result.get(key) == expected for key in
          ('input_hashes_before', 'input_hashes_after', 'snapshot_hashes_after')),
          'VALIDATION_INPUT_CHANGED')
    observation = parse_json(markers[0].encode('utf-8'))
    comparison = comparator.compare_observation(bundle, observation)
    return observation, comparison


@dataclass(frozen=True, slots=True)
class ValidationReceipt:
    command_id: str
    project_revision: str
    manifest_sha256: str
    source_release_sha256: str
    engine_sha256: str
    observation_sha256: str
    evidence_sha256: str
    run_id: str
    status: str = field(default='OWNED_PROFILE_VALIDATED', init=False)
    public_ack: bool = field(default=False, init=False)
    selected_state_verified: bool = field(default=False, init=False)


@dataclass
class _Record:
    bundle: object
    directory: Path
    observation: bytes
    evidence: dict
    source_files: dict
    receipt: ValidationReceipt


class ValidationOwner:
    """Trusted local issuer, bounded evidence retained for every attempt.

    evidence_parent belongs to the host; it is never a request path. New native
    runs alone can mint receipts. Mutation/selection/lease authorization stays
    with the publication coordinator. Failure holds this issuer until close.
    """
    def __init__(self, evidence_parent: Path):
        _need(type(evidence_parent) in (Path, type(Path())) and evidence_parent.is_absolute(),
              'VALIDATION_OWNED_PARENT_REQUIRED')
        for path in (*reversed(evidence_parent.parents), evidence_parent):
            _regular(path)
            _need(path.is_dir(), 'VALIDATION_OWNED_PARENT_REQUIRED')
        self._parent = evidence_parent
        self._mutex = threading.RLock()
        self._closed = self._held = False
        self._attempts = []
        self._records = {}
        _need(source_release() == _IMPORT_RELEASE, 'VALIDATION_IMPORT_RELEASE_CHANGED')
        _loaded_release()
        self._source_files, self._source_sha = _IMPORT_RELEASE

    def _healthy(self):
        _need(not self._closed, 'VALIDATION_OWNER_CLOSED')
        _need(not self._held, 'VALIDATION_OWNER_HELD')
        _need(source_release() == (self._source_files, self._source_sha), 'VALIDATION_RELEASE_CHANGED')
        _loaded_release()
        for name, module in (('profile_readback', comparator), ('linux_executor', executor)):
            _need(_sha((HERE / (name + '.py')).read_bytes()) == module._validation_source,
                  'VALIDATION_LOADED_MODULE_CHANGED')
        _need(_sha(Path(factory.__file__).read_bytes()) == _sha(comparator._raw),
              'VALIDATION_LOADED_FACTORY_CHANGED')

    def _inventory(self, directory):
        files, total = {}, 0
        stack = [directory]
        while stack:
            current = stack.pop()
            _regular(current)
            for path in sorted(current.iterdir()):
                info = _regular(path)
                if path.is_dir():
                    stack.append(path)
                else:
                    _need(info.st_size <= 2 * 1024 * 1024, 'VALIDATION_EVIDENCE_LIMIT')
                    raw = executor._read_file(path, 2 * 1024 * 1024)
                    total += len(raw)
                    _need(total <= MAX_EVIDENCE_BYTES and len(files) < 256, 'VALIDATION_EVIDENCE_LIMIT')
                    files[path.relative_to(directory).as_posix()] = _sha(raw)
        return files

    def validate(self, command_id, bundle, *, timeout_seconds=20):
        _need(type(command_id) is str and _COMMAND.fullmatch(command_id), 'VALIDATION_COMMAND_ID')
        _need(type(timeout_seconds) is int and 5 <= timeout_seconds <= 20, 'VALIDATION_DEADLINE')
        _need(type(bundle) is bundle_codec.CompleteFixtureBundle, 'VALIDATION_BUNDLE_TYPE')
        factory.qualify(bundle)
        _need(bundle.engine_sha256 == executor.BINARY_SHA256, 'VALIDATION_ENGINE_PIN')
        _need(self._mutex.acquire(timeout=2), 'VALIDATION_OWNER_BUSY')
        try:
            self._healthy()
            # Validation receipts are intentionally not an implicit retry API.
            _need(command_id not in self._attempts, 'VALIDATION_COMMAND_ALREADY_ATTEMPTED')
            _need(len(self._attempts) < MAX_RUNS, 'VALIDATION_RUN_LIMIT')
            self._attempts.append(command_id)
            directory = self._parent / ('validate-' + uuid.uuid4().hex)
            try:
                directory.mkdir(exist_ok=False)
                (directory / 'manifest.json').write_bytes(bundle.manifest_bytes)
                project = directory / 'input'
                for name, raw in bundle.files.items():
                    target = project / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as stream:
                        stream.write(raw)
                result = executor.run(project, mode='profile-validate', output=directory / 'executor',
                                      timeout_seconds=timeout_seconds)
                # Fixed filenames, never a path returned by a candidate or log.
                stdout = executor._read_file(directory / 'executor/engine-stdout.txt', 262144).decode('utf-8', 'strict')
                stderr = executor._read_file(directory / 'executor/engine-stderr.txt', 262144).decode('utf-8', 'strict')
                _need(parse_json(executor._read_file(directory / 'executor/result.json', 262144)) == result,
                      'VALIDATION_CAPTURE_CHANGED')
                observation, comparison = evaluate_run(result, stdout, stderr, bundle)
                self._healthy()
                evidence = self._inventory(directory)
                raw_observation = canonical_bytes(observation)
                receipt = ValidationReceipt(command_id, bundle.project_revision, _sha(bundle.manifest_bytes),
                    self._source_sha, executor.BINARY_SHA256, _sha(raw_observation),
                    _sha(canonical_bytes(evidence)), result['run_id'])
                self._records[command_id] = _Record(bundle, directory, raw_observation, evidence,
                                                   dict(self._source_files), receipt)
                return receipt
            except BaseException:
                self._held = True
                raise
        finally:
            self._mutex.release()

    def observation(self, receipt, bundle):
        """Recheck this issuer's registered historical observation; no new run."""
        _need(self._mutex.acquire(timeout=2), 'VALIDATION_OWNER_BUSY')
        try:
            self._healthy()
            _need(type(receipt) is ValidationReceipt and type(bundle) is bundle_codec.CompleteFixtureBundle,
                  'VALIDATION_REGISTERED_RECEIPT_REQUIRED')
            record = self._records.get(receipt.command_id)
            _need(record is not None and record.receipt is receipt, 'VALIDATION_REGISTERED_RECEIPT_REQUIRED')
            _need(bundle.manifest_bytes == record.bundle.manifest_bytes and bundle.files == record.bundle.files,
                  'VALIDATION_RECEIPT_BUNDLE_MISMATCH')
            try:
                _need(self._inventory(record.directory) == record.evidence, 'VALIDATION_EVIDENCE_CHANGED')
                _need(_sha(record.observation) == receipt.observation_sha256, 'VALIDATION_OBSERVATION_CHANGED')
            except BaseException:
                self._held = True
                raise
            return parse_json(record.observation)
        finally:
            self._mutex.release()

    def snapshot(self):
        with self._mutex:
            return {'closed': self._closed, 'held': self._held, 'attempts': tuple(self._attempts),
                    'registered_commands': tuple(sorted(self._records)), 'public_ack': False}

    def close(self):
        _need(self._mutex.acquire(timeout=2), 'VALIDATION_CLOSE_BUSY')
        try:
            self._closed = True
        finally:
            self._mutex.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

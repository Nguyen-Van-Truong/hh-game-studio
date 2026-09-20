"""Draft installed GT06 selector; fixed paths, no remote configuration surface.

The release installs the selector. A final execution/run/request freeze must bind
the returned metadata hashes as well as source hashes. Neither metadata file is
inside its own execution source map. GT05 asset admission remains unchanged.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import stat

import binding_candidate as binding


SELECTOR_SCHEMA = 'HH-GT06-EXECUTION-SELECTION-1'
SELECTOR_PATH = 'host/replay/execution-current.json'
BINDING_PATH = 'host/replay/execution-source.json'
METADATA_PATHS = frozenset({SELECTOR_PATH, BINDING_PATH})
_GT03_SUFFIXES = frozenset({'.py', '.gd', '.uid', '.cfg', '.godot', '.json'})
_FIXTURE_SUFFIXES = frozenset({'.gd', '.uid', '.godot', '.tscn', '.tres'})


def _files(studio: Path, relative: str, suffixes: frozenset[str], *, recursive: bool) -> set[str]:
    """Inventory explicit source domains without importing or following entries."""
    result: set[str] = set()
    pending = [studio / relative]
    while pending:
        directory = pending.pop()
        binding._checked_stat(directory, file=False)
        try:
            entries = sorted(directory.iterdir())
            for entry in entries:
                if entry.name == '__pycache__':
                    continue
                info = entry.lstat()
                binding._need(not stat.S_ISLNK(info.st_mode)
                              and not getattr(info, 'st_file_attributes', 0) & 0x400,
                              'BINDING_REPARSE')
                if stat.S_ISDIR(info.st_mode):
                    if recursive:
                        pending.append(entry)
                elif entry.suffix in suffixes:
                    binding._need(stat.S_ISREG(info.st_mode), 'BINDING_FILE_TYPE')
                    result.add(binding._name(entry.relative_to(studio).as_posix()))
        except OSError:
            raise binding.BindingRejected('BINDING_FILE_MISSING_OR_UNREADABLE') from None
    return result


def _required_sources(studio: Path) -> frozenset[str]:
    names = {'toolchain.lock.json', 'build/bootstrap/run_fixture.py',
             'contracts/perf-collector.schema.json', 'host/replay/profile.json'}
    for relative in ('godot-addon', 'host/core', 'protocol'):
        names.update(_files(studio, relative, _GT03_SUFFIXES, recursive=True))
    names.update(_files(studio, 'host/replay', frozenset({'.py'}), recursive=False))
    for relative in ('godot-addon/observe', 'fixtures/play-observe'):
        names.update(_files(studio, relative, _FIXTURE_SUFFIXES, recursive=True))
    names.difference_update(METADATA_PATHS)
    binding._source_map({name: '0' * 64 for name in names})
    return frozenset(names)


def _selection(studio: Path) -> tuple[bytes, bytes, dict[str, str]]:
    """Strictly read one internally consistent fixed metadata generation."""
    studio = binding._absolute(studio)
    binding._checked_stat(studio, file=False)
    selector_path, binding_path = studio / SELECTOR_PATH, studio / BINDING_PATH
    selector_raw = binding._read(selector_path, binding.MAX_BINDING_BYTES)
    selector = binding._json_object(selector_raw)
    binding._need(set(selector) == {'schema', 'binding_sha256'}
                  and selector['schema'] == SELECTOR_SCHEMA, 'SELECTION_SCHEMA')
    expected = binding._digest(selector['binding_sha256'])
    binding_raw = binding._read(binding_path, binding.MAX_BINDING_BYTES)
    binding._need(hashlib.sha256(binding_raw).hexdigest() == expected, 'BINDING_MANIFEST_HASH')
    document = binding._object(binding_raw)
    declared = binding._source_map(document['source_files'])
    forbidden = {name.casefold() for name in METADATA_PATHS}
    binding._need(not any(name.casefold() in forbidden for name in declared),
                  'SELECTION_METADATA_IN_SOURCE')
    binding._need(binding._read(selector_path, binding.MAX_BINDING_BYTES) == selector_raw
                  and binding._read(binding_path, binding.MAX_BINDING_BYTES) == binding_raw,
                  'SELECTION_CHANGED')
    metadata = {SELECTOR_PATH: hashlib.sha256(selector_raw).hexdigest(),
                BINDING_PATH: hashlib.sha256(binding_raw).hexdigest()}
    return selector_raw, binding_raw, metadata


def selection_identity(studio: Path) -> dict[str, str]:
    """Return strict fixed metadata hashes for the caller's import-generation latch.

    The coordinator wires this latch before importing runtime dependencies and
    rejects a different generation on every sources() call. This pure reader has
    no process-global state and no caller-selectable metadata path.
    """
    return dict(sorted(_selection(studio)[2].items()))


def load_installed(studio: Path, accepted_source_files: dict[str, str]) -> dict[str, str]:
    """Read the fixed trusted release selector and return source + metadata map.

    ``accepted_source_files`` is supplied only by unchanged pinned GT05 admission.
    No selector path, expected hash, source inventory or override is a request field.
    The caller compares the returned metadata with its import-generation latch,
    retains source pre/postchecks and preserves generated run.json ordering.
    """
    studio = binding._absolute(studio)
    selector_raw, binding_raw, metadata = _selection(studio)

    required = _required_sources(studio)
    verified = binding.read_execution_binding(studio, studio / BINDING_PATH,
        expected_sha256=metadata[BINDING_PATH], accepted_source_files=accepted_source_files,
        required_sources=required)
    binding._need(_required_sources(studio) == required, 'SELECTION_DEPENDENCIES_CHANGED')
    binding._need(binding._read(studio / SELECTOR_PATH, binding.MAX_BINDING_BYTES) == selector_raw
                  and binding._read(studio / BINDING_PATH, binding.MAX_BINDING_BYTES) == binding_raw,
                  'SELECTION_CHANGED')
    verified.update(metadata)
    return dict(sorted(verified.items()))

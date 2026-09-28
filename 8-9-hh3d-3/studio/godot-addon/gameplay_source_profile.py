"""Byte admission for the contained gameplay-source diagnostic, authority zero.

Godot owns syntax/type analysis. This module does not implement GDScript or
grant publication: an admitted byte envelope is still untrusted executable code.
The first diagnostic uses one script/scene; dependency-graph admission and
public AUTH-01..07 integration remain separate unfinished requirements.
"""
from __future__ import annotations

import hashlib
import posixpath
import re
from collections.abc import Mapping

PROFILE = 'hh-godot-gameplay-source-1'
MAX_BYTES = 16_384
MAX_FILES = 64
MAX_TOTAL_BYTES = 256 * 1024
_PROJECT_PATH = re.compile(r"(?:res://)?(scripts|scenes)/[A-Za-z0-9._/-]+\Z")
_REFERENCE = re.compile(r"(?:preload|load|extends)\(?(?:\s*)['\"]res://([^'\"]+)['\"]\)?")
PROJECT_TEMPLATE = (
    'config_version=5\n[application]\nconfig/name="HH gameplay source diagnostic"\n'
    '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    '[threading]\nworker_pool/max_threads=4\n'
    '[debug]\ngdscript/warnings/untyped_declaration=2\n'
    'gdscript/warnings/inference_on_variant=2\n')


class GameplaySourceError(ValueError):
    pass


def _path(value: object) -> bool:
    if type(value) is not str or _PROJECT_PATH.fullmatch(value) is None:
        return False
    normalized = posixpath.normpath(value.removeprefix('res://'))
    return normalized == value.removeprefix('res://') and not normalized.startswith('../')


def validate_source(source: bytes) -> dict:
    """Check bounded, exact bytes only; never interpret strings as a sandbox."""
    if type(source) is not bytes:
        raise GameplaySourceError('GAMEPLAY_SOURCE_TYPE')
    if not 1 <= len(source) <= MAX_BYTES:
        raise GameplaySourceError('GAMEPLAY_SOURCE_SIZE')
    try:
        text = source.decode('utf-8', errors='strict')
    except UnicodeDecodeError as error:
        raise GameplaySourceError('GAMEPLAY_SOURCE_UTF8') from error
    if '\x00' in text or text.startswith('\ufeff'):
        raise GameplaySourceError('GAMEPLAY_SOURCE_BYTES')
    return {'profile': PROFILE, 'authority': 0, 'bytes': len(source),
            'sha256': hashlib.sha256(source).hexdigest(),
            'syntax_and_types_verified': False, 'dependency_closure_verified': False,
            'public_ack': False, 'sandbox_acceptance': False}


def validate_dependency_closure(files: Mapping[str, bytes], *, entrypoint: str) -> dict:
    """Validate a bounded, immutable script dependency envelope.

    This only proves that referenced project files are present and byte-bound;
    Godot must still prove syntax/types and the executor must still prove OS
    confinement.  No source is executed and no publication capability is
    granted here.
    """
    if not isinstance(files, Mapping) or not files or len(files) > MAX_FILES or not _path(entrypoint):
        raise GameplaySourceError('GAMEPLAY_DEPENDENCY_SHAPE')
    checked: dict[str, bytes] = {}
    total = 0
    for name, raw in files.items():
        if not _path(name) or type(raw) is not bytes or not 1 <= len(raw) <= MAX_BYTES:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_FILE')
        if name in checked:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_DUPLICATE')
        validate_source(raw)
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_SIZE')
        checked[name] = raw
    if entrypoint not in checked:
        raise GameplaySourceError('GAMEPLAY_DEPENDENCY_ENTRYPOINT')
    pending = [entrypoint]
    reachable: set[str] = set()
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        text = checked[name].decode('utf-8')
        for reference in _REFERENCE.findall(text):
            if not _path(reference) or reference not in checked:
                raise GameplaySourceError('GAMEPLAY_DEPENDENCY_MISSING')
            pending.append(reference)
    if reachable != set(checked):
        raise GameplaySourceError('GAMEPLAY_DEPENDENCY_UNREFERENCED')
    return {
        'profile': PROFILE, 'authority': 0,
        'entrypoint': entrypoint,
        'files': {name: hashlib.sha256(checked[name]).hexdigest() for name in sorted(checked)},
        'dependency_closure_verified': True,
        'syntax_and_types_verified': False,
        'public_ack': False, 'sandbox_acceptance': False,
    }


def driver() -> str:
    """Trusted parent: each engine child installs the guard before parsing.

    Children cannot signal/ptrace the parent. Its phase ordering and real wait
    results drive execution; printed phase markers remain diagnostic data only.
    The same PID-1 wall deadline covers all phases, not a fresh timeout per phase.
    """
    return (
        'import subprocess,sys\n'
        'for phase in ("parse","import","play"):\n'
        ' print("HH_GAMEPLAY_PHASE_BEGIN "+phase,flush=True)\n'
        ' code=subprocess.run(["/usr/local/bin/python3","-I","-B",'
        '"/harness/gameplay_sandbox.py",phase],stdin=subprocess.DEVNULL).returncode\n'
        ' print("HH_GAMEPLAY_PHASE_END "+phase+" "+str(code),flush=True)\n'
        ' if code!=0:sys.exit(45)\n')

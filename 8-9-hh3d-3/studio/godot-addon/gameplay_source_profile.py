"""Byte admission for the contained gameplay-source diagnostic, authority zero.

Godot owns syntax/type analysis. This module does not implement GDScript or
grant publication: an admitted byte envelope is still untrusted executable code.
The first diagnostic uses one script/scene; dependency-graph admission and
public AUTH-01..07 integration remain separate unfinished requirements.
"""
from __future__ import annotations

import hashlib
import posixpath
from collections.abc import Mapping
import unicodedata

PROFILE = 'hh-godot-gameplay-source-1'
MAX_BYTES = 16_384
MAX_FILES = 64
MAX_TOTAL_BYTES = 256 * 1024
_PROJECT_PATH = frozenset(('scripts', 'scenes'))
_WINDOWS_DEVICES = frozenset({
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
})
PROJECT_TEMPLATE = (
    'config_version=5\n[application]\nconfig/name="HH gameplay source diagnostic"\n'
    '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    '[threading]\nworker_pool/max_threads=4\n'
    '[debug]\ngdscript/warnings/untyped_declaration=2\n'
    'gdscript/warnings/inference_on_variant=2\n')


class GameplaySourceError(ValueError):
    pass


def _path(value: object) -> bool:
    if type(value) is not str or value.startswith('res://') or '\\' in value or ':' in value or '\x00' in value:
        return False
    parts = value.split('/')
    if len(parts) < 2 or parts[0] not in _PROJECT_PATH or any(not part or part in ('.', '..') for part in parts[1:]):
        return False
    for part in parts[1:]:
        # The envelope is copied to Windows hosts as well as Linux containers.
        # Reject names that can alias, become streams, or address a device there.
        if part != unicodedata.normalize('NFC', part) or part[-1] in ' .':
            return False
        if any(ord(char) < 32 for char in part):
            return False
        if part.split('.', 1)[0].upper() in _WINDOWS_DEVICES:
            return False
    normalized = posixpath.normpath(value)
    return normalized == value and not normalized.startswith('../')


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


def validate_source_bundle(files: Mapping[str, bytes], *, entrypoint: str) -> dict:
    """Validate an exact bounded source envelope without parsing GDScript.

    A complete dependency *inventory* is bound by path and hash here. This
    deliberately does not infer imports from source text: regexes cannot
    model Godot's parser, scene ext_resources, UID references, dynamic loads,
    comments, or strings. Godot import/parse and runtime observation must
    prove the actual closure later.
    """
    if not isinstance(files, Mapping) or not files or len(files) > MAX_FILES or not _path(entrypoint):
        raise GameplaySourceError('GAMEPLAY_DEPENDENCY_SHAPE')
    checked: dict[str, bytes] = {}
    folded: set[str] = set()
    total = 0
    for name, raw in files.items():
        if not _path(name) or type(raw) is not bytes or not 1 <= len(raw) <= MAX_BYTES:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_FILE')
        if name in checked:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_DUPLICATE')
        alias = name.casefold()
        if alias in folded:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_ALIAS')
        validate_source(raw)
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_SIZE')
        checked[name] = raw
        folded.add(alias)
    if entrypoint not in checked:
        raise GameplaySourceError('GAMEPLAY_DEPENDENCY_ENTRYPOINT')
    return {
        'profile': PROFILE, 'authority': 0,
        'entrypoint': entrypoint,
        'files': {name: hashlib.sha256(checked[name]).hexdigest() for name in sorted(checked)},
        'dependency_inventory_verified': True,
        'dependency_closure_verified': False,
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
        'from pathlib import Path\n'
        'primary="scripts/fixture_actor.gd"\n'
        'scripts=sorted(p.relative_to("/project").as_posix() for p in Path("/project/scripts").rglob("*.gd") if p.is_file())\n'
        'if primary not in scripts or len(scripts)>64:sys.exit(45)\n'
        'scripts=[primary]+[p for p in scripts if p!=primary]\n'
        'for phase in ("parse","import","play"):\n'
        ' print("HH_GAMEPLAY_PHASE_BEGIN "+phase,flush=True)\n'
        ' for script in (scripts if phase=="parse" else [None]):\n'
        '  secondary=script is not None and script!=primary\n'
        '  if secondary:print("HH_GAMEPLAY_MODULE_BEGIN "+script,flush=True)\n'
        '  argv=["/usr/local/bin/python3","-I","-B","/harness/gameplay_sandbox.py",phase]\n'
        '  if script is not None:argv.append(script)\n'
        '  code=subprocess.run(argv,stdin=subprocess.DEVNULL).returncode\n'
        '  if secondary:print("HH_GAMEPLAY_MODULE_END "+script+" "+str(code),flush=True)\n'
        '  if code!=0:break\n'
        ' print("HH_GAMEPLAY_PHASE_END "+phase+" "+str(code),flush=True)\n'
        ' if code!=0:sys.exit(45)\n')

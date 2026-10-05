"""Byte admission for the contained gameplay-source diagnostic, authority zero.

Godot owns syntax/type/asset-import analysis. This module does not implement
GDScript, GLB or PNG parsing and does not grant publication: an admitted byte
envelope is still untrusted executable code. Dependency-graph closure, native
asset import and public AUTH-01..07 integration remain unfinished.
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
MAX_ASSET_BYTES = 1 * 1024 * 1024
MAX_ASSET_TOTAL_BYTES = 2 * 1024 * 1024
_PROJECT_PATH = frozenset(('scripts', 'scenes'))
_ASSET_FILES = frozenset(('assets/avatar.glb', 'assets/sprite_sheet.png'))
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


def validate_asset(name: str, raw: bytes) -> dict:
    """Admit only the two bounded binary fixture artifacts.

    This binds bytes and basic container signatures; it does not parse GLB
    meshes, PNG dimensions, Blender metadata, or prove Godot importability.
    """
    if name not in _ASSET_FILES or type(raw) is not bytes or not 1 <= len(raw) <= MAX_ASSET_BYTES:
        raise GameplaySourceError('GAMEPLAY_ASSET_FILE')
    if name.endswith('.glb') and (len(raw) < 12 or raw[:4] != b'glTF'
                                  or int.from_bytes(raw[4:8], 'little') != 2
                                  or int.from_bytes(raw[8:12], 'little') != len(raw)):
        raise GameplaySourceError('GAMEPLAY_ASSET_GLB')
    if name.endswith('.png') and not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        raise GameplaySourceError('GAMEPLAY_ASSET_PNG')
    return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest(),
            'size_bytes': len(raw), 'asset_import_verified': False}


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
    assets: dict[str, bytes] = {}
    folded: set[str] = set()
    total = 0
    for name, raw in files.items():
        if type(name) is not str:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_FILE')
        alias = name.casefold()
        if alias in folded:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_ALIAS')
        if name in _ASSET_FILES:
            validate_asset(name, raw)
            assets[name] = raw
            folded.add(alias)
            continue
        if not _path(name) or type(raw) is not bytes or not 1 <= len(raw) <= MAX_BYTES:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_FILE')
        if name in checked:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_DUPLICATE')
        validate_source(raw)
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise GameplaySourceError('GAMEPLAY_DEPENDENCY_SIZE')
        checked[name] = raw
        folded.add(alias)
    if entrypoint not in checked:
        raise GameplaySourceError('GAMEPLAY_DEPENDENCY_ENTRYPOINT')
    asset_total = sum(len(raw) for raw in assets.values())
    if asset_total > MAX_ASSET_TOTAL_BYTES:
        raise GameplaySourceError('GAMEPLAY_ASSET_SIZE')
    return {
        'profile': PROFILE, 'authority': 0,
        'entrypoint': entrypoint,
        'files': {name: hashlib.sha256(checked[name]).hexdigest() for name in sorted(checked)},
        'assets': {name: {'sha256': hashlib.sha256(assets[name]).hexdigest(),
                          'size_bytes': len(assets[name]),
                          'asset_import_verified': False}
                   for name in sorted(assets)},
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

    Resource records are advisory, unauthenticated transcript data. Missing
    observations stay null; they never alter the child's result or admission.
    """
    return '''import json,math,resource,subprocess,sys,time
from pathlib import Path
safe_integer=(1<<53)-1
memory_fields=("low","high","max","oom","oom_kill","oom_group_kill")
def clock():
    try:
        value=time.monotonic_ns()
        return value if type(value) is int and value>=0 else None
    except (OSError,ValueError):
        return None
def cpu_usage():
    try:
        value=resource.getrusage(resource.RUSAGE_CHILDREN)
        pair=(value.ru_utime,value.ru_stime)
        if all(type(n) in (int,float) and math.isfinite(n) and 0<=n<=safe_integer for n in pair):
            return pair
    except (OSError,ValueError):
        pass
    return (None,None)
def cpu_limits():
    try:
        pair=resource.getrlimit(resource.RLIMIT_CPU)
        if len(pair)==2 and all(type(n) is int and -1<=n<=safe_integer for n in pair):
            return pair
    except (OSError,ValueError):
        pass
    return (None,None)
def memory_events():
    unavailable={"status":"unavailable","counts":dict.fromkeys(memory_fields)}
    try:
        with Path("/sys/fs/cgroup/memory.events").open("rb") as stream:
            raw=stream.read(4097)
        if not 0<len(raw)<=4096:
            return unavailable
        values={}
        lines=raw.decode("ascii").splitlines()
        if len(lines)>16:
            return unavailable
        for line in lines:
            key,value=line.split()
            if key in values or not value.isdecimal() or not 0<=int(value)<=safe_integer:
                return unavailable
            values[key]=int(value)
        if any(key in values for key in memory_fields):
            return {"status":"observed","counts":{key:values.get(key) for key in memory_fields}}
    except (OSError,ValueError):
        pass
    return unavailable
def delta(before,after):
    return after-before if before is not None and after is not None and 0<=after-before<=safe_integer else None
def microseconds(value):
    return value//1000 if value is not None and value//1000<=safe_integer else None
primary="scripts/fixture_actor.gd"
scripts=sorted(p.relative_to("/project").as_posix() for p in Path("/project/scripts").rglob("*.gd") if p.is_file())
if primary not in scripts or len(scripts)>64:sys.exit(45)
scripts=[primary]+[p for p in scripts if p!=primary]
sample_index=0
for phase in ("parse","import","play"):
    print("HH_GAMEPLAY_PHASE_BEGIN "+phase,flush=True)
    for script in (scripts if phase=="parse" else [None]):
        secondary=script is not None and script!=primary
        if secondary:print("HH_GAMEPLAY_MODULE_BEGIN "+script,flush=True)
        argv=["/usr/local/bin/python3","-I","-B","/harness/gameplay_sandbox.py",phase]
        if script is not None:argv.append(script)
        limits=cpu_limits()
        usage_before=cpu_usage()
        memory_before=memory_events()
        started=clock()
        code=subprocess.run(argv,stdin=subprocess.DEVNULL).returncode
        ended=clock()
        usage_after=cpu_usage()
        memory_after=memory_events()
        record={"schema":"hh-gameplay-child-resources-1","scope":"diagnostic_untrusted_transcript",
            "authority":0,"phase":phase,"sample_index":sample_index,"returncode":code,
            "start_monotonic_us":microseconds(started),"end_monotonic_us":microseconds(ended),"elapsed_ns":delta(started,ended),
            "cpu_limit_soft_seconds":limits[0],"cpu_limit_hard_seconds":limits[1],
            "user_cpu_seconds":delta(usage_before[0],usage_after[0]),
            "system_cpu_seconds":delta(usage_before[1],usage_after[1]),
            "memory_events_before":memory_before,"memory_events_after":memory_after}
        print("HH_GAMEPLAY_CHILD_RESOURCES "+json.dumps(record,separators=(",",":"),allow_nan=False),flush=True)
        sample_index+=1
        if secondary:print("HH_GAMEPLAY_MODULE_END "+script+" "+str(code),flush=True)
        if code!=0:break
    print("HH_GAMEPLAY_PHASE_END "+phase+" "+str(code),flush=True)
    if code!=0:sys.exit(45)
'''

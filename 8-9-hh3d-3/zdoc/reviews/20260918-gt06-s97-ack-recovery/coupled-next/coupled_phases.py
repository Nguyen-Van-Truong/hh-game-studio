"""S97 binding adapter over the immutable S96 diagnostic; import launches nothing."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import traceback

BASE = Path(__file__).resolve().parent
ENTRY = Path(__file__).resolve()
ROOT = BASE.parents[3]
S96 = ROOT / 'zdoc/reviews/20260918-gt06-s96-coupled-phases'
SOURCE_MAP = BASE / 'source-current.json'
RUN_ID = 'gt06-s97-coupled-phases-01'
PREFLIGHT_ID = 'gt06-s97-coupled-phases-preflight-01'
RETAINED_ENTRY_SHA256 = 'b1e311144b5beaad3fc0188b4d09e285351a4978502e64c0ac015122d4465ee0'
NATIVE = 'tests/replay/benchmark_native.gd'
KNOWN_CODES = frozenset({'S97_REPARSE', 'S97_RETAINED_ENTRY', 'S97_SOURCE_MAP_PENDING',
    'S97_SOURCE_MAP_INVALID', 'S97_SOURCE_SCOPE', 'S97_COMPOSITION_REBOUND'})


def need(value, code):
    if not value:
        raise RuntimeError(code)


def plain(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists():
            info = item.lstat()
            need(not item.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'S97_REPARSE')
    return path


def load_retained():
    path = plain(S96 / 'coupled_phases.py')
    need(hashlib.sha256(path.read_bytes()).hexdigest() == RETAINED_ENTRY_SHA256,
         'S97_RETAINED_ENTRY')
    spec = importlib.util.spec_from_file_location('_s97_retained_s96', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_freeze(value, old_files, digest):
    need(isinstance(value, dict) and value.get('freeze_status') == 'ROOT_FROZEN',
         'S97_SOURCE_MAP_PENDING')
    files = value.get('source_files')
    closure = value.get('source_closure_sha256')
    need(isinstance(files, dict) and len(files) == 51 and isinstance(closure, str)
         and re.fullmatch('[0-9a-f]{64}', closure) is not None
         and all(isinstance(name, str) and isinstance(pin, str)
                 and re.fullmatch('[0-9a-f]{64}', pin) is not None for name, pin in files.items()),
         'S97_SOURCE_MAP_INVALID')
    need(digest(files) == closure, 'S97_SOURCE_MAP_INVALID')
    need(files.keys() == old_files.keys()
         and {name for name in files if files[name] != old_files[name]} == {NATIVE},
         'S97_SOURCE_SCOPE')
    return closure


def configure(retained, source_sha256):
    """Only bindings change; retained execution, native patch and observers delegate."""
    need(retained.RUN_ID == 'gt06-s96-coupled-phases-01', 'S97_COMPOSITION_REBOUND')
    original_helpers = retained.HELPERS
    retained.BASE, retained.ENTRY, retained.ROOT = BASE, ENTRY, ROOT
    retained.SOURCE_MAP, retained.SOURCE_SHA256 = SOURCE_MAP, source_sha256
    retained.RUN_ID, retained.PREFLIGHT_ID = RUN_ID, PREFLIGHT_ID
    retained.OUTPUT = retained.STUDIO / '.local/reviews' / RUN_ID
    retained.LAUNCH = BASE / 'launch-01'
    # Keep all original bytes at their true paths, even their old map/test files.
    # They are provenance; campaign() reads only the new frozen source map.
    retained.HELPERS = (*original_helpers, ENTRY, BASE / 'register_task.ps1',
                        BASE / 'test_coupled_phases.py', SOURCE_MAP, BASE / 'README.md')
    retained.KNOWN_CODES = retained.KNOWN_CODES | KNOWN_CODES
    original_request = retained.request_value

    def request_value(console, windowed):
        value, godot = original_request(console, windowed)
        value['schema'] = 'HH-GT06-S97-COUPLED-REQUEST-1'
        value['composition_origin'] = (S96 / 'coupled_phases.py').relative_to(ROOT).as_posix()
        value['native_census_schema_reused'] = 'hh-studio.gt06.s96-ack-sparse-attribution'
        value['base_source_role'] = 'root_frozen_S97_candidate_not_accepted'
        return value, godot

    retained.request_value = request_value
    return retained


def composition():
    # Reject missing/pending input before importing the retained composition.
    need(plain(SOURCE_MAP).is_file(), 'S97_SOURCE_MAP_PENDING')
    value = json.loads(SOURCE_MAP.read_bytes())
    need(isinstance(value, dict) and value.get('freeze_status') == 'ROOT_FROZEN',
         'S97_SOURCE_MAP_PENDING')
    retained = load_retained()
    old_files = json.loads(plain(retained.SOURCE_MAP).read_bytes())['source_files']
    closure = validate_freeze(value, old_files, retained.map_digest)
    return configure(retained, closure)


def main():
    return composition().main()


def sanitized_error(error):
    result = {'exception_class': type(error).__name__, 'frames': [
        {'file': Path(frame.filename).name, 'line': frame.lineno}
        for frame in traceback.extract_tb(error.__traceback__)[-16:]]}
    if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] in KNOWN_CODES:
        result['known_code'] = error.args[0]
    elif len(error.args) == 1 and type(error.args[0]) is str and error.args[0] == 'S96_SOURCE_MISMATCH':
        result['known_code'] = 'S96_SOURCE_MISMATCH'
        result['source_difference'] = error.source_difference
    return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        message = json.dumps(sanitized_error(error)) + '\n'
        if sys.stderr is not None and not sys.stderr.closed:
            sys.stderr.write(message)
            sys.stderr.flush()
        else:
            with plain(BASE / 'launch-01/entry-startup-failure.json').open('x', encoding='utf-8') as stream:
                stream.write(message)
        raise SystemExit(1)

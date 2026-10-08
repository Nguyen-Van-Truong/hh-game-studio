"""Bind isolated trusted-loader reports to the immutable source inventory.

No candidate marker may be passed here as a trusted observation. The driver and
host use only output belonging to the dedicated, pinned observer process. This
proves static loader edges, not arbitrary dynamic loads/FileAccess behavior.
"""
import importlib.util
import json
from pathlib import Path

PREFIX = b'HH_LOADER_DEPENDENCIES '
MAX_BYTES = 128 * 1024


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('LOADER_DUPLICATE_KEY')
        result[key] = value
    return result


def parse(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('LOADER_REPORT_BYTES')
    rows = [line[len(PREFIX):] for line in raw.splitlines() if line.startswith(PREFIX)]
    if len(rows) != 1:
        raise ValueError('LOADER_REPORT_COUNT')
    try:
        return json.loads(rows[0], object_pairs_hook=_pairs)
    except (ValueError, RecursionError, UnicodeError) as error:
        raise ValueError('LOADER_REPORT_JSON') from error


def validate(files, raw, reopened_raw=None, *, validator=None):
    # Never import a module from the project/evidence directory.
    if validator is None:
        path = Path(__file__).with_name('gameplay_dependency_evidence.py')
        spec = importlib.util.spec_from_file_location('_trusted_dependency_evidence', path)
        validator = importlib.util.module_from_spec(spec)
        exec(compile(path.read_bytes(), str(path), 'exec'), validator.__dict__)
    first = parse(raw)
    kwargs = {} if reopened_raw is None else dict(
        reopened_files=files, reopened_observation=parse(reopened_raw))
    result = validator.validate_dependency_observation(files, first, **kwargs)
    return {**result, 'observation': first, 'loader_graph_bound': True,
            'observation_scope': 'godot_loader_static_edges',
            'dynamic_dependencies_verified': False}

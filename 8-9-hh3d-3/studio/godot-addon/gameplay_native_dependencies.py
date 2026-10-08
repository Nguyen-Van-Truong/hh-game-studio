"""Bind isolated trusted-loader reports to the immutable source inventory.

No candidate marker may be passed here as a trusted observation. The driver and
host use only output belonging to the dedicated, pinned observer process. The
scoped contract below proves the observer's *literal resource inventory* after
close/reopen binding; it does not prove computed paths, runtime ``FileAccess``,
or arbitrary dynamic loads. The generic authority and closure flags therefore
remain false even when the scoped contract is true.
"""
import importlib.util
import json
from pathlib import Path

PREFIX = b'HH_LOADER_DEPENDENCIES '
MAX_BYTES = 128 * 1024
LITERAL_LOADER_SCOPE = 'godot_loader_literal_resource_inventory_v1'
_LITERAL_EDGE_KINDS = frozenset(('loader_reference', 'script_preload',
                                 'dynamic_load'))


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


def _literal_loader_scope(observation, result, *, reopened_raw):
    """Return a narrow report only for a bound, reopened loader inventory.

    ``gameplay_dependencies.gd`` emits exactly the three edge kinds below:
    ResourceLoader references, literal ``preload("res://...")`` references,
    and literal ``load("res://...")`` references.  Rejecting any other kind
    here prevents a caller from using this wrapper to widen the observer's
    contract.  In particular, this helper never changes generic closure,
    dynamic-dependency, authority, or public-acknowledgement fields.
    """
    scoped = reopened_raw is not None and result.get('reopen_match') is True
    report = {
        'literal_loader_scope': LITERAL_LOADER_SCOPE if scoped else None,
        'literal_loader_scope_verified': scoped,
        'literal_loader_edge_counts': None,
    }
    if not scoped:
        return report
    # Do not let a custom validator manufacture a scoped claim while omitting
    # the authority-zero contract returned by the real validator.
    if (result.get('schema') != observation.get('schema')
            or result.get('authority') != 0
            or result.get('public_ack') is not False
            or result.get('native_observation_verified') is not False
            or result.get('dependency_closure_verified') is not False):
        raise ValueError('LOADER_LITERAL_SCOPE_AUTHORITY')
    counts = {kind: 0 for kind in sorted(_LITERAL_EDGE_KINDS)}
    for node in observation['nodes']:
        for edge in node['edges']:
            kind = edge['kind']
            if kind not in _LITERAL_EDGE_KINDS:
                raise ValueError('LOADER_LITERAL_SCOPE_EDGE_KIND')
            counts[kind] += 1
    report['literal_loader_edge_counts'] = counts
    return report


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
    scoped = _literal_loader_scope(first, result, reopened_raw=reopened_raw)
    return {**result, 'observation': first, 'loader_graph_bound': True,
            'observation_scope': 'godot_loader_literal_resource_inventory',
            'dynamic_dependencies_verified': False, **scoped}

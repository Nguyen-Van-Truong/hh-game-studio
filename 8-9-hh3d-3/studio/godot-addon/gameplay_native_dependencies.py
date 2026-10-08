"""Bind isolated trusted-loader reports to the immutable source inventory.

No candidate marker may be passed here as a trusted observation. The driver and
host use only output belonging to the dedicated, pinned observer process. The
scoped contract below proves the observer's *literal resource inventory* after
close/reopen binding; it does not prove computed paths, runtime ``FileAccess``,
or arbitrary dynamic loads. The generic authority and closure flags therefore
remain false even when the scoped contract is true.
"""
import importlib.util
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

PREFIX = b'HH_LOADER_DEPENDENCIES '
MAX_BYTES = 128 * 1024
LITERAL_LOADER_SCOPE = 'godot_loader_literal_resource_inventory_v1'
STATIC_LITERAL_SCOPE = 'godot_static_literal_script_dependencies_v1'
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


def _validator_module(validator):
    # Never import a module from the project/evidence directory.
    if validator is None:
        path = Path(__file__).with_name('gameplay_dependency_evidence.py')
        spec = importlib.util.spec_from_file_location('_trusted_dependency_evidence', path)
        validator = importlib.util.module_from_spec(spec)
        exec(compile(path.read_bytes(), str(path), 'exec'), validator.__dict__)
    return validator


def _script_tokens(text):
    """Read lexical tokens only; never evaluate or compile candidate code.

    Comments and ordinary, raw, or multiline strings remain inert. Resource
    arguments use the deliberately smaller plain-string subset below; escaped
    and multiline path literals fail closed instead of being guessed.
    """
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
        elif char == '#':
            end = text.find('\n', index)
            index = len(text) if end < 0 else end + 1
        elif char in "\"'":
            delimiter = char * (3 if text.startswith(char * 3, index) else 1)
            index += len(delimiter)
            start = index
            escaped = False
            while index < len(text) and not text.startswith(delimiter, index):
                if text[index] == '\\':
                    escaped = True
                    index += 2
                else:
                    index += 1
            if index >= len(text):
                raise ValueError('STATIC_DEPENDENCY_UNTERMINATED_STRING')
            value = text[start:index]
            yield ('string' if len(delimiter) == 1 and not escaped
                   and '\n' not in value and '\r' not in value else 'opaque_string', value)
            index += len(delimiter)
        elif char == '_' or char.isalpha():
            start = index
            index += 1
            while index < len(text) and (text[index] == '_' or text[index].isalnum()):
                index += 1
            yield ('word', text[start:index])
        else:
            yield ('symbol', char)
            index += 1


def admit_static_literals(files, *, validator=None):
    """Reject nonliteral/aliased resource loaders before native activation.

    This is a bounded source admission rule for O13 AUTH-02, not a GDScript
    parser or a dynamic-dependency claim. Native syntax/type/import validation
    and authenticated loader readback remain mandatory. All uses of the
    ResourceLoader namespace must be its direct single-literal ``load`` call;
    this also rejects aliases, reflective calls, and threaded loader APIs.
    """
    validator = _validator_module(validator)
    if not isinstance(files, Mapping) or not files or len(files) > validator.MAX_FILES:
        raise ValueError('STATIC_DEPENDENCY_FILE_SET')
    # Reuse the established bounded byte/path/alias contract, without claiming
    # that these synthetic edge-free rows are an engine observation.
    nodes = []
    for name, data in files.items():
        if type(name) is not str or type(data) is not bytes:
            raise ValueError('STATIC_DEPENDENCY_FILE_BYTES')
        nodes.append({'path': name, 'kind': 'script' if name.endswith('.gd') else
                      ('scene' if name.endswith('.tscn') else 'asset'),
                      'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'edges': []})
    validator.validate_dependency_observation(files, {
        'schema': validator.SCHEMA, 'version': validator.VERSION,
        'entrypoint': sorted(files)[0], 'nodes': nodes})
    references = {}
    for name, data in sorted(files.items()):
        if name.endswith('.tscn'):
            try:
                scene = data.decode('utf-8', errors='strict')
            except UnicodeError as error:
                raise ValueError('STATIC_DEPENDENCY_ENCODING') from error
            edges = set()
            # Text scenes encode ext_resource paths as quoted res:// values.
            # Keep the native observer's loader_reference spelling so this
            # sidecar can bind its exact output without rewriting evidence.
            for line in scene.splitlines():
                if not line.lstrip().startswith('[ext_resource'):
                    continue
                match = re.search(r'\bpath\s*=\s*"(res://[^"\r\n]+)"', line)
                if match is None:
                    raise ValueError('STATIC_DEPENDENCY_EXT_RESOURCE')
                target = validator._path(match.group(1)[6:], code='STATIC_DEPENDENCY_OUTSIDE_ROOT')
                if target not in files:
                    raise ValueError('STATIC_DEPENDENCY_MISSING')
                edges.add(('loader_reference', target))
            references[name] = [{'kind': kind, 'target': target}
                                for kind, target in sorted(edges)]
            continue
        if not name.endswith('.gd'):
            references[name] = []
            continue
        try:
            tokens = list(_script_tokens(data.decode('utf-8', errors='strict')))
        except UnicodeError as error:
            raise ValueError('STATIC_DEPENDENCY_ENCODING') from error
        edges = set()
        for index, token in enumerate(tokens):
            if token == ('word', 'ResourceLoader'):
                if tokens[index + 1:index + 4] != [
                        ('symbol', '.'), ('word', 'load'), ('symbol', '(')]:
                    raise ValueError('STATIC_DEPENDENCY_LOADER_ALIAS')
            if token not in (('word', 'load'), ('word', 'preload')):
                continue
            if tokens[max(0, index - 1):index] == [('symbol', '.')]:
                if token != ('word', 'load') or index < 2 or tokens[index - 2] != ('word', 'ResourceLoader'):
                    raise ValueError('STATIC_DEPENDENCY_LOADER_ALIAS')
            call = tokens[index + 1:index + 4]
            if (len(call) != 3 or call[0] != ('symbol', '(')
                    or call[1][0] != 'string' or call[2] != ('symbol', ')')):
                raise ValueError('STATIC_DEPENDENCY_NONLITERAL_LOAD')
            target = call[1][1]
            if not target.startswith('res://'):
                raise ValueError('STATIC_DEPENDENCY_OUTSIDE_ROOT')
            target = validator._path(target[6:], code='STATIC_DEPENDENCY_OUTSIDE_ROOT')
            if target not in files:
                raise ValueError('STATIC_DEPENDENCY_MISSING')
            # The pinned Godot observer reports both direct ResourceLoader.load
            # and bare literal load() as dynamic_load edges. Keep this
            # contract aligned with that native spelling; the admission rule
            # above still distinguishes direct from aliased loader APIs.
            kind = 'script_preload' if token[1] == 'preload' else 'dynamic_load'
            edges.add((kind, target))
        references[name] = [{'kind': kind, 'target': target} for kind, target in sorted(edges)]
    return {'scope': STATIC_LITERAL_SCOPE, 'script_edges': references,
            'input_hashes': {name: hashlib.sha256(data).hexdigest()
                             for name, data in sorted(files.items())},
            'native_observation_verified': False, 'dependency_closure_verified': False,
            'dynamic_dependencies_verified': False, 'public_ack': False, 'authority': 0}


def validate_static_literals(files, raw, reopened_raw, *, validator=None):
    """Bind source admission to two observations from the trusted observer.

    Callers must obtain both streams through ``linux_executor.read_attribution``
    and validate native exits before using this result. It cannot authenticate
    arbitrary caller bytes or promote a child gameplay claim.
    """
    validator = _validator_module(validator)
    admitted = admit_static_literals(files, validator=validator)
    if reopened_raw is None:
        raise ValueError('STATIC_DEPENDENCY_REOPEN_REQUIRED')
    result = validate(files, raw, reopened_raw, validator=validator)
    observed = {node['path']: sorted(node['edges'], key=lambda edge: (edge['kind'], edge['target']))
                for node in result['observation']['nodes']}
    if observed != admitted['script_edges']:
        raise ValueError('STATIC_DEPENDENCY_SCRIPT_GRAPH_MISMATCH')
    return {**result, 'static_literal_scope': STATIC_LITERAL_SCOPE,
            'static_literal_script_graph_bound': True,
            'static_literal_admission': admitted}


def validate(files, raw, reopened_raw=None, *, validator=None):
    validator = _validator_module(validator)
    first = parse(raw)
    kwargs = {} if reopened_raw is None else dict(
        reopened_files=files, reopened_observation=parse(reopened_raw))
    result = validator.validate_dependency_observation(files, first, **kwargs)
    scoped = _literal_loader_scope(first, result, reopened_raw=reopened_raw)
    return {**result, 'observation': first, 'loader_graph_bound': True,
            'observation_scope': 'godot_loader_literal_resource_inventory',
            'dynamic_dependencies_verified': False, **scoped}

"""Disposable three-call instrumentation; no runtime imports or disk writes.

The original snapshot AST is preserved after stripping exactly three wrappers.
Each wrapper delegates once, retains only primitive counts/times, and propagates
the original return/exception. Per-chunk events never enter the HTTP event ring.
"""
import ast
import copy
import hashlib
import inspect
import threading
import time
import textwrap


CALLS = {'stream.read': 'read', 'digest.update': 'hash', 'os.fsync': 'fsync'}
MARKER = '__s100_snapshot_call__'


def call_name(node):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id + '.' + node.attr
    return None


class SnapshotMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.local = threading.local()
        self.phase = 'initialize'
        self.sequence = 0
        self.active = {}
        self.rows = {}
        self.slow = []
        self.proof = None

    @staticmethod
    def blank():
        return {'calls': 0, 'returned': 0, 'total_ns': 0, 'max_ns': 0, 'bytes': 0}

    def call(self, kind, method, *args, **kwargs):
        bucket = self.local.bucket
        with self.lock:
            bucket['active_operation'] = kind
            start = bucket['operation_started_ns'] = time.perf_counter_ns()
        returned, value = False, None
        try:
            value = method(*args, **kwargs)
            returned = True
            return value
        finally:
            end = time.perf_counter_ns()
            with self.lock:
                row = bucket['operations'][kind]
                elapsed = end - start
                row['calls'] += 1
                row['returned'] += int(returned)
                row['total_ns'] += elapsed
                row['max_ns'] = max(row['max_ns'], elapsed)
                if returned and kind == 'read':
                    row['bytes'] += len(value)
                elif returned and kind == 'hash':
                    row['bytes'] += len(args[0])
                bucket['active_operation'] = None
                bucket['operation_started_ns'] = None

    def run(self, method, instance, *, synchronize):
        if getattr(self.local, 'bucket', None) is not None:
            raise ValueError('NESTED_SNAPSHOT_UNEXPECTED')
        with self.lock:
            self.sequence += 1
            bucket = {'snapshot_id': self.sequence, 'thread_id': threading.get_ident(),
                'phase': self.phase, 'synchronize': synchronize,
                'started_ns': time.perf_counter_ns(), 'active_operation': None,
                'operation_started_ns': None,
                'operations': {name: self.blank() for name in CALLS.values()}}
            self.active[bucket['snapshot_id']] = bucket
            self.local.bucket = bucket
        returned = False
        try:
            value = method(instance, synchronize=synchronize)
            returned = True
            return value
        finally:
            end = time.perf_counter_ns()
            with self.lock:
                bucket.update(ended_ns=end, elapsed_ns=end-bucket['started_ns'], returned=returned)
                totals = self.rows.setdefault(bucket['phase'], {'snapshots': self.blank(),
                    'operations': {name: self.blank() for name in CALLS.values()}})
                snapshots = totals['snapshots']
                snapshots['calls'] += 1
                snapshots['returned'] += int(returned)
                snapshots['total_ns'] += bucket['elapsed_ns']
                snapshots['max_ns'] = max(snapshots['max_ns'], bucket['elapsed_ns'])
                for kind, row in bucket['operations'].items():
                    target = totals['operations'][kind]
                    for key in ('calls', 'returned', 'total_ns', 'bytes'):
                        target[key] += row[key]
                    target['max_ns'] = max(target['max_ns'], row['max_ns'])
                if bucket['elapsed_ns'] >= 50_000_000:
                    self.slow.append(copy.deepcopy(bucket))
                    self.slow.sort(key=lambda item: item['elapsed_ns'], reverse=True)
                    del self.slow[16:]
                del self.active[bucket['snapshot_id']]
                self.local.bucket = None

    def snapshot(self):
        with self.lock:
            return {'schema': 'HH-S100-SNAPSHOT-SUBPHASES-1',
                'captured_ns': time.perf_counter_ns(), 'clock': 'perf_counter_ns',
                'rows': copy.deepcopy(self.rows), 'unfinished': copy.deepcopy(list(self.active.values())),
                'largest_slow_snapshots': copy.deepcopy(self.slow), 'ast_proof': self.proof,
                'limits': 'read/hash/fsync inside original _snapshot only; open/fstat/flush/close and scheduling remain residual; append/parser/SQLite not split',
                'observer_overhead': 'two QPC reads and two recorder mutex sections per inner call, included in snapshot duration; no per-chunk ring events; no subtraction'}


def instrument_snapshot(original, metrics):
    if original.__code__.co_freevars:
        raise ValueError('SNAPSHOT_FREE_VARIABLES_UNSUPPORTED')
    source = textwrap.dedent(inspect.getsource(original))
    before = ast.parse(source)
    if len(before.body) != 1 or not isinstance(before.body[0], ast.FunctionDef) or before.body[0].decorator_list:
        raise ValueError('SNAPSHOT_SHAPE_CHANGED')
    counts = {name: 0 for name in CALLS}

    class Wrap(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            name = call_name(node.func)
            if name not in CALLS:
                return node
            counts[name] += 1
            return ast.copy_location(ast.Call(func=ast.Name(id=MARKER, ctx=ast.Load()),
                args=[ast.Constant(CALLS[name]), node.func, *node.args], keywords=node.keywords), node)

    transformed = ast.fix_missing_locations(Wrap().visit(copy.deepcopy(before)))
    if counts != {name: 1 for name in CALLS}:
        raise ValueError('SNAPSHOT_CALL_SET_CHANGED')

    class Strip(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id == MARKER:
                if len(node.args) < 2 or not isinstance(node.args[0], ast.Constant):
                    raise ValueError('SNAPSHOT_WRAPPER_INVALID')
                return ast.copy_location(ast.Call(func=node.args[1], args=node.args[2:], keywords=node.keywords), node)
            return node

    stripped = Strip().visit(copy.deepcopy(transformed))
    before_dump = ast.dump(before, include_attributes=False)
    if ast.dump(stripped, include_attributes=False) != before_dump:
        raise ValueError('SNAPSHOT_AST_NOT_IDENTICAL')
    namespace = dict(original.__globals__)
    if MARKER in namespace:
        raise ValueError('SNAPSHOT_MARKER_COLLISION')
    namespace[MARKER] = metrics.call
    exec(compile(transformed, '<s100-three-call-snapshot>', 'exec'), namespace)
    wrapped = namespace[before.body[0].name]
    metrics.proof = {'stripped_ast_identical': True, 'wrapped_calls': counts,
        'original_method_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'original_ast_sha256': hashlib.sha256(before_dump.encode()).hexdigest(),
        'transformed_ast_sha256': hashlib.sha256(ast.dump(transformed, include_attributes=False).encode()).hexdigest()}
    return wrapped

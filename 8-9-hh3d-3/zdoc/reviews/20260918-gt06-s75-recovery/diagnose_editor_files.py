"""Bounded causal probe of editor indexing evidence JSON; never a benchmark.

One native semantic cycle, then two explicit filesystem scans in a disposable
project. The second scan indexes 38 additional JSON files with the benchmark's
normal input/output naming. Census stays outside res://. Optional ignored arm
uses a predeclared .gdignore; production source/settings/counters do not change.
"""
from pathlib import Path
import argparse
import json
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_native_benchmark as n
from studio.tests.replay.benchmark_job import BenchmarkProcess, verify_capture

GDSCRIPT = r'''

var _diagnostic_scan_generation: int = 0

func _diagnostic_scan_changed(_changed: bool) -> void:
    _diagnostic_scan_generation += 1

func _diagnostic_tree_items(item: TreeItem, rows: Array[Dictionary]) -> void:
    if item == null:
        return
    rows.append({"id": item.get_instance_id(), "text": item.get_text(0),
        "metadata": str(item.get_metadata(0))})
    for child: TreeItem in item.get_children():
        _diagnostic_tree_items(child, rows)

func _diagnostic_nodes(node: Node, rows: Array[Dictionary]) -> void:
    var row: Dictionary = {"id": node.get_instance_id(), "class": node.get_class(),
        "path": str(node.get_path())}
    if node is Tree:
        var items: Array[Dictionary] = []
        _diagnostic_tree_items(node.get_root(), items)
        row["items"] = items
    if node is RichTextLabel:
        row["paragraphs"] = node.get_paragraph_count()
    if node is Window:
        row["visible"] = node.visible
        row["focused"] = node.has_focus()
    rows.append(row)
    for child: Node in node.get_children(true):
        _diagnostic_nodes(child, rows)

func _diagnostic_census(label: String) -> void:
    var total: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    var rows: Array[Dictionary] = []
    _diagnostic_nodes(get_tree().root, rows)
    var target: String = DIAGNOSTIC_DIRECTORY.path_join(label + ".json")
    if FileAccess.file_exists(target):
        _fail("DIAGNOSTIC_CENSUS_EXISTS")
        return
    var file: FileAccess = FileAccess.open(target, FileAccess.WRITE)
    if file == null:
        _fail("DIAGNOSTIC_CENSUS_OPEN")
        return
    file.store_string(JSON.stringify({"label": label, "objects": total,
        "resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
        "pid": OS.get_process_id(), "mono_us": Time.get_ticks_usec(),
        "scan_generation": _diagnostic_scan_generation, "nodes": rows}) + "\n")
    file.flush()
    file.close()

func _diagnostic_scan() -> bool:
    var filesystem: EditorFileSystem = EditorInterface.get_resource_filesystem()
    var previous: int = _diagnostic_scan_generation
    var deadline: int = Time.get_ticks_usec() + 8000000
    filesystem.scan_sources()
    while _diagnostic_scan_generation == previous or filesystem.is_scanning():
        if Time.get_ticks_usec() > deadline:
            _fail("DIAGNOSTIC_SCAN_TIMEOUT")
            return false
        await get_tree().process_frame
    var frame: int = Engine.get_process_frames()
    var settled: int = Time.get_ticks_usec() + SETTLE_US
    while Engine.get_process_frames() < frame + SETTLE_FRAMES or Time.get_ticks_usec() < settled:
        await get_tree().process_frame
    return true

func _diagnostic_files() -> void:
    var filesystem: EditorFileSystem = EditorInterface.get_resource_filesystem()
    filesystem.sources_changed.connect(_diagnostic_scan_changed)
    if not await _diagnostic_scan():
        return
    _diagnostic_census("before")
    var paths: Array[String] = []
    for index: int in range(10):
        paths.append("res://benchmark/out/ready-%02d.json" % index)
        paths.append("res://benchmark/input/start-%02d.json" % index)
    for index: int in range(9):
        paths.append("res://benchmark/input/ack-%02d.json" % index)
        paths.append("res://benchmark/out/batch-%02d.json" % (index + 1))
    for path: String in paths:
        if FileAccess.file_exists(path):
            _fail("DIAGNOSTIC_SEED_EXISTS")
            return
        var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
        if file == null:
            _fail("DIAGNOSTIC_SEED_OPEN")
            return
        file.store_string("{\"diagnostic_only\":true}\n")
        file.close()
    if not await _diagnostic_scan():
        return
    _diagnostic_census("after")
    filesystem.sources_changed.disconnect(_diagnostic_scan_changed)
    print("HH_S75_CENSUS_COMPLETE " + str(paths.size()))
    get_tree().quit(0)
'''


def run(ignored):
    factory, trusted = n.load_fixture()
    source = n.source_files()
    # Include the runtime's non-Python dependency, absent from module discovery.
    schema = 'contracts/perf-collector.schema.json'
    source[schema] = n.sha(n.read_regular(n.STUDIO / schema))
    lock = json.loads(n.read_regular(n.STUDIO / 'toolchain.lock.json'))['godot']
    executable = n.STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    run_id = 'gt06-s75-editor-files-' + ('ignored' if ignored else 'indexed') + '-03'
    root = n.STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    census = root / 'census'
    census.mkdir()
    project = root / 'project'
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
        'run_id': run_id, 'mode': 'diagnostic', 'source_closure_sha256': n.closure(source),
        'profile_sha256': n.benchmark_profile.PROFILE_SHA256,
        'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}
    n.prepare(project, factory, trusted, binding)
    (project / 'benchmark/input').mkdir()
    if ignored:
        n.write(project / 'benchmark/.gdignore', b'# Diagnostic evidence is not imported.\n')
    driver = project / 'addons/hh_benchmark/benchmark_native.gd'
    raw = driver.read_text(encoding='utf-8')
    assert raw.count('    get_tree().quit(0)') == 1
    raw = raw.replace('    get_tree().quit(0)', '    _diagnostic_files()')
    raw += '\nconst DIAGNOSTIC_DIRECTORY: String = ' + json.dumps(census.as_posix()) + '\n' + GDSCRIPT
    driver.write_text(raw, encoding='utf-8', newline='\n')
    initial = n.project_files(project)
    for name, digest in source.items():
        data = n.read_regular(n.STUDIO / name)
        assert n.sha(data) == digest
        n.write(root / 'source/studio' / name, data)
    n.write(root / 'diagnostic.json', {'full_benchmark': False, 'formal_acceptance': False,
        'run_id': run_id, 'ignored': ignored, 'synthetic_json_files': 38,
        'explicit_scan_intervention': 'scan_sources', 'outer_wall_seconds': 60,
        'source_files': source, 'initial_project_files': initial,
        'runner_sha256': n.sha(Path(__file__).read_bytes()), 'binding': binding})
    owner = None
    try:
        n.native_job.run_trusted_stage(
            [str(executable), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=root / 'import-host', source_files=source, source_root=n.STUDIO,
            binary_sha256=lock['gui_sha256'])
        n.native_job.verify_captured_stage(root / 'import-host', n.sha(n.read_regular(root / 'import-host/capture.json')))
        snapshot = n.project_files(project)
        assert all(snapshot.get(k) == v for k, v in initial.items()), 'import source drift'
        runtime = dict(source)
        runtime.update({(project / name).relative_to(n.STUDIO).as_posix(): value
            for name, value in snapshot.items() if name != n.MUTABLE_SCENE})
        n.write(root / 'runtime-source-files.json', runtime)
        owner = BenchmarkProcess([str(executable), '--editor', '--path', str(project),
            'res://scenes/fixture.tscn', '--', '--hh-benchmark-mode=diagnostic'],
            cwd=project, output=root / 'editor-host', source_root=n.STUDIO,
            source_files=runtime, binary_sha256=lock['gui_sha256'])
        deadline = time.monotonic() + 60
        while owner.tick(stop=time.monotonic() >= deadline) is None:
            time.sleep(.1)
        capture = owner.finish()
        verify_capture(root / 'editor-host', n.sha(n.read_regular(root / 'editor-host/capture.json')),
            source_root=n.STUDIO, expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
        for lane in ('import-host', 'editor-host'):
            assert not (root / lane / 'stderr.txt').read_bytes().strip(), lane + ' stderr'
            assert not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED',
                (root / lane / 'stdout.txt').read_bytes()), lane + ' log warning'
        assert b'HH_S75_CENSUS_COMPLETE 38' in (root / 'editor-host/stdout.txt').read_bytes()
        rows = [json.loads((census / (label + '.json')).read_bytes()) for label in ('before', 'after')]
        result = {'formal_acceptance': False, 'full_benchmark': False,
            'ignored': ignored, 'objects': [row['objects'] for row in rows],
            'nodes': [len(row['nodes']) for row in rows],
            'tree_items': [sum(len(node.get('items', [])) for node in row['nodes']) for row in rows],
            'actual_process_exit': capture['actual_process_exit'], 'job': capture['job']}
        n.write(root / 'result.json', result)
        print(json.dumps(result), flush=True)
    except BaseException as exc:
        n.write(root / 'failure.json', {'type': type(exc).__name__, 'detail': str(exc), 'formal_acceptance': False})
        raise
    finally:
        if owner is not None:
            owner.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ignored', action='store_true')
    run(parser.parse_args().ignored)

"""Disposable six x fifty semantic cycles with externally captured PSS points.

Supplemental, not a full benchmark. Optional frozen background cadence arm.
No host command mix, threshold waiver, existing raw mutation or focus stealing.
"""
from pathlib import Path
import argparse
import json
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from studio.tests.replay import run_native_benchmark as n
from studio.tests.replay.benchmark_job import BenchmarkProcess,verify_capture
from studio.host.replay.process_probe import ProcessProbe
from pss_handles import HandleProbe

EXTRA=r'''

func _diagnostic_point(label: String) -> void:
    var settings: EditorSettings = EditorInterface.get_editor_settings()
    var point: Dictionary = {"label": label, "pid": OS.get_process_id(),
        "mono_us": Time.get_ticks_usec(), "batch": _batch,
        "frames": Engine.get_process_frames(), "focused": get_window().has_focus(),
        "low_processor_usage_mode": OS.low_processor_usage_mode,
        "low_processor_usage_mode_sleep_usec": OS.low_processor_usage_mode_sleep_usec,
        "focused_sleep": settings.get_setting("interface/editor/timers/low_processor_mode_sleep_usec"),
        "unfocused_sleep": settings.get_setting("interface/editor/timers/unfocused_low_processor_mode_sleep_usec"),
        "update_continuously": settings.get_setting("interface/editor/display/update_continuously"),
        "objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
        "resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT))}
    var path: String = DIAGNOSTIC_DIRECTORY.path_join(label + ".json")
    var pending: String = DIAGNOSTIC_DIRECTORY.path_join(label + ".pending")
    var file: FileAccess = FileAccess.open(pending, FileAccess.WRITE)
    if file == null:
        _fail("DIAGNOSTIC_POINT_OPEN")
        return
    file.store_string(JSON.stringify(point) + "\n")
    file.flush()
    file.close()
    if DirAccess.rename_absolute(pending, path) != OK:
        _fail("DIAGNOSTIC_POINT_PUBLISH")
        return
    var deadline: int = Time.get_ticks_usec() + 20000000
    var ack: String = DIAGNOSTIC_DIRECTORY.path_join(label + ".ack")
    while not FileAccess.file_exists(ack):
        if Time.get_ticks_usec() > deadline:
            _fail("DIAGNOSTIC_POINT_ACK_TIMEOUT")
            return
        await get_tree().process_frame

func _diagnostic_pause() -> void:
    set_process(false)
    await _diagnostic_point("batch-%02d" % _batch)
    if _failed:
        return
    if _batch == _batch_limit - 1:
        await get_tree().create_timer(60.0).timeout
        await _diagnostic_point("idle")
        if _failed:
            return
    _advance_batch()
    set_process(true)
'''


def run(fast):
    factory,trusted=n.load_fixture(); source=n.source_files()
    lock=json.loads(n.read_regular(n.STUDIO/'toolchain.lock.json'))['godot']
    executable=n.STUDIO/'.local/tooling/godot-4.7.2-stable'/lock['gui_executable']
    run_id='gt06-s76-handles-'+('responsive' if fast else 'stock')+'-01'
    root=n.STUDIO/'.local/reviews'/run_id;root.mkdir(exist_ok=False)
    points=root/'points';points.mkdir(); project=root/'project'
    binding={'schema_id':'hh-studio.native-cycle-benchmark-run','schema_version':'1.2.0',
        'run_id':run_id,'mode':'diagnostic','source_closure_sha256':n.closure(source),
        'profile_sha256':n.benchmark_profile.PROFILE_SHA256,
        'batch_barrier':'diagnostic_none','batch_start':'diagnostic_immediate'}
    n.prepare(project,factory,trusted,binding)
    driver=project/'addons/hh_benchmark/benchmark_native.gd'
    script=driver.read_text(encoding='utf-8')
    assert script.count('        _batch_limit = 1\n        _cycle_limit = 1')==1
    script=script.replace('        _batch_limit = 1\n        _cycle_limit = 1',
                          '        _batch_limit = 6\n        _cycle_limit = 50')
    needle='    if _mode != "full":\n        _advance_batch()'
    assert script.count(needle)==1
    script=script.replace(needle,'    if _mode != "full":\n        _diagnostic_pause()')
    script+='\nconst DIAGNOSTIC_DIRECTORY: String = '+json.dumps(points.as_posix())+'\n'+EXTRA
    driver.write_text(script,encoding='utf-8',newline='\n')
    if fast:
        config=project/'project.godot';text=config.read_text(encoding='utf-8')
        assert text.count('run/output/max_lines=100')==1
        text=text.replace('run/output/max_lines=100','run/output/max_lines=100\n'
            'interface/editor/timers/low_processor_mode_sleep_usec=6900\n'
            'interface/editor/timers/unfocused_low_processor_mode_sleep_usec=6900\n'
            'interface/editor/display/update_continuously=false')
        config.write_text(text,encoding='utf-8',newline='\n')
    initial=n.project_files(project)
    for name,digest in source.items():
        raw=n.read_regular(n.STUDIO/name);assert n.sha(raw)==digest
        n.write(root/'source/studio'/name,raw)
    n.write(root/'diagnostic.json',{'formal_acceptance':False,'full_benchmark':False,'run_id':run_id,
        'source_files':source,'initial_project_files':initial,'native_batches':6,'cycles_each':50,
        'background_cadence_override':6900 if fast else None,'idle_seconds':60,
        'outer_wall_seconds':540,'runner_sha256':n.sha(Path(__file__).read_bytes()),
        'pss_helper_sha256':n.sha(Path(__file__).with_name('pss_handles.py').read_bytes()),'binding':binding})
    owner=None;probe=None;observed={};started=time.monotonic()
    try:
        n.native_job.run_trusted_stage([str(executable),'--headless','--editor','--path',str(project),'--import'],
            cwd=project,output=root/'import-host',source_files=source,source_root=n.STUDIO,binary_sha256=lock['gui_sha256'])
        n.native_job.verify_captured_stage(root/'import-host',n.sha(n.read_regular(root/'import-host/capture.json')))
        snapshot=n.project_files(project);assert all(snapshot.get(k)==v for k,v in initial.items())
        runtime=dict(source);runtime.update({(project/name).relative_to(n.STUDIO).as_posix():value
            for name,value in snapshot.items() if name!=n.MUTABLE_SCENE})
        n.write(root/'runtime-source-files.json',runtime)
        owner=BenchmarkProcess([str(executable),'--editor','--path',str(project),'res://scenes/fixture.tscn',
            '--','--hh-benchmark-mode=diagnostic'],cwd=project,output=root/'editor-host',source_root=n.STUDIO,
            source_files=runtime,binary_sha256=lock['gui_sha256'])
        while owner.tick(stop=time.monotonic()-started>=540) is None:
            for path in sorted(points.glob('*.json')):
                if path.stem in observed:continue
                # File may exist before writer closes: retry only incomplete JSON.
                try: point=json.loads(path.read_bytes())
                except json.JSONDecodeError:continue
                if probe is None:
                    start=json.loads((root/'editor-host/process-start.json').read_bytes())
                    assert point['pid']==start['pid']
                    with ProcessProbe(start['pid'],executable) as check:
                        assert check.sample() is not None
                        probe=HandleProbe(start['pid'],check.process_start.removeprefix('windows:'),executable)
                assert point['pid']==probe.pid
                captured=probe.snapshot();observed[path.stem]=captured
                n.write(root/'handles'/(path.stem+'.json'),captured)
                n.write(points/(path.stem+'.ack'),b'snapshot captured and freed\n')
                print(json.dumps({'run_id':run_id,'point':path.stem,'handles':captured['before_handle_count'],
                    'types':captured['type_counts'],'native':point}),flush=True)
            time.sleep(.1)
        capture=owner.finish()
        verify_capture(root/'editor-host',n.sha(n.read_regular(root/'editor-host/capture.json')),
            source_root=n.STUDIO,expected_source_files=runtime,expected_binary_sha256=lock['gui_sha256'])
        assert set(observed)=={f'batch-{i:02}' for i in range(6)}|{'idle'}
        for lane in ['import-host','editor-host']:
            assert not (root/lane/'stderr.txt').read_bytes().strip()
            assert not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED',
                (root/lane/'stdout.txt').read_bytes())
        assert n.source_files()==source
        probe.close()
        probe=None
        owner.close()
        owner=None
        n.write(root/'result.json',{'formal_acceptance':False,'completed_diagnostic':True,'full_benchmark':False,
            'actual_process_exit':capture['actual_process_exit'],'job':capture['job'],
            'source_unchanged':True,'points':{key:n.sha(n.read_regular(root/'handles'/(key+'.json'))) for key in observed}})
    except BaseException as exc:
        n.write(root/'failure.json',{'type':type(exc).__name__,'detail':str(exc),'formal_acceptance':False})
        raise
    finally:
        try:
            if probe is not None:probe.close()
        finally:
            if owner is not None:owner.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--responsive',action='store_true');run(p.parse_args().responsive)

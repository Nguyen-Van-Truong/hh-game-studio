"""New frozen native run: checked export close failures retain exact ownership."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
from run_blender_ipc_probe import load,sources


def frozen(output,binary):
    from studio.host.blender.ui_host import BlenderUIHost,HostError,cli_job
    from studio.host.blender import export_job
    rows=[];owner=None;failed=None;fault_patch=None
    def check(label,value):
        row={'label':label,'passed':value is True};rows.append(row)
        print('GT04_CLEANUP_CHECK '+json.dumps(row),flush=True)
        if value is not True:raise AssertionError(label)
    def command(key,op,state=None,payload=None):
        return {'schema':'HH-BLENDER-UI-COMMAND-1','command_id':key,'operation':op,
            'expected_revision':state['revision'] if state else None,
            'expected_context':state['context'] if state else None,'payload':payload or {}}
    try:
        owner=BlenderUIHost(output,binary=binary)
        before=owner.execute(command('initial','scene.inspect'))['result']
        state=owner.execute(command('create','mesh.create_box',before,{'object_id':'box','size':[1,2,3]}))['result']['after']
        exported=owner.export_glb(command('export','export.prepare',state,{'slot':'export'}))
        check('normal_export_verified_and_drained',exported['completed'] is True and exported['job']['closed'] is True
            and exported['job']['zero_observed'] is True and exported['wrapper_exit_code']==0)
        (output/'normal-export.json').write_text(json.dumps(exported,indent=2)+'\n',encoding='utf-8')
        failed=export_job.ExportJob(owner,owner.result('export')['result'])
        with owner._export_lock:owner._export_job=failed
        configure=export_job.configure_limits
        def configure_fault(native):
            nonlocal fault_patch
            result=configure(native)
            fault_patch=patch.object(native._native.kernel,'CloseHandle',return_value=0)
            fault_patch.start()
            return result
        with patch.object(export_job,'configure_limits',configure_fault):
            try:failed.run()
            except cli_job.JobError as error:
                check('native_close_failure_exposes_export_owner',str(error)=='CLI_JOB_CLOSE_UNCERTAIN'
                    and error.cleanup_owner is failed)
            else:raise AssertionError('injected CloseHandle failure unexpectedly returned success')
        initial=(failed.directory/'host-result.json').read_bytes()
        report=json.loads(initial)
        check('failed_run_done_but_no_success_receipt',failed.done.is_set() and failed.cleanup_held
            and report['completed'] is False and report['status']=='EXPORT_CLEANUP_HELD' and report['public_ack'] is False)
        native=failed._job;process=failed._process
        check('same_native_owner_retained_before_retry',cli_job.owner_for_process(process) is native
            and native.snapshot()['handle_retained'] is True and native.active_count()==0 and process.poll()==0)
        try:owner.close()
        except HostError as error:
            check('failed_host_retry_retains_outer_owner',str(error)=='EXPORT_CLEANUP_HELD'
                and error.cleanup_owner is owner and owner._export_job is failed and not owner._closed)
        else:raise AssertionError('second injected close failure unexpectedly completed host close')
        check('gui_drained_while_export_close_held',owner._job.closed and owner._job.zero_observed
            and owner._process.poll()==0 and all(not thread.is_alive() for thread in owner.threads))
        check('same_export_handle_remains_owned_after_host_close',cli_job.owner_for_process(process) is native
            and native.snapshot()['handle_retained'] is True and native.active_count()==0)
        fault_patch.stop();fault_patch=None
        cleanup=owner.close()
        check('retry_closes_exact_export_owner',cleanup['export_cleanup']['job']['closed'] is True
            and cleanup['export_cleanup']['job']['zero_observed'] is True
            and cleanup['export_cleanup']['job']['active_count']==0 and failed._job is native
            and not failed.cleanup_held and cli_job.owner_for_process(process) is None)
        check('gui_and_wrapper_actual_exit_zero',cleanup['actual_process_exit']=={'pid':owner.pid,'exit_code':0}
            and cleanup['wrapper_exit_code']==0 and cleanup['job']['active_count']==0)
        check('initial_unknown_report_preserved',(failed.directory/'host-result.json').read_bytes()==initial)
        attempts=[json.loads(path.read_bytes()) for path in sorted(failed.directory.glob('cleanup-attempt-*.json'))]
        check('append_only_failure_failure_success_evidence',[row['cleanup_held'] for row in attempts]==[True,True,False]
            and [row['attempt'] for row in attempts]==[1,2,3] and all(row['public_ack'] is False for row in attempts))
        check('repeated_close_no_new_attempt',owner.close()==cleanup
            and len(list(failed.directory.glob('cleanup-attempt-*.json')))==3)
        check('no_retained_native_hold',not cli_job.HOLDS and not cli_job._LIVE)
        result={'passed':True,'checks':rows,'public_ack':False,'candidate_only':True,
            'failed_directory':failed.directory.relative_to(output).as_posix(),
            'original_failed_report_sha256':hashlib.sha256(initial).hexdigest(),
            'fault':'checked CloseHandle failure injected before actual native close; two calls',
            'cleanup':cleanup,'source_files':sources(STUDIO)}
        (output/'native.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('GT04_CLEANUP_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    finally:
        if fault_patch is not None:fault_patch.stop()
        if owner is not None:owner.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frozen',action='store_true');parser.add_argument('--binary',type=Path)
    args=parser.parse_args();out=args.output.absolute()
    if args.frozen:return frozen(out,args.binary)
    runner=load(STUDIO/'build/bootstrap/run_fixture.py');runner._reject_reparse_ancestors(out)
    out.mkdir(exist_ok=False);original=sources(STUDIO);snapshot=out/'source/studio'
    for name in original:
        dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STUDIO/name,dest)
    if sources(snapshot)!=original:raise ValueError('source snapshot differs')
    closure=runner.source_closure_sha256(original)
    (out/'source-closure.json').write_text(json.dumps({'files':original,'source_closure_sha256':closure},indent=2)+'\n',encoding='utf-8')
    owned=load(snapshot/'build/bootstrap/run_fixture.py')
    unit=owned.run_process([sys.executable,'-B','-m','unittest','discover','-s','tests/blender','-p','test_*.py','-v'],
        cwd=snapshot,output=out,timeout=30,label='unit')
    host=owned.run_process([sys.executable,'-B',str(snapshot/'tests/blender/run_export_cleanup_probe.py'),
        '--frozen','--output',str(out),'--binary',str(STUDIO/'.local/tooling/blender-5.2.1-windows-x64/blender.exe')],
        cwd=snapshot,output=out,timeout=60,label='native')
    value={'source_closure_sha256':closure,'unit':unit,'host':host,'candidate_only':True,'public_ack':False,
        'source_unchanged':sources(STUDIO)==original,'snapshot_unchanged':sources(snapshot)==original}
    (out/'capture.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value))
    return int(unit['exit_code']!=0 or host['exit_code']!=0)


if __name__=='__main__':raise SystemExit(main())

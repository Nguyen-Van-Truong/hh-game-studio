"""S50 exact-owner host death, idle child, and independent process admission proof."""
from pathlib import Path
import datetime
import json
import subprocess
import sys
import threading
import time
import os
import hashlib
import importlib.util
SOURCE = Path(os.environ['HH_S50_FROZEN_STUDIO']).resolve()
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location('s50_final_executor', SOURCE / 'godot-addon/linux_executor.py')
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)



def project(root, idle):
    root.mkdir(); (root/'scripts').mkdir(); (root/'scenes').mkdir()
    (root/'project.godot').write_bytes(executor.PROJECT_TEMPLATE.encode())
    (root/'scenes/fixture.tscn').write_text('[gd_scene format=3]\n[node name="Fixture" type="Node3D"]\n')
    code='extends Node3D\n'
    if idle:
        code+='static func _static_init() -> void:\n\tOS.delay_msec(3000)\n\tprint("S50_IDLE_BODY_AFTER_HOST_DEATH")\n\twhile true:\n\t\tOS.delay_msec(100)\n'
    (root/'scripts/fixture_actor.gd').write_text(code)


def main(root):
    root.mkdir()
    idle=root/'idle'; valid=root/'valid'; project(idle,True); project(valid,False)
    owned=executor._owned_runner(); process=None; job=None
    evidence={'public_ack':False,'sandbox_acceptance':False, 'source_executor_sha256':hashlib.sha256((SOURCE/'godot-addon/linux_executor.py').read_bytes()).hexdigest(), 'source_cli_job_sha256':hashlib.sha256((SOURCE/'godot-addon/cli_job.py').read_bytes()).hexdigest()}
    observer=[]; thread=None
    def call(args,label,timeout=5):
        return executor._cli(owned,args,root,label,timeout=timeout,cap=32768)
    def inspect(cid,label):
        row,raw=call(['inspect',cid],label)
        executor._need(executor._cli_clean(row),'PROBE_INSPECT')
        return json.loads(raw)[0]
    def launch(prj,out,label):
        stdout=(root/(label+'-stdout.txt')).open('wb'); stderr=(root/(label+'-stderr.txt')).open('wb')
        argv=[sys.executable,'-B',str(Path(__file__).resolve()),'worker',str(prj),str(out)]
        proc=subprocess.Popen([sys.executable,'-B','-c',executor._HELPER,*argv],stdin=subprocess.PIPE,
                              stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        handle=executor._cli_jobs().create(proc)
        proc.stdin.write(b'GO\n');proc.stdin.close()
        return proc,handle,stdout,stderr
    cid=None; name=None
    try:
        if executor._read_owner(executor._owner_path()):
            evidence['preexisting_recovery']=executor.run(valid,mode='parse',output=root/'preexisting-recovery',timeout_seconds=8)
            executor._need(evidence['preexisting_recovery']['diagnostic_process_clean'],'PROBE_PREEXISTING_RECOVERY')
        process,job,hostout,hosterr=launch(idle,root/'host-run','host')
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            path=executor._owner_path()
            owner=executor._read_owner(path)
            if owner and owner['phase']=='start_pending' and owner['container_id']:
                cid=owner['container_id'];name=owner['name'];break
            executor._need(process.poll() is None,'PROBE_HOST_DIED_EARLY')
            time.sleep(.05)
        executor._need(cid,'PROBE_START_NOT_OBSERVED')
        for attempt in range(5):
            value=inspect(cid,'running-inspect-'+str(attempt))
            if value['State']['Running']:break
            time.sleep(.1)
        executor._need(executor._owned_identity(value,name,cid) and value['State']['Running'],'PROBE_NOT_RUNNING')
        evidence['initial_state']=value['State'];evidence['owner_before_death']=owner
        # Passive independent observer: no second engine or executor request.
        def observe():
            observer.append(call(['attach','--no-stdin','--sig-proxy=false',cid],'orphan-attach',timeout=12))
        thread=threading.Thread(target=observe);thread.start()
        second,second_job,secondout,seconderr=launch(valid,root/'concurrent-run','concurrent')
        try:
            second.wait(timeout=5)
            evidence['concurrent_result']=json.loads((root/'concurrent-run/result.json').read_text())
            executor._need('EXECUTOR_ADMISSION_BUSY' in evidence['concurrent_result']['errors'],'PROBE_CONCURRENT_ADMITTED')
        finally:
            if second.poll() is None:second_job.terminate();second.wait(timeout=3)
            second_job.close();secondout.close();seconderr.close()
        evidence['host_killed_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        job.terminate();process.wait(timeout=3)
        settle=time.monotonic()+1
        while job.active_count() and time.monotonic()<settle:time.sleep(.02)
        evidence['host_job_active_count']=job.active_count()
        evidence['host_actual_exit']=process.returncode
        job.close();evidence['host_job_owner']=job.snapshot();job=None;hostout.close();hosterr.close()
        after_death=inspect(cid,'after-host-death-inspect')
        evidence['after_host_death_state']=after_death['State']
        executor._need(executor._owned_identity(after_death,name,cid) and after_death['State']['Running'] and after_death['State']['Pid']>0,'PROBE_ORPHAN_NOT_OBSERVED_RUNNING')
        thread.join(timeout=15)
        executor._need(not thread.is_alive() and observer,'PROBE_OBSERVER_INCOMPLETE')
        evidence['observer_host']=observer[0][0]
        evidence['child_body_observed']=b'S50_IDLE_BODY_AFTER_HOST_DEATH' in observer[0][1]
        value=inspect(cid,'orphan-exited-inspect');evidence['orphan_state']=value['State']
        executor._need(executor._owned_identity(value,name,cid) and not value['State']['Running']
                       and value['State']['Pid']==0,'PROBE_ORPHAN_NOT_STOPPED')
        def stamp(x):return datetime.datetime.fromisoformat(x.replace('Z','+00:00'))
        evidence['container_lifetime_seconds']=(stamp(value['State']['FinishedAt'])-stamp(value['State']['StartedAt'])).total_seconds()
        executor._need(evidence['child_body_observed'] and evidence['container_lifetime_seconds']<=10,
                       'PROBE_DEADLINE_UNPROVEN')
        evidence['recovery_result']=executor.run(valid,mode='parse',output=root/'recovery-run',timeout_seconds=8)
        executor._need(evidence['recovery_result']['diagnostic_process_clean']
                       and evidence['recovery_result']['admission']['recovery']['removed']
                       and evidence['recovery_result']['owned_removed'],'PROBE_RECOVERY_FAILED')
        evidence['observed']=True
    finally:
        if job:
            job.terminate();process.wait(timeout=3);job.close()
        # Recovery failure retains durable ownership; do not replace it or broadly clean.
        executor._write(root/'probe-result.json',evidence)
    print(json.dumps({'observed':evidence.get('observed',False),'container_lifetime_seconds':evidence.get('container_lifetime_seconds'),
                      'child_body_observed':evidence.get('child_body_observed'),'host_job_active_count':evidence.get('host_job_active_count')}))


if __name__=='__main__':
    if sys.argv[1]=='worker':
        result=executor.run(Path(sys.argv[2]),mode='parse',output=Path(sys.argv[3]),timeout_seconds=8)
        print(json.dumps(result))
    else:main(Path(sys.argv[1]))

"""FIFO03 frozen evidence. Default operation is read-only and starts no engine."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode=True

AUDIT=Path(__file__).resolve().parent;ROOT=AUDIT.parents[2]
PACKAGE=AUDIT.parent/'20260917-gt04-fifo-03';FILES={}
EXPECTED_CLOSURE='7eab49db44887486919d4d827a36f597260ca99e02797c293827a03fb37e58d1'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def need(value,label):
    if not value:raise ValueError(label)

def verify(overrides=None,*,check_live=False):
    overrides=overrides or {};FILES.clear()
    def raw(path):
        name=path.relative_to(ROOT).as_posix();data=overrides.get(name,path.read_bytes())
        FILES[name]=digest(data);return data
    def read(path):return json.loads(raw(path))
    source=read(PACKAGE/'source-closure.json');files=source['files'];snapshot=PACKAGE/'source/studio'
    closure=digest(''.join('8-9-hh3d-3/studio/'+name+'\0'+value+'\n' for name,value in sorted(files.items())).encode())
    need(closure==source['source_closure_sha256']==EXPECTED_CLOSURE,'closure digest')
    need({path.relative_to(snapshot).as_posix():digest(raw(path)) for path in snapshot.rglob('*')
        if path.is_file() and '__pycache__' not in path.parts}==files,'frozen inventory')
    if check_live:
        for name,value in files.items():need(digest((ROOT/'studio'/name).read_bytes())==value,'live source '+name)
    runtime={name:value for name,value in files.items() if (name.endswith('.py') and
        name.startswith(('blender-addon/','host/core/','protocol/','host/blender/'))) or
        name in ('blender-addon/exporter.lock.json','godot-addon/cli_job.py','toolchain.lock.json')}
    capture=read(PACKAGE/'capture.json');native=read(PACKAGE/'native.json')
    need(capture['source_closure_sha256']==closure and capture['source_unchanged'] is True
        and capture['snapshot_unchanged'] is True and capture['public_ack'] is False
        and capture['candidate_only'] is True and native['source_files']==files,'source map binding')
    for name,record in (('unit',capture['unit']),('native',capture['host'])):
        actual=read(PACKAGE/record['host'])
        need(record['exit_code']==0 and record['wrapper_exit_code']==0 and actual['exit_code']==0
            and actual['target_pid']==record['target_pid'] and record['timed_out'] is False
            and record['tree_verified'] is True,'captured process exit '+name)
        raw(PACKAGE/record['stdout']);raw(PACKAGE/record['stderr'])
    tests=raw(PACKAGE/'unit-stderr.txt').decode().replace('\r\n','\n')
    need(re.findall(r'Ran (\d+) tests in ',tests)==['119'] and tests.rstrip().endswith('OK')
        and len(re.findall(r'^test\w+ \([^\n]+\) \.\.\. ok$',tests,re.M))==119,'raw 119 tests')
    stdout=raw(PACKAGE/'native-stdout.txt').decode();need(not raw(PACKAGE/'native-stderr.txt'),'native stderr')
    checks=[json.loads(line[len('GT04_FIFO_CHECK '):]) for line in stdout.splitlines() if line.startswith('GT04_FIFO_CHECK ')]
    need(checks==native['checks'] and len(checks)==19 and len({row['label'] for row in checks})==19
        and all(row['passed'] is True for row in checks),'native 19 checks')
    complete=[json.loads(line[len('GT04_FIFO_COMPLETE '):]) for line in stdout.splitlines() if line.startswith('GT04_FIFO_COMPLETE ')]
    need(complete==[{'passed':True,'checks':19}] and native['passed'] is True and native['public_ack'] is False
        and native['candidate_only'] is True and native['clients_are_synthetic_stdio_fixture'] is True,'native completion')
    roots=list(PACKAGE.glob('blender-*'));need(len(roots)==1,'one GUI owner');root=roots[0]
    launch=read(root/'launch.json');start=read(root/'process-start.json');end=read(root/'process-exit.json');closed=read(root/'close.json')
    need(launch['source_files']==runtime and end=={'pid':start['pid'],'exit_code':0}
        and closed==native['cleanup'] and closed['actual_process_exit']==end and closed['wrapper_exit_code']==0
        and closed['closed'] is True and closed['held'] is False and closed['logs_overflow'] is False,'GUI binding')
    job=closed['job'];need(job['closed'] is True and job['zero_observed'] is True and job['active_count']==0
        and job['handle_retained'] is False and job['tainted'] is False and job['close_uncertain'] is False
        and not job['failed_operations'],'checked native Job')
    for name in ('control-hello.json','data-hello.json','stdout.txt','stderr.txt'):raw(root/name)

    sys.path.insert(0,str(snapshot.parent))
    from studio.host.blender.durable_session import response_bytes,queue
    from studio.host.blender.writer_journal import PROJECT,REQUESTS,GRANTS,META
    from studio.host.core.journal import Journal
    from studio.host.core.limits import DEFAULT_LIMITS
    from studio.protocol.core import canonical_bytes
    # Decode and validate in memory; constructing Journal would acquire a disk lock.
    journal=object.__new__(Journal);journal.profile=DEFAULT_LIMITS
    journal._records=[];journal._commands={};journal._pending=set();journal._leases={}
    for line in raw(root/'journal/blender-journal.jsonl').splitlines(keepends=True):
        row=journal._decode_record(line);journal._apply_loaded(row,len(journal._records));journal._records.append(row)
    rows=journal._records
    def command(project,key):return journal._command((project,key))
    def originals(project,key):
        return [(i,row) for i,row in enumerate(rows) if row['kind']=='command'
            and row['project_id']==project and row['command_id']==key and row['status']=='ACCEPTED_PENDING']
    need(not journal._pending,'no unresolved native/ticket/grant records')
    generation=command(META,'session-binding')['receipt']['generation']
    need(command(META,'writer-fifo')['receipt']=={'schema':1,'public_ack':False}
        and command(META,'writer-stop')['receipt']=={'stopped':True,'public_ack':False},'durable FIFO and Stop markers')
    need(command(REQUESTS,'cancel-first')['receipt']['state']=='CANCELED'
        and command(REQUESTS,'cancel-first')['receipt']['reason']=='CLIENT_CANCELLED'
        and command(REQUESTS,'expire-first')['receipt']['state']=='EXPIRED'
        and command(REQUESTS,'expire-first')['receipt']['reason']=='QUEUE_DEADLINE'
        and command(GRANTS,'cancel-first') is None and command(GRANTS,'expire-first') is None,'head cancel/expiry no grant')
    need(command(REQUESTS,'overflow') is None and command(PROJECT,'late-alice') is None,'overflow/stale rejected before intent')
    stop_index=journal._commands[(META,'writer-stop')]
    need(all(row['kind']=='command' and row['project_id']==REQUESTS and row['status']=='CANCELED'
        and row['receipt']['reason']=='HOST_STOPPED' for row in rows[stop_index+1:]),'Stop prevents subsequent lease/effect admission')
    flood=[command(REQUESTS,'flood-'+str(i)) for i in range(8)]
    need(all(row is not None and row['status']=='CANCELED' and row['receipt']['state']=='CANCELED'
        and row['receipt']['reason']=='HOST_STOPPED' for row in flood)
        and all(originals(REQUESTS,'flood-'+str(i))[0][0]<stop_index for i in range(8))
        and 0<=native['stop_elapsed_ms']<2000,'eight bounded waiters canceled by priority Stop')
    grants=native['grants'];need(len(grants)==2 and len(native['responses'])==2,'two grant receipts')
    leases=[row for row in rows if row['kind']=='lease']
    need([row['owner'] for row in leases]==['initial','alice','bob']
        and [row['fencing_epoch'] for row in leases]==[1,2,3],'strict native epochs')
    pids=native['client_pids'];need(len(pids)==2 and len(set(pids))==2 and all(type(pid) is int and pid>0 for pid in pids)
        and native['client_exit_codes']==[0,0],'two distinct actual clients')
    events=native['client_events']
    need([(item['client_pid'],item['message']['op']) for item in events]==[
        (pids[0],'enqueue'),(pids[0],'wait'),(pids[1],'enqueue'),(pids[1],'wait'),
        (pids[0],'execute'),(pids[0],'done'),(pids[1],'execute'),(pids[1],'done')],'two waiting clients before grant/edit')
    ticket_order=[]
    for index,writer in enumerate(('alice','bob')):
        ticket='ticket-'+writer;grant=grants[index];lease=grant['lease'];response=native['responses'][index]
        original=originals(REQUESTS,ticket);need(len(original)==1,'one durable ticket admission');ticket_order.append(original[0][0])
        request=command(REQUESTS,ticket);marker=command(GRANTS,ticket)
        need(request['status']=='COMMITTED' and request['receipt']==grant and grant['state']=='GRANTED'
            and grant['writer']==writer and grant['generation']==generation and grant['public_ack'] is False
            and grant['lease_ms']==10000 and grant['wait_ms']==30000
            and original[0][1]['receipt']['queue_expires_ms']==grant['queue_expires_ms'],'exact durable ticket receipt')
        need(marker['status']=='COMMITTED' and marker['receipt']=={'ticket_id':ticket,'generation':generation,
            'lease':lease,'public_ack':False} and lease=={k:v for k,v in leases[index+1].items() if k!='kind'}
            and marker['created_ms']>=leases[index]['expires_ms']
            and lease['expires_ms']-marker['created_ms']==10000
            and lease['expires_ms']<=grant['queue_expires_ms'],'fenced handoff after observed expiry')
        actual=read(PACKAGE/('client-%d-exit.json'%index));client=read(PACKAGE/('client-'+writer+'.json'))
        need(actual=={'pid':pids[index],'exit_code':0} and client['pid']==pids[index] and client['exit_code']==0
            and client['ticket']==grant and client['response']==response
            and not raw(PACKAGE/('client-%d-stderr.txt'%index)),'client captured exit/receipt')
        stream=[item['message'] for item in events if item['client_pid']==pids[index]]
        need(all(item['ticket_id']==ticket and item['writer']==writer for item in stream)
            and stream[0]['pid']==pids[index] and stream[-1]==client['done'] and stream[-1]['pid']==pids[index],
            'client PID/ticket event binding')
        cmd=stream[2]['command'];terminal=command(PROJECT,'create-'+writer)
        need(terminal['status']=='COMMITTED' and terminal['digest']==queue.c.digest(cmd)
            and response_bytes(terminal['receipt'])==canonical_bytes(response)
            and response['status']=='COMMITTED' and response['native']['state']=='COMPLETED'
            and response['native']['command_digest']==terminal['digest'],'durable native edit receipt bytes')
    need(ticket_order==sorted(ticket_order) and ticket_order[1]<originals(GRANTS,'ticket-alice')[0][0],
        'persisted FIFO order and two pending clients')
    after=native['responses'][-1]['native']['result']['after']
    need([row['object_id'] for row in after['snapshot']['objects']]==['alice','bob']
        and json.loads(response_bytes(command(PROJECT,'before-stop')['receipt']))['native']['result']==after,
        'two native objects unchanged after stale write')
    for name in ('README.md','verify_evidence.py','test_evidence.py'):raw(AUDIT/name)
    return {'passed':True,'source_closure_sha256':closure,'source_files':len(files),'python_tests':119,
        'native_checks':19,'actual_client_processes':2,'journal_records':len(rows),
        'portable_artifacts':len(FILES),'public_ack':False,'formal_acceptance':False,'current_source_checked':check_live}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-derived',action='store_true')
    parser.add_argument('--check-live',action='store_true');args=parser.parse_args();result=verify(check_live=args.check_live)
    if args.write_derived:
        (AUDIT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        (AUDIT/'portable-artifacts.json').write_text(json.dumps({'files':dict(sorted(FILES.items()))},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

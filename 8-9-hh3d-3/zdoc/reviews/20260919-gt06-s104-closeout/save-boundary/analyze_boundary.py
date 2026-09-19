import json,hashlib,sys
from pathlib import Path

def read_run(root):
 root=Path(root); stdout=(root/'editor-host/stdout.txt').read_bytes(); native=(Path('studio/tests/replay/benchmark_native.gd')).read_bytes()
 native_sha=hashlib.sha256(native).hexdigest(); lines=stdout.decode().splitlines(); ev=[]; enters={}; completes={}
 for n,line in enumerate(lines,1):
  if line.startswith('HH_GT06_S103_SAVE_ENTER '):
   x=json.loads(line.split(' ',1)[1]); enters[(x['batch'],x['cycle'])]=(x,n)
  elif line.startswith('HH_GT06_S103_SAVE_COMPLETE '):
   x=json.loads(line.split(' ',1)[1]); completes[(x['batch'],x['cycle'])]=(x,n)
 allkeys=sorted(set(enters)|set(completes)); rows=[]
 for key in allkeys:
  c=completes.get(key); e=enters.get(key); r={'batch':key[0],'cycle':key[1],'enter':bool(e),'complete':bool(c)}
  if c:
   x=c[0]; r['probe_source_sha256_matches']=x['probe_source_sha256']==native_sha
   r['binding_ok']=all(x.get(k)==(e[0].get(k) if e else x.get(k)) for k in ('run_id','pid','batch','cycle','sequence','source_closure_sha256','profile_sha256','save_start_us','process_entry_us','process_entry_frame','entry_event_us'))
   r['observation_complete']=x['observation_complete'] and not x['failed'] and x['save_result']==0
   fields=['call_entry_us','call_return_us','signal_us','save_process_exit_us','next_process_entry_us','next_process_exit_us','readback_end_us','signal_frame','save_process_exit_frame','next_process_entry_frame','next_process_exit_frame']
   r['boundaries_present']=all(isinstance(x.get(f),int) and x[f]>0 for f in fields)
   if r['boundaries_present']:
    r['call_us']=x['call_return_us']-x['call_entry_us']; r['after_call_us']=x['save_process_exit_us']-x['call_return_us']; r['next_frame_gap_us']=x['next_process_entry_us']-x['save_process_exit_us']; r['call_to_next_frame_us']=x['next_process_entry_us']-x['call_entry_us']; r['save_to_readback_us']=x['readback_end_us']-x['save_start_us']; r['frame_order_actual']=[x['process_entry_frame'],x['save_process_exit_frame'],x['next_process_entry_frame'],x['next_process_exit_frame']]
  rows.append(r)
 valid=[r for r in rows if r.get('complete') and r.get('probe_source_sha256_matches') and r.get('binding_ok') and r.get('observation_complete') and r.get('boundaries_present')]
 def mx(k):
  return max((r[k] for r in valid),default=None)
 return {'run_id':(valid[0]['run_id'] if valid and 'run_id' in valid[0] else (next(iter(completes.values()))[0]['run_id'] if completes else None)),'root':str(root),'native_source_sha256':native_sha,'marker_enter_count':len(enters),'marker_complete_count':len(completes),'valid_complete_boundary_count':len(valid),'reader_compatible_count':0,'max_call_us':mx('call_us'),'max_after_call_us':mx('after_call_us'),'max_next_frame_gap_us':mx('next_frame_gap_us'),'max_call_to_next_frame_us':mx('call_to_next_frame_us'),'max_save_to_readback_us':mx('save_to_readback_us'),'sample_rows':valid[:2],'frame_order_note':'Observed frames are process-entry < save-process-exit < next-process-entry < next-process-exit; existing reader incorrectly requires process_entry_frame == save_process_exit_frame.'}
for p in sys.argv[1:]: print(json.dumps(read_run(p),sort_keys=True))

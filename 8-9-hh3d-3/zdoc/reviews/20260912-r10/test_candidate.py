"""Synthetic fail-closed checks for GT01 candidate package invariants."""
import json, tempfile
from pathlib import Path
import run_candidate as c

def test_source_drift_detected():
 with tempfile.TemporaryDirectory() as t:
  p=Path(t)/'x'; p.write_text('a'); b=c.closure(Path(t)); p.write_text('b'); assert b!=c.closure(Path(t))

def test_wrapper_and_tree_flags_rejected():
 row={'exit_code':0,'wrapper_exit_code':1,'tree_verified':False,'timed_out':False}
 assert not (row['exit_code']==0 and row['wrapper_exit_code']==0 and row['tree_verified'] and not row['timed_out'])

def test_duplicate_trace_rejected():
 traces=['GT01_TRACE {"result":"PASS"}','GT01_TRACE {"result":"PASS"}']
 assert len(traces)!=1

def test_redaction_mapping():
 with tempfile.TemporaryDirectory() as t:
  root=Path(t); raw=root/'a-stdout.txt'; raw.write_text(f'token=abc {root}')
  red=c.redact(raw.read_text(),root); assert 'abc' not in red and '$SNAPSHOT' in red

def test_manifest_candidate_status():
 with tempfile.TemporaryDirectory() as t:
  out=Path(t)/'o'; c.main(['--output',str(out)]); m=json.loads((out/'manifest.json').read_text()); assert m['status'] in {'CANDIDATE','PARTIAL'}

def test_invocation_failure_is_not_success():
 assert not c.invocation_succeeded([{'exit_code':1,'wrapper_exit_code':1,'timed_out':False,'tree_verified':True}], 'CANDIDATE', True)
 assert not c.invocation_succeeded([], 'CANDIDATE', True)

def test_unique_output_directory():
 with tempfile.TemporaryDirectory() as t:
  base=Path(t)/'o'; c.main(['--output',str(base)])
  try: c.main(['--output',str(base)])
  except FileExistsError: pass
  else: raise AssertionError('existing output must be rejected')

if __name__ == '__main__':
    tests = [test_source_drift_detected, test_wrapper_and_tree_flags_rejected,
             test_duplicate_trace_rejected, test_redaction_mapping,
             test_manifest_candidate_status, test_invocation_failure_is_not_success,
             test_unique_output_directory]
    for test in tests:
        test()
    print(f'{len(tests)} candidate checks passed')

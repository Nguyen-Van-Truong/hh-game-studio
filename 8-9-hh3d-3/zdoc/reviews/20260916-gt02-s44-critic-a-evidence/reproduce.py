"""Independent critic diagnostic; fixture directories are disposable and owned."""
import hashlib
import json
from pathlib import Path
import sys

PRODUCT = Path(__file__).resolve().parents[3]
STUDIO = PRODUCT / 'studio'
sys.path.insert(0, str(STUDIO / 'tests/protocol'))
from test_file_consumer import FileConsumerTests
from host.core.fixture_selector import SelectorError


def run():
    case = FileConsumerTests('test_load_committed_confirms_file_without_new_effect_or_receipt')
    try:
        case.setUp()
        case.activate(case.request())
        original_version, original_bytes = case.files.read('active.json')
        case.reopen()
        case.selector.load_committed(now_ms=201)
        initial = case.selector.snapshot()
        initial_head = case.log.binding().witnessed
        initial_blobs = len(list(case.store.root.iterdir()))
        request = case.request('cmd-after-reopen', 'new-value')
        admission = case.selector.prepare(request, now_ms=202)
        case.selector.stage('cmd-after-reopen', now_ms=203)
        case.selector.select('cmd-after-reopen', now_ms=204)
        try:
            case.selector.adopt('cmd-after-reopen', now_ms=205)
        except SelectorError as exc:
            error = {'code':exc.code,'outcome_unknown':exc.outcome_unknown,
                     'cause':getattr(exc.__cause__, 'code', None)}
        else:
            raise AssertionError('readonly update unexpectedly committed')
        after = case.selector.snapshot()
        receipt = case.selector.lookup('cmd-after-reopen')
        result = {
            'case':'new-command-after-readonly-reopen',
            'readonly':case.files._readonly,
            'admission':admission,
            'error':error,
            'prior_generation':initial['generation'],
            'after_generation':after['generation'],
            'prior_ready':initial['ready'],
            'after_ready':after['ready'],
            'journal_events_added':case.log.binding().witnessed.sequence-initial_head.sequence,
            'blobs_added':len(list(case.store.root.iterdir()))-initial_blobs,
            'pending_command':after['pending_command'],
            'lookup':receipt,
            'file_unchanged':case.files.read('active.json')==(original_version,original_bytes),
        }
        assert result['admission']['status']=='ACCEPTED_PENDING'
        assert result['journal_events_added']==4 and result['blobs_added']==2
        assert result['after_generation']==result['prior_generation']+1
        assert result['prior_ready'] and not result['after_ready']
        assert result['error']['cause']=='SAFE_REOPEN_REQUIRES_RECONCILIATION'
        assert result['lookup']['status']=='UNKNOWN' and result['file_unchanged']
        result['defect_reproduced']=True
        print('HH_CRITIC_A_REPRO '+json.dumps(result,sort_keys=True),flush=True)
    finally:
        case.doCleanups()


if __name__=='__main__':
    run()

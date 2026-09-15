"""Independent frozen review B: real journal lock/read failures after one confirmed mock effect."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
manifest = json.loads((ROOT/'zdoc/reviews/20260915-gt02-s30-01/source-closure.json').read_text())
source = {name:(ROOT/'studio'/name).read_bytes() for name in manifest['files']}
hashes = {name:hashlib.sha256(data).hexdigest() for name,data in source.items()}
assert all((ROOT/'studio'/name).read_bytes()==data for name,data in source.items())

with tempfile.TemporaryDirectory(prefix='gt02-s30-lock-audit-b-') as temporary:
    snapshot = Path(temporary)
    for name,data in source.items():
        path = snapshot/'studio'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
    sys.path.insert(0,str(snapshot))
    from studio.build.bootstrap.run_fixture import source_closure_sha256
    from studio.host.core.journal import Journal, JournalLimits
    from studio.host.core.transport import FixtureClient, LoopbackFixtureHost
    from studio.protocol.core import Status

    @contextmanager
    def failure(journal, code):
        original = journal.limits
        guard = journal.path.with_name(journal.path.name+'.guard')
        alias = guard.with_name('guard-alias')
        saved = guard.with_name('guard-saved')
        marker = journal.path.with_name(journal.path.name+'.lock')
        if code == 'JOURNAL_LOCKED':
            journal.limits = replace(original,lock_timeout_ms=25)
            try:
                with journal._writer_lock():
                    yield
            finally:
                journal.limits = original
        elif code == 'JOURNAL_LOCK_FAILED':
            guard.rename(saved)
            guard.mkdir()
            try:
                yield
            finally:
                guard.rmdir()
                saved.rename(guard)
        elif code == 'JOURNAL_LOCK_UNSAFE':
            os.link(guard,alias)
            try:
                yield
            finally:
                alias.unlink()
        elif code == 'JOURNAL_LEGACY_LOCK_RECOVERY_REQUIRED':
            marker.write_bytes(b'{}')
            try:
                yield
            finally:
                marker.unlink()
        elif code in {'JOURNAL_FULL','JOURNAL_RECORD_LIMIT'}:
            journal.limits = (replace(original,max_bytes=journal.path.stat().st_size-1)
                              if code == 'JOURNAL_FULL' else replace(original,max_records=1))
            try:
                yield
            finally:
                journal.limits = original
        else:
            raise AssertionError(code)

    rows=[]
    for code in ('JOURNAL_LOCKED','JOURNAL_LOCK_FAILED','JOURNAL_LOCK_UNSAFE',
                 'JOURNAL_LEGACY_LOCK_RECOVERY_REQUIRED','JOURNAL_FULL','JOURNAL_RECORD_LIMIT'):
        with tempfile.TemporaryDirectory(prefix='gt02-s30-lock-fixture-b-') as fixture_dir:
            root=Path(fixture_dir)
            journal=Journal(root/'journal.jsonl')
            with LoopbackFixtureHost('audit.fixture',root,journal) as host:
                credential=host.sessions.issue(scopes=frozenset({'fixture.read','fixture.write','control.cancel'}))
                client=FixtureClient(host.port,host.control_port,credential)
                request=client.request('audit.already-applied',value=73,lease=client.lease())
                pending=client.submit(request)
                assert pending.status is Status.ACCEPTED_PENDING
                end=time.monotonic()+2
                while time.monotonic()<end:
                    committed=client.lookup(request.command_id)
                    if committed.status is Status.COMMITTED:
                        break
                    time.sleep(.005)
                assert committed.status is Status.COMMITTED
                with failure(journal,code):
                    observed={
                        'lookup':client.lookup(request.command_id),
                        'same_id_retry':client.submit(request),
                        'cancel':client.cancel(request.command_id),
                        'archive':client.lookup_archive(request.command_id),
                    }
                    result={name:{'status':item.status.value,'code':item.code,'postconditions':item.postconditions}
                            for name,item in observed.items()}
                    assert all(item.code==code for item in observed.values()),result
                    assert all(item.status is Status.UNKNOWN for item in observed.values()),result
                    assert all(item.postconditions.get('next_action')=='lookup.reconcile' and item.postconditions.get('accepting_work') is False and 'no_effect' not in item.postconditions for item in observed.values()),result
                    assert host.fixture.effect_count==1
                recovered=client.lookup(request.command_id)
                assert recovered==committed and host.fixture.effect_count==1
                assert host._stopped.is_set()
                assert client.submit(client.request('new.after.unknown',value=74)).code=='HOST_STOPPED'
                rows.append({'failure':code,'before':committed.status.value,'during':result,
                             'after':recovered.status.value,'effect_count':host.fixture.effect_count})
    report={'proof_class':'INDEPENDENT_FROZEN_REVIEW_REAL_LOOPBACK_AND_JOURNAL',
        'snapshot_closure_sha256':source_closure_sha256(hashes),
        'transport_sha256':hashes['host/core/transport.py'],'journal_sha256':hashes['host/core/journal.py'],
        'rows':rows,'source_unchanged':all((ROOT/'studio'/name).read_bytes()==data for name,data in source.items())}
    assert report['snapshot_closure_sha256']=='60799065f406fbb3b13d2dc0df093477210927f86e84b54175dfd36351521a1a'
    text=json.dumps(report,indent=2)
    Path(__file__).with_name('independent-lock-results.json').write_text(text+'\n',encoding='utf-8')
    print(text)

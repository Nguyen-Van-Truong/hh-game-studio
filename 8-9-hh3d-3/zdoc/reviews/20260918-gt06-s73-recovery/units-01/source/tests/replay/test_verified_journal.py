"""The optional index cache must preserve the accepted journal boundaries."""
from pathlib import Path
import os
import json
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from studio.host.core.journal import Journal, JournalError, JournalLimits
from studio.host.replay.verified_journal import VerifiedJournal


class VerifiedJournalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'commands.jsonl'
        self.journal = VerifiedJournal(self.path)

    def append(self, name='c1', journal=None, pending=False, now=1):
        return (journal or self.journal).append_command(project_id='p', command_id=name,
            digest='sha256:' + 'a' * 64, receipt={'value': name}, now_ms=now, pending=pending)

    def lookup(self, name='c1'):
        return self.journal.lookup(project_id='p', command_id=name, now_ms=3)

    def test_exact_history_cache_skips_replay_but_still_checks_receipt(self):
        self.append()
        with patch.object(self.journal, '_load', wraps=self.journal._load) as load:
            self.assertEqual(self.lookup()['receipt'], {'value': 'c1'})
            self.append('c2')
            self.assertEqual(self.lookup('c2')['receipt'], {'value': 'c2'})
            self.assertEqual(load.call_count, 0)

    def test_other_writer_append_refreshes_dedupe_and_lease(self):
        self.append()
        other = Journal(self.path)
        self.append('c2', journal=other)
        lease = other.acquire_lease(project_id='p', target='t', owner='other', now_ms=1, ttl_ms=100)
        self.assertEqual(self.lookup('c2')['receipt'], {'value': 'c2'})
        self.journal.check_lease(lease, now_ms=2)
        with self.assertRaisesRegex(JournalError, 'LEASE_BUSY'):
            self.journal.acquire_lease(project_id='p', target='t', owner='local', now_ms=2, ttl_ms=100)

    def test_in_place_corruption_same_length_and_mtime_is_rejected(self):
        self.append()
        info = self.path.stat()
        raw = self.path.read_bytes().replace(b'"value":"c1"', b'"value":"xx"')
        self.path.write_bytes(raw)
        os.utime(self.path, ns=(info.st_atime_ns, info.st_mtime_ns))
        with self.assertRaisesRegex(JournalError, 'CHECKSUM_MISMATCH'):
            self.lookup()
        self.assertIsNone(self.journal._verified_hash)

    def test_truncated_tail_is_rejected_and_cannot_reuse_cached_receipt(self):
        self.append()
        with self.path.open('ab') as stream:
            stream.write(b'{')
        with self.assertRaisesRegex(JournalError, 'TRUNCATED'):
            self.lookup()
        with self.assertRaisesRegex(JournalError, 'TRUNCATED'):
            self.lookup()

    def test_cached_read_requires_successful_recovery_fsync(self):
        self.append()
        with patch('studio.host.replay.verified_journal.os.fsync', side_effect=OSError('test')):
            with self.assertRaisesRegex(JournalError, 'DURABILITY_UNCONFIRMED'):
                self.lookup()
        self.assertIsNone(self.journal._verified_hash)
        self.assertEqual(self.lookup()['receipt']['value'], 'c1')

    def test_append_sync_failure_invalidates_cache_and_reopen_reconciles(self):
        self.append()
        actual = os.fsync
        calls = []

        def fail_write(fd):
            calls.append(fd)
            if len(calls) == 2:  # inherited reload barrier then actual append
                raise OSError('simulated failed flush')
            return actual(fd)

        with patch('studio.host.replay.verified_journal.os.fsync', side_effect=fail_write):
            with self.assertRaisesRegex(JournalError, 'WRITE_FAILED'):
                self.append('c2')
        self.assertIsNone(self.journal._verified_hash)
        self.assertEqual(self.lookup('c2')['receipt']['value'], 'c2')
        self.assertEqual(VerifiedJournal(self.path).lookup(project_id='p', command_id='c2', now_ms=3)['receipt']['value'], 'c2')

    def test_compact_expiry_retains_tombstones(self):
        self.journal = VerifiedJournal(self.path, limits=JournalLimits(retry_horizon_ms=10))
        self.append()
        self.journal.compact(now_ms=30)
        for j in (self.journal, VerifiedJournal(self.path)):
            with self.assertRaisesRegex(JournalError, 'RETRY_HORIZON_EXPIRED'):
                j.lookup(project_id='p', command_id='c1', now_ms=31)
            with self.assertRaisesRegex(JournalError, 'RETRY_HORIZON_EXPIRED'):
                self.append(journal=j, now=31)

    def test_same_bytes_replaced_file_requires_full_validation(self):
        self.append()
        replacement = self.path.with_suffix('.new')
        replacement.write_bytes(self.path.read_bytes())
        os.replace(replacement, self.path)
        with patch.object(self.journal, '_load', wraps=self.journal._load) as load:
            self.lookup()
            self.assertEqual(load.call_count, 1)

    def test_policy_change_cannot_bypass_record_limit(self):
        self.append()
        self.append('c2')
        self.journal.limits = JournalLimits(max_records=1)
        with self.assertRaisesRegex(JournalError, 'RECORD_LIMIT'):
            self.lookup()

    def test_pending_terminal_history_and_conflicting_digest(self):
        self.append(pending=True)
        self.journal.finish_command(project_id='p', command_id='c1', status='COMMITTED', receipt={'value': 'done'}, now_ms=2)
        self.assertEqual(self.lookup()['receipt']['value'], 'done')
        with self.assertRaisesRegex(JournalError, 'COMMAND_ID'):
            self.journal.append_command(project_id='p', command_id='c1', digest='sha256:'+'b'*64, receipt={}, now_ms=3)

    def test_independent_cached_writers_preserve_dedupe_and_all_unique_ids(self):
        code = '''import json,sys
from studio.host.replay.verified_journal import VerifiedJournal
j=VerifiedJournal(sys.argv[1]); assert sys.stdin.readline()=='GO\\n'
for name in ['shared']+[sys.argv[2]+'.'+str(i) for i in range(4)]:
 r=j.append_command(project_id='p',command_id=name,digest='sha256:'+'a'*64,receipt={'name':name},now_ms=1)
 assert r['receipt']=={'name':name}
 assert j.lookup(project_id='p',command_id=name,now_ms=2)['receipt']=={'name':name}
print('DONE',flush=True)
'''
        processes = []
        deadline = time.monotonic() + 15
        try:
            for i in range(4):
                processes.append(subprocess.Popen([sys.executable, '-B', '-c', code, str(self.path), f'w{i}'],
                    cwd=Path(__file__).resolve().parents[3], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
            for process in processes:
                process.stdin.write('GO\n')
                process.stdin.flush()
            while any(p.poll() is None for p in processes) and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(all(p.poll() == 0 for p in processes), 'bounded concurrent writers failed')
            for process in processes:
                self.assertEqual(process.stdout.read().strip(), 'DONE')
                self.assertEqual(process.stderr.read(), '')
            records = [json.loads(line)['record'] for line in self.path.read_bytes().splitlines()]
            self.assertEqual(len(records), 17)
            self.assertEqual(len({r['command_id'] for r in records}), 17)
            self.assertEqual(self.lookup('shared')['receipt'], {'name': 'shared'})
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()  # retained Popen handle; fixed workers spawn no children
            cleanup_deadline = time.monotonic() + 3
            for process in processes:
                process.wait(timeout=max(.001, cleanup_deadline - time.monotonic()))
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)

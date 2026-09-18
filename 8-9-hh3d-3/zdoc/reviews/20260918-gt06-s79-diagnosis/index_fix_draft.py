"""Review-only minimal repair candidate. Never writes runtime source.

Default: write index_fix_draft.patch beside this file.
--check: load repaired modules in memory, then run the independent probes.
"""
from pathlib import Path
import difflib
import importlib
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('draft context no longer matches source exactly once')
    return source.replace(old, new, 1)


def proposed_sources():
    disk_path = 'studio/host/replay/disk_journal_index.py'
    service_path = 'studio/host/replay/service.py'
    disk = (ROOT / disk_path).read_text(encoding='utf-8')
    disk = replace_once(disk, '''            try:
                cursor = self._db.execute(sql, args)
                return cursor.fetchone() if fetch else None
            except sqlite3.Error as error:
                raise DiskIndexError("INDEX_IO_FAILED") from error
            finally:
                if cursor is not None:
                    cursor.close()
''', '''            try:
                try:
                    cursor = self._db.execute(sql, args)
                    return cursor.fetchone() if fetch else None
                finally:
                    if cursor is not None:
                        cursor.close()
            except sqlite3.Error as error:
                raise DiskIndexError("INDEX_IO_FAILED") from error
''')
    service = (ROOT / service_path).read_text(encoding='utf-8')
    service = replace_once(service, '''        parent = backend.root / 'service'
        parent.mkdir(exist_ok=False)
        self._journal = Journal(parent / 'commands.jsonl', limits=JournalLimits(max_records=512, max_pending_commands=2))
''', '''        self._journal = None
        self._watchdog = None
''')
    service = replace_once(service, '''        self._watchdog = threading.Thread(target=self._expire, name='hh-replay-owner-expiry', daemon=True)
        self._watchdog.start()
''', '''        try:
            parent = backend.root / 'service'
            parent.mkdir(exist_ok=False)
            self._journal = Journal(parent / 'commands.jsonl', limits=JournalLimits(max_records=512, max_pending_commands=2))
            self._watchdog = threading.Thread(target=self._expire, name='hh-replay-owner-expiry', daemon=True)
            self._watchdog.start()
        except BaseException as error:
            if self._journal is None and isinstance(error, JournalError):
                self._journal = getattr(error, 'cleanup_owner', None)
            try:
                self.close()
            except BaseException:
                error.cleanup_owner = self
            raise
''')
    service = replace_once(service, '''        except BaseException:
            if permit is not None:
''', '''        except BaseException as error:
            uncertain = isinstance(error, JournalError) and error.outcome_unknown
            if uncertain:
                self.sessions.halt()
                self.backend.stop()
            if permit is not None:
''')
    service = replace_once(service, '''            if admitted_here:
                self._record_unknown(request.command_id)
''', '''            if admitted_here or uncertain:
                self._record_unknown(request.command_id)
''')
    service = replace_once(service, '''            self._journal.close()
            self._closed = True
''', '''            if self._journal is not None:
                self._journal.close()
            self._closed = True
''')
    service = replace_once(service, '''        self._watchdog.join(1)
        need(not self._watchdog.is_alive(), 'REPLAY_WATCHDOG_HELD')
''', '''        if self._watchdog is not None and self._watchdog.ident is not None:
            self._watchdog.join(1)
            need(not self._watchdog.is_alive(), 'REPLAY_WATCHDOG_HELD')
''')
    return {disk_path: disk, service_path: service}


if __name__ == '__main__':
    sources = proposed_sources()
    if sys.argv[1:] == ['--check']:
        for relative in ('studio/host/replay/disk_journal_index.py',
                         'studio/host/replay/verified_journal.py',
                         'studio/host/replay/service.py'):
            module_name = relative[:-3].replace('/', '.')
            module = importlib.import_module(module_name)
            source = sources.get(relative, (ROOT / relative).read_text(encoding='utf-8'))
            exec(compile(source, str(ROOT / relative), 'exec'), module.__dict__)
        print('INDEX_DRAFT_MODE=in_memory_only; runtime source bytes unchanged', flush=True)
        sys.argv = [str(Path(__file__).with_name('index_fault_probe.py'))]
        runpy.run_path(sys.argv[0], run_name='__main__')
    elif not sys.argv[1:]:
        patch = ''.join(''.join(difflib.unified_diff(
            (ROOT / relative).read_text(encoding='utf-8').splitlines(keepends=True),
            modified.splitlines(keepends=True), fromfile='a/' + relative, tofile='b/' + relative))
            for relative, modified in sources.items())
        destination = Path(__file__).with_suffix('.patch')
        destination.write_text(patch, encoding='utf-8', newline='\n')
        print(destination)
    else:
        raise SystemExit('only --check is supported')

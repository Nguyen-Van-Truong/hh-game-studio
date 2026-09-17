"""Prepared-only GT06 diagnostic: real HTTP against a private S71 history copy.

Run through run_fixture.run_process, not its Godot-specific CLI. The parent
captures actual exit/owned-tree cleanup. This child never launches an engine.
It preserves failed receipts and never promotes reconciliation to acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import time
from datetime import datetime, timezone

sys.dont_write_bytecode = True
HISTORY_SHA256 = '1fa1c75a60335c0811506c46ccd8e2af54fe3066b67d12d9a33e5e7848127c83'
HISTORY_BYTES = 33_224_600
HISTORY_RECORDS = 47_188
SELECTION_SHA256 = '478f879161938837df151dec5847fab99596081f60d29a78f0d15e046fb3f865'
LOOKUP_BUDGET_SECONDS = 5.0
CLIENT_TIMEOUT_SECONDS = 2.0
CHUNK = 1_048_576


class DiagnosticError(RuntimeError):
    pass


def need(value, code):
    if not value:
        raise DiagnosticError(code)


def now_us():
    return time.perf_counter_ns() // 1000


def safe_file(path):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'REGULAR_SINGLE_LINK_REQUIRED')
    for part in (path, *path.absolute().parents):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, 'st_file_attributes', 0) & 0x400, 'REPARSE_PATH')


def file_hash(path, limit=None):
    safe_file(path)
    digest, size, records = hashlib.sha256(), 0, 0
    with path.open('rb') as source:
        while raw := source.read(CHUNK if limit is None else min(CHUNK, limit - size)):
            digest.update(raw)
            size += len(raw)
            records += raw.count(b'\n')
            if limit is not None and size == limit:
                break
    return {'sha256': digest.hexdigest(), 'size_bytes': size, 'records': records}


def source_hashes(root, names):
    result = {}
    for name in sorted(names):
        relative = PurePosixPath(name)
        need(not relative.is_absolute() and relative.as_posix() == name
             and all(p not in ('', '.', '..') for p in relative.parts)
             and '\\' not in name, 'SOURCE_PATH')
        path = root / 'studio' / relative
        safe_file(path)
        result[name] = file_hash(path)['sha256']
    return result


def manifest_hash(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save(root, report):
    temporary = root / 'report.json.tmp'
    with temporary.open('xb') as target:
        target.write(json.dumps(report, sort_keys=True, indent=2, allow_nan=False).encode())
        target.write(b'\n')
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, root / 'report.json')


def p95(values):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * .95
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def remaining(deadline, seconds=0):
    need(time.monotonic() + seconds < deadline, 'DIAGNOSTIC_DEADLINE')


def lookup(client, command_id, digest, deadline, row, stamps, Status, canonical_bytes):
    end = min(deadline, time.monotonic() + LOOKUP_BUDGET_SECONDS)
    while True:
        # Keep the normal client timeout exactly 2 seconds. The remaining
        # budget must fit a full call; it is never reset by another UNKNOWN.
        remaining(end, CLIENT_TIMEOUT_SECONDS)
        began = now_us()
        response = client.lookup(command_id)
        finished = now_us()
        stamps.append(finished)
        row['lookup_attempts'].append({'started_mono_us': began,
            'ended_mono_us': finished, 'response': response.as_dict()})
        remaining(end)
        need(response.command_id == command_id, 'LOOKUP_IDENTITY')
        unknown = response.status is Status.UNKNOWN and response.code == 'CONNECTION_LOST_LOOKUP'
        found_digest = response.postconditions.get('request_digest')
        need(found_digest == digest or unknown and found_digest is None, 'LOOKUP_DIGEST')
        if unknown or response.status is Status.ACCEPTED_PENDING:
            time.sleep(.001)
            continue
        need(response.status is Status.COMMITTED and response.code == 'READBACK_CONFIRMED',
             'LOOKUP_NOT_COMMITTED')
        snapshot = response.postconditions.get('snapshot')
        need(snapshot == {'effect_count': 0, 'revision': 'rev-0', 'value': 0}, 'INSPECT_READBACK')
        need(response.result_revision == 'rev-0'
             and response.result_hash == 'sha256:' + hashlib.sha256(canonical_bytes(snapshot)).hexdigest(),
             'INSPECT_READBACK_HASH')
        row['terminal_response'] = response.as_dict()
        row['terminal_mono_us'] = finished
        row['terminal_ms'] = (finished - row['started_mono_us']) / 1000
        return response


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path, help='8-9-hh3d-3 directory')
    parser.add_argument('--journal', required=True, type=Path, help='Original S71 commands.jsonl; read only')
    parser.add_argument('--source-map', required=True, type=Path, help='S71 source-files.json; names select current files')
    parser.add_argument('--output', required=True, type=Path, help='New exclusive child evidence directory')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--commands', type=int, default=30)
    parser.add_argument('--deadline-seconds', type=int, default=90)
    args = parser.parse_args(argv)
    need(re.fullmatch(r'[a-z][a-z0-9._-]{0,47}', args.run_id), 'RUN_ID')
    need(1 <= args.commands <= 30 and 10 <= args.deadline_seconds <= 100, 'DIAGNOSTIC_BOUNDS')
    source_root = args.source_root.resolve(strict=True)
    original = args.journal.absolute()
    safe_file(original)
    output = args.output.absolute()
    # A new path is mandatory. Never remove or overwrite a prior run.
    output.mkdir(parents=False, exist_ok=False)
    report = {'schema_id': 'hh-studio.gt06-large-history-http-diagnostic', 'schema_version': '1.0.0',
        'run_id': args.run_id, 'scope': 'DIAGNOSTIC_ONLY_NOT_FULL_BENCHMARK',
        'formal_acceptance': False, 'native_acceptance': False, 'engine_launches': 0,
        'status': 'RUNNING', 'phase': 'prepare', 'completed': False,
        'started_utc': datetime.now(timezone.utc).isoformat(), 'host_pid': os.getpid(),
        'client_timeout_seconds': CLIENT_TIMEOUT_SECONDS, 'lookup_budget_seconds': LOOKUP_BUDGET_SECONDS,
        'deadline_seconds': args.deadline_seconds, 'requested_commands': args.commands,
        'actual_exit_authority': 'OUTER run_fixture.run_process process exit and owned-tree capture REQUIRED',
        'fixture_scope': 'fresh read-only project; old records retained, old project state not restored',
        'source_sha256_before': {}, 'commands': [], 'failures': [], 'host_closed': False,
        'host_response_mono_us': [], 'stages_ms': {}}
    report['driver_sha256'] = file_hash(Path(__file__).resolve())['sha256']
    save(output, report)
    host, copied, names = None, None, set()
    started = time.monotonic()
    deadline = started + args.deadline_seconds
    try:
        selection = json.loads(args.source_map.read_text(encoding='utf-8'))
        need(type(selection) is dict and len(selection) == 49, 'S71_SOURCE_MAP')
        names = set(selection)
        report['source_selection_manifest_sha256'] = file_hash(args.source_map)['sha256']
        need(report['source_selection_manifest_sha256'] == SELECTION_SHA256, 'S71_SOURCE_MAP_HASH')
        report['source_sha256_before'] = source_hashes(source_root, names)
        report['source_manifest_sha256_before'] = manifest_hash(report['source_sha256_before'])
        # The script's -B invocation disables new bytecode artifacts. Source
        # stability is checked again after imports and after host shutdown.
        sys.path.insert(0, str(source_root))
        from studio.host.replay.verified_journal import VerifiedJournal
        from studio.host.core.transport import FixtureClient, LoopbackFixtureHost
        from studio.protocol.core import Status, canonical_bytes
        for module in list(sys.modules.values()):
            raw_path = getattr(module, '__file__', None)
            if not raw_path:
                continue
            path = Path(raw_path).resolve()
            try:
                name = path.relative_to(source_root / 'studio').as_posix()
            except ValueError:
                continue
            if path.suffix == '.py':
                names.add(name)
        imported = source_hashes(source_root, names)
        need(all(imported[name] == value for name, value in report['source_sha256_before'].items()),
             'SOURCE_CHANGED_DURING_IMPORT')
        report['source_sha256_before'] = imported
        report['source_manifest_sha256_before'] = manifest_hash(imported)
        need(Path(sys.modules[VerifiedJournal.__module__].__file__).resolve()
             == source_root / 'studio/host/replay/verified_journal.py', 'WRONG_JOURNAL_MODULE')
        need(Path(sys.modules[FixtureClient.__module__].__file__).resolve()
             == source_root / 'studio/host/core/transport.py', 'WRONG_TRANSPORT_MODULE')
        project = Path(tempfile.mkdtemp(prefix='private-project-', dir=output))
        report['private_project_directory'] = project.name
        copied = project / 'commands.jsonl'
        began = time.monotonic()
        digest, byte_count, records = hashlib.sha256(), 0, 0
        with original.open('rb') as reader, copied.open('xb') as writer:
            while raw := reader.read(CHUNK):
                remaining(deadline)
                writer.write(raw)
                digest.update(raw)
                byte_count += len(raw)
                records += raw.count(b'\n')
            writer.flush()
            os.fsync(writer.fileno())
        report['input_history'] = {'sha256': digest.hexdigest(), 'size_bytes': byte_count, 'records': records}
        need(report['input_history'] == {'sha256': HISTORY_SHA256, 'size_bytes': HISTORY_BYTES,
                                        'records': HISTORY_RECORDS}, 'S71_HISTORY_MISMATCH')
        need(file_hash(copied) == report['input_history'], 'COPY_READBACK_MISMATCH')
        report['stages_ms']['copy_and_verify'] = (time.monotonic() - began) * 1000
        report['phase'] = 'journal_load'
        save(output, report)
        remaining(deadline)
        began = time.monotonic()
        journal = VerifiedJournal(copied)
        report['stages_ms']['journal_load'] = (time.monotonic() - began) * 1000
        remaining(deadline)
        project_id = 'gt06.history.' + args.run_id
        host = LoopbackFixtureHost(project_id, project, journal)
        host.start()
        credential = host.sessions.issue(scopes=frozenset({'fixture.read'}), ttl_ms=900_000)
        client = FixtureClient(host.port, host.control_port, credential)
        need(client.timeout == CLIENT_TIMEOUT_SECONDS, 'CLIENT_TIMEOUT_CHANGED')
        remaining(deadline, CLIENT_TIMEOUT_SECONDS)
        need(client.discover().supports('fixture.inspect'), 'INSPECT_CAPABILITY')
        report['project_id'] = project_id
        report['phase'] = 'http_inspections'
        report['host_response_mono_us'].append(now_us())
        for ordinal in range(args.commands):
            remaining(deadline, CLIENT_TIMEOUT_SECONDS)
            command_id = f'{args.run_id}.inspect.{ordinal:03d}'
            request = client.request(command_id)  # No lease and no mutation capability.
            row = {'ordinal': ordinal, 'command_id': command_id, 'request_digest': request.digest,
                   'lookup_attempts': [], 'started_mono_us': now_us()}
            report['commands'].append(row)
            response = client.submit(request)
            received = now_us()
            report['host_response_mono_us'].append(received)
            row.update(receipt_mono_us=received, receipt_ms=(received - row['started_mono_us']) / 1000,
                       receipt=response.as_dict())
            need(response.command_id == command_id, 'SUBMIT_IDENTITY')
            accepted = response.status is Status.ACCEPTED_PENDING and response.code == 'QUEUED'
            unknown = response.status is Status.UNKNOWN and response.code == 'CONNECTION_LOST_LOOKUP'
            if accepted:
                need(response.postconditions.get('request_digest') == request.digest, 'SUBMIT_DIGEST')
            else:
                row['admission_failed'] = True
                report['failures'].append('SUBMIT_' + response.status.value + '_' + response.code)
            # Persist lost receipts before attempting failure-only reconciliation.
            if not accepted:
                save(output, report)
            need(accepted or unknown, 'SUBMIT_NOT_ACCEPTED')
            terminal = lookup(client, command_id, request.digest, deadline, row,
                              report['host_response_mono_us'], Status, canonical_bytes)
            row['terminal_after_unknown_is_failure_reconciliation_only'] = not accepted
            if not accepted:
                break  # Never recover a failed admission into a successful diagnostic.
            if ordinal == args.commands - 1:
                # Actual second HTTP lookup; do not resubmit or replay mutation.
                repeated = {'started_mono_us': now_us(), 'lookup_attempts': []}
                second = lookup(client, command_id, request.digest, deadline, repeated,
                                report['host_response_mono_us'], Status, canonical_bytes)
                need(second.as_dict() == terminal.as_dict(), 'REPEAT_TERMINAL_CHANGED')
                row['repeat_same_id_lookup'] = repeated
            save(output, report)
        remaining(deadline)
        need(not report['failures'] and len(report['commands']) == args.commands, 'HTTP_DIAGNOSTIC_INCOMPLETE')
        report['completed'] = True
    except BaseException as error:
        code = str(error) if isinstance(error, DiagnosticError) else getattr(error, 'code', type(error).__name__)
        report['failures'].append(code if isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', code)
                                  else 'UNCLASSIFIED_ERROR')
        report['failure_phase'] = report['phase']
        report['completed'] = False
    finally:
        if host is not None:
            try:
                host.close()
                report['host_closed'] = True
                report['host_diagnostic_codes'] = [json.loads(raw)['payload']['code'] for raw in host.diagnostics]
                if report['host_diagnostic_codes']:
                    report['failures'].append('UNEXPECTED_HOST_DIAGNOSTICS')
            except BaseException as error:
                report['failures'].append('HOST_CLOSE_' + type(error).__name__)
        try:
            report['original_history_after'] = file_hash(original)
            need(report['original_history_after'] == {'sha256': HISTORY_SHA256, 'size_bytes': HISTORY_BYTES,
                                                       'records': HISTORY_RECORDS}, 'ORIGINAL_HISTORY_CHANGED')
            if copied is not None:
                report['copied_prefix_after'] = file_hash(copied, limit=HISTORY_BYTES)
                need(report['copied_prefix_after'] == report['original_history_after'], 'HISTORY_PREFIX_CHANGED')
                report['copied_journal_after'] = file_hash(copied)
                report['appended_records'] = report['copied_journal_after']['records'] - HISTORY_RECORDS
                if report['completed']:
                    need(report['appended_records'] == 2 * args.commands, 'UNEXPECTED_JOURNAL_RECORD_COUNT')
            if names:
                report['source_sha256_after'] = source_hashes(source_root, names)
                need(report['source_sha256_after'] == report['source_sha256_before'], 'SOURCE_CHANGED')
                report['source_manifest_sha256_after'] = manifest_hash(report['source_sha256_after'])
            report['driver_sha256_after'] = file_hash(Path(__file__).resolve())['sha256']
            need(report['driver_sha256_after'] == report['driver_sha256'], 'DRIVER_CHANGED')
        except BaseException as error:
            report['failures'].append(str(error) if isinstance(error, DiagnosticError) else 'FINAL_HASH_' + type(error).__name__)
        stamps = report['host_response_mono_us']
        if stamps:
            report['command_observation_ended_mono_us'] = stamps[-1]
        receipts = [row['receipt_ms'] for row in report['commands'] if 'receipt_ms' in row]
        terminals = [row['terminal_ms'] for row in report['commands'] if 'terminal_ms' in row]
        report['summary'] = {'receipt_p95_ms': p95(receipts), 'inspect_terminal_p95_ms': p95(terminals),
            'max_response_gap_ms': max(((b - a) / 1000 for a, b in zip(stamps, stamps[1:])), default=None),
            'receipt_samples': len(receipts), 'terminal_samples': len(terminals),
            'percentile_method': 'linear_type7',
            'gap_scope': 'HTTP command response observations, including failure/repeat lookups; excludes setup/shutdown',
            'total_child_work_ms': (time.monotonic() - started) * 1000}
        report['status'] = 'DIAGNOSTIC_OK' if report['completed'] and not report['failures'] and report['host_closed'] else 'DIAGNOSTIC_FAILED'
        report['completed'] = report['status'] == 'DIAGNOSTIC_OK'
        report['phase'] = 'terminal'
        report['ended_utc'] = datetime.now(timezone.utc).isoformat()
        save(output, report)
    print(json.dumps({'status': report['status'], 'run_id': args.run_id,
                      'formal_acceptance': False, 'summary': report['summary']}))
    return 0 if report['completed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

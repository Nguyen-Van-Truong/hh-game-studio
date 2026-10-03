"""Owned sequential GT06 campaign; raw capture is never an acceptance verdict.

Each of the profile's fresh host/editor pairs retains both identities for 35 batches.
Native ready -> 1000 real HTTP commands -> bound start permit -> 100 native
cycles -> quiescent OS observation -> bound ACK with fresh native counters.
Only a fully captured run can be resumed as part of the same source campaign.
An objectively infrastructure-aborted pair may receive one fresh attempt while
the immutable seven-day campaign lease remains valid; product/harness failures
stay terminal. Interrupted runs retain their artifacts and partial samples
never enter the dataset. No production limits change.
"""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import stat
import sys
import threading
import time
import uuid

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay.benchmark_commands import CommandProducer
from studio.tests.replay.benchmark_job import (
    BenchmarkJobError, BenchmarkProcess, require, verify_capture, write as write_cleanup,
)
from studio.tests.replay.benchmark_readiness import validate_startup_readiness
from studio.tests.replay.benchmark_import_observer import ImportObserver, validate_import_snapshot
from studio.tests.replay.benchmark_http_phases import (
    validate_journal_timing_snapshot, validate_phase_snapshot,
)
from studio.tests.replay import benchmark_environment as environment
from studio.tests.replay import benchmark_profile as profile
from studio.tests.replay.measure_window import measurement_window
from studio.tests.replay.benchmark_assembly import read_artifact, assemble_sample, assemble_run, assemble_dataset
from studio.tests.replay.run_native_benchmark import (
    load_fixture, source_files as imported_source_files, closure, read_regular, write, sha, encoded,
    prepare, project_files, MUTABLE_SCENE, validate_cycle_timing,
)
from studio.host.replay.process_probe import ProcessProbe
from studio.pipeline import native_job

SEQUENCE = 'host1000_then_native100_then_joint_ack_v1'
HEAVY_PREFLIGHT_NAMES = frozenset({
    'chrome.exe', 'brave.exe', 'msedge.exe', 'firefox.exe', 'opera.exe',
    'wsl.exe', 'wslhost.exe', 'wslrelay.exe', 'vmmemwsl', 'vmmemwsl.exe',
    'telegram.exe', 'slack.exe', 'teams.exe', 'ms-teams.exe', 'discord.exe', 'zalo.exe',
    'outlook.exe',
})
# O9.2 permits one fresh retry of an infrastructure-aborted pair, while
# product/harness failures remain terminal.  Historical campaign.json files
# carry ``max_attempts_per_run=1`` and are deliberately left on that policy.
MAX_ATTEMPTS = 2
CAMPAIGN_LIFECYCLE_SCHEMA = 'hh-studio.benchmark-campaign-lifecycle'
CAMPAIGN_STATE_SCHEMA = 'hh-studio.benchmark-campaign-state'
CAMPAIGN_LIFECYCLE_VERSION = '1.0.0'
CAMPAIGN_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
CAMPAIGN_WINDOW_SECONDS = 4 * 60 * 60
PREFLIGHT_RECHECK_SECONDS = 5 * 60
INFRA_RETRY_MIN_REMAINING_SECONDS = 40 * 60
LAUNCH_OBSERVATION_SCHEMA = 'HH-GT06-LAUNCH-OBSERVATION-1'
LAUNCH_SAMPLE_SCHEMA = 'HH-GT06-LAUNCH-SAMPLE-STREAM-1'

# Both entry points belong to the campaign even when only one is imported in
# this process. Bind the scheduler registration too, without weakening the
# imported dependency closure or the exact parent/child equality check.
CAMPAIGN_FIXED_SOURCES = (
    'tests/replay/run_benchmark_campaign.py',
    'tests/replay/run_campaign_task.py',
    'tests/replay/campaign_task.ps1',
    'tests/replay/benchmark_environment.py',
    'contracts/perf-collector.schema.json',
)


def source_files():
    files = imported_source_files()
    for relative in CAMPAIGN_FIXED_SOURCES:
        files[relative] = sha(read_regular(STUDIO / relative))
    return dict(sorted(files.items()))


def clock():
    return time.perf_counter_ns() // 1000


def reference(root, path):
    raw = artifact_bytes(path)
    return {'file': path.relative_to(root).as_posix(), 'sha256': sha(raw), 'size_bytes': len(raw)}


def artifact_bytes(path):
    """Empty logs/guard files are evidence too; reject links and growing files."""
    for component in (path, *path.parents):
        info = component.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'CAMPAIGN_ARTIFACT_REPARSE')
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 <= info.st_size <= 128 * 1024**2,
            'CAMPAIGN_ARTIFACT_SIZE')
    raw = path.read_bytes()
    require(len(raw) == info.st_size, 'CAMPAIGN_ARTIFACT_CHANGED')
    return raw


def publish(path, value):
    """Trusted fixed-slot fixture input, exclusive temp + no-overwrite rename."""
    require(not path.exists(), 'CAMPAIGN_INPUT_EXISTS')
    temporary = path.with_suffix(path.suffix + '.tmp')
    raw = encoded(value)
    with temporary.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    # On Windows rename rejects an existing destination; do not use replace.
    temporary.rename(path)
    require(read_regular(path) == raw, 'CAMPAIGN_INPUT_READBACK')
    return clock()


class CampaignDeferredError(BenchmarkJobError):
    """The campaign is durable, but this measurement window is not ready.

    The original gate code remains the public ``code`` so callers that already
    classify the resource failure keep their historical diagnostics.  The
    explicit attributes let lifecycle consumers distinguish a deferred pair
    from a terminal product/harness failure without guessing from text.
    """
    def __init__(self, code, *, reason, next_check_epoch, pair_index=None):
        super().__init__(code)
        self.deferred = True
        self.lifecycle_code = 'DEFERRED'
        self.deferred_code = 'CAMPAIGN_DEFERRED'
        self.reason = reason
        self.next_check_epoch = next_check_epoch
        self.pair_index = pair_index


def _utc(epoch):
    return datetime.fromtimestamp(float(epoch), timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _epoch(value, code):
    require(type(value) in (int, float) and value >= 0, code)
    return float(value)


def _append_json_line(path, value, *, code='CAMPAIGN_STATE_WRITE'):
    """Append one fsynced lifecycle event without rewriting prior history."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(path):
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                'CAMPAIGN_STATE_UNSAFE_PATH')
        mode = 'ab'
    else:
        mode = 'xb'
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    try:
        with path.open(mode) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        # A second writer must never silently append to a path that appeared
        # after our lstat.  The campaign lease will surface this as a gate.
        require(False, code)
    require(path.read_bytes().endswith(raw), code)


def campaign_attempt_limit(root):
    """Read the frozen attempt policy, failing closed when history is corrupt.

    A malformed historical campaign is not equivalent to a fresh campaign.
    Falling back to ``MAX_ATTEMPTS`` could silently grant a retry that the
    frozen receipt never authorized.
    """
    path = root / 'campaign.json'
    if not path.is_file():
        return MAX_ATTEMPTS
    try:
        value = json.loads(read_regular(path))
    except (OSError, ValueError, TypeError):
        require(False, 'CAMPAIGN_ATTEMPT_POLICY_CORRUPT')
    require(type(value) is dict and 'max_attempts_per_run' in value,
            'CAMPAIGN_ATTEMPT_POLICY_CORRUPT')
    limit = value['max_attempts_per_run']
    require(type(limit) is int and 1 <= limit <= MAX_ATTEMPTS,
            'CAMPAIGN_ATTEMPT_POLICY_CORRUPT')
    return limit


def _validate_campaign_state(root, lifecycle):
    path = root / 'campaign-state.jsonl'
    require(path.exists(), 'CAMPAIGN_STATE_MISSING')
    lines = read_regular(path, 4 * 1024**2).splitlines()
    require(lines, 'CAMPAIGN_STATE_MISSING')
    previous_epoch = None
    for expected, raw in enumerate(lines):
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            require(False, 'CAMPAIGN_STATE_CORRUPT')
        require(value.get('schema_id') == CAMPAIGN_STATE_SCHEMA
                and value.get('schema_version') == CAMPAIGN_LIFECYCLE_VERSION
                and value.get('campaign_id') == lifecycle['campaign_id']
                and value.get('source_closure_sha256') == lifecycle['source_closure_sha256']
                and value.get('profile_sha256') == lifecycle['profile_sha256']
                and value.get('sequence') == expected
                and value.get('state') in ('OPEN', 'DEFERRED', 'INFRA_RETRY', 'COMPLETE'),
                'CAMPAIGN_STATE_BINDING')
        observed = _epoch(value.get('observed_epoch'), 'CAMPAIGN_STATE_TIME')
        require(value.get('observed_utc') == _utc(observed), 'CAMPAIGN_STATE_TIME')
        if previous_epoch is not None:
            require(observed >= previous_epoch, 'CAMPAIGN_STATE_ORDER')
        previous_epoch = observed
        if value.get('state') == 'DEFERRED':
            next_check = _epoch(value.get('next_check_epoch'), 'CAMPAIGN_STATE_DEFER')
            require(next_check >= observed
                    and value.get('next_check_utc') == _utc(next_check),
                    'CAMPAIGN_STATE_DEFER')
    return json.loads(lines[-1])


def ensure_campaign_lifecycle(root, *, campaign_id, source_closure_sha256,
                              profile_sha256, toolchain_sha256, now=None):
    """Create or verify the immutable seven-day same-closure campaign lease."""
    now = time.time() if now is None else float(now)
    require(now >= 0, 'CAMPAIGN_LIFECYCLE_CLOCK')
    path = root / 'campaign-lifecycle.json'
    if path.exists():
        value = json.loads(read_regular(path))
        require(value.get('schema_id') == CAMPAIGN_LIFECYCLE_SCHEMA
                and value.get('schema_version') == CAMPAIGN_LIFECYCLE_VERSION,
                'CAMPAIGN_LIFECYCLE_SCHEMA')
        require(value.get('campaign_id') == campaign_id
                and value.get('source_closure_sha256') == source_closure_sha256
                and value.get('profile_sha256') == profile_sha256
                and value.get('toolchain_sha256') == toolchain_sha256,
                'CAMPAIGN_LIFECYCLE_BINDING')
        opened = _epoch(value.get('opened_epoch'), 'CAMPAIGN_LIFECYCLE_OPENED')
        expires = _epoch(value.get('expires_epoch'), 'CAMPAIGN_LIFECYCLE_EXPIRES')
        require(value.get('max_age_seconds') == CAMPAIGN_MAX_AGE_SECONDS
                and expires > opened and expires - opened == CAMPAIGN_MAX_AGE_SECONDS,
                'CAMPAIGN_LIFECYCLE_WINDOW')
        require(value.get('opened_utc') == _utc(opened)
                and value.get('expires_utc') == _utc(expires), 'CAMPAIGN_LIFECYCLE_TIME')
        require(now <= expires, 'CAMPAIGN_LIFECYCLE_EXPIRED')
        _validate_campaign_state(root, value)
        return value
    opened = now
    expires = opened + CAMPAIGN_MAX_AGE_SECONDS
    value = {'schema_id': CAMPAIGN_LIFECYCLE_SCHEMA, 'schema_version': CAMPAIGN_LIFECYCLE_VERSION,
             'campaign_id': campaign_id, 'source_closure_sha256': source_closure_sha256,
             'profile_sha256': profile_sha256, 'toolchain_sha256': toolchain_sha256,
             'opened_epoch': opened, 'expires_epoch': expires, 'opened_utc': _utc(opened),
             'expires_utc': _utc(expires), 'max_age_seconds': CAMPAIGN_MAX_AGE_SECONDS,
             'formal_acceptance': False}
    write(path, value)
    _append_json_line(root / 'campaign-state.jsonl', {
        'schema_id': CAMPAIGN_STATE_SCHEMA, 'schema_version': CAMPAIGN_LIFECYCLE_VERSION,
        'sequence': 0, 'state': 'OPEN', 'campaign_id': campaign_id,
        'source_closure_sha256': source_closure_sha256, 'profile_sha256': profile_sha256,
        'observed_epoch': opened, 'observed_utc': _utc(opened), 'formal_acceptance': False})
    return value


def _record_campaign_state(root, lifecycle, state, *, pair_index=None, attempt=None,
                           reason=None, code=None, now=None, next_check_epoch=None):
    path = root / 'campaign-state.jsonl'
    sequence = 0
    if path.exists():
        previous = _validate_campaign_state(root, lifecycle)
        previous_sequence = previous.get('sequence')
        require(type(previous_sequence) is int and previous_sequence >= 0,
                'CAMPAIGN_STATE_SEQUENCE')
        sequence = previous_sequence + 1
    now = time.time() if now is None else float(now)
    require(now >= 0, 'CAMPAIGN_STATE_TIME')
    require(previous.get('state') != 'COMPLETE' if path.exists() else True,
            'CAMPAIGN_STATE_TERMINAL')
    row = {'schema_id': CAMPAIGN_STATE_SCHEMA, 'schema_version': CAMPAIGN_LIFECYCLE_VERSION,
           'sequence': sequence, 'state': state, 'campaign_id': lifecycle['campaign_id'],
           'source_closure_sha256': lifecycle['source_closure_sha256'],
           'profile_sha256': lifecycle['profile_sha256'], 'observed_epoch': now,
           'observed_utc': _utc(now), 'formal_acceptance': False}
    if pair_index is not None:
        row['pair_index'] = pair_index
    if attempt is not None:
        row['attempt'] = attempt
    if reason is not None:
        row['reason'] = reason
    if code is not None:
        row['code'] = code
    if next_check_epoch is not None:
        row['next_check_epoch'] = next_check_epoch
        row['next_check_utc'] = _utc(next_check_epoch)
    _append_json_line(path, row)
    return row


def defer_campaign(root, lifecycle, *, code, reason, pair_index=None, now=None):
    """Persist a DEFERRED decision and retain the first defer receipt forever."""
    now = time.time() if now is None else float(now)
    next_check = now + PREFLIGHT_RECHECK_SECONDS
    deferred = {'schema_id': 'hh-studio.benchmark-campaign-deferred', 'schema_version': '1.0.0',
                'campaign_id': lifecycle['campaign_id'],
                'source_closure_sha256': lifecycle['source_closure_sha256'],
                'profile_sha256': lifecycle['profile_sha256'], 'reason': reason,
                'code': code, 'pair_index': pair_index, 'first_observed_epoch': now,
                'first_observed_utc': _utc(now), 'next_check_epoch': next_check,
                'next_check_utc': _utc(next_check), 'formal_acceptance': False}
    path = root / 'deferred.json'
    if path.exists():
        previous = json.loads(read_regular(path))
        require(previous.get('schema_id') == deferred['schema_id']
                and previous.get('campaign_id') == deferred['campaign_id']
                and previous.get('source_closure_sha256') == deferred['source_closure_sha256']
                and previous.get('profile_sha256') == deferred['profile_sha256'],
                'CAMPAIGN_DEFERRED_BINDING')
    else:
        write(path, deferred)
    # ``deferred.json`` is the immutable first receipt.  Every subsequent
    # defer gets its own append-only state row so the latest backoff is
    # durable without rewriting that receipt.
    _record_campaign_state(root, lifecycle, 'DEFERRED', pair_index=pair_index,
                           reason=reason, code=code, now=now,
                           next_check_epoch=next_check)
    raise CampaignDeferredError(code, reason=reason, next_check_epoch=next_check,
                                pair_index=pair_index)


def require_defer_elapsed(root, lifecycle, *, now=None):
    """Honor the five-minute backoff without rewriting the first receipt."""
    path = root / 'deferred.json'
    if not path.exists():
        return
    try:
        value = json.loads(read_regular(path))
    except (ValueError, TypeError, OSError):
        require(False, 'CAMPAIGN_DEFERRED_CORRUPT')
    require(value.get('schema_id') == 'hh-studio.benchmark-campaign-deferred'
            and value.get('campaign_id') == lifecycle['campaign_id']
            and value.get('source_closure_sha256') == lifecycle['source_closure_sha256']
            and value.get('profile_sha256') == lifecycle['profile_sha256'],
            'CAMPAIGN_DEFERRED_BINDING')
    # The receipt remains immutable, while the state log carries the latest
    # defer timestamp/check.  Never keep using the first five-minute window.
    latest = _validate_campaign_state(root, lifecycle)
    if latest.get('state') != 'DEFERRED':
        return
    next_check = _epoch(latest.get('next_check_epoch'), 'CAMPAIGN_DEFERRED_TIME')
    require(latest.get('next_check_utc') == _utc(next_check), 'CAMPAIGN_DEFERRED_TIME')
    now = time.time() if now is None else float(now)
    if now < next_check:
        raise CampaignDeferredError(latest.get('code', value.get('code',
                                    'CAMPAIGN_PREFLIGHT_DEFERRED')),
                                    reason='WAIT_RECHECK_INTERVAL',
                                    next_check_epoch=next_check,
                                    pair_index=value.get('pair_index'))


def infra_retry_allowed(root, lifecycle, *, source_closure_sha256, profile_sha256,
                        attempt, now=None, window_remaining_seconds=None):
    """O9.2a gate for exactly one fresh INFRA_ABORT retry."""
    now = time.time() if now is None else float(now)
    require(lifecycle['source_closure_sha256'] == source_closure_sha256
            and lifecycle['profile_sha256'] == profile_sha256, 'CAMPAIGN_RETRY_BINDING')
    require(attempt == 1, 'CAMPAIGN_RETRY_ATTEMPTS')
    require(type(window_remaining_seconds) in (int, float), 'CAMPAIGN_RETRY_WINDOW')
    require(window_remaining_seconds >= 0, 'CAMPAIGN_RETRY_WINDOW')
    if window_remaining_seconds < INFRA_RETRY_MIN_REMAINING_SECONDS:
        return False
    try:
        environment.require_infra_budget(root.parent, read_regular)
    except BenchmarkJobError:
        return False
    return now <= lifecycle['expires_epoch']


def _window_remaining_seconds(window_started_mono):
    """Return the observed remainder of this invocation's four-hour window."""
    require(type(window_started_mono) in (int, float), 'CAMPAIGN_WINDOW_CLOCK')
    elapsed = time.monotonic() - float(window_started_mono)
    require(elapsed >= 0, 'CAMPAIGN_WINDOW_CLOCK')
    return max(0.0, CAMPAIGN_WINDOW_SECONDS - elapsed)


def _watchdog_retry_slots(root, lifecycle, *, source_closure_sha256,
                          profile_sha256, campaign_sha256, max_attempts,
                          window_started_mono):
    """Return only watchdog slots authorized for this exact fresh retry.

    A watchdog receipt is a stop latch by default.  It is temporarily
    exempted only when the immutable prior failure proves INFRA_ABORT and
    cleanup, the context is bound to the current closure, and O9.2's live
    remaining-window/budget gate authorizes the one retry.  Once a later
    attempt has a complete bound capture, the old latch is historical raw
    evidence and no longer blocks closeout.
    """
    if lifecycle is None:
        return frozenset()
    allowed = set()
    remaining = _window_remaining_seconds(window_started_mono)
    for index in range(profile.PROFILE.process_runs):
        for attempt in range(1, max_attempts + 1):
            output = root / f'run-{index:02d}-attempt-{attempt:02d}'
            stop = output / 'watchdog-stop.json'
            failure_path = output / 'parent-failure.json'
            if not stop.is_file() or not failure_path.is_file():
                continue
            try:
                failure = json.loads(read_regular(failure_path))
                context = json.loads(read_regular(output / 'context.json'))
            except (OSError, ValueError, TypeError):
                continue
            if (failure.get('classification') != 'INFRA_ABORT'
                    or failure.get('owner_closed') is not True
                    or failure.get('owned_tree_zero') is not True
                    or context.get('source_closure_sha256') != source_closure_sha256
                    or context.get('profile_sha256') != profile_sha256
                    or context.get('campaign_sha256') != campaign_sha256
                    or context.get('index') != index
                    or context.get('attempt') != attempt
                    or context.get('run_id') != f'{lifecycle["campaign_id"]}.r{index:02d}.a{attempt:02d}'
                    or (output / 'stop-request.json').exists()):
                continue
            try:
                _o9_verify_retry_cleanup(output, context)
            except BaseException:
                continue
            # The parent receipt is mutable raw metadata. Rebuild and bind
            # the watchdog role evidence from the frozen sample stream before
            # exempting this stop latch for a retry; a forged/stale
            # INFRA_ABORT must remain latched.
            try:
                role_stop = _o9_verify_role_stop(output, context)
                if (type(role_stop) is not dict
                        or role_stop.get('classification') != 'INFRA_ABORT'):
                    continue
            except BaseException:
                continue
            # A later successful attempt proves this stop is no longer an
            # active latch; retain the stop artifact for review.
            later_success = False
            for later in range(attempt + 1, max_attempts + 1):
                capture_path = root / f'run-{index:02d}-attempt-{later:02d}' / 'run-capture.json'
                if not capture_path.is_file():
                    continue
                try:
                    capture = json.loads(read_regular(capture_path))
                except (OSError, ValueError, TypeError):
                    continue
                if (capture.get('completed') is True
                        and capture.get('source_closure_sha256') == source_closure_sha256
                        and capture.get('profile_sha256') == profile_sha256
                        and capture.get('run_id') == f'{lifecycle["campaign_id"]}.r{index:02d}.a{later:02d}'):
                    later_success = True
                    break
            if later_success:
                allowed.add(output)
                continue
            if attempt == 1 and attempt < max_attempts:
                try:
                    if infra_retry_allowed(root, lifecycle,
                            source_closure_sha256=source_closure_sha256,
                            profile_sha256=profile_sha256, attempt=attempt,
                            window_remaining_seconds=remaining):
                        allowed.add(output)
                except BenchmarkJobError:
                    # An unproven authorization remains a latched stop.
                    pass
    return frozenset(allowed)


class NativeLog:
    """Consume complete lines only; retain bounded markers, not heartbeat history."""
    def __init__(self, owner):
        self.owner, self.offset, self.tail = owner, 0, b''
        self.events = {}
        self.last_heartbeat = None

    def poll(self):
        code = self.owner.tick()
        # Startup errors arrive on stderr before the first native marker.
        # This lane already requires empty stderr at completion; fail at the
        # first observation instead of spending hours on an invalid prefix.
        errors = self.owner.output / 'stderr.txt'
        if errors.exists():
            require(errors.stat().st_size == 0, 'CAMPAIGN_NATIVE_STDERR')
        path = self.owner.output / 'stdout.txt'
        try:
            with path.open('rb') as stream:
                stream.seek(self.offset)
                raw = stream.read(1024 * 1024)
                self.offset += len(raw)
        except FileNotFoundError:
            raw = b''
        rows = (self.tail + raw).split(b'\n')
        self.tail = rows.pop()
        require(len(self.tail) <= 65_536, 'CAMPAIGN_LOG_LINE_LIMIT')
        for line in rows:
            text = line.decode('utf-8').strip()
            require(not re.search(r'\b(?:ERROR|WARNING)\b|ObjectDB instances leaked', text), 'CAMPAIGN_NATIVE_LOG')
            if not text.startswith('HH_GT06_BENCHMARK_'):
                continue
            tag, payload = text.split(' ', 1)
            value = json.loads(payload)
            require(not tag.endswith('_FAILED'), 'CAMPAIGN_NATIVE_FAILURE')
            if tag.endswith('_HEARTBEAT'):
                self.last_heartbeat = value
            else:
                require(sum(len(v) for v in self.events.values()) < 256, 'CAMPAIGN_MARKER_LIMIT')
                self.events.setdefault(tag, []).append(value)
        return code

    def wait(self, suffix, index, timeout):
        end = time.monotonic() + timeout
        tag = 'HH_GT06_BENCHMARK_' + suffix
        while True:
            code = self.poll()
            matches = [row for row in self.events.get(tag, [])
                       if row.get('index', row.get('batch_index')) == index]
            require(len(matches) <= 1, 'CAMPAIGN_DUPLICATE_MARKER')
            if matches:
                return matches[0]
            require(code is None, 'CAMPAIGN_EARLY_NATIVE_EXIT')
            require(time.monotonic() < end, 'CAMPAIGN_PHASE_TIMEOUT')
            time.sleep(.02)


class CampaignProducer(CommandProducer):
    def __init__(self, root, run_id, log):
        self.native_log = log
        super().__init__(root, run_id)

    def _received(self, *, expected_diagnostic=None):
        observed = super()._received(expected_diagnostic=expected_diagnostic)
        require(self.native_log.poll() is None, 'CAMPAIGN_NATIVE_EXIT_DURING_COMMANDS')
        return observed


def sample_editor(probe):
    observed = probe.sample_with_handle_count()
    require(observed is not None and observed['visible_window_handles'], 'CAMPAIGN_EDITOR_UNOBSERVED')
    require(type(observed.get('handle_mono_us')) is int
            and type(observed.get('held_handles')) is int,
            'CAMPAIGN_EDITOR_HANDLES')
    return {'host_mono_us': observed['host_mono_us'],
            'handle_mono_us': observed['handle_mono_us'],
            'rss_bytes': {'value': observed['rss_bytes'], 'unavailable_reason': None},
            'private_commit_bytes': {'value': observed['private_commit_bytes'], 'unavailable_reason': None},
            'held_handles': {'value': observed['held_handles'], 'unavailable_reason': None},
            'visible_window_handles': observed['visible_window_handles']}


def open_probe(owner, executable):
    end = time.monotonic() + 10
    while True:
        require(owner.tick() is None, 'CAMPAIGN_EDITOR_START_EXIT')
        try:
            start = json.loads((owner.output / 'process-start.json').read_bytes())
        except (FileNotFoundError, json.JSONDecodeError):
            require(time.monotonic() < end, 'CAMPAIGN_EDITOR_START_TIMEOUT')
            time.sleep(.02)
            continue
        require(set(start) == {'pid'} and type(start['pid']) is int, 'CAMPAIGN_EDITOR_START_SHAPE')
        return ProcessProbe(start['pid'], executable)


def verify_sources(files):
    require(source_files() == files, 'CAMPAIGN_SOURCE_CHANGED')


def stop_requested(output, *, run_id, source_closure_sha256, campaign_sha256):
    """Local fixed-slot control; a request can only stop this exact owned run.

    Publish with an exclusive temp file and no-overwrite rename. Invalid or
    stale control fails closed through the same owner cleanup. No new process,
    resume, PID-based signal, or successful measurement is inferred from it.
    """
    path = output / 'stop-request.json'
    if not os.path.lexists(path):
        return False

    def unique_pairs(rows):
        value = {}
        for key, item in rows:
            require(key not in value, 'CAMPAIGN_STOP_DUPLICATE_KEY')
            value[key] = item
        return value

    value = json.loads(read_regular(path, 4096), object_pairs_hook=unique_pairs)
    expected = {'schema': 'HH-GT06-CAMPAIGN-STOP-1', 'run_id': run_id,
        'source_closure_sha256': source_closure_sha256,
        'campaign_sha256': campaign_sha256, 'reason': 'OPERATOR_STOP'}
    require(type(value) is dict and value == expected, 'CAMPAIGN_STOP_BINDING')
    return True


def require_campaign_running(root, *, active=None, max_attempts=None,
                             allow_watchdog_slots=()):
    """A Stop in any fixed attempt slot stays latched across run boundaries.

    The active run validates its control payload separately. Presence in an
    older slot is sufficient to fail closed, including a broken symlink.
    Check only the bounded profile.process_runs x MAX_ATTEMPTS slots, not arbitrary directories.
    """
    max_attempts = campaign_attempt_limit(root) if max_attempts is None else max_attempts
    require(type(max_attempts) is int and 1 <= max_attempts <= MAX_ATTEMPTS,
            'CAMPAIGN_ATTEMPT_POLICY')
    allow_watchdog_slots = frozenset(allow_watchdog_slots)
    for index in range(profile.PROFILE.process_runs):
        for attempt in range(1, max_attempts + 1):
            output = root / f'run-{index:02d}-attempt-{attempt:02d}'
            if output != active:
                require(not os.path.lexists(output / 'stop-request.json'), 'CAMPAIGN_STOP_LATCHED')
            if output not in allow_watchdog_slots:
                require(not os.path.lexists(output / 'watchdog-stop.json'),
                        'CAMPAIGN_WATCHDOG_STOP_LATCHED')


def wait_owned_run(owner, output, *, run_id, source_closure_sha256, campaign_sha256,
                   check_campaign_stop=None, watchdog=None):
    while True:
        if check_campaign_stop is not None:
            check_campaign_stop()
        stop = stop_requested(output, run_id=run_id,
            source_closure_sha256=source_closure_sha256, campaign_sha256=campaign_sha256)
        terminal = owner.tick(stop=stop)
        # The owner/child's existing failure always takes precedence. The
        # watchdog cannot rewrite a recorded failed run into infrastructure.
        if terminal not in (None, 0):
            raise BenchmarkJobError('BENCHMARK_WRAPPER_EXIT')
        if watchdog is not None and not (output / 'child-failure.json').exists():
            watchdog.poll(force=terminal is not None)
        if terminal is not None:
            # Stop can arrive while tick observes the terminal process exit.
            require(not stop_requested(output, run_id=run_id,
                source_closure_sha256=source_closure_sha256, campaign_sha256=campaign_sha256),
                'BENCHMARK_STOPPED')
            if check_campaign_stop is not None:
                check_campaign_stop()
            return
        time.sleep(.05)


class CampaignScreenError(BenchmarkJobError):
    """A failed gate row, without inferring leak ownership or root cause."""
    def __init__(self, code, *, index, role, counter, baseline, observed, maximum):
        super().__init__(code)
        # Only selected numeric fields and fixed role/counter labels are retained.
        # Construct this after failure, never resample or retain a successful row.
        self.screen_observation = {
            'schema_id': 'hh-studio.benchmark-screen-failure', 'schema_version': '1.1.0',
            'batch_index': index, 'baseline_batch_indices': [2, 3, 4], 'role': role,
            'counter': counter, 'baseline_value': baseline, 'observed_value': observed,
            'maximum_inclusive': maximum, 'root_cause_claim': False,
        }


def screen_sample(sample, baseline):
    """Stop only hard failures; O1 keeps mild counter noise running to batch 34."""
    for role in ('host', 'editor'):
        require(set(sample['memory'][role]) == set(profile._COUNTERS), 'CAMPAIGN_COUNTER_SHAPE')
        for name in profile._COUNTERS:
            row = sample['memory'][role][name]
            if role == 'host' and name in ('objects', 'resources'):
                continue
            value = row['value']
            require(type(value) is int and value >= (1 if name in ('rss_bytes', 'private_commit_bytes') else 0),
                    'CAMPAIGN_COUNTER_UNAVAILABLE')
            if sample['index'] < 5:
                continue
            require(type(baseline) is dict, 'CAMPAIGN_BASELINE_UNAVAILABLE')
            reference_value = baseline[role][name]['value']
            if name in ('held_handles', 'objects'):
                margin = profile.PROFILE.early_object_margin if name == 'objects' else profile.PROFILE.early_handle_margin
                if value > reference_value + margin:
                    raise CampaignScreenError(
                        'CAMPAIGN_EARLY_COUNTER_LIMIT', index=sample['index'], role=role,
                        counter=name, baseline=reference_value, observed=value,
                        maximum=reference_value + margin)
            elif name == 'private_commit_bytes' and value * 100 > reference_value * profile.PROFILE.early_private_commit_percent:
                raise CampaignScreenError(
                    'CAMPAIGN_EARLY_PRIVATE_COMMIT_LIMIT', index=sample['index'], role=role,
                    counter=name, baseline=reference_value, observed=value,
                    maximum=reference_value * profile.PROFILE.early_private_commit_percent // 100)
    gap = sample.get('max_status_gap_ms')
    require(type(gap) in (int, float) and gap >= 0 and gap <= profile.PROFILE.max_status_gap_ms,
            'CAMPAIGN_STATUS_GAP')


def write_child_failure(root, *, run_id, batches, progress, error):
    record = {'completed': False, 'formal_acceptance': False,
        'run_id': run_id, 'completed_batches': len(batches), 'phase': progress,
        'code': getattr(error, 'code', type(error).__name__),
        'partial_command': getattr(error, 'report', None)}
    if isinstance(error, CampaignScreenError):
        record['screen_observation'] = error.screen_observation
    write(root / 'child-failure.json', record)


def workstation_profile():
    """Machine facts fixed before samples; free RAM/load are not baseline pins."""
    from ctypes import wintypes as w
    import winreg
    class Memory(ctypes.Structure):
        _fields_ = [('length', w.DWORD), ('load', w.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in ('physical', 'available', 'page_total',
            'page_available', 'virtual_total', 'virtual_available', 'extended_available')]
    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GlobalMemoryStatusEx.argtypes, kernel.GlobalMemoryStatusEx.restype = [ctypes.POINTER(Memory)], w.BOOL
    require(kernel.GlobalMemoryStatusEx(ctypes.byref(memory)), 'CAMPAIGN_MACHINE_MEMORY')
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
        cpu = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    class Display(ctypes.Structure):
        _fields_ = [('cb', w.DWORD), ('name', w.WCHAR * 32), ('description', w.WCHAR * 128),
                    ('flags', w.DWORD), ('device_id', w.WCHAR * 128), ('key', w.WCHAR * 128)]
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.EnumDisplayDevicesW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.POINTER(Display), w.DWORD]
    user.EnumDisplayDevicesW.restype = w.BOOL
    displays = []
    for index in range(32):
        display = Display()
        display.cb = ctypes.sizeof(display)
        if not user.EnumDisplayDevicesW(None, index, ctypes.byref(display), 0):
            break
        displays.append({'description': display.description, 'flags': display.flags})
    require(displays, 'CAMPAIGN_MACHINE_DISPLAY')
    return {'schema_id': 'hh-studio.benchmark-workstation', 'schema_version': '1.0.0',
        'os': platform.win32_ver(), 'machine': platform.machine(), 'cpu': cpu,
        'logical_processors': os.cpu_count(), 'physical_memory_bytes': memory.physical,
        'displays': displays, 'python': platform.python_version(), 'pointer_bits': ctypes.sizeof(ctypes.c_void_p) * 8,
        'renderer': 'gl_compatibility', 'sequence': SEQUENCE,
        'scope': 'current machine fixed before campaign; not a claim of performance on other devices'}


def heavy_preflight_processes(*, all_processes=False):
    """Name/PID inventory only; no command lines, termination or load estimates.

    O4.1 permits app names as inventory, never as a launch prohibition.
    all_processes includes engine names and enables top-private/WSL inventory.
    Unknown snapshot/enumeration/close failures never authorize a launch.
    """
    require(os.name == 'nt', 'CAMPAIGN_PREFLIGHT_PLATFORM')
    from ctypes import wintypes as w
    class Entry(ctypes.Structure):
        _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD),
                    ('heap', ctypes.c_void_p), ('module', w.DWORD), ('threads', w.DWORD),
                    ('parent_pid', w.DWORD), ('base_priority', ctypes.c_long),
                    ('flags', w.DWORD), ('exe', w.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    kernel.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32FirstW.restype = w.BOOL
    kernel.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.restype = w.BOOL
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    require(snapshot not in (None, ctypes.c_void_p(-1).value), 'CAMPAIGN_PREFLIGHT_SNAPSHOT')
    found = []
    primary = None
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        # A Windows process snapshot always includes this caller. Even an
        # empty first result is therefore not a verified clear environment.
        require(kernel.Process32FirstW(snapshot, ctypes.byref(entry)), 'CAMPAIGN_PREFLIGHT_PROCESS_FIRST')
        for _ in range(65536):
            name = entry.exe.lower()
            if all_processes or name in HEAVY_PREFLIGHT_NAMES:
                found.append({'pid': int(entry.pid), 'name': name})
            entry.size = ctypes.sizeof(entry)
            if not kernel.Process32NextW(snapshot, ctypes.byref(entry)):
                require(ctypes.get_last_error() == 18, 'CAMPAIGN_PREFLIGHT_PROCESS_NEXT')  # ERROR_NO_MORE_FILES
                break
        else:
            raise BenchmarkJobError('CAMPAIGN_PREFLIGHT_PROCESS_CAP')
    except BaseException as error:
        primary = error
        raise
    finally:
        if not kernel.CloseHandle(snapshot):
            if primary is None:
                raise BenchmarkJobError('CAMPAIGN_PREFLIGHT_SNAPSHOT_CLOSE')
            primary.add_note('CAMPAIGN_PREFLIGHT_SNAPSHOT_CLOSE')
    return sorted(found, key=lambda row: (row['name'], row['pid']))


def environment_snapshot(*, job_handle=None,
                         docker_inventory=environment._REQUIRE_DOCKER_INVENTORY):
    return environment.native_snapshot(heavy_preflight_processes(all_processes=True),
        job_handle=job_handle, heavy_names=HEAVY_PREFLIGHT_NAMES,
        docker_inventory=docker_inventory)


O9_ROLE_PROCESS_SCHEMA = 'HH-GT06-O9.3-ROLE-PROCESS-BINDING-1'
O9_ROLE_PROCESS_VERSION = '1.0.0'


def _o9_role_binding(context):
    """Return the fixed O9.3 binding carried by every current attempt."""
    return {key: context[key] for key in ('run_id', 'source_closure_sha256', 'campaign_sha256')}


def _o9_role_process_start(value):
    if type(value) is not str or re.fullmatch(r'windows:[1-9][0-9]{0,19}', value) is None:
        return None
    return int(value.split(':', 1)[1])


def _o9_read_role_process_binding(output, context):
    path = output / 'role-process-binding.json'
    if not path.is_file():
        return None
    value = json.loads(read_regular(path))
    require(value.get('schema_id') == O9_ROLE_PROCESS_SCHEMA
            and value.get('schema_version') == O9_ROLE_PROCESS_VERSION,
            'O9_3_ROLE_PROCESS_SCHEMA')
    binding = _o9_role_binding(context)
    require(all(value.get(key) == expected for key, expected in binding.items()),
            'O9_3_ROLE_PROCESS_BINDING')
    roles = value.get('roles')
    require(type(roles) is dict and set(roles) == {'host', 'editor'},
            'O9_3_ROLE_PROCESS_ROLES')
    normalized = {}
    identities = set()
    for role in ('host', 'editor'):
        identity = roles[role]
        require(type(identity) is dict and set(identity) == {'pid', 'process_start'},
                'O9_3_ROLE_PROCESS_IDENTITY')
        start = _o9_role_process_start(identity['process_start'])
        require(type(identity['pid']) is int and identity['pid'] > 0 and start is not None,
                'O9_3_ROLE_PROCESS_IDENTITY')
        key = (identity['pid'], start)
        require(key not in identities, 'O9_3_ROLE_PROCESS_DUPLICATE')
        identities.add(key)
        normalized[role] = {'pid': identity['pid'], 'process_start_100ns': start}
    return {'binding': binding, 'roles': normalized}


def _o9_annotate_role_processes(output, context, row):
    """Label watchdog-owned processes only after exact PID/start binding."""
    binding = _o9_read_role_process_binding(output, context)
    if binding is None:
        return row
    result = dict(row)
    owned = row.get('owned_processes')
    require(type(owned) is list, 'O9_3_ROLE_PROCESS_SAMPLE')
    rows = []
    for process in owned:
        require(type(process) is dict, 'O9_3_ROLE_PROCESS_SAMPLE')
        current = dict(process)
        key = (process.get('pid'), process.get('process_start_100ns'))
        for role, expected in binding['roles'].items():
            if key == (expected['pid'], expected['process_start_100ns']):
                current['role'] = role
                break
        rows.append(current)
    result['owned_processes'] = rows
    return result


def _o9_role_context(output, context, row):
    """Load only complete child previews; missing data stays an O9.3 gap."""
    process_binding = _o9_read_role_process_binding(output, context)
    binding = _o9_role_binding(context)
    samples = []
    for path in sorted(output.glob('sample-preview-*.json')):
        try:
            value = json.loads(read_regular(path))
            index = value.get('index')
            if type(index) is int and 0 <= index <= 34 and type(value.get('memory')) is dict:
                samples.append({'index': index, 'memory': value['memory']})
        except (OSError, ValueError, TypeError):
            continue
    samples = {value['index']: value for value in samples}
    batch_samples = [samples[index] for index in sorted(samples)]
    baseline = None
    if all(index in samples for index in environment.O9_ROLE_BASELINE_BATCHES):
        baseline = profile.baseline_memory_rows(
            [samples[index]['memory'] for index in environment.O9_ROLE_BASELINE_BATCHES],
            '$.o9_role_baseline')
    if batch_samples:
        row = dict(row)
        row['batch_index'] = batch_samples[-1]['index']
    return binding, process_binding, baseline, batch_samples, row


def _o9_role_annotator(output, context):
    return lambda row: _o9_annotate_role_processes(output, context, row)


def _o9_role_classifier(output, context):
    def classify(sample_index, row, decision):
        binding, _process_binding, baseline, batch_samples, trigger = _o9_role_context(output, context, row)
        return environment.classify_role_counter_trigger(
            binding=binding, watchdog_sample_index=sample_index,
            watchdog_row=trigger, baseline_memory=baseline,
            batch_samples=batch_samples, trigger_reason=decision['reason'])
    return classify


def _o9_verify_role_stop(output, context):
    """Rebuild O9.3 attribution from the durable stop row before closeout."""
    stop_path = output / 'watchdog-stop.json'
    if not stop_path.is_file():
        return None
    stop = json.loads(read_regular(stop_path))
    require(type(stop) is dict and stop.get('schema') == 'HH-GT06-WATCHDOG-STOP-1'
            and stop.get('run_id') == context['run_id']
            and stop.get('source_closure_sha256') == context['source_closure_sha256']
            and stop.get('campaign_sha256') == context['campaign_sha256']
            and stop.get('formal_acceptance') is False,
            'O9_3_ROLE_STOP_BINDING')
    role_result = stop.get('role_counter')
    require(type(role_result) is dict, 'O9_3_ROLE_STOP_MISSING')
    require(role_result.get('formal_acceptance') is False
            and role_result.get('classification') in ('INFRA_ABORT', 'PRODUCT_FAIL'),
            'O9_3_ROLE_STOP_SHAPE')
    if role_result.get('evidence') is None:
        require(role_result.get('classification') == 'INFRA_ABORT'
                and role_result.get('reason') == 'ROLE_COUNTER_EVIDENCE_GAP',
                'O9_3_ROLE_STOP_GAP')
        return role_result
    lines = read_regular(output / 'environment-samples.jsonl', 64 * 1024**2).splitlines()
    sample_index = stop.get('sample_index')
    require(type(sample_index) is int and sample_index >= 0 and sample_index < len(lines) - 1,
            'O9_3_ROLE_STOP_INDEX')
    row = environment.unpack_sample(json.loads(lines[sample_index + 1]))
    binding, _process_binding, baseline, batch_samples, trigger = _o9_role_context(output, context, row)
    expected = environment.classify_role_counter_trigger(
        binding=binding, watchdog_sample_index=sample_index,
        watchdog_row=trigger, baseline_memory=baseline,
        batch_samples=batch_samples, trigger_reason=stop['reason'])
    environment.verify_role_counter_evidence(
        role_result['evidence'], binding=binding, watchdog_sample_index=sample_index,
        watchdog_row=trigger, baseline_memory=baseline, batch_samples=batch_samples)
    require(expected['classification'] == role_result['classification']
            and expected['reason'] == role_result.get('reason')
            and expected.get('failures', []) == role_result.get('failures', []),
            'O9_3_ROLE_STOP_RECLASSIFIED')
    return role_result


def _o9_verify_retry_cleanup(output, context):
    """Verify owner cleanup observations before exempting a retry latch."""
    require(type(context) is dict, 'O9_3_RETRY_CONTEXT')
    for role in ('host-owner', 'editor-host'):
        cleanup = json.loads(read_regular(output / role / 'cleanup-001.json'))
        require(type(cleanup) is dict, 'O9_2_RETRY_CLEANUP')
        job = cleanup.get('job')
        wrapper = cleanup.get('wrapper_process_handle')
        require(cleanup.get('closed') is True
                and cleanup.get('completed') is False
                and type(job) is dict and job.get('closed') is True
                and job.get('zero_observed') is True
                and job.get('handle_retained') is False
                and job.get('close_uncertain') is False
                and type(wrapper) is dict and wrapper.get('closed') is True
                and wrapper.get('handle_retained') is False
                and wrapper.get('close_uncertain') is False,
                'O9_2_RETRY_CLEANUP')


def environment_preflight():
    """O4.1 resource/engine gate; app names are inventory only."""
    try:
        return environment.preflight(environment_snapshot())
    except Exception as error:
        return {'schema_id': environment.SCHEMA, 'schema_version': environment.VERSION,
                'observed_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'pass': False, 'failure_code': getattr(error, 'code', type(error).__name__),
                'heavy_processes': None, 'foreign_engines': None,
                'required_heavy_processes_closed': False}


def require_environment_preflight(result):
    environment.require_preflight(result)


def _observe_launch_row(policy, row):
    previous = policy.previous
    require('cpu_observation' in row, 'CAMPAIGN_PREFLIGHT_CPU_OBSERVATION_MISSING')
    failure = policy.observe(row)  # Recomputes recorded per-process CPU too.
    require(failure is None, 'CAMPAIGN_PREFLIGHT_OBSERVATION_' + (failure['reason'] if failure else 'FAILED'))
    require_environment_preflight(environment.preflight(row))
    if previous is None:
        return None
    total = row['cpu_total_100ns'] - previous['cpu_total_100ns']
    idle = row['cpu_idle_100ns'] - previous['cpu_idle_100ns']
    require(total > 0, 'CAMPAIGN_PREFLIGHT_CPU_UNOBSERVED')
    return 100 * (total - idle) / total


def _launch_summary(output, binding, policy, percentages, count):
    span = (policy.previous['uptime_ms'] - policy.first['uptime_ms']) / 1000
    require(60 <= span <= 60 + environment.MAX_SAMPLE_GAP_SECONDS, 'CAMPAIGN_PREFLIGHT_OBSERVATION_DURATION')
    require(percentages and not all(value > 95 for value in percentages), 'CAMPAIGN_PREFLIGHT_CPU_BUSY')
    return {'schema': LAUNCH_OBSERVATION_SCHEMA, **binding, 'sample_count': count,
            'observed_seconds': span, 'cpu_interval_percent': percentages,
            'cpu_max_percent': max(percentages), 'cpu_mean_percent': sum(percentages) / len(percentages),
            'samples': reference(output, output / 'environment-launch-samples.jsonl'),
            'preflight': reference(output, output / 'environment-preflight-before.json'),
            'formal_acceptance': False}


def observe_pair_launch(output, context, check_campaign_stop):
    """A new, bounded minute before every fresh pair; never reuses arm telemetry."""
    binding = {key: context[key] for key in ('run_id', 'source_closure_sha256', 'campaign_sha256')}
    policy, percentages = environment.Policy(), []
    with (output / 'environment-launch-samples.jsonl').open('xb') as stream:
        stream.write(encoded({'schema': LAUNCH_SAMPLE_SCHEMA, **binding}))
        # 13 samples normally span 60 s. One extra tolerates millisecond rounding;
        # a stalled uptime clock cannot turn this into an unbounded observation.
        for count in range(1, 15):
            started = time.monotonic()
            check_campaign_stop()
            verify_sources(context['source_files'])
            row = environment_snapshot()
            row['cpu_observation'] = environment.cpu_interval(policy.previous, row)
            stream.write(encoded(environment.pack_sample(row)))
            stream.flush()
            os.fsync(stream.fileno())
            check_campaign_stop()
            percentage = _observe_launch_row(policy, row)
            if percentage is not None:
                percentages.append(percentage)
            if row['uptime_ms'] - policy.first['uptime_ms'] >= 60_000:
                break
            if count < 14:
                time.sleep(max(0, environment.INTERVAL_SECONDS - (time.monotonic() - started)))
    write(output / 'environment-preflight-before.json', environment.preflight(policy.previous))
    summary = _launch_summary(output, binding, policy, percentages, count)
    write(output / 'launch-observation.json', summary)
    verify_sources(context['source_files'])
    check_campaign_stop()


def verify_launch_observation(output, context, first_run_sample):
    """Current verifier requires the new proof; old captures use their frozen verifier."""
    require(context.get('launch_observation_schema') == LAUNCH_OBSERVATION_SCHEMA,
            'CAMPAIGN_LAUNCH_OBSERVATION_REQUIRED_CURRENT_VERIFIER')
    binding = {key: context[key] for key in ('run_id', 'source_closure_sha256', 'campaign_sha256')}
    lines = read_regular(output / 'environment-launch-samples.jsonl', 64 * 1024**2).splitlines()
    require(lines and json.loads(lines[0]) == {'schema': LAUNCH_SAMPLE_SCHEMA, **binding},
            'CAMPAIGN_LAUNCH_OBSERVATION_BINDING')
    policy, percentages = environment.Policy(), []
    require(2 <= len(lines) - 1 <= 14, 'CAMPAIGN_PREFLIGHT_OBSERVATION_DURATION')
    for line in lines[1:]:
        percentage = _observe_launch_row(policy, environment.unpack_sample(json.loads(line)))
        if percentage is not None:
            percentages.append(percentage)
    require(json.loads(read_regular(output / 'environment-preflight-before.json')) == environment.preflight(policy.previous),
            'CAMPAIGN_LAUNCH_PREFLIGHT_CHANGED')
    expected = _launch_summary(output, binding, policy, percentages, len(lines) - 1)
    require(json.loads(read_regular(output / 'launch-observation.json')) == expected,
            'CAMPAIGN_LAUNCH_OBSERVATION_CHANGED')
    uptime_gap = (first_run_sample['uptime_ms'] - policy.previous['uptime_ms']) / 1000
    awake_gap = (first_run_sample['awake_100ns'] - policy.previous['awake_100ns']) / 10_000_000
    require(0 <= uptime_gap <= environment.MAX_SAMPLE_GAP_SECONDS and awake_gap >= 0
            and abs(uptime_gap - awake_gap) <= .1, 'CAMPAIGN_LAUNCH_OBSERVATION_STALE')



def seal_campaign_capture(root, result):
    """Reuse an identical completed capture without rebinding its environment.

    A later invocation still records its own before/after snapshots; they are
    supplemental observations and cannot replace the completed run's hashes.
    """
    final = root / 'campaign-capture.json'
    if not final.exists():
        write(final, result)
        return final
    previous = json.loads(read_regular(final))
    normalized = dict(result)
    for field, phase in (('environment_preflight_before', 'before'),
                         ('environment_preflight_after', 'after')):
        ref = previous.get(field)
        require(type(ref) is dict and set(ref) == {'file', 'sha256', 'size_bytes'}
                and type(ref['file']) is str
                and re.fullmatch(r'environment/[0-9a-f]{32}-' + phase + r'\.json', ref['file']),
                'CAMPAIGN_ENVIRONMENT_REFERENCE')
        path = root / ref['file']
        require(reference(root, path) == ref, 'CAMPAIGN_ENVIRONMENT_HASH')
        if phase == 'before':
            require_environment_preflight(json.loads(read_regular(path)))
        normalized[field] = ref
    require(previous == normalized, 'CAMPAIGN_EXISTING_CAPTURE_CHANGED')
    return final


def verify_owner_captures(root, context):
    """Delegate raw exits/limits/invocation/source binding to the checked owner."""
    sources = context['source_files']
    verify_capture(root / 'host-owner', sha(read_regular(root / 'host-owner/capture.json')),
        source_root=STUDIO, expected_source_files=sources,
        expected_binary_sha256=sha(read_regular(Path(sys.executable), 256 * 1024**2)),
        expected_campaign_host=True)
    snapshot = json.loads(read_regular(root / 'editor-snapshot.json'))
    runtime = dict(sources)
    runtime.update({(root / 'project' / name).relative_to(STUDIO).as_posix(): value
                    for name, value in snapshot.items() if name != MUTABLE_SCENE})
    lock = json.loads(read_regular(root / 'toolchain.lock.json'))['godot']
    verify_capture(root / 'editor-host', sha(read_regular(root / 'editor-host/capture.json')),
        source_root=STUDIO, expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
    native_job.verify_captured_stage(root / 'import-host', sha(read_regular(root / 'import-host/capture.json')))


def verify_run_capture(root, captured, source_digest, *, campaign_id, index, attempt, campaign_sha256):
    """Re-hash the entire completed run before treating it as resumable."""
    require(captured.get('schema_id') == 'hh-studio.benchmark-owned-run'
            and captured.get('completed') is True and captured.get('source_closure_sha256') == source_digest
            and captured.get('profile_sha256') == profile.PROFILE_SHA256, 'CAMPAIGN_RESUME_BINDING')
    run_id = f'{campaign_id}.r{index:02d}.a{attempt:02d}'
    require(captured.get('index') == index and captured.get('run_id') == run_id, 'CAMPAIGN_RESUME_SLOT')
    context = json.loads(read_regular(root / 'context.json'))
    require(context['index'] == index and context['attempt'] == attempt and context['run_id'] == run_id
            and context['campaign_sha256'] == campaign_sha256
            and context['source_closure_sha256'] == source_digest
            and closure(context['source_files']) == source_digest, 'CAMPAIGN_RESUME_CONTEXT')
    require(context.get('launch_observation_schema') == LAUNCH_OBSERVATION_SCHEMA,
            'CAMPAIGN_LAUNCH_OBSERVATION_REQUIRED_CURRENT_VERIFIER')
    files = captured['artifacts']
    require(type(files) is dict and files, 'CAMPAIGN_RESUME_ARTIFACTS')
    for relative, digest in files.items():
        require(type(relative) is str and '\\' not in relative and not Path(relative).is_absolute()
                and all(part not in ('', '.', '..') for part in relative.split('/')), 'CAMPAIGN_ARTIFACT_PATH')
        require(sha(artifact_bytes(root / relative)) == digest, 'CAMPAIGN_RESUME_ARTIFACT_CHANGED')
    require({'context.json', 'child-result.json', 'child-terminal-cleanup.json',
             'http-phases-final.json', 'journal-timings-final.json', 'import-observation.json',
             'host-owner/capture.json', 'editor-host/capture.json',
             'host-owner/process-start.json', 'host-owner/process-exit.json', 'host-owner/stdout.txt',
             'host-owner/stderr.txt', 'editor-host/process-start.json', 'editor-host/process-exit.json',
             'editor-host/stdout.txt', 'editor-host/stderr.txt'}.issubset(files), 'CAMPAIGN_RESUME_MISSING_ARTIFACTS')
    host = json.loads(read_regular(root / 'host-owner/capture.json'))
    child = json.loads(read_regular(root / 'child-result.json'))
    editor = json.loads(read_regular(root / 'editor-host/capture.json'))
    require(child['source_closure_sha256'] == source_digest and child['completed'] is True
            and child['run_id'] == captured['run_id'] and child['processes'] == captured['processes'],
            'CAMPAIGN_RESUME_CHILD')
    require(child['index'] == index, 'CAMPAIGN_RESUME_CHILD_SLOT')
    for role, value in (('host', host), ('editor', editor)):
        actual = value['actual_process_exit']
        require(value['completed'] is True and value['source_unchanged'] is True
                and value['wrapper_exit_code'] == 0 and actual['exit_code'] == 0
                and actual['pid'] == child['processes'][role]['pid']
                and value['natural_tree_exit'] is True and value['job']['closed'] is True
                and value['job']['zero_observed'] is True and value['job']['tainted'] is False,
                'CAMPAIGN_RESUME_OWNERSHIP')
    require(len(child['batches']) == 35, 'CAMPAIGN_RESUME_BATCH_COUNT')
    verify_child_terminal_cleanup(root, context, child)
    verify_observations(root, context, child)
    require({'environment-preflight-before.json', 'environment-preflight-after.json',
             'environment-samples.jsonl', 'environment-launch-samples.jsonl',
             'launch-observation.json'}.issubset(files), 'CAMPAIGN_ENVIRONMENT_MISSING')
    require_environment_preflight(json.loads(read_regular(root / 'environment-preflight-before.json')))
    environment.require_snapshot(json.loads(read_regular(root / 'environment-preflight-after.json')))
    environment.verify_watchdog(root, read_regular, elapsed_seconds=host['elapsed_seconds'],
                               expected_binding={'run_id': run_id,
                                                 'source_closure_sha256': source_digest,
                                                 'campaign_sha256': campaign_sha256},
                               require_docker_inventory=True)
    first_run_sample = environment.unpack_sample(json.loads(
        read_regular(root / 'environment-samples.jsonl', 64 * 1024**2).splitlines()[1]))
    verify_launch_observation(root, context, first_run_sample)
    verify_owner_captures(root, context)
    return child


def run_campaign(campaign_id, root):
    window_started_mono = time.monotonic()
    from studio.tests.replay.benchmark_job import HELD_OWNERS
    with measurement_window(campaign_id, 'GT06 formal 2x35',
                            safe_to_release=lambda: not HELD_OWNERS):
        return _run_campaign_window(campaign_id, root,
                                     window_started_mono=window_started_mono)


def _run_campaign_window(campaign_id, root, *, window_started_mono=None):
    # Every invocation (including resume) captures fresh, immutable resource
    # observations. A cached PASS must never authorize a later launch.
    invocation = uuid.uuid4().hex
    preflight_path = root / 'environment' / f'{invocation}-before.json'
    after_path = root / 'environment' / f'{invocation}-after.json'
    primary = None
    if window_started_mono is None:
        window_started_mono = time.monotonic()
    try:
        with environment.KeepAwake():
            try:
                return _run_campaign(campaign_id, root, preflight_path, after_path,
                                     window_started_mono=window_started_mono)
            except TypeError as error:
                # Keep lightweight test doubles and old scheduler wrappers
                # source-compatible while the real implementation observes the
                # invocation window.
                if "unexpected keyword argument 'window_started_mono'" not in str(error):
                    raise
                return _run_campaign(campaign_id, root, preflight_path, after_path)
    except BaseException as error:
        primary = error
        raise
    finally:
        # The success path records the after snapshot before binding its hash.
        # Failure paths also retain a snapshot without replacing the real error.
        if preflight_path.exists() and not after_path.exists():
            try:
                write(after_path, environment_preflight())
            except Exception as snapshot_error:
                if primary is None:
                    raise
                primary.add_note('Post-run environment snapshot could not be persisted: '
                                 + type(snapshot_error).__name__)


def _run_campaign(campaign_id, root, preflight_path, after_path, *,
                  window_started_mono=None):
    if window_started_mono is None:
        window_started_mono = time.monotonic()
    load_fixture()  # Same dynamic dependency closure in parent and child.
    before = source_files()
    digest = closure(before)
    machine = workstation_profile()
    lock_raw = read_regular(STUDIO / 'toolchain.lock.json')
    new_campaign = not root.exists()
    frozen_attempts = MAX_ATTEMPTS if new_campaign else campaign_attempt_limit(root)
    frozen = {'schema_id': 'hh-studio.benchmark-campaign', 'schema_version': '1.2.0',
        'campaign_id': campaign_id, 'source_files': before, 'source_closure_sha256': digest,
        'profile_sha256': profile.PROFILE_SHA256, 'workstation': machine, 'sequence': SEQUENCE,
        'toolchain_sha256': sha(lock_raw), 'formal_acceptance': False,
        'python_executable_sha256': sha(read_regular(Path(sys.executable), 256 * 1024**2)),
        'run_count': profile.PROFILE.process_runs, 'batches_per_run': profile.PROFILE.warmup_batches + profile.PROFILE.measured_batches,
        'max_attempts_per_run': frozen_attempts, 'launch_observation_schema': LAUNCH_OBSERVATION_SCHEMA}
    if not new_campaign:
        require(json.loads(read_regular(root / 'campaign.json')) == json.loads(encoded(frozen)),
                'CAMPAIGN_RESUME_SOURCE_OR_MACHINE_CHANGED')
    else:
        root.mkdir(exist_ok=False)
        write(root / 'campaign.json', frozen)
        write(root / 'benchmark-profile.json', json.dumps(asdict(profile.PROFILE), sort_keys=True,
              separators=(',', ':'), allow_nan=False).encode())
        for name, expected in before.items():
            raw = read_regular(STUDIO / name)
            require(sha(raw) == expected, 'CAMPAIGN_FREEZE_CHANGED')
            write(root / 'source/studio' / name, raw)
    lifecycle = None
    lifecycle_path = root / 'campaign-lifecycle.json'
    defer_wait = None
    resuming_deferred = False
    if new_campaign or lifecycle_path.exists():
        lifecycle = ensure_campaign_lifecycle(root, campaign_id=campaign_id,
            source_closure_sha256=digest, profile_sha256=profile.PROFILE_SHA256,
            toolchain_sha256=sha(lock_raw))
        # A previous invocation that deferred remains durable, but must wait
        # for the latest append-only state's five-minute recheck timestamp.
        if (root / 'deferred.json').exists():
            resuming_deferred = (_validate_campaign_state(root, lifecycle).get('state') == 'DEFERRED')
            try:
                require_defer_elapsed(root, lifecycle)
            except CampaignDeferredError as error:
                defer_wait = error
    campaign_sha = sha(read_regular(root / 'campaign.json'))
    authorized_watchdog_slots = set(_watchdog_retry_slots(
        root, lifecycle, source_closure_sha256=digest,
        profile_sha256=profile.PROFILE_SHA256, campaign_sha256=campaign_sha,
        max_attempts=frozen_attempts, window_started_mono=window_started_mono))
    # Resource availability is dynamic evidence, so it is deliberately kept
    # outside campaign.json. Persist the snapshot before enforcing it: a
    # failed preflight must leave a reviewable record and never launch a pair.
    preflight_before = environment_preflight()
    write(preflight_path, preflight_before)
    # Stop/watchdog latches are checked after capturing this invocation's
    # preflight, so a requested stop cannot be masked by resource state and
    # the failed invocation still has complete reviewable evidence.
    require_campaign_running(root, max_attempts=frozen_attempts,
                             allow_watchdog_slots=authorized_watchdog_slots)
    if lifecycle is not None:
        try:
            require_environment_preflight(preflight_before)
        except BenchmarkJobError as error:
            if defer_wait is not None:
                # Preserve the current observed gate code while honoring the
                # latest five-minute receipt.  No new timestamp is appended
                # until a real recheck window opens.
                raise CampaignDeferredError(
                    error.code, reason='WAIT_RECHECK_INTERVAL',
                    next_check_epoch=defer_wait.next_check_epoch,
                    pair_index=defer_wait.pair_index)
            defer_campaign(root, lifecycle, code=error.code,
                           reason='CAMPAIGN_PREFLIGHT', pair_index=None)
        if defer_wait is not None:
            raise defer_wait
        if resuming_deferred:
            _record_campaign_state(root, lifecycle, 'OPEN', reason='DEFER_RECHECK_READY',
                                   code='CAMPAIGN_DEFERRED_RESUMED', now=time.time())
    else:
        require_environment_preflight(preflight_before)
    completed = []
    identities = set()

    def remember(captured):
        for process in captured['processes'].values():
            identity = (process['pid'], process['process_start'])
            require(identity not in identities, 'CAMPAIGN_PROCESS_REUSE')
            identities.add(identity)

    for index in range(profile.PROFILE.process_runs):
        require_campaign_running(root, max_attempts=frozen_attempts,
                                 allow_watchdog_slots=authorized_watchdog_slots)
        finished = []
        attempts = []
        for attempt in range(1, frozen_attempts + 1):
            output = root / f'run-{index:02d}-attempt-{attempt:02d}'
            if not output.exists():
                break
            attempts.append(output)
            capture_path = output / 'run-capture.json'
            if capture_path.is_file():
                captured = json.loads(read_regular(capture_path))
                verify_run_capture(output, captured, digest, campaign_id=campaign_id,
                                   index=index, attempt=attempt, campaign_sha256=campaign_sha)
                finished.append((output, captured))
        require(len(finished) <= 1, 'CAMPAIGN_DUPLICATE_SUCCESS')
        require_campaign_running(root, max_attempts=frozen_attempts,
                                 allow_watchdog_slots=authorized_watchdog_slots)
        if finished:
            output, captured = finished[0]
            measured = profile.summarize_run(json.loads(read_regular(output / 'assembled-run.json', profile.MAX_BYTES)))
            require(measured['status'] == 'PASS', 'CAMPAIGN_RUN_MEASUREMENTS_NOT_PASS')
            remember(captured)
            completed.append({'index': index, 'run_id': captured['run_id'], 'capture': reference(root, output / 'run-capture.json')})
            continue
        # O9.2a: every fresh pair gets its own resource gate.  A transient
        # preflight failure is durable DEFERRED state; no empty attempt slot
        # is created and a later invocation can continue this same closure.
        if lifecycle is not None:
            pair_preflight = environment_preflight()
            try:
                require_environment_preflight(pair_preflight)
            except BenchmarkJobError as error:
                defer_campaign(root, lifecycle, code=error.code,
                               reason='PAIR_PREFLIGHT', pair_index=index)
            try:
                environment.require_infra_budget(root.parent, read_regular)
            except BenchmarkJobError as error:
                defer_campaign(root, lifecycle, code=error.code,
                               reason='INFRA_RETRY_BUDGET', pair_index=index)
        # A failed process pair is never silently reused. Prior attempts must
        # have a parent-captured closed/zero record before starting another.
        for prior in attempts:
            require(not (prior / 'stop-request.json').exists(), 'CAMPAIGN_STOP_LATCHED')
            failure = json.loads(read_regular(prior / 'parent-failure.json'))
            context = json.loads(read_regular(prior / 'context.json'))
            prior_attempt = int(prior.name.rsplit('-attempt-', 1)[1])
            require(context.get('run_id') == f'{campaign_id}.r{index:02d}.a{prior_attempt:02d}'
                    and context.get('source_closure_sha256') == digest
                    and context.get('profile_sha256') == profile.PROFILE_SHA256
                    and context.get('campaign_sha256') == campaign_sha
                    and context.get('index') == index
                    and context.get('attempt') == prior_attempt,
                    'CAMPAIGN_PRIOR_CONTEXT_BINDING')
            require(failure.get('owned_tree_zero') is True and failure.get('owner_closed') is True,
                    'CAMPAIGN_PRIOR_OWNER_HELD')
            _o9_verify_retry_cleanup(prior, context)
            # Only an objectively classified infrastructure abort is eligible
            # for the one fresh same-closure retry. Product and harness rows
            # remain terminal and are never silently replayed.
            if failure.get('classification') != 'INFRA_ABORT':
                code = failure.get('code')
                require(False, code if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', code)
                        else 'CAMPAIGN_PRIOR_FAILURE')
            if (prior / 'watchdog-stop.json').is_file():
                role_stop = _o9_verify_role_stop(prior, context)
                require(type(role_stop) is dict
                        and role_stop.get('classification') == 'INFRA_ABORT',
                        'CAMPAIGN_PRIOR_WATCHDOG_BINDING')
            require(infra_retry_allowed(root, lifecycle,
                                        source_closure_sha256=digest,
                                        profile_sha256=profile.PROFILE_SHA256,
                                        attempt=prior_attempt,
                                        window_remaining_seconds=_window_remaining_seconds(
                                            window_started_mono)),
                    'CAMPAIGN_PRIOR_RETRY_NOT_AUTHORIZED')
            _record_campaign_state(root, lifecycle, 'INFRA_RETRY', pair_index=index,
                                   attempt=prior_attempt,
                                   reason=failure.get('code', 'CAMPAIGN_INFRA_RETRY'))
        require(len(attempts) < frozen_attempts, 'CAMPAIGN_ATTEMPTS_EXHAUSTED')
        attempt = len(attempts) + 1
        while True:
            output = root / f'run-{index:02d}-attempt-{attempt:02d}'
            output.mkdir(exist_ok=False)
            run_id = f'{campaign_id}.r{index:02d}.a{attempt:02d}'
            context = {'run_id': run_id, 'index': index, 'attempt': attempt,
                'source_files': before, 'source_closure_sha256': digest, 'profile_sha256': profile.PROFILE_SHA256,
                'campaign_sha256': sha(read_regular(root / 'campaign.json')),
                'launch_observation_schema': LAUNCH_OBSERVATION_SCHEMA}
            write(output / 'context.json', context)
            write(output / 'source-files.json', before)
            write(output / 'toolchain.lock.json', lock_raw)
            write(output / 'benchmark-profile.json', read_regular(root / 'benchmark-profile.json'))
            for name, expected in before.items():
                raw = read_regular(root / 'source/studio' / name)
                require(sha(raw) == expected, 'CAMPAIGN_FROZEN_COPY_CHANGED')
                write(output / 'source/studio' / name, raw)
            owner = None
            watchdog = None
            primary = None
            try:
                verify_sources(before)
                require_campaign_running(root, max_attempts=frozen_attempts,
                                         allow_watchdog_slots=authorized_watchdog_slots)
                observe_pair_launch(output, context, lambda: require_campaign_running(
                    root, allow_watchdog_slots=authorized_watchdog_slots))
                owner = BenchmarkProcess([sys.executable, '-B', str(Path(__file__).resolve()), '--campaign-id', campaign_id,
                    '--child-index', str(index), '--attempt', str(attempt)], cwd=output, output=output / 'host-owner',
                    source_root=STUDIO, source_files=before,
                    binary_sha256=sha(read_regular(Path(sys.executable), 256 * 1024**2)), campaign_host=True)
                watchdog = environment.Watchdog(output,
                    lambda: environment_snapshot(job_handle=owner.job._handle, docker_inventory=[]),
                    {'run_id': run_id, 'source_closure_sha256': digest, 'campaign_sha256': campaign_sha}, write,
                    docker_probe=environment.running_containers,
                    role_annotator=_o9_role_annotator(output, context),
                    role_classifier=_o9_role_classifier(output, context))
                wait_owned_run(owner, output, run_id=run_id,
                    source_closure_sha256=digest, campaign_sha256=campaign_sha,
                    check_campaign_stop=lambda: require_campaign_running(
                        root, active=output, allow_watchdog_slots=authorized_watchdog_slots), watchdog=watchdog)
                watchdog.close()
                watchdog_binding = {'run_id': run_id, 'source_closure_sha256': digest,
                                    'campaign_sha256': campaign_sha}
                environment.verify_watchdog(output, read_regular, expected_binding=watchdog_binding,
                                            require_docker_inventory=True)
                host = owner.finish()
                environment.verify_watchdog(output, read_regular, elapsed_seconds=host['elapsed_seconds'],
                                            expected_binding=watchdog_binding, require_docker_inventory=True)
                write(output / 'environment-preflight-after.json', environment_preflight())
                require_campaign_running(root, allow_watchdog_slots=authorized_watchdog_slots)
                child = json.loads(read_regular(output / 'child-result.json'))
                require(host['actual_process_exit']['pid'] == child['processes']['host']['pid'], 'CAMPAIGN_HOST_IDENTITY')
                write(output / 'cleanup.json', {'schema_id': 'hh-studio.benchmark-cleanup', 'schema_version': '1.0.0',
                    'run_id': run_id, 'processes': child['processes'], 'host_exit_code': host['actual_process_exit']['exit_code'],
                    'editor_exit_code': child['cleanup']['editor_exit_code'],
                    'owned_tree_zero': host['job']['zero_observed'] and child['cleanup']['editor_owned_tree_zero'],
                    'held_handles': child['cleanup']['held_handles']})
                manifest = {'schema_id': 'hh-studio.benchmark-run-assembly', 'schema_version': '1.0.0',
                    'run_id': run_id, 'index': index, 'profile_sha256': profile.PROFILE_SHA256,
                    'source_closure_sha256': digest, 'processes': child['processes'],
                    'refs': {name: reference(output, output / relative) for name, relative in {
                        'native_index': 'project/benchmark/out/index.json', 'source_manifest': 'source-files.json',
                        'toolchain': 'toolchain.lock.json', 'profile': 'benchmark-profile.json',
                        'native_stdout': 'editor-host/stdout.txt', 'native_stderr': 'editor-host/stderr.txt',
                        'cleanup': 'cleanup.json'}.items()}}
                for name, key in {'native_batches': 'native', 'command_batches': 'command',
                    'joint_observations': 'joint', 'ready_artifacts': 'ready', 'start_artifacts': 'start', 'ack_artifacts': 'ack'}.items():
                    manifest[name] = [row[key] for row in child['batches']]
                assembled = assemble_run(output, manifest)
                require_campaign_running(root, allow_watchdog_slots=authorized_watchdog_slots)
                write(output / 'assembly-manifest.json', manifest)
                write(output / 'assembled-run.json', assembled.value['run'])
                measured = profile.summarize_run(assembled.value['run'])
                write(output / 'measurement-summary.json', measured)
                artifacts = {p.relative_to(output).as_posix(): sha(artifact_bytes(p))
                             for p in sorted(output.rglob('*')) if p.is_file()
                             and '.godot' not in p.relative_to(output).parts}
                captured = {'schema_id': 'hh-studio.benchmark-owned-run', 'schema_version': '1.0.0',
                    'run_id': run_id, 'index': index, 'completed': True, 'source_closure_sha256': digest,
                    'profile_sha256': profile.PROFILE_SHA256, 'processes': child['processes'],
                    'artifacts': artifacts, 'formal_acceptance': False, 'measurement_acceptance': 'RUN_ASSEMBLED_DATASET_PENDING'}
                verify_run_capture(output, captured, digest, campaign_id=campaign_id,
                                   index=index, attempt=attempt, campaign_sha256=campaign_sha)
                require_campaign_running(root, allow_watchdog_slots=authorized_watchdog_slots)
                write(output / 'run-capture.json', captured)
                require_campaign_running(root, allow_watchdog_slots=authorized_watchdog_slots)
                # Complete raw/exit evidence is retained even if its O1 windows
                # fail. A second pair cannot repair a failure in the first pair.
                require(measured['status'] == 'PASS', 'CAMPAIGN_RUN_MEASUREMENTS_NOT_PASS')
                remember(captured)
                completed.append({'index': index, 'run_id': run_id, 'capture': reference(root, output / 'run-capture.json')})
                print('HH_GT06_CAMPAIGN_RUN_COMPLETE ' + json.dumps(completed[-1]), flush=True)
            except BaseException as error:
                primary = error
                owner = owner or getattr(error, 'cleanup_owner', None)
                cleanup_error = None
                if owner is not None:
                    try:
                        owner.close()
                    except BaseException as cleanup:
                        cleanup_error = cleanup
                classification = environment.failure_classification(error, output)
                role_counter_verification = None
                if (output / 'watchdog-stop.json').is_file():
                    try:
                        role_counter_verification = _o9_verify_role_stop(output, context)
                    except BaseException as verification_error:
                        # A stop latch with unverifiable role evidence is a
                        # harness failure. It cannot be retried as an infra
                        # sample and cannot silently inherit the original
                        # watchdog classification.
                        classification = 'HARNESS_FAIL'
                        role_counter_verification = {
                            'status': 'FAIL',
                            'code': getattr(verification_error, 'code', type(verification_error).__name__),
                        }
                try:
                    write(output / 'parent-failure.json', {'completed': False, 'run_id': run_id,
                        'code': getattr(error, 'code', type(error).__name__), 'formal_acceptance': False,
                        'classification': classification,
                        'role_counter_verification': role_counter_verification,
                        'watchdog_persistence_errors': getattr(error, 'watchdog_persistence_errors', []),
                        'attempt_local_date': time.strftime('%Y-%m-%d'),
                        'owner_closed': owner.closed if owner else False,
                        'owned_tree_zero': owner.job.zero_observed if owner and owner.job else False,
                        'cleanup_error': type(cleanup_error).__name__ if cleanup_error else None})
                except BaseException as capture_error:
                    raise error from capture_error
                if cleanup_error is not None:
                    raise error from cleanup_error
                # O9.2 permits one fresh retry only for an objectively
                # classified INFRA_ABORT.  The failed attempt remains raw
                # evidence and is never folded into the eventual dataset.
                if (lifecycle is not None and classification == 'INFRA_ABORT'
                        and attempt < frozen_attempts
                        and owner is not None and owner.closed and owner.job.zero_observed
                        and infra_retry_allowed(root, lifecycle,
                            source_closure_sha256=digest,
                            profile_sha256=profile.PROFILE_SHA256, attempt=attempt,
                            window_remaining_seconds=_window_remaining_seconds(window_started_mono))):
                    # This invocation has now proven the exact failed slot is
                    # eligible for its one same-closure retry. Keep the
                    # authorization live for the next attempt; computing it
                    # only once before the pair loop would re-hit the stop
                    # latch and block the authorized retry.
                    authorized_watchdog_slots.add(output)
                    _record_campaign_state(root, lifecycle, 'INFRA_RETRY', pair_index=index,
                                           attempt=attempt, reason=getattr(error, 'code', type(error).__name__))
                    attempts.append(output)
                    attempt += 1
                    continue
                raise
            finally:
                if watchdog is not None:
                    watchdog.close()
                if owner is not None and primary is None:
                    owner.close()
                if primary is not None and not (output / 'environment-preflight-after.json').exists():
                    try:
                        write(output / 'environment-preflight-after.json', environment_preflight())
                    except Exception as snapshot_error:
                        primary.add_note('Pair after snapshot failed: ' + type(snapshot_error).__name__)
            break
    verify_sources(before)
    # The after snapshot is evidence, not an additional acceptance gate.
    preflight_after = environment_preflight()
    write(after_path, preflight_after)
    require_campaign_running(root, allow_watchdog_slots=authorized_watchdog_slots)
    result = {'schema_id': 'hh-studio.benchmark-campaign-capture', 'schema_version': '1.0.0',
        'campaign_id': campaign_id, 'completed': True, 'formal_acceptance': False,
        'source_closure_sha256': digest, 'profile_sha256': profile.PROFILE_SHA256,
        'campaign_sha256': sha(read_regular(root / 'campaign.json')), 'runs': completed,
        'environment_preflight_before': reference(root, preflight_path),
        'environment_preflight_after': reference(root, after_path),
        'measurement_acceptance': 'REQUIRES_STRICT_ASSEMBLY_AND_REVIEW'}
    final = seal_campaign_capture(root, result)
    runs = []
    for row in completed:
        require_campaign_running(root, allow_watchdog_slots=authorized_watchdog_slots)
        output = root / row['capture']['file'].rsplit('/', 1)[0]
        runs.append(assemble_run(output, json.loads(read_regular(output / 'assembly-manifest.json'))))
    provenance = {'source_closure_sha256': digest, 'toolchain_sha256': sha(lock_raw),
        'workstation_profile_sha256': sha(encoded(machine)), 'driver_sha256': before[Path(__file__).relative_to(STUDIO).as_posix()],
        'capture_manifest_sha256': sha(read_regular(final))}
    dataset = assemble_dataset(provenance, runs)
    summary = profile.summarize_dataset(dataset)
    for name, value in (('dataset.json', dataset), ('summary.json', summary)):
        require_campaign_running(root, allow_watchdog_slots=authorized_watchdog_slots)
        target = root / name
        if target.exists():
            require(json.loads(read_regular(target, profile.MAX_BYTES)) == value, 'CAMPAIGN_FINAL_CHANGED')
        else:
            write(target, value)
    require(summary['status'] == 'PASS', 'CAMPAIGN_MEASUREMENTS_NOT_PASS')
    require_campaign_running(root, allow_watchdog_slots=authorized_watchdog_slots)
    if lifecycle is not None:
        _record_campaign_state(root, lifecycle, 'COMPLETE', now=time.time())
    return 0


def _cleanup_error(stage, error):
    code = getattr(error, 'code', None)
    return {'stage': stage, 'type': type(error).__name__,
            'code': code if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', code) else None}


def _write_observation(root, context, kind, observation):
    """A separate exact artifact; command/sample schemas and gates stay fixed."""
    names = {'http': 'http-phases-final.json', 'import': 'import-observation.json',
             'journal': 'journal-timings-final.json'}
    require(kind in names, 'CAMPAIGN_OBSERVATION_KIND')
    write(root / names[kind], {
        'schema_id': 'hh-studio.benchmark-observation', 'schema_version': '1.0.0',
        'kind': kind, 'run_id': context['run_id'],
        'source_closure_sha256': context['source_closure_sha256'],
        'profile_sha256': context['profile_sha256'],
        'context': reference(root, root / 'context.json'),
        'available': observation is not None, 'observation': observation,
        'missing_reason': 'PRODUCER_NOT_CREATED' if observation is None else None,
        'formal_acceptance': False,
        'scope': 'Always-on bounded observation; no timing/overhead subtraction or acceptance override'})


def verify_observations(root, context, child):
    """Bind the new observation artifacts without treating telemetry as PASS."""
    for kind, name in [('http', 'http-phases-final.json'), ('journal', 'journal-timings-final.json'),
                       ('import', 'import-observation.json')]:
        value = json.loads(read_regular(root / name))
        require(value.get('schema_id') == 'hh-studio.benchmark-observation'
                and value.get('schema_version') == '1.0.0' and value.get('kind') == kind
                and value.get('run_id') == context['run_id']
                and value.get('source_closure_sha256') == context['source_closure_sha256']
                and value.get('profile_sha256') == context['profile_sha256']
                and value.get('context') == reference(root, root / 'context.json')
                and value.get('available') is True and value.get('missing_reason') is None
                and type(value.get('observation')) is dict and value.get('formal_acceptance') is False,
                'CAMPAIGN_OBSERVATION_BINDING')
        if kind == 'http':
            require(value['observation'].get('pid') == child['processes']['host']['pid'],
                    'CAMPAIGN_OBSERVATION_HOST_IDENTITY')
            validate_phase_snapshot(value['observation'], child['processes']['host']['pid'])
        elif kind == 'journal':
            validate_journal_timing_snapshot(value['observation'], child['processes']['host']['pid'])
        else:
            validate_import_snapshot(value['observation'])
            identity = value['observation']['target_identity']
            if identity is not None:
                target = _target_exit_state(root, 'import-host')['actual_target_exit']
                require(target is not None and target['pid'] == identity['pid'],
                        'CAMPAIGN_OBSERVATION_IMPORT_IDENTITY')


def _observed_import(root, context, project, executable, binary_hash, observer, errors):
    """Never let observer cleanup or persistence erase the import's failure."""
    primary = None
    local_errors = []
    try:
        observer.start()
        return native_job.run_trusted_stage(
            [str(executable), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=root / 'import-host', source_files=context['source_files'], source_root=STUDIO,
            binary_sha256=binary_hash)
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            observer.close()
        except BaseException as error:
            local_errors.append(('import_observer_close', error))
        try:
            snapshot = observer.snapshot()
            _write_observation(root, context, 'import', snapshot)
            validate_import_snapshot(snapshot)
        except BaseException as error:
            local_errors.append(('import_observation_receipt', error))
        errors.extend(local_errors)
        if local_errors and primary is None:
            raise BenchmarkJobError('CAMPAIGN_IMPORT_OBSERVATION_INCOMPLETE') from local_errors[0][1]


def _probe_cleanup_state(probe):
    if probe is None:
        return {'present': False}
    return {'present': True, 'handle_retained': probe.handle is not None,
            'close_uncertain': probe.close_uncertain}


def _import_cleanup_state(observer):
    if observer is None:
        return {'present': False}
    snapshot = observer.snapshot()
    fields = ('closed', 'thread_alive', 'handle_retained', 'handle_close_uncertain',
              'probe_handles_released', 'global_held_probe_count', 'error_count')
    return dict(present=True, **{field: snapshot[field] for field in fields})


def _producer_cleanup_state(producer):
    if producer is None:
        return {'present': False}
    host, journal = producer.host, producer.journal
    index = journal._index_store if journal is not None else None
    return {'present': True, 'closed': producer.closed, 'failed': producer.failed,
            'host': None if host is None else {
                'stopped': host._stopped.is_set(), 'closing': host._closing.is_set(),
                'threads_alive': [thread.is_alive() for thread in host._threads],
                'main_socket_closed': host._main.socket.fileno() == -1,
                'control_socket_closed': host._control.socket.fileno() == -1},
            'observer_probe': _probe_cleanup_state(producer.observer.probe)
                if producer.observer is not None else {'present': False},
            'journal': None if journal is None else {
                'cache_closed': journal._cache_closed, 'index_retained': index is not None,
                'database_retained': index._db is not None if index is not None else False,
                'directory_retained': index._dir is not None if index is not None else False}}


def _editor_cleanup_state(owner):
    if owner is None:
        return {'present': False}
    process = owner.process
    return {'present': True, 'closed': owner.closed,
            'job': owner.job.snapshot() if owner.job is not None else None,
            'wrapper_process_handle': owner.process_handle_snapshot(),
            'drain_threads_alive': [thread.is_alive() for thread in owner.threads],
            # close() already waited. Never poll a released native process handle.
            'helper_pid': process.pid if process is not None else None,
            'helper_exit_code': process.returncode if process is not None else None}


def _target_exit_state(root, role):
    """A missing target receipt never inherits its helper's exit code."""
    records, refs = {}, {}
    for kind in ('start', 'exit'):
        path = root / role / f'process-{kind}.json'
        if not path.exists():
            records[kind], refs[kind] = None, None
            continue
        raw = read_regular(path)
        record = json.loads(raw)
        keys = {'pid'} if kind == 'start' else {'pid', 'exit_code'}
        require(type(record) is dict and set(record) == keys
                and type(record['pid']) is int and record['pid'] > 0
                and (kind == 'start' or type(record['exit_code']) is int), 'CAMPAIGN_TERMINAL_EXIT_SHAPE')
        records[kind] = record
        refs[kind] = {'file': path.relative_to(root).as_posix(), 'sha256': sha(raw), 'size_bytes': len(raw)}
    if records['exit'] is not None:
        require(records['start'] is not None and records['start']['pid'] == records['exit']['pid'],
                'CAMPAIGN_TERMINAL_EXIT_IDENTITY')
    return {'actual_target_exit': records['exit'], 'start': refs['start'], 'exit': refs['exit'],
            'missing_reason': 'TARGET_EXIT_NOT_RECORDED' if records['exit'] is None else None,
            'natural_exit_not_inferred': True}


def _finish_child_cleanup(root, context, progress, batches, *, producer, probe, owner,
                          retained, done, thread, primary, errors, import_observer=None):
    """Observe every independent role after all closes, even on body failure.

    Only live checked state and exact target receipts are recorded. This is not
    a successful-run cleanup receipt or a claim about the child's own exit.
    """
    # Keep the existing identity handle until the editor Job is drained. The
    # helper may be killed with its target and never write process-exit.json.
    # A separate failure-only observation preserves that exit without inventing
    # a helper receipt or changing successful-run acceptance.
    owners = [('producer', producer), ('editor_owner', owner), ('editor_probe', probe)]
    if import_observer is not None:
        owners.append(('import_observer', import_observer))
    if retained is not None and all(retained is not value for _, value in owners):
        owners.append(('constructor_owner', retained))
    for stage, action in [('heartbeat_stop', done.set),
                          ('heartbeat_join', lambda: thread.join(2) if thread.ident is not None else None)]:
        try:
            action()
        except BaseException as error:
            errors.append((stage, error))
    seen = set()
    editor_exit_observation = None
    for role, owned in owners:
        if owned is None or id(owned) in seen:
            continue
        seen.add(id(owned))
        if role == 'editor_probe' and primary is not None and owned.handle is not None:
            try:
                editor_exit_observation = owned.exit_observation()
            except BaseException as error:
                errors.append(('editor_exit_observe', error))
        try:
            owned.close()
        except BaseException as error:
            errors.append((role + '_close', error))

    # No close or native probe operation occurs below this point. A failed
    # snapshot cannot skip another role or erase a retained exception owner.
    observations = {'editor_exit_after_cleanup': editor_exit_observation}
    getters = [('heartbeat_alive', thread.is_alive),
               ('producer', lambda: _producer_cleanup_state(producer)),
               ('editor_probe', lambda: _probe_cleanup_state(probe)),
               ('editor_owner', lambda: _editor_cleanup_state(owner)),
               ('import_observer', lambda: _import_cleanup_state(import_observer)),
               ('editor_target', lambda: _target_exit_state(root, 'editor-host')),
               ('import_target', lambda: _target_exit_state(root, 'import-host'))]
    if any(role == 'constructor_owner' for role, _ in owners):
        getters.append(('constructor_owner', lambda: {'present': True,
            'job': retained.snapshot()} if isinstance(retained, native_job.cli_job.Owner)
            else {'present': True, 'state_unavailable': True}))
    for name, getter in getters:
        try:
            observations[name] = getter()
        except BaseException as error:
            observations[name] = None
            errors.append((name + '_observe', error))
    if observations.get('heartbeat_alive') is True:
        errors.append(('heartbeat_alive', BenchmarkJobError('CAMPAIGN_CLEANUP_HELD')))
    try:
        _write_observation(root, context, 'http', producer.phase_snapshot() if producer is not None else None)
    except BaseException as error:
        errors.append(('http_observation_receipt', error))
    try:
        _write_observation(root, context, 'journal',
                           producer.journal_timing_snapshot() if producer is not None else None)
    except BaseException as error:
        errors.append(('journal_observation_receipt', error))
    try:
        context_ref = reference(root, root / 'context.json')
        write_cleanup(root / 'child-terminal-cleanup.json', {
            'schema_id': 'hh-studio.benchmark-child-terminal-cleanup', 'schema_version': '1.0.0',
            'run_id': context['run_id'], 'source_closure_sha256': context['source_closure_sha256'],
            'profile_sha256': context['profile_sha256'], 'context': context_ref,
            'observed_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'observed_mono_us': clock(), 'phase': dict(progress), 'completed_batches': len(batches),
            'primary_error': _cleanup_error('body', primary) if primary is not None else None,
            'errors': [_cleanup_error(stage, error) for stage, error in errors],
            'observations': observations, 'host_actual_exit': None, 'supervisor_actual_exit': None,
            'self_exit_missing_reason': 'NOT_OBSERVABLE_BY_CHILD_TERMINAL_RECORD',
            'scope': 'Post-finally cleanup observations; no benchmark acceptance or natural-exit inference',
            'formal_acceptance': False})
    except BaseException as error:
        errors.append(('terminal_receipt', error))
    if errors:
        failure = primary if primary is not None else BenchmarkJobError('CAMPAIGN_CLEANUP_HELD')
        # Keep every exception (and its cleanup_owner), plus the original role
        # references. Do not replace the initiating error's explicit cause.
        failure.cleanup_errors = tuple(error for _, error in errors)
        failure.cleanup_owners = tuple(owned for _, owned in owners if owned is not None)
        if primary is None:
            raise failure


def verify_child_terminal_cleanup(root, context, child):
    """Current runs require the new receipt; historical frozen runs are unchanged."""
    record = json.loads(read_regular(root / 'child-terminal-cleanup.json'))
    require(record['schema_id'] == 'hh-studio.benchmark-child-terminal-cleanup'
            and record['schema_version'] == '1.0.0' and record['run_id'] == context['run_id']
            and record['source_closure_sha256'] == context['source_closure_sha256']
            and record['profile_sha256'] == context['profile_sha256']
            and record['context'] == reference(root, root / 'context.json')
            and record['completed_batches'] == 35 and record['primary_error'] is None
            and record['errors'] == [] and record['formal_acceptance'] is False,
            'CAMPAIGN_TERMINAL_BINDING')
    observed = record['observations']
    require(observed['heartbeat_alive'] is False and 'constructor_owner' not in observed,
            'CAMPAIGN_TERMINAL_HELD')
    expected_import = {'present': True, 'closed': True, 'thread_alive': False,
        'handle_retained': False, 'handle_close_uncertain': False,
        'probe_handles_released': True, 'global_held_probe_count': 0, 'error_count': 0}
    imported = observed.get('import_observer')
    require(type(imported) is dict and imported.keys() == expected_import.keys()
            and all(type(imported[key]) is type(value) and imported[key] == value
                    for key, value in expected_import.items()), 'CAMPAIGN_TERMINAL_IMPORT_OBSERVER_HELD')
    producer, editor = observed['producer'], observed['editor_owner']
    for probe in (observed['editor_probe'], producer['observer_probe']):
        expected_probe = {'present': True, 'handle_retained': False, 'close_uncertain': False}
        require(type(probe) is dict and probe.keys() == expected_probe.keys()
                and all(probe[key] is value for key, value in expected_probe.items()),
                'CAMPAIGN_TERMINAL_PROBE_HELD')
    host, journal = producer['host'], producer['journal']
    require(producer['present'] is True and producer['closed'] is True
            and host['stopped'] is True and host['closing'] is True
            and all(value is False for value in host['threads_alive'])
            and host['main_socket_closed'] is True and host['control_socket_closed'] is True
            and type(journal) is dict and journal.keys() == {
                'cache_closed', 'index_retained', 'database_retained', 'directory_retained'}
            and journal['cache_closed'] is True and journal['index_retained'] is False
            and journal['database_retained'] is False and journal['directory_retained'] is False,
            'CAMPAIGN_TERMINAL_PRODUCER_HELD')
    capture = json.loads(read_regular(root / 'editor-host/capture.json'))
    require(editor['present'] is True and editor['closed'] is True
            and all(value is False for value in editor['drain_threads_alive'])
            and type(editor['helper_exit_code']) is int and editor['helper_exit_code'] == 0
            and editor['helper_exit_code'] == capture['wrapper_exit_code']
            and type(editor['helper_pid']) is int and editor['helper_pid'] > 0
            and editor['helper_pid'] != capture['actual_process_exit']['pid']
            and encoded(editor['job']) == encoded(capture['job'])
            and encoded(editor['wrapper_process_handle']) == encoded(capture['wrapper_process_handle']),
            'CAMPAIGN_TERMINAL_OWNER_HELD')
    for role in ('editor', 'import'):
        target = _target_exit_state(root, role + '-host')
        require(observed[role + '_target'] == target and target['actual_target_exit'] is not None
                and target['actual_target_exit']['exit_code'] == 0, 'CAMPAIGN_TERMINAL_TARGET_EXIT')
    require(observed['editor_target']['actual_target_exit']['pid'] == child['processes']['editor']['pid']
            and record['host_actual_exit'] is None and record['supervisor_actual_exit'] is None,
            'CAMPAIGN_TERMINAL_EXIT_SCOPE')


def run_child(root):
    factory, trusted = load_fixture()
    context = json.loads(read_regular(root / 'context.json'))
    before, run_id = context['source_files'], context['run_id']
    verify_sources(before)
    lock = json.loads(read_regular(STUDIO / 'toolchain.lock.json'))['godot']
    executable = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
        'run_id': run_id, 'mode': 'full', 'source_closure_sha256': closure(before),
        'profile_sha256': profile.PROFILE_SHA256, 'batch_barrier': 'host_ack_v1', 'batch_start': 'host_permit_v1'}
    project = root / 'project'
    initial = prepare(project, factory, trusted, binding)
    (project / 'benchmark/input').mkdir()
    write(root / 'initial-project-files.json', initial)
    owner = producer = probe = import_observer = None
    done = threading.Event()
    progress = {'batch': -1, 'phase': 'import'}

    def heartbeat():
        while not done.wait(1):
            print('HH_GT06_CAMPAIGN_PROGRESS ' + json.dumps({'run_id': run_id, **progress}), flush=True)

    thread = threading.Thread(target=heartbeat, daemon=True)
    batches = []
    baseline_memory = None
    warmup_samples = []
    primary = retained = None
    cleanup_errors = []
    try:
        thread.start()
        import_observer = ImportObserver(root / 'import-host', project, executable)
        imported = _observed_import(root, context, project, executable, lock['gui_sha256'],
                                    import_observer, cleanup_errors)
        native_job.verify_captured_stage(root / 'import-host', sha(read_regular(root / 'import-host/capture.json')))
        require(not list((project / 'benchmark/out').iterdir()), 'CAMPAIGN_IMPORT_ACTIVATED')
        snapshot = project_files(project)
        require(all(snapshot.get(name) == value for name, value in initial.items()), 'CAMPAIGN_IMPORT_DRIFT')
        write(root / 'editor-snapshot.json', snapshot)
        runtime_sources = dict(before)
        runtime_sources.update({(project / name).relative_to(STUDIO).as_posix(): value
                               for name, value in snapshot.items() if name != MUTABLE_SCENE})
        owner = BenchmarkProcess([str(executable), '--editor', '--path', str(project), 'res://scenes/fixture.tscn',
            '--', '--hh-benchmark-mode=full'], cwd=project, output=root / 'editor-host', source_root=STUDIO,
            source_files=runtime_sources, binary_sha256=lock['gui_sha256'])
        log = NativeLog(owner)
        probe = open_probe(owner, executable)
        producer = CampaignProducer(root / 'commands', run_id, log)
        processes = {'host': dict(producer.identity), 'editor': {'pid': probe.pid, 'process_start': probe.process_start}}
        write(root / 'role-process-binding.json', {
            'schema_id': O9_ROLE_PROCESS_SCHEMA, 'schema_version': O9_ROLE_PROCESS_VERSION,
            'run_id': run_id, 'source_closure_sha256': closure(before),
            'campaign_sha256': context['campaign_sha256'],
            'roles': processes})
        for index in range(35):
            progress.update(batch=index, phase='ready')
            ready_marker = log.wait('READY', index, 20)
            ready_path = project / f'benchmark/out/ready-{index:02d}.json'
            ready_raw = read_regular(ready_path)
            ready = json.loads(ready_raw)
            require(ready_marker['sha256'] == sha(ready_raw), 'CAMPAIGN_READY_HASH')
            require(ready['run_id'] == run_id and ready['batch_index'] == index
                    and ready['source_closure_sha256'] == closure(before)
                    and ready['profile_sha256'] == profile.PROFILE_SHA256, 'CAMPAIGN_READY_BINDING')
            started = clock()
            progress['phase'] = 'commands'
            command_path = root / f'command-{index:02d}.json'
            report = producer.run_batch(index)
            write(command_path, report)
            command_ref = reference(root, command_path)
            effect_count = report['effect_count_after']
            del report
            gc.collect()
            start_path = project / f'benchmark/input/start-{index:02d}.json'
            start = {'schema_id': 'hh-studio.native-cycle-batch-start', 'schema_version': '1.0.0',
                'run_id': run_id, 'batch_index': index, 'source_closure_sha256': closure(before),
                'profile_sha256': profile.PROFILE_SHA256, 'command_batch_sha256': command_ref['sha256'],
                'ready_sha256': sha(ready_raw), 'deadline_mono_us': ready['deadline_mono_us']}
            publish(start_path, start)
            progress['phase'] = 'native_cycles'
            marker = log.wait('BATCH', index, 185)
            native_path = project / f'benchmark/out/batch-{index:02d}.json'
            native_raw = read_regular(native_path)
            native = json.loads(native_raw)
            require(marker['sha256'] == sha(native_raw) and native['pid'] == probe.pid
                    and native['run_id'] == run_id and native['index'] == index
                    and len(native['cycles']) == len(native['raw_timings']) == 100, 'CAMPAIGN_NATIVE_BATCH')
            for cycle, timing in zip(native['cycles'], native['raw_timings']):
                validate_cycle_timing(timing, cycle, native['memory'], native)
            progress['phase'] = 'joint_observation'
            host = producer._observe()
            editor = sample_editor(probe)
            ack_path = project / f'benchmark/input/ack-{index:02d}.json'
            ack = {'schema_id': 'hh-studio.native-cycle-batch-ack', 'schema_version': '1.0.0',
                'run_id': run_id, 'batch_index': index, 'native_batch_sha256': sha(native_raw),
                'source_closure_sha256': closure(before), 'profile_sha256': profile.PROFILE_SHA256,
                'deadline_mono_us': native['barrier']['deadline_mono_us']}
            ack_written = publish(ack_path, ack)
            receipt = log.wait('ACK', index, 30)
            ended = clock()
            editor['native_observation'] = {'source': 'native_ack',
                'native_mono_us': receipt['ack_observed_mono_us'], 'process_frame': receipt['process_frame'],
                'objects': receipt['objects'], 'resources': receipt['resources']}
            joint_path = root / f'joint-{index:02d}.json'
            joint = {'schema_id': 'hh-studio.benchmark-joint-observation', 'schema_version': '1.2.0',
                'run_id': run_id, 'index': index, 'profile_sha256': profile.PROFILE_SHA256,
                'source_closure_sha256': closure(before), 'native_batch_sha256': sha(native_raw),
                'command_batch_sha256': command_ref['sha256'], 'processes': processes,
                'phase': 'post_batch_quiescent', 'host_window': {'started_mono_us': started,
                    'ended_mono_us': ended, 'ack_written_mono_us': ack_written},
                'host': {'monotonic_us': host['monotonic_us'], 'counters': host['counters']},
                'editor': editor, 'host_effect_count': effect_count, 'barrier_receipt': receipt,
                'ack_ref': reference(root, ack_path)}
            write(joint_path, joint)
            batches.append({'index': index, 'command': command_ref, 'native': reference(root, native_path),
                'joint': reference(root, joint_path), 'ack': reference(root, ack_path),
                'ready': reference(root, ready_path), 'start': reference(root, start_path)})
            write(root / f'batch-capture-{index:02d}.json', batches[-1])
            bound = {name: read_artifact(root, ref) for name, ref in batches[-1].items() if name != 'index'}
            sample = assemble_sample(bound['native'], bound['command'], bound['joint'],
                run_id=run_id, index=index, processes=processes, source_closure_sha256=closure(before),
                barrier_receipt=receipt, ack=bound['ack'], ready=bound['ready'], start=bound['start'])
            write(root / f'sample-preview-{index:02d}.json', sample)
            screen_sample(sample, baseline_memory)
            if 2 <= index <= 4:
                warmup_samples.append(sample)
            if index == 4:
                baseline_memory = profile.baseline_memory_rows([row['memory'] for row in warmup_samples],
                                                               '$.campaign_baseline')
            del native, native_raw, joint, editor, host, receipt
            del bound, sample
            gc.collect()
        progress['phase'] = 'draining'
        while log.poll() is None:
            time.sleep(.02)
        native_capture = owner.finish()
        require(not (root / 'editor-host/stderr.txt').read_bytes().strip(), 'CAMPAIGN_NATIVE_STDERR')
        index_path = project / 'benchmark/out/index.json'
        native_index = json.loads(read_regular(index_path))
        require(native_index['schema_version'] == '1.3.0'
                and native_index['completed'] is True and native_index['benchmark_complete'] is True
                and native_index['input'] == binding and native_index['pid'] == probe.pid
                and len(native_index['host_barriers']) == len(native_index['batches']) == 35,
                'CAMPAIGN_NATIVE_COMPLETION')
        first_ready = json.loads(read_regular(project / 'benchmark/out/ready-00.json'))
        first_batch = json.loads(read_regular(project / 'benchmark/out/batch-00.json'))
        validate_startup_readiness(native_index['startup_readiness'], binding=binding,
            pid=probe.pid, source_files={name: snapshot[name.removeprefix('res://')]
                for name in native_index['source_files']},
            baseline_revision=native_index['baseline_revision'],
            scene_file_sha256=snapshot[MUTABLE_SCENE],
            first_batch_started_mono_us=first_batch['started_mono_us'],
            first_cycle_root_before=first_batch['cycles'][0]['root_before'],
            run_started_mono_us=native_index['started_mono_us'],
            first_ready_mono_us=first_ready['issued_mono_us'],
            first_ready_frame=first_ready['process_frame'])
        expected_inputs = {f'benchmark/input/{kind}-{i:02d}.json' for kind in ('ack', 'start') for i in range(35)}
        after = project_files(project)
        require({k: v for k, v in after.items() if k != MUTABLE_SCENE and k not in expected_inputs}
                == {k: v for k, v in snapshot.items() if k != MUTABLE_SCENE}, 'CAMPAIGN_PROJECT_DRIFT')
        probe.close()
        producer.close()
        # Derive the retained owner/probe handle count after checked cleanup.
        # The parent independently verifies its wrapper handle after host exit.
        held_handles = sum((
            int(native_capture['job']['handle_retained']),
            int(native_capture['wrapper_process_handle']['handle_retained']),
            int(probe.handle is not None),
            int(producer.observer.probe.handle is not None),
        ))
        require(owner.closed and producer.closed and held_handles == 0, 'CAMPAIGN_CLEANUP_HELD')
        verify_sources(before)
        write(root / 'child-result.json', {'completed': True, 'formal_acceptance': False,
            'run_id': run_id, 'index': context['index'], 'sequence': SEQUENCE, 'processes': processes,
            'source_closure_sha256': closure(before), 'profile_sha256': profile.PROFILE_SHA256,
            'batches': batches, 'native_index': reference(root, index_path),
            'editor_capture': reference(root, root / 'editor-host/capture.json'),
            'import_capture': reference(root, root / 'import-host/capture.json'),
            'source_unchanged': True, 'cleanup': {'editor_exit_code': native_capture['actual_process_exit']['exit_code'],
                'editor_owned_tree_zero': native_capture['job']['zero_observed'], 'held_handles': held_handles},
            'host_exit_not_yet_observed': True})
    except BaseException as error:
        primary = error
        retained = getattr(error, 'cleanup_owner', None)
        if owner is None and isinstance(retained, BenchmarkProcess):
            owner = retained
        elif producer is None and isinstance(retained, CommandProducer):
            producer = retained
        elif probe is None and isinstance(retained, ProcessProbe):
            probe = retained
        try:
            write_child_failure(root, run_id=run_id, batches=batches, progress=progress, error=error)
        except BaseException as receipt_error:
            cleanup_errors.append(('failure_receipt', receipt_error))
        raise
    finally:
        _finish_child_cleanup(root, context, progress, batches, producer=producer, probe=probe,
            owner=owner, retained=retained, done=done, thread=thread, primary=primary, errors=cleanup_errors,
            import_observer=import_observer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-id', required=True)
    parser.add_argument('--child-index', type=int)
    parser.add_argument('--attempt', type=int)
    args = parser.parse_args()
    require(os.name == 'nt' and re.fullmatch(r'gt06-[a-z0-9-]{1,25}', args.campaign_id), 'CAMPAIGN_ID')
    root = STUDIO / '.local/reviews' / args.campaign_id
    if args.child_index is not None:
        require(0 <= args.child_index < profile.PROFILE.process_runs and type(args.attempt) is int and 1 <= args.attempt <= MAX_ATTEMPTS,
                'CAMPAIGN_CHILD_ARGUMENTS')
        run_child(root / f'run-{args.child_index:02d}-attempt-{args.attempt:02d}')
        return 0
    require(args.attempt is None, 'CAMPAIGN_ARGUMENTS')
    return run_campaign(args.campaign_id, root)


if __name__ == '__main__':
    raise SystemExit(main())

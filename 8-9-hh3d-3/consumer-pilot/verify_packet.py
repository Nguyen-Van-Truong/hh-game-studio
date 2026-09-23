"""Verify the S177 freeze from disk or Git blobs, with optional local raw audit.

This is evidence-integrity validation, never pilot or GT06 acceptance. It
starts no engine and writes no result into the frozen packet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

from run_runtime import verify_report

ROOT = Path(__file__).resolve().parents[2]
SCOPE = '8-9-hh3d-3/'
PACKET = SCOPE + 'zdoc/reviews/20260923-consumer-pilot-s177/'
MANIFEST = PACKET + 'manifest-s177-v3.json'
LIVE_PLAN = SCOPE + 'zdoc/8-9-godot-blender-agent-studio-plan.txt'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


class Reader:
    def __init__(self, root=ROOT, ref=None):
        self.root, self.ref = Path(root), ref

    def __call__(self, relative):
        path = PurePosixPath(relative)
        need(relative.startswith(SCOPE) and '\\' not in relative and ':' not in relative
             and '..' not in path.parts and not path.is_absolute(), 'unsafe packet path')
        if self.ref:
            return subprocess.check_output(['git', 'show', self.ref + ':' + relative], cwd=self.root)
        resolved = (self.root / relative).resolve()
        resolved.relative_to(self.root.resolve())
        return resolved.read_bytes()


def verify(read, manifest_path=MANIFEST):
    manifest = json.loads(read(manifest_path))
    need(manifest['schema'] in ('HH-CONSUMER-PILOT-S177-MANIFEST-2', 'HH-CONSUMER-PILOT-S177-MANIFEST-3')
         and manifest['authority'] == 0 and manifest['gt06_acceptance'] is False
         and manifest['pilot_acceptance'] is False, 'packet scope/schema')
    need(manifest_path not in manifest['files'], 'manifest cannot hash itself')
    for path, row in manifest['files'].items():
        data = read(path)
        need(digest(data) == row['sha256'] and len(data) == row['bytes'], 'packet drift: ' + path)
    if manifest['schema'].endswith('-3'):
        snapshot = manifest['plan_snapshot']
        need(snapshot == PACKET + 'plan-s179-snapshot.txt' and snapshot in manifest['files']
             and LIVE_PLAN not in manifest['files'], 'immutable plan snapshot required')
        need(manifest['files'][snapshot]['sha256'] == manifest['plan_at_execution_sha256'],
             'execution plan binding')
    unchecked_read = read
    def read(path):
        need(path == manifest_path or path in manifest['files'], 'unhashed evidence: ' + path)
        return unchecked_read(path)
    runtime = json.loads(read(PACKET + 'runtime/manifest.json'))
    original = json.loads(read(PACKET + 'runtime/result.json'))
    report = json.loads(read(PACKET + 'runtime/report.json'))
    validation = json.loads(read(SCOPE + 'zdoc/reviews/20260923-consumer-pilot-s177-derived/runtime-validation-01.json'))
    need(validation['original_result_sha256'] == digest(read(PACKET + 'runtime/result.json'))
         and validation['manifest_sha256'] == digest(read(PACKET + 'runtime/manifest.json'))
         and validation['report_sha256'] == digest(read(PACKET + 'runtime/report.json'))
         and validation['engine_log_sha256'] == digest(read(PACKET + 'runtime/godot.log')), 'derived/raw binding')
    need(original['run_id'] == runtime['run_id'] == report['run_id'] == validation['run_id'], 'runtime identity')
    for name, sha in runtime['runtime_sources'].items():
        need(digest(read(SCOPE + 'consumer-pilot/' + name)) == sha, 'executed runtime source differs: ' + name)
    for name, row in runtime['inputs'].items():
        need(digest(read(SCOPE + 'consumer-pilot/input/' + name)) == row['sha256'], 'executed input differs: ' + name)
    for label in ('parse', 'runtime'):
        host = original['hosts'][label]
        receipt = json.loads(read(PACKET + 'runtime/' + label + '-host.json'))
        need(host['exit_code'] == receipt['exit_code'] == host['wrapper_exit_code'] == 0
             and host['target_pid'] == receipt['target_pid'] and host['tree_verified'] is True
             and host['timed_out'] is False, label + ' exit/cleanup mismatch')
    need(report['pid'] == original['hosts']['runtime']['target_pid'], 'report PID')
    verify_report(report, runtime, original['hosts']['runtime'])
    need(not read(PACKET + 'runtime/parse-stderr.txt') and not read(PACKET + 'runtime/runtime-stderr.txt'), 'stderr')
    lines = read(PACKET + 'runtime/godot.log').decode('utf-8').splitlines()
    need(lines.count('HH_CONSUMER_PILOT_PASS') == 1
         and not any('ERROR' in line or 'WARNING' in line for line in lines), 'runtime log')
    need(original['runtime_checks_passed'] is False and original['failure'] == 'unique completion marker',
         'preserve original collector failure')
    need(validation['runtime_checks_passed'] is True and validation['engine_started'] is False,
         'derived verdict scope')
    return {'integrity_verified': True, 'files': len(manifest['files']), 'manifest_sha256': digest(read(manifest_path)),
            'engine_started': False, 'pilot_acceptance': False, 'gt06_acceptance': False}


def verify_archive(read, root=ROOT):
    receipt = json.loads(read(PACKET + 'raw-archive.json'))
    archive = Reader(root)(receipt['path'])
    need(digest(archive) == receipt['sha256'] and len(archive) == receipt['bytes'], 'local raw archive drift')
    return {'local_archive_verified': True, 'members': receipt['members']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', help='Read exact Git blobs, e.g. HEAD; omit for current disk bytes')
    parser.add_argument('--manifest', default=MANIFEST, help='Exact packet manifest; use v2 with its historical --ref')
    parser.add_argument('--with-archive', action='store_true', help='Also hash the local raw archive; no engine')
    args = parser.parse_args()
    reader = Reader(ref=args.ref)
    result = verify(reader, args.manifest)
    if args.with_archive:
        result.update(verify_archive(reader))
    print(json.dumps(result))

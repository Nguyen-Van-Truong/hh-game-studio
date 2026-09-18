"""Publish actual verified GT05 assets into a new protected staged snapshot.

Internal coordinator runner only. The fixed evidence IDs come from a local
verification invocation; every gate is recomputed by the installed provider.
Verification has its own 60-second wall budget, separate from 20-second engine
stages. The bounded bootstrap Job owns the entire verification/storage child.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio.protocol.core import canonical_bytes
from studio.host.core.journal import Journal
from studio.pipeline import snapshot_state as model
from studio.pipeline.snapshot_owner import SnapshotOwner, epoch_ms
from studio.pipeline.snapshot_provider import CapturedSnapshotProvider, RUN_ROLES
from studio.pipeline.run_validation import owned_run
from run_unit_suite import source_files, sha, write


def need(value, label):
    if not value:
        raise AssertionError(label)


def worker(output):
    config = json.loads((output / 'invocation.json').read_bytes())
    files = config['source_files']
    need(source_files(STUDIO) == files, 'source changed before publication')
    provider = CapturedSnapshotProvider(STUDIO, runs=config['runs'], source_files=files)
    journal = Journal(output / 'journal.jsonl')
    lease = journal.acquire_lease(project_id=model.PROJECT, target=model.TARGET,
        owner='captured-pipeline-coordinator', now_ms=epoch_ms(), ttl_ms=120000)
    request = {'schema': model.SCHEMA, 'profile': model.PROFILE, 'command_id': 'snapshot.actual-assets',
        'expected_source_sha256': provider.current_source()}
    owner = SnapshotOwner.create(output, journal=journal, provider=provider, current_source=provider.current_source)
    storage_id = owner.storage_id
    try:
        raw = owner.publish(request, lease, deadline_ms=epoch_ms() + 60000)
        reply = json.loads(raw)
        need(reply['status'] == 'COMMITTED' and reply['public_ack'] is False, 'staged receipt')
        manifest, payloads = owner.read_selected()
        proof = provider.last_proof
        need(proof is not None and proof['publishable'] is True and proof['current_source_verified'] is True,
             'complete provider proof')
        for name, value in payloads.items():
            need(manifest['artifacts'][name] == {'sha256': sha(value), 'size_bytes': len(value)}, 'protected readback')
        first_proof = provider.last_proof
        retry = owner.publish(request, lease, deadline_ms=epoch_ms() + 60000)
        need(retry == raw and provider.last_proof is first_proof, 'retry repeated verification')
        write(output / 'verified-chain.json', proof)
        write(output / 'publication-manifest.json', manifest)
        with (output / 'receipt.json').open('xb') as stream:
            stream.write(raw)
        expected_payloads = {name: sha(value) for name, value in payloads.items()}
    finally:
        owner.close()
    recovered = SnapshotOwner.reopen(storage_id)
    try:
        replay = recovered.lookup_bytes(request['command_id'], sha(canonical_bytes(request)))
        manifest2, payloads2 = recovered.read_selected()
        need(replay == raw and manifest2 == manifest
             and {name: sha(value) for name, value in payloads2.items()} == expected_payloads, 'readonly recovery')
    finally:
        recovered.close()
    # A fresh writer owner using the same durable command journal must route to
    # the original immutable snapshot without invoking its new provider.
    duplicate_provider = CapturedSnapshotProvider(STUDIO, runs=config['runs'], source_files=files)
    duplicate = SnapshotOwner.create(output, journal=journal, provider=duplicate_provider,
                                     current_source=duplicate_provider.current_source)
    try:
        routed = duplicate.publish(request, lease, deadline_ms=epoch_ms() + 60000)
        need(routed == raw and duplicate_provider.last_proof is None, 'cross-owner dedupe repeated provider')
        need({path.name for path in duplicate.files.root.iterdir()} == {'.writer'}, 'duplicate wrote assets')
    finally:
        duplicate.close()
    need(source_files(STUDIO) == files, 'source changed during publication')
    result = {'schema': 'HH-GT05-ACTUAL-SNAPSHOT-CAPTURE-1', 'storage_id': storage_id,
        'request': request, 'receipt_sha256': sha(raw), 'payload_sha256': expected_payloads,
        'verified_chain_sha256': sha((output / 'verified-chain.json').read_bytes()),
        'manifest_sha256': sha((output / 'publication-manifest.json').read_bytes()),
        'same_owner_exact_retry': True, 'readonly_reopen_exact_retry': True,
        'cross_owner_exact_retry_without_provider': True, 'current_source_verified': True,
        'complete_chain_verified': True, 'public_ack': False, 'editor_activation': False,
        'formal_acceptance': False}
    write(output / 'observed.json', result)
    print('GT05_ACTUAL_SNAPSHOT ' + json.dumps({'observed_sha256': sha((output / 'observed.json').read_bytes()),
        'receipt_sha256': sha(raw), 'status': 'COMMITTED', 'public_ack': False}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id')
    parser.add_argument('--chain-id')
    parser.add_argument('--worker', type=Path)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    chain = owned_run(args.chain_id)
    supplied = json.loads((chain / 'invocation.json').read_bytes())
    runs = {role: supplied[role] for role in RUN_ROLES}
    output = owned_run(args.run_id)
    output.mkdir(exist_ok=False)
    files = source_files(STUDIO)
    for name, digest in files.items():
        raw = (STUDIO / name).read_bytes()
        need(sha(raw) == digest, 'source changed before snapshot')
        target = output / 'source' / (sha(name.encode()) + Path(name).suffix)
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(raw)
    write(output / 'invocation.json', {'runs': runs, 'source_files': files,
        'source_closure_sha256': sha(canonical_bytes(files)), 'worker_timeout_seconds': 90,
        'verification_deadline_seconds': 60, 'python_sha256': sha(Path(sys.executable).read_bytes())})
    path = STUDIO / 'build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('gt05_actual_snapshot_owned', path)
    runner = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), runner.__dict__)
    host = runner.run_process([sys.executable, '-B', str(Path(__file__).resolve()), '--worker', str(output)],
        cwd=STUDIO, output=output, timeout=90, label='publication')
    stable = source_files(STUDIO) == files
    passed = stable and host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified'] and not host['timed_out']
    if passed:
        raw = (output / 'observed.json').read_bytes()
        observed = json.loads(raw)
        markers = [json.loads(line[len('GT05_ACTUAL_SNAPSHOT '):])
            for line in (output / host['stdout']).read_text(encoding='utf-8').splitlines()
            if line.startswith('GT05_ACTUAL_SNAPSHOT ')]
        passed = markers == [{'observed_sha256': sha(raw), 'receipt_sha256': observed['receipt_sha256'],
                              'status': 'COMMITTED', 'public_ack': False}]
        passed = passed and sha((output / 'receipt.json').read_bytes()) == observed['receipt_sha256']
        passed = passed and sha((output / 'verified-chain.json').read_bytes()) == observed['verified_chain_sha256']
        passed = passed and sha((output / 'publication-manifest.json').read_bytes()) == observed['manifest_sha256']
    result = {'host': host, 'source_unchanged': stable, 'passed': passed, 'formal_acceptance': False}
    write(output / 'capture.json', result)
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

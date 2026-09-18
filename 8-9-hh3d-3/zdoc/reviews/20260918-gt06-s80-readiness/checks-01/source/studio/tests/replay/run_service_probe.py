"""Coordinator-only bounded real HTTP/Play probe; never acceptance by itself."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
from pathlib import Path
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.replay import native_runner as native, contract
from studio.host.replay.backend import PreparedPlay, BackendError
from studio.host.replay.service import ReplayService
from studio.host.replay.transport import ReplayTransport
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Request, Response, canonical_bytes, parse_json


def run(run_id, mode):
    driver_sha = native.sha(Path(__file__).read_bytes())
    backend = owner = server = None
    checks = []
    try:
        try:
            backend = PreparedPlay.prepare(run_id)
        except BackendError as error:
            backend = error.cleanup_owner
            raise
        output = backend.root / 'http-probe'
        output.mkdir()
        owner = ReplayService(backend)
        credential = owner.sessions.issue(ttl_ms=110_000)
        server = ReplayTransport(owner).start()
        sequence = 0

        def check(label, value):
            checks.append({'label': label, 'passed': value is True})
            native.need(value is True, label)

        def call(path, body, *, bearer=None):
            nonlocal sequence
            port = server.stop_port if path == '/v1/stop' else server.control_port if path == '/v1/lookup' else server.port
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=22)
            try:
                started = time.perf_counter_ns()
                connection.request('POST', path, canonical_bytes(body), {'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + (bearer or credential.bearer), 'X-HH-Catalog': contract.CATALOG_DIGEST})
                response = connection.getresponse()
                raw = response.read(262145)
                elapsed = (time.perf_counter_ns() - started) / 1000000
                native.need(len(raw) <= 262144, 'PROBE_RESPONSE_CAP')
                parsed = parse_json(raw)
                # Tokens/headers never enter recorded requests or diagnostics.
                if path != '/v1/lookup' or parsed.get('status') != 'ACCEPTED_PENDING':
                    native.write(output / ('http-' + str(sequence) + '.json'), {'route': path, 'body': body,
                        'status_code': response.status, 'response': parsed, 'elapsed_ms': elapsed})
                    sequence += 1
                return response.status, parsed, raw, elapsed
            finally:
                connection.close()

        code, _, _, _ = call('/v1/discovery', {'project_id': owner.project_id}, bearer='z' * 43)
        check('foreign_bearer_denied', code == 400)
        code, discovery, _, _ = call('/v1/discovery', {'project_id': owner.project_id})
        check('fixed_catalog_discovered', code == 200 and discovery['schema_digest'] == contract.CATALOG_DIGEST)
        code, lease, _, _ = call('/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 30_000})
        check('actual_bound_lease', code == 200 and lease['binding'] == backend.binding)
        binding = backend.binding
        preconditions = {'expected_generation': binding['generation'],
            'expected_snapshot_sha256': binding['runtime_snapshot_sha256'], 'expected_source_sha256': binding['source_closure_sha256']}

        def request(command, operation, payload):
            return Request(command, owner.project_id, operation, lease['lease_id'], lease['fencing_epoch'],
                lease['expected_revision'], {'stable_id': binding['runtime_instance_id']}, payload,
                'sha256:' + native.sha(canonical_bytes(payload)), min(lease['expires_ms'], epoch_ms() + 19_000))

        start = request('probe.play', 'play.start', {**preconditions, 'trace_sha256': binding['trace_sha256']})
        code, pending, _, _ = call('/v1/commands', start.as_dict())
        check('native_launch_pending', code == 200 and Response.from_dict(pending).status.value == 'ACCEPTED_PENDING'
            and backend.status()['process'] is not None)
        if mode == 'stop':
            code, stopped, _, elapsed = call('/v1/stop', {'project_id': owner.project_id, 'command_id': 'probe.stop'})
            check('priority_stop_latched', code == 200 and stopped['stopped'] is True and elapsed < 1000)
            code, _, _, _ = call('/v1/commands', start.as_dict())
            check('reconnect_cannot_resume', code == 400)
        deadline = time.monotonic() + 27
        terminal = None
        while time.monotonic() < deadline:
            code, observed, raw, _ = call('/v1/lookup', {'project_id': owner.project_id, 'command_id': start.command_id})
            check('lookup_authenticated', code == 200)
            if observed['status'] != 'ACCEPTED_PENDING':
                terminal = observed
                break
            time.sleep(.1)
        check('bounded_terminal_observed', terminal is not None)
        Response.from_dict(terminal)
        if mode == 'stop':
            check('stopped_without_fake_commit', terminal['status'] == 'CANCELED')
            backend.close()
            raw = json.loads(native.read_regular(backend.root / 'runtime-host/capture.json'))
            job = raw['job']
            check('stopped_owned_tree_drained', raw['completed'] is False and job['closed'] is True
                and job['zero_observed'] is True and job['tainted'] is False and job['handle_retained'] is False)
        else:
            check('native_postcondition_committed', terminal['status'] == 'COMMITTED'
                and terminal['code'] == 'REPLAY_NATIVE_COMPLETED')
            code, duplicate, _, _ = call('/v1/commands', start.as_dict())
            check('same_command_no_second_runtime', code == 200 and duplicate == terminal
                and backend.status()['phase'] == 'COMPLETED')
            code, lease, _, _ = call('/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 30_000})
            check('inspection_lease_refreshed', code == 200)
            capture = json.loads(native.read_regular(backend.root / 'capture.json'))
            expected = {key: binding[key] for key in ('runtime_instance_id', 'generation', 'source_closure_sha256', 'runtime_snapshot_sha256')}
            expected.update(report_sha256=capture['report_sha256'], **capture['process'])
            query = request('probe.inspect', 'play.inspect', {'expected': expected,
                'properties': ['phase', 'body_position', 'sim_tick', 'ui_tick'], 'phase': 'PAUSED', 'page_size': 2})
            code, observed, _, _ = call('/v1/commands', query.as_dict())
            observation = observed.get('postconditions', {}).get('observation', {})
            check('bounded_historical_inspector', code == 200 and observed['status'] == 'COMMITTED'
                and observation.get('historical') is True and observation.get('live') is False
                and observation.get('returned_count') == 2 and observation.get('next_cursor') is not None)
            capture_request = request('probe.capture', 'play.capture', {**preconditions, 'label': 'menu'})
            code, image, _, _ = call('/v1/commands', capture_request.as_dict())
            result = image.get('postconditions', {})
            check('hash_bound_menu_capture', code == 200 and image['status'] == 'COMMITTED'
                and result.get('phase') == 'MENU' and result.get('artifact', {}).get('sha256')
                == native.sha(native.read_regular(backend.project / 'out/menu.png')))
            code, stopped, _, _ = call('/v1/stop', {'project_id': owner.project_id, 'command_id': 'probe.stop'})
            check('completed_owner_stops', code == 200 and stopped['stopped'] is True)
        owner.close()
        owner = None
        server.close()
        server = None
        check('driver_source_unchanged', driver_sha == native.sha(Path(__file__).read_bytes()))
        result = {'schema': 'HH-GT06-HTTP-PROBE-1', 'run_id': run_id, 'mode': mode, 'checks': checks,
            'binding': binding, 'driver_sha256': driver_sha, 'formal_acceptance': False,
            'scope': 'fixed prepared replay with retained inspection, not a live debugger or UX benchmark'}
        native.write(output / 'result.json', result)
        print('HH_GT06_HTTP_COMPLETE ' + json.dumps({'run_id': run_id, 'mode': mode,
            'checks': len(checks), 'result_sha256': native.sha(native.encoded(result))}), flush=True)
    finally:
        failures = []
        for resource in (owner, backend, server):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    failures.append(error)
        if failures:
            raise failures[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--mode', required=True, choices=('complete', 'stop'))
    args = parser.parse_args()
    run(args.run_id, args.mode)

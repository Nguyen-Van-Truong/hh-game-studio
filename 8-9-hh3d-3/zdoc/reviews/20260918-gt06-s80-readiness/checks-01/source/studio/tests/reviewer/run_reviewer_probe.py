"""Coordinator-only actual Tk/HTTP/Play integration; run under owned bootstrap."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
import time
import tkinter as tk

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.replay import native_runner as native
from studio.reviewer.main import PreparedReviewer
from studio.reviewer.app import ReviewerWindow
from studio.reviewer.model import UiAction, Phase, UiCode


def run(run_id, mode):
    paths = sorted((STUDIO / 'reviewer').glob('*.py')) + [Path(__file__)]
    source = {p.relative_to(STUDIO).as_posix(): native.sha(p.read_bytes()) for p in paths}
    root = None
    original_error = None
    owner = PreparedReviewer.prepare(run_id)
    try:
        output = owner.backend.root / 'reviewer-probe'
        output.mkdir()
        native.write(output / 'source.json', source)
        for index, path in enumerate(paths):
            native.write(output / 'source' / (str(index) + '.py'), path.read_bytes())
        errors, events, heartbeats = [], [], []
        flags = {'play_key': False, 'stop_key': False, 'inspect_button': False,
                 'capture_button': False, 'close_requested': False}
        started = time.monotonic()
        root = tk.Tk()
        root.geometry('940x620+60+60')
        window = ReviewerWindow(root, owner.client, on_close=owner.close)

        def close():
            if not flags['close_requested']:
                flags['close_requested'] = True
                window.close()

        def callbacks_error(exc, value, traceback):
            # Never record arbitrary exception text from network/native state.
            errors.append(type(value).__name__)
            close()
        root.report_callback_exception = callbacks_error

        def heartbeat():
            if window._destroyed:
                return
            now = time.monotonic()
            heartbeats.append(round((now - started) * 1000, 6))
            state = window.state
            row = {'phase': state.phase.value, 'code': state.code.value,
                'stop_latched': state.stop_latched, 'pending': len(state.pending),
                'connected': state.connected}
            if not events or any(events[-1][k] != v for k, v in row.items()):
                events.append({**row, 'elapsed_ms': heartbeats[-1]})
            if now - started > 45:
                errors.append('REVIEWER_PROBE_DEADLINE')
                close()
            elif not flags['play_key'] and root.winfo_viewable():
                flags['play_key'] = True
                root.focus_force()
                root.event_generate('<Control-p>')
            elif mode == 'stop' and state.phase is Phase.RUNNING and not flags['stop_key']:
                flags['stop_key'] = True
                root.focus_force()
                root.event_generate('<Escape>')
            elif mode == 'stop' and state.stop_latched and state.code is UiCode.DRAINING:
                close()
            elif mode == 'complete' and state.phase is Phase.COMMITTED:
                if not flags['inspect_button']:
                    flags['inspect_button'] = True
                    window.buttons[UiAction.INSPECT].invoke()
                elif state.code is UiCode.INSPECTION_READY and not flags['capture_button']:
                    native.need(state.historical is not None and len(state.historical.rows) == 8,
                                'REVIEWER_INSPECTION_ROWS')
                    native.write(output / 'inspection.json', asdict(state.historical))
                    flags['capture_button'] = True
                    window.buttons[UiAction.CAPTURE].invoke()
                elif state.code is UiCode.CAPTURE_READY:
                    native.need(state.historical is not None and state.historical.capture.label == 'menu',
                                'REVIEWER_CAPTURE_LABEL')
                    native.write(output / 'capture-metadata.json', asdict(state.historical))
                    close()
            elif state.phase in (Phase.UNKNOWN, Phase.DISCONNECTED, Phase.REJECTED):
                errors.append('REVIEWER_STATE_' + state.phase.value.upper())
                close()
            if not window._destroyed:
                root.after(20, heartbeat)

        root.after(100, heartbeat)
        root.mainloop()
        owner.close()
        native.write(output / 'observations.json', {'events': events, 'heartbeat_monotonic_ms': heartbeats,
            'flags': flags, 'errors': errors, 'closed': owner.closed,
            'window_closed': window.state.phase is Phase.CLOSED})
        native.need(not errors and owner.closed and window.state.phase is Phase.CLOSED, 'REVIEWER_PROBE_CLEAN_CLOSE')
        native.need(flags['play_key'] and any(e['phase'] == 'running' for e in events), 'REVIEWER_KEYBOARD_PLAY')
        if mode == 'complete':
            native.need(flags['inspect_button'] and flags['capture_button'] and owner.backend._result is not None,
                        'REVIEWER_COMPLETE_POSTCONDITIONS')
        else:
            native.need(flags['stop_key'] and any(e['stop_latched'] for e in events), 'REVIEWER_KEYBOARD_STOP')
            captured = __import__('json').loads(native.read_regular(owner.backend.root / 'runtime-host/capture.json'))
            native.need(captured['completed'] is False and captured['job']['closed'] is True
                        and captured['job']['zero_observed'] is True, 'REVIEWER_STOP_NATIVE_DRAIN')
        native.need(source == {p.relative_to(STUDIO).as_posix(): native.sha(p.read_bytes()) for p in paths},
                    'REVIEWER_SOURCE_CHANGED')
        intervals = [b-a for a, b in zip(heartbeats, heartbeats[1:])]
        result = {'schema': 'HH-GT06-REVIEWER-PROBE-1', 'run_id': run_id, 'mode': mode,
            'binding': owner.backend.binding, 'reviewer_source_closure': native.closure(source),
            'source_unchanged': True, 'flags': flags, 'closed': True, 'formal_acceptance': False,
            'heartbeat_max_ms': max(intervals) if intervals else None,
            'heartbeat_samples': len(intervals), 'scope': 'actual Tk keyboard/buttons and HTTP; not the full UX benchmark'}
        native.write(output / 'result.json', result)
        print('HH_GT06_REVIEWER_COMPLETE ' + __import__('json').dumps({'run_id': run_id,
              'mode': mode, 'result_sha256': native.sha(native.encoded(result))}), flush=True)
    except BaseException as error:
        original_error = error
        raise
    finally:
        try:
            owner.close()
        except BaseException as cleanup_error:
            # PreparedReviewer retains an uncertain owner in HELD_REVIEWERS.
            # Preserve the initiating failure, with cleanup failure as its cause.
            if original_error is not None:
                raise original_error from cleanup_error
            raise
        finally:
            if root is not None:
                try:
                    root.destroy()
                except tk.TclError:
                    pass


def bounded_run(run_id, mode):
    output = STUDIO / '.local/reviews' / (run_id + '-driver')
    output.mkdir(exist_ok=False)
    runner = STUDIO / 'build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('hh_reviewer_owned_runner', runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    driver = native.sha(Path(__file__).read_bytes())
    host = module.run_process([sys.executable, '-B', str(Path(__file__).resolve()), '--child',
        '--run-id', run_id, '--mode', mode], cwd=STUDIO, output=output, timeout=110, label='reviewer')
    result_path = STUDIO / '.local/reviews' / run_id / 'reviewer-probe/result.json'
    completed = (host['exit_code'] == 0 and host['wrapper_exit_code'] == 0 and host['tree_verified']
        and not host['timed_out'] and result_path.is_file()
        and (output / host['stderr']).stat().st_size == 0 and driver == native.sha(Path(__file__).read_bytes()))
    native.write(output / 'capture.json', {'host': host, 'completed': completed, 'driver_sha256': driver,
        'result_sha256': native.sha(result_path.read_bytes()) if result_path.is_file() else None})
    print(json.dumps({'completed': completed, 'run_id': run_id, 'mode': mode}), flush=True)
    return 0 if completed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--mode', choices=('complete', 'stop'), required=True)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    if args.child:
        run(args.run_id, args.mode)
    else:
        raise SystemExit(bounded_run(args.run_id, args.mode))

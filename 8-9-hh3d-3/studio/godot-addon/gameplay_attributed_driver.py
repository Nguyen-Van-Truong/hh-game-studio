"""Pinned private driver for authenticated phase/OS observation.

Launched only by linux_executor under the existing PID-1 timeout and limits.
Candidate output is isolated in pipes and signed as untrusted payload. No
per-child timeout, engine authority or dependency claim is introduced here.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys


def codec_module():
    path = Path(__file__).with_name('gameplay_attribution.py')
    spec = importlib.util.spec_from_file_location('_trusted_gameplay_attribution', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_child(codec, recorder, phase, script):
    read_fd, write_fd = os.pipe()
    process = None
    selector = selectors.DefaultSelector()
    pipes = []
    reaped = False
    try:
        argv = ['/usr/local/bin/python3', '-I', '-B', '/harness/gameplay_sandbox.py', phase]
        if script is not None:
            argv.append(script)
        argv += ['--guard-fd', str(write_fd)]
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, pass_fds=(write_fd,))
        os.close(write_fd)
        write_fd = None
        recorder.begin_child(phase, script, process.pid)
        guard_stream = os.fdopen(read_fd, 'rb', buffering=0)
        read_fd = None
        pipes = [process.stdout, process.stderr, guard_stream]
        eof = [False, False, False]
        guard = bytearray()
        for index, stream in enumerate(pipes):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, index)
        while selector.get_map():
            for key, _ in selector.select():
                index = key.data
                chunk = os.read(key.fileobj.fileno(), codec.MAX_CHUNK_BYTES)
                if not chunk:
                    eof[index] = True
                    selector.unregister(key.fileobj)
                    if index == 2 and guard:
                        codec.need(len(guard) <= 1024 and guard.endswith(b'\n')
                                   and guard.count(b'\n') == 1, 'ATTRIBUTION_GUARD_PACKET')
                        facts = json.loads(guard, object_pairs_hook=codec._pairs)
                        codec.need(codec.valid_guard(facts), 'ATTRIBUTION_GUARD_PACKET')
                        recorder.guard(process.pid, facts)
                elif index == 2:
                    guard.extend(chunk)
                    codec.need(len(guard) <= 1024, 'ATTRIBUTION_GUARD_CAP')
                else:
                    recorder.output(process.pid, ('stdout', 'stderr')[index], chunk)
        code = process.wait()
        reaped = True
        # A success without the trusted pre-exec packet cannot authorize replay.
        codec.need(code != 0 or bool(guard), 'ATTRIBUTION_GUARD_MISSING')
        recorder.end_child(process.pid, code, reaped=reaped, pipe_eof=eof)
        return code
    finally:
        # Exceptions/caps withhold the key. PID 1 still bounds this entire job.
        if process is not None and not reaped:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1)
        selector.close()
        for stream in pipes:
            stream.close()
        for fd in (read_fd, write_fd):
            if fd is not None:
                os.close(fd)


def main():
    codec = codec_module()
    codec.protect_parent()
    codec.need(len(sys.argv) == 2, 'ATTRIBUTION_DRIVER_ARGUMENTS')
    context = json.loads(sys.argv[1], object_pairs_hook=codec._pairs)
    recorder = codec.Recorder(sys.stdout.buffer, context)
    primary = 'scripts/fixture_actor.gd'
    scripts = sorted(p.relative_to('/project').as_posix()
                     for p in Path('/project/scripts').rglob('*.gd') if p.is_file())
    codec.need(primary in scripts and len(scripts) <= 64, 'ATTRIBUTION_SCRIPT_INVENTORY')
    scripts = [primary] + [script for script in scripts if script != primary]
    for phase, script in [('parse', s) for s in scripts] + [('import', None), ('play', None)]:
        code = run_child(codec, recorder, phase, script)
        if code != 0:
            recorder.finish(45)
            return 45
    recorder.finish(0)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

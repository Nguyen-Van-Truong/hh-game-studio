"""Exact startup-log classification for the pinned gameplay-source harness.

This verdict only explains a complete normal-success transcript. It does not
make the raw log clean, authenticate gameplay claims, or grant publication or
sandbox acceptance. The host must separately bind the binary/harness pins and
derive the script inventory from the admitted source bundle.
"""
from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
import re

POLICY = 'hh-gameplay-startup-log-1'
MAX_LOG_BYTES = 262_144
PRIMARY_SCRIPT = 'scripts/fixture_actor.gd'
GUARD_MARKER = 'HH_GAMEPLAY_OS_GUARD fork=EPERM socket=EPERM'
GUARDED_STARTUP_ERROR = ('ERROR: Cannot create pipe from command: "xdg-user-dir" "DESKTOP" 2>/dev/null.\n'
                         '   at: execute (drivers/unix/os_unix.cpp:899)\n')
GUARDED_SOCKET_ERROR = ('ERROR: Condition "_sock == -1" is true. Returning: FAILED\n'
                        '   at: _inet_open (drivers/unix/net_socket_unix.cpp:288)\n')
GUARDED_LISTEN_ERROR = ('ERROR: Condition "err != OK" is true. Returning: ERR_CANT_CREATE\n'
                        '   at: listen (core/io/tcp_server.cpp:56)\n')
GAMEPLAY_STARTUP_ERRORS = (GUARDED_STARTUP_ERROR * 2
    + (GUARDED_SOCKET_ERROR + GUARDED_LISTEN_ERROR) * 2 + GUARDED_STARTUP_ERROR)
GAMEPLAY_PHASE_EVENTS = tuple(event for phase in ('parse', 'import', 'play')
    for event in (f'HH_GAMEPLAY_PHASE_BEGIN {phase}', GUARD_MARKER,
                  f'HH_GAMEPLAY_PHASE_END {phase} 0'))


def _script_inventory(scripts: list[str]) -> bool:
    if (type(scripts) is not list or not 1 <= len(scripts) <= 64
            or any(type(path) is not str for path in scripts)
            or scripts[0] != PRIMARY_SCRIPT
            or scripts[1:] != sorted(scripts[1:])
            or len({path.casefold() for path in scripts}) != len(scripts)):
        return False
    for path in scripts:
        if (not path.startswith('scripts/') or not path.endswith('.gd')
                or any(ord(char) < 32 or char in '\\:' for char in path)
                or any(part in ('', '.', '..') for part in path.split('/'))
                or PurePosixPath(path).as_posix() != path):
            return False
    return True


def classify(stdout: bytes, stderr: bytes, scripts: list[str]) -> dict:
    """Classify exact startup noise; hashes always cover the original bytes."""
    verdict = {'policy': POLICY, 'accepted': False,
               'stdout_sha256': hashlib.sha256(stdout).hexdigest() if type(stdout) is bytes else None,
               'stderr_sha256': hashlib.sha256(stderr).hexdigest() if type(stderr) is bytes else None}
    if (type(stdout) is not bytes or type(stderr) is not bytes
            or len(stdout) > MAX_LOG_BYTES or len(stderr) > MAX_LOG_BYTES
            or not _script_inventory(scripts)):
        return verdict
    try:
        out = stdout.decode('utf-8', errors='strict')
        err = stderr.decode('utf-8', errors='strict').replace('\r\n', '\n')
    except UnicodeDecodeError:
        return verdict
    if '\x00' in out or '\x00' in err or re.search(r'ERROR|WARNING|leaked', out, re.IGNORECASE):
        return verdict
    expected = ['HH_GAMEPLAY_PHASE_BEGIN parse']
    for index, script in enumerate(scripts):
        if index:
            expected.append('HH_GAMEPLAY_MODULE_BEGIN ' + script)
        expected.append(GUARD_MARKER)
        if index:
            expected.append('HH_GAMEPLAY_MODULE_END ' + script + ' 0')
    expected.append('HH_GAMEPLAY_PHASE_END parse 0')
    expected.extend(GAMEPLAY_PHASE_EVENTS[3:])
    events = tuple(line for line in out.splitlines()
                   if line.startswith(('HH_GAMEPLAY_PHASE_', 'HH_GAMEPLAY_OS_GUARD', 'HH_GAMEPLAY_MODULE_')))
    errors = GUARDED_STARTUP_ERROR * (len(scripts) - 1) + GAMEPLAY_STARTUP_ERRORS
    verdict['accepted'] = events == tuple(expected) and err == errors
    return verdict


def classify_attributed(observation: dict, scripts: list[str]) -> dict:
    """Explain child noise after the caller verifies the parent wire.

    Phase markers from candidate text do not contribute to this decision.
    This classifier is not itself an attribution verifier.
    """
    stdout, stderr = observation['child_stdout'], observation['child_stderr']
    verdict = {'policy': 'hh-gameplay-attributed-startup-log-1', 'accepted': False,
               'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
               'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
               'wire_sha256': observation['wire_sha256']}
    if not _script_inventory(scripts) or observation.get('driver_returncode') != 0:
        return verdict
    phases = observation.get('phase_results', [])
    expected_old = [('parse', script) for script in scripts] + [('import', None), ('play', None)]
    expected_new = [('dependencies', None), ('dependencies_reopen', None)]
    expected_new += [('parse', script) for script in scripts]
    expected_new += [('import', None), ('play', None)]
    observed = [(row.get('phase'), row.get('script')) for row in phases]
    expected = expected_new if observed == expected_new else expected_old
    if (observed != expected
            or any(type(row.get('returncode')) is not int or row['returncode'] != 0
                   or type(row.get('guard')) is not dict for row in phases)):
        return verdict
    try:
        out = stdout.decode('utf-8', errors='strict')
        err = stderr.decode('utf-8', errors='strict').replace('\r\n', '\n')
    except UnicodeDecodeError:
        return verdict
    if expected is expected_new:
        # Each Godot child emits one startup diagnostic.  The trusted
        # dependency and reopen phases both precede candidate parse/import/play.
        # Keep this order exact; a count-only check would accept a phase stream
        # whose diagnostics came from a different child.
        errors = (GUARDED_STARTUP_ERROR * (len(scripts) + 3)
                  + (GUARDED_SOCKET_ERROR + GUARDED_LISTEN_ERROR) * 2
                  + GUARDED_STARTUP_ERROR)
    else:
        errors = GUARDED_STARTUP_ERROR * (len(scripts) - 1) + GAMEPLAY_STARTUP_ERRORS
    verdict['accepted'] = ('\x00' not in out and '\x00' not in err
        and not re.search(r'ERROR|WARNING|leaked', out, re.IGNORECASE) and err == errors)
    return verdict

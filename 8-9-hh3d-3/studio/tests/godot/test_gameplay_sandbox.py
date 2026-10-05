"""Filter-policy regressions; native denial proof belongs to the Linux probe."""
import errno
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gameplay_sandbox_tests',
    Path(__file__).resolve().parents[2] / 'godot-addon/gameplay_sandbox.py')
sandbox = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sandbox)


def evaluate(number, flags=0, arch=sandbox.ARCH_X86_64):
    """Small classic-BPF interpreter over synthetic seccomp_data."""
    data = {0: number, 4: arch, 16: flags & 0xFFFFFFFF}
    rows, pc, value = sandbox.instructions(), 0, 0
    for _ in range(128):
        code, yes, no, operand = rows[pc]
        if code == 0x20:
            value = data[operand]
        elif code == 0x06:
            return operand
        elif code == 0x15:
            pc += yes if value == operand else no
        elif code == 0x35:
            pc += yes if value >= operand else no
        elif code == 0x45:
            pc += yes if value & operand else no
        else:
            raise AssertionError('unexpected instruction')
        pc += 1
    raise AssertionError('filter failed to terminate')


class GameplaySandboxTests(unittest.TestCase):
    def test_wrong_abi_and_x32_cannot_bypass_policy(self):
        for arch in (0, 0x40000003, 0xC00000B7):
            self.assertEqual(evaluate(57, arch=arch), sandbox.KILL)
        for number in (0x40000000, 0x40000039, 0xFFFFFFFF):
            self.assertEqual(evaluate(number), sandbox.KILL)

    def test_process_network_and_cross_process_access_are_denied(self):
        for number in (41, 53, 57, 58, 62, 101, 200, 272, 308, 310, 311, 438):
            self.assertEqual(evaluate(number), sandbox.ERRNO | errno.EPERM)

    def test_threads_work_but_fork_and_vfork_clone_flags_do_not(self):
        for flags in (0, 17, 0x100 | 17, 0x4000 | 0x100 | 17):
            self.assertEqual(evaluate(56, flags), sandbox.ERRNO | errno.EPERM)
        self.assertEqual(evaluate(56, 0x3D0F00), sandbox.ALLOW)
        self.assertEqual(evaluate(435), sandbox.ERRNO | errno.ENOSYS)

    def test_regular_io_and_initial_engine_exec_remain_available(self):
        for number in (0, 1, 2, 3, 9, 12, 59, 60, 202, 231, 257):
            self.assertEqual(evaluate(number), sandbox.ALLOW)

    def test_secondary_script_is_checked_directly_and_cannot_escape(self):
        argv = sandbox.command('parse', parse_script='scripts/unused.gd')
        self.assertEqual(argv[-3:], ['--check-only', '--script', 'res://scripts/unused.gd'])
        for path in ('../outside.gd', '/tmp/a.gd', 'res://scripts/a.gd',
                     'scripts/../a.gd', 'scripts//a.gd', 'scripts/./a.gd',
                     'scripts/a.gd\n', 'scripts/a.txt', 'scripts\\a.gd', ''):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'SCRIPT_PATH'):
                sandbox.command('parse', parse_script=path)
        with self.assertRaisesRegex(ValueError, 'SCRIPT_PATH'):
            sandbox.command('play', parse_script='scripts/a.gd')

    def test_launcher_does_not_offer_arbitrary_program_or_arguments(self):
        for phase in ('parse', 'import', 'play', 'readback'):
            self.assertEqual(sandbox.command(phase)[0], sandbox.BINARY)
        for phase in ('run', '/bin/sh', '--script=evil', None):
            with self.assertRaisesRegex(ValueError, 'PHASE'):
                sandbox.command(phase)

    def test_wrong_platform_rejects_before_native_calls(self):
        with patch.object(sandbox.sys, 'platform', 'win32'):
            with self.assertRaisesRegex(RuntimeError, 'PLATFORM'):
                sandbox.install()


if __name__ == '__main__':
    unittest.main()

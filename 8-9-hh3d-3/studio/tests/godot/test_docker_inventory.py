"""Pure admission inventory regressions; no Docker, pipe or engine dispatch."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from studio.host.core import docker_inventory as inventory

STUDIO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('inventory_executor_tests',
    STUDIO / 'godot-addon/linux_executor.py')
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)


def encoded(rows):
    return json.dumps(rows, separators=(',', ':')).encode()


def container(identifier='a' * 64, state='running', **changes):
    return {'Id': identifier, 'State': state,
            'Labels': {inventory.EXECUTOR_LABEL: inventory.EXECUTOR_CONTEXT}, **changes}


def response(body):
    return (b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: '
            + str(len(body)).encode() + b'\r\n\r\n' + body)


class InventoryTests(unittest.TestCase):
    @contextmanager
    def native(self, payload=None):
        payload = response(encoded([])) if payload is None else payload
        fragments = [payload[i:i + 4096] for i in range(0, len(payload), 4096)]
        kernel = Mock()
        kernel.CreateFileW.return_value = 123
        owner = Mock()
        owner._io.side_effect = lambda kind, size, deadline, data=b'': (
            b'' if kind == 'write' else fragments.pop(0) if fragments else b'')
        with patch.object(inventory.os, 'name', 'nt'), \
             patch.object(inventory.C, 'WinDLL', return_value=kernel, create=True), \
             patch.object(inventory.OwnedPipe, '_adopt', return_value=owner), \
             patch.object(inventory.time, 'monotonic', return_value=100.0), \
             patch.object(inventory, '_RETAINED_PIPES', []) as held, \
             patch.object(inventory, '_RETAINED_HANDLES', []):
            yield kernel, owner, held

    def test_fixed_all_container_label_request_and_one_absolute_deadline(self):
        with self.native() as (kernel, owner, _held):
            self.assertEqual(inventory.query_owned_executor_containers(105.0), [])
            kernel.CreateFileW.assert_called_once_with(
                r'\\.\pipe\dockerDesktopLinuxEngine', 0xC0000000, 0, None, 3, 0x40000000, None)
            self.assertEqual(inventory.REQUEST,
                b'GET /containers/json?all=1&filters=%7B%22label%22%3A%5B%22'
                b'hh.gt03.executor%3Dhh-gt03-linux-desktop-v1%22%5D%7D HTTP/1.1\r\n'
                b'Host: docker\r\nAccept: application/json\r\nConnection: close\r\n\r\n')
            self.assertTrue(all(call.args[2] == 105.0 for call in owner._io.call_args_list))
            owner.close.assert_called_once_with()

    def test_stopped_created_and_running_ids_are_retained_with_old_output_bound(self):
        self.assertEqual(inventory.parse_owned_ids(encoded([
            container('c' * 64, 'created'), container('b' * 64, 'exited'), container(),
        ])), ['a' * 64, 'b' * 64, 'c' * 64])
        rows = [container(f'{i:064x}') for i in range(64)]
        self.assertEqual(len(inventory.parse_owned_ids(encoded(rows[:63]))), 63)
        with self.assertRaises(inventory.InventoryError):
            inventory.parse_owned_ids(encoded(rows))

    def test_unknown_labels_ids_states_and_duplicate_keys_never_become_empty(self):
        bad_rows = [container(Id='a' * 63), container(Id='A' * 64),
                    container(Labels={}), container(Labels=None),
                    container(Labels={inventory.EXECUTOR_LABEL: 'another-context'}),
                    container(State='unknown'), container(State=None)]
        bodies = [encoded([row]) for row in bad_rows]
        bodies += [encoded([container(), container()]), b'null', b'[] trailing', b'\xff',
                   b'[{"Id":"secret","Id":"other"}]', b'[{"extra":NaN}]']
        for body in bodies:
            with self.subTest(body=body[:80]), self.assertRaises(inventory.InventoryError) as caught:
                inventory.parse_owned_ids(body)
            self.assertEqual(caught.exception.reason, 'bad_output')
            self.assertFalse(caught.exception.retryable)

    def test_truncated_or_oversized_body_fails_closed_and_closes_pipe(self):
        for payload in (response(b'[]')[:-1], response(b'x' * (inventory.BODY_LIMIT + 1))):
            with self.subTest(size=len(payload)), self.native(payload) as (_kernel, owner, _held):
                with self.assertRaises(inventory.InventoryError):
                    inventory.query_owned_executor_containers(105.0)
                owner.close.assert_called_once_with()

    def test_timeout_closes_pipe_without_a_second_query(self):
        with self.native() as (kernel, owner, _held):
            owner._io.side_effect = inventory.PipeIOError('PIPE_TIMEOUT')
            with self.assertRaises(inventory.InventoryError) as caught:
                inventory.query_owned_executor_containers(105.0)
            self.assertEqual(caught.exception.reason, 'timeout')
            self.assertFalse(caught.exception.retryable)
            kernel.CreateFileW.assert_called_once()
            owner.close.assert_called_once_with()

    def test_failed_close_retains_owner_and_forbids_further_inventory(self):
        with self.native() as (kernel, owner, held):
            owner.close.side_effect = RuntimeError('unproven close')
            with self.assertRaises(inventory.InventoryError):
                inventory.query_owned_executor_containers(105.0)
            self.assertEqual(held, [owner])
            with self.assertRaises(inventory.InventoryError) as caught:
                inventory.query_owned_executor_containers(105.0)
            self.assertFalse(caught.exception.retryable)
            kernel.CreateFileW.assert_called_once()

    def test_late_close_cannot_return_success(self):
        with self.native() as (_kernel, owner, _held):
            clock = [100.0]
            owner.close.side_effect = lambda: clock.__setitem__(0, 105.0)
            with patch.object(inventory.time, 'monotonic', side_effect=lambda: clock[0]):
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.query_owned_executor_containers(105.0)
            self.assertEqual(caught.exception.reason, 'timeout')

    def test_executor_timeout_receipt_is_unknown_without_fake_process_exit(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(executor.time, 'monotonic', return_value=100.0), \
             patch.object(inventory, 'query_owned_executor_containers',
                          side_effect=inventory.InventoryError('timeout')) as query:
            with self.assertRaisesRegex(executor.ExecutorError, 'EXECUTOR_INVENTORY_TIMEOUT'):
                executor._inventory_ids(Path(folder))
            row = json.loads((Path(folder) / 'admission-inventory.json').read_text())
        query.assert_called_once_with(105.0)
        self.assertEqual((row['status'], row['container_ids'], row['timeout_seconds']), ('timeout', None, 5))
        self.assertNotIn('exit_code', row)
        self.assertNotIn('job_owner', row)


if __name__ == '__main__':
    unittest.main()

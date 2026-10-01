"""Pure Docker inventory boundary doubles; no daemon, pipe or subprocess launch.

These checks establish parser/deadline/ownership contracts for the candidate
observer. They do not establish native cancellation or campaign acceptance.
"""
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
import json
import sys
import traceback
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import benchmark_docker_inventory as inventory


def row(identifier='a', names=None, **changes):
    return {'Id': identifier * 64, 'Names': ['/hh-test'] if names is None else names,
            'State': 'running', **changes}


def encoded(rows):
    return json.dumps(rows, separators=(',', ':')).encode('utf-8')


def content_length(body, headers=b''):
    return (b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
            + b'Content-Length: ' + str(len(body)).encode('ascii') + b'\r\n'
            + headers + b'\r\n' + body)


def chunked(chunks):
    return (b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
            b'Transfer-Encoding: chunked\r\n\r\n'
            + b''.join(f'{len(part):X}\r\n'.encode('ascii') + part + b'\r\n'
                       for part in chunks) + b'0\r\n\r\n')


def pieces(data, width=4096):
    return [data[start:start + width] for start in range(0, len(data), width)]


class ParserTests(unittest.TestCase):
    def parse(self, data, width=4096, clock=None, deadline=102.0):
        clock = [100.0] if clock is None else clock
        receive = Mock(side_effect=pieces(data, width) + [b''])
        with patch.object(inventory.time, 'monotonic', side_effect=lambda: clock[0]):
            return inventory.parse_response(receive, deadline)

    def assert_bad(self, data, width=4096):
        with self.assertRaises(inventory.InventoryError) as caught:
            self.parse(data, width)
        self.assertEqual(caught.exception.reason, 'bad_output')
        self.assertFalse(caught.exception.retryable)

    def test_fragmented_content_length_and_chunked_have_identical_inventory(self):
        body = encoded([row('b', ['/zeta']), row('a', ['/hh-arena', '/alias'])])
        for width in (1, 7, 4096):
            for response in (content_length(body), chunked([body[:3], body[3:29], body[29:]])):
                with self.subTest(width=width, framing=response[:80]):
                    parsed = self.parse(response, width)
                    self.assertEqual(parsed, body)
                    self.assertEqual(inventory.parse_names(parsed), ['alias', 'hh-arena', 'zeta'])

    def test_length_body_returns_without_waiting_for_pipe_eof(self):
        receive = Mock(return_value=content_length(b'[]'))
        with patch.object(inventory.time, 'monotonic', return_value=100.0):
            self.assertEqual(inventory.parse_response(receive, 102.0), b'[]')
        receive.assert_called_once_with()

    def test_empty_inventory_requires_a_valid_json_list(self):
        self.assertEqual(inventory.parse_names(self.parse(content_length(b'[]'))), [])
        with self.assertRaises(inventory.InventoryError):
            inventory.parse_names(self.parse(content_length(b'')))

    def test_response_status_is_bounded_and_retryable_without_raw_body(self):
        for code in (301, 400, 404, 500, 503):
            receive = Mock(return_value=f'HTTP/1.1 {code} secret-reason\r\n'.encode())
            with self.subTest(status=code), patch.object(inventory.time, 'monotonic', return_value=100.0):
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.parse_response(receive, 102.0)
            self.assertEqual(caught.exception.reason, 'nonzero')
            self.assertEqual(caught.exception.detail, code)
            self.assertTrue(caught.exception.retryable)
            self.assertNotIn('secret', str(caught.exception))

    def test_malformed_status_and_headers_fail_closed(self):
        cases = (
            b'HTTP/2 200 OK\r\n\r\n',
            b'HTTP/1.1 20 OK\r\n\r\n',
            b'HTTP/1.1 200 \x00\r\n\r\n',
            b'HTTP/1.1 200 OK\nContent-Length: 2\n\n[]',
            b'HTTP/1.1 200 OK\r\nMissingColon\r\n\r\n[]',
            b'HTTP/1.1 200 OK\r\nBad Name: value\r\n\r\n[]',
            content_length(b'[]', b'X-Test: \x00secret\r\n'),
            content_length(b'[]', b'X-Test: \xff\r\n'),
            content_length(b'[]', b' Content-Type: application/json\r\n'),
        )
        for response in cases:
            with self.subTest(response=response[:90]):
                self.assert_bad(response)

    def test_missing_duplicate_and_ambiguous_framing_fail_closed(self):
        prefix = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
        cases = (
            prefix + b'\r\n[]',
            prefix + b'Content-Length: 2\r\ncontent-length: 2\r\n\r\n[]',
            prefix + b'Content-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n[]',
            prefix + b'Transfer-Encoding: chunked\r\ntransfer-encoding: chunked\r\n\r\n0\r\n\r\n',
            prefix + b'Content-Length: -2\r\n\r\n[]',
            prefix + b'Content-Length: +2\r\n\r\n[]',
            prefix + b'Content-Length: 2, 2\r\n\r\n[]',
            prefix + b'Content-Length: 000000002\r\n\r\n[]',
            prefix + b'Transfer-Encoding: gzip, chunked\r\n\r\n0\r\n\r\n',
            content_length(b'[]', b'Content-Type: application/json\r\n'),
            content_length(b'[]') + b'HTTP/1.1 200 OK\r\n',
        )
        for response in cases:
            with self.subTest(response=response[:130]):
                self.assert_bad(response)

    def test_encoding_and_content_type_are_not_guessed(self):
        for headers in (b'Content-Encoding: gzip\r\n', b'Content-Encoding: br\r\n'):
            self.assert_bad(content_length(b'[]', headers))
        for response in (
            b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n[]',
            b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\n[]',
        ):
            self.assert_bad(response)
        self.assertEqual(self.parse(content_length(b'[]', b'Content-Encoding: identity\r\n')), b'[]')

    def test_truncated_header_length_and_chunked_bodies_fail_closed(self):
        for response in (
            b'HTTP/1.1 200',
            content_length(b'[]')[:-1],
            chunked([b'[]'])[:-1],
            chunked([b'[]'])[:-5],
            b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 3\r\n\r\n[]',
        ):
            with self.subTest(response=response[-30:]):
                self.assert_bad(response, 3)

    def test_chunk_extensions_trailers_and_bad_terminators_fail_closed(self):
        prefix = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n'
        for chunks in (
            b'2;foo=bar\r\n[]\r\n0\r\n\r\n',
            b'+2\r\n[]\r\n0\r\n\r\n',
            b'xyz\r\n[]\r\n0\r\n\r\n',
            b'2\r\n[]xx0\r\n\r\n',
            b'0\r\nX-Trailer: secret\r\n\r\n',
            b'000000002\r\n[]\r\n0\r\n\r\n',
        ):
            with self.subTest(chunks=chunks):
                self.assert_bad(prefix + chunks, 2)

    def test_header_body_chunk_count_and_receive_storage_are_bounded(self):
        self.assert_bad(content_length(b'[]', b'X-Large: ' + b'x' * 8192 + b'\r\n'))
        self.assert_bad(content_length(b'x' * 65537))
        self.assert_bad(chunked([b'x' * 32768, b'x' * 32769]))
        self.assert_bad(chunked([b'x'] * 1024))
        self.assertEqual(len(self.parse(content_length(b'x' * 65536))), 65536)
        for data in (b'', b'x' * 4097, bytearray(b'[]'), 'secret-text'):
            with self.subTest(received_type=type(data).__name__, length=len(data)), \
                 patch.object(inventory.time, 'monotonic', return_value=100.0):
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.parse_response(Mock(return_value=data), 102.0)
            self.assertEqual(caught.exception.reason, 'bad_output')

    def test_all_fragments_share_original_deadline_and_late_data_is_rejected(self):
        response = pieces(content_length(b'[]'), 1)
        clock = [100.0]
        def receive():
            clock[0] += 0.04
            return response.pop(0) if response else b''
        with patch.object(inventory.time, 'monotonic', side_effect=lambda: clock[0]):
            with self.assertRaises(inventory.InventoryError) as caught:
                inventory.parse_response(receive, 102.0)
        self.assertEqual(caught.exception.reason, 'timeout')
        self.assertLessEqual(clock[0], 102.05)
        for arrival in (102.0, 102.001):
            clock[0] = 100.0
            def late_receive():
                clock[0] = arrival
                return content_length(b'[]')
            with self.subTest(arrival=arrival), \
                 patch.object(inventory.time, 'monotonic', side_effect=lambda: clock[0]):
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.parse_response(late_receive, 102.0)
            self.assertEqual(caught.exception.reason, 'timeout')

    def test_expired_deadline_performs_no_read(self):
        receive = Mock()
        with patch.object(inventory.time, 'monotonic', return_value=102.0):
            with self.assertRaises(inventory.InventoryError) as caught:
                inventory.parse_response(receive, 102.0)
        self.assertEqual(caught.exception.reason, 'timeout')
        receive.assert_not_called()


class NameTests(unittest.TestCase):
    def assert_bad(self, body):
        with self.assertRaises(inventory.InventoryError) as caught:
            inventory.parse_names(body)
        self.assertEqual(caught.exception.reason, 'bad_output')
        self.assertFalse(caught.exception.retryable)

    def test_valid_names_are_sorted_and_exactly_one_slash_is_removed(self):
        self.assertEqual(inventory.parse_names(encoded([
            row('a', ['/Z9_.-']), row('b', ['/hh-arena', '/alias']),
        ])), ['Z9_.-', 'alias', 'hh-arena'])

    def test_invalid_json_utf8_duplicate_keys_and_nonfinite_values_fail_closed(self):
        for body in (b'\xff', b'', b'[] trailing', b'null', b'{}', b'"secret"',
                     bytearray(b'[]'), '[]', b'x' * (inventory.BODY_LIMIT + 1),
                     b'[{"Names":[],"Names":["/secret"]}]',
                     b'[{"extra":NaN}]', b'[{"extra":Infinity}]', b'[{"extra":-Infinity}]',
                     b'[' * 1100 + b']' * 1100):
            with self.subTest(body=body[:65]):
                self.assert_bad(body)

    def test_required_id_state_and_names_shape_are_validated(self):
        invalid = [None, [], 7, True, {}, row(Id=7), row(Id='a' * 63),
                   row(Id='A' * 64), row(Id='g' * 64), row(State='exited'),
                   row(State='paused'), row(State=None), row(Names=[]),
                   row(Names='/hh-test'), row(Names=None)]
        for missing in ('Id', 'State', 'Names'):
            value = row()
            del value[missing]
            invalid.append(value)
        for value in invalid:
            with self.subTest(value=value):
                self.assert_bad(encoded([value]))

    def test_names_cannot_hide_paths_spaces_unicode_or_empty_aliases(self):
        for name in ('hh-test', '//hh-test', '/', '/-bad', '/bad/name', '/bad name',
                     '/bad\nname', '/bad\x00name', '/bÃ©', None, 3, True):
            with self.subTest(name=name):
                self.assert_bad(encoded([row(names=[name])]))

    def test_aggregate_name_storage_is_bounded_even_when_json_body_is_small(self):
        names = ['/' + ('n' * 1023) for _ in range(65)]
        self.assert_bad(encoded([row(names=names)]))

    def test_duplicate_ids_and_aliases_are_unknown(self):
        for rows in (
            [row('a', ['/first']), row('a', ['/second'])],
            [row('a', ['/same']), row('b', ['/same'])],
            [row('a', ['/same', '/same'])],
            [row('a', ['/good', '/bad/name'])],
        ):
            with self.subTest(rows=rows):
                self.assert_bad(encoded(rows))

    def test_inventory_row_count_is_bounded(self):
        self.assert_bad(encoded([row()] * 4097))

    def test_invalid_body_error_does_not_print_or_expose_raw_secret(self):
        output = StringIO()
        with redirect_stdout(output):
            try:
                payload = ('[{"' + 'secret-key' + '":"' + 'secret-value' + '"}, broken]').encode()
                inventory.parse_names(payload)
            except inventory.InventoryError as error:
                rendered = ''.join(traceback.format_exception(error))
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('secret-key', rendered)
        self.assertNotIn('secret-value', rendered)


class QueryTests(unittest.TestCase):
    def test_unexpected_native_error_is_sanitized_and_closed_without_retry(self):
        with self.native() as (_kernel, owner, *_rest):
            owner._io.side_effect = RuntimeError('secret-native-response')
            with self.assertRaises(inventory.InventoryError) as caught:
                inventory.query_containers(102.0)
            owner.close.assert_called_once_with()
        self.assertEqual(caught.exception.reason, 'oserror')
        self.assertFalse(caught.exception.retryable)
        self.assertIsNone(caught.exception.__context__)
        self.assertNotIn('secret', ''.join(traceback.format_exception(caught.exception)))

    @contextmanager
    def native(self, *, response=None, clock=None, retained_pipes=None, retained_handles=None):
        clock = [100.0] if clock is None else clock
        response = content_length(encoded([row()])) if response is None else response
        received = pieces(response, 17) + [b'']
        kernel = Mock()
        kernel.CreateFileW.return_value = 123
        kernel.CloseHandle.return_value = True
        owner = Mock()
        owner._io.side_effect = lambda kind, _size, _deadline, _payload=b'': (
            b'' if kind == 'write' else received.pop(0))
        owner.close.return_value = None
        retained_pipes = [] if retained_pipes is None else retained_pipes
        retained_handles = [] if retained_handles is None else retained_handles
        with patch.object(inventory.os, 'name', 'nt'), \
             patch.object(inventory.C, 'WinDLL', return_value=kernel, create=True) as load, \
             patch.object(inventory.C, 'get_last_error', return_value=231, create=True), \
             patch.object(inventory.OwnedPipe, '_adopt', return_value=owner) as adopt, \
             patch.object(inventory.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(inventory, '_RETAINED_PIPES', retained_pipes), \
             patch.object(inventory, '_RETAINED_HANDLES', retained_handles):
            yield kernel, owner, adopt, load, clock, retained_pipes, retained_handles

    def test_fixed_local_readonly_get_and_same_absolute_deadline(self):
        with self.native() as (kernel, owner, adopt, _load, _clock, pipes, handles):
            self.assertEqual(inventory.query_containers(102.0), ['hh-test'])
            kernel.CreateFileW.assert_called_once_with(
                r'\\.\pipe\dockerDesktopLinuxEngine', 0xC0000000, 0, None, 3, 0x40000000, None)
            adopt.assert_called_once_with(123)
            self.assertEqual(owner._io.call_args_list[0].args,
                             ('write', len(inventory.REQUEST), 102.0, inventory.REQUEST))
            self.assertEqual(inventory.REQUEST,
                b'GET /containers/json?all=0 HTTP/1.1\r\nHost: docker\r\n'
                b'Accept: application/json\r\nConnection: close\r\n\r\n')
            self.assertTrue(all(call.args[2] == 102.0 for call in owner._io.call_args_list))
            self.assertTrue(all(call.args[:2] == ('read', 4096)
                                for call in owner._io.call_args_list[1:]))
            owner.close.assert_called_once_with()
            kernel.CloseHandle.assert_not_called()
            self.assertEqual((pipes, handles), ([], []))

    def test_expired_deadline_and_unsupported_platform_never_open_pipe(self):
        with self.native(clock=[102.0]) as (_kernel, owner, _adopt, load, *_rest):
            with self.assertRaises(inventory.InventoryError) as caught:
                inventory.query_containers(102.0)
            self.assertEqual(caught.exception.reason, 'timeout')
            load.assert_not_called()
            owner._io.assert_not_called()
        with self.native() as (_kernel, _owner, _adopt, load, *_rest):
            with patch.object(inventory.os, 'name', 'posix'):
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.query_containers(102.0)
            self.assertEqual(caught.exception.reason, 'oserror')
            self.assertFalse(caught.exception.retryable)
            load.assert_not_called()

    def test_failed_open_is_scalar_retryable_unknown_not_empty(self):
        for handle in (None, inventory.C.c_void_p(-1).value):
            with self.subTest(handle=handle), self.native() as (kernel, owner, adopt, *_rest):
                kernel.CreateFileW.return_value = handle
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.query_containers(102.0)
                self.assertEqual(caught.exception.reason, 'oserror')
                self.assertEqual(caught.exception.detail, 231)
                self.assertTrue(caught.exception.retryable)
                adopt.assert_not_called()
                owner.close.assert_not_called()
                kernel.CloseHandle.assert_not_called()

    def test_parser_failure_and_pipe_error_always_close_owned_pipe(self):
        for response in (content_length(b'broken-secret-body'),
                         content_length(encoded([row(State='exited')])),
                         b'HTTP/1.1 503 secret-reason\r\n'):
            with self.subTest(response=response[:80]), self.native(response=response) as (_k, owner, *_rest):
                with self.assertRaises(inventory.InventoryError):
                    inventory.query_containers(102.0)
                owner.close.assert_called_once_with()
        for code, reason in (('PIPE_TIMEOUT', 'timeout'), ('PIPE_IO_FAILED', 'oserror'),
                             ('PIPE_DRAIN_PENDING', 'oserror')):
            with self.subTest(code=code), self.native() as (_k, owner, *_rest):
                owner._io.side_effect = inventory.PipeIOError(code)
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.query_containers(102.0)
                self.assertEqual(caught.exception.reason, reason)
                self.assertFalse(caught.exception.retryable)
                owner.close.assert_called_once_with()

    def test_late_read_and_late_cleanup_cannot_return_success(self):
        for late_stage in ('read', 'close'):
            with self.subTest(stage=late_stage), self.native() as (_k, owner, _a, _l, clock, *_rest):
                if late_stage == 'read':
                    def late_io(kind, _size, _deadline, _payload=b''):
                        if kind == 'read':
                            clock[0] = 102.001
                            return content_length(encoded([row()]))
                        return b''
                    owner._io.side_effect = late_io
                else:
                    owner.close.side_effect = lambda: clock.__setitem__(0, 102.001)
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.query_containers(102.0)
                self.assertEqual(caught.exception.reason, 'timeout')
                self.assertFalse(caught.exception.retryable)
                owner.close.assert_called_once_with()

    def test_failed_close_retains_owner_and_blocks_every_later_query(self):
        with self.native(response=b'HTTP/1.1 503 secret-reason\r\n') as (
                kernel, owner, _adopt, _load, _clock, pipes, _handles):
            owner.close.side_effect = RuntimeError('secret-close-message')
            with self.assertRaises(inventory.InventoryError) as caught:
                inventory.query_containers(102.0)
            self.assertEqual(caught.exception.reason, 'oserror')
            self.assertFalse(caught.exception.retryable)
            self.assertIs(pipes[0], owner)
            kernel.CreateFileW.reset_mock()
            with self.assertRaises(inventory.InventoryError) as next_error:
                inventory.query_containers(102.0)
            self.assertFalse(next_error.exception.retryable)
            kernel.CreateFileW.assert_not_called()
            owner.close.assert_called_once_with()

    def test_adoption_failure_closes_raw_handle_or_retains_it_without_retry(self):
        for closed in (True, False):
            with self.subTest(closed=closed), self.native() as (
                    kernel, owner, adopt, _load, _clock, pipes, handles):
                adopt.side_effect = RuntimeError('secret-adoption-error')
                kernel.CloseHandle.return_value = closed
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.query_containers(102.0)
                self.assertEqual(caught.exception.reason, 'oserror')
                self.assertFalse(caught.exception.retryable)
                kernel.CloseHandle.assert_called_once_with(123)
                owner._io.assert_not_called()
                owner.close.assert_not_called()
                self.assertEqual(pipes, [])
                self.assertEqual(handles, [] if closed else [(kernel, 123)])
                if not closed:
                    kernel.CreateFileW.reset_mock()
                    with self.assertRaises(inventory.InventoryError):
                        inventory.query_containers(102.0)
                    kernel.CreateFileW.assert_not_called()

    def test_preexisting_retained_resources_forbid_new_inventory(self):
        for held in ('pipe', 'handle'):
            with self.subTest(held=held), self.native(
                    retained_pipes=[object()] if held == 'pipe' else [],
                    retained_handles=[object()] if held == 'handle' else []) as (
                    kernel, _owner, _adopt, load, *_rest):
                with self.assertRaises(inventory.InventoryError) as caught:
                    inventory.query_containers(102.0)
                self.assertEqual(caught.exception.reason, 'oserror')
                self.assertFalse(caught.exception.retryable)
                load.assert_not_called()
                kernel.CreateFileW.assert_not_called()

    def test_query_failure_does_not_print_or_expose_raw_secret_context(self):
        output = StringIO()
        with self.native(response=b'HTTP/1.1 503 secret-status\r\n') as (_k, owner, *_rest):
            owner.close.side_effect = RuntimeError('secret-close-error')
            with redirect_stdout(output):
                try:
                    inventory.query_containers(102.0)
                except inventory.InventoryError as error:
                    rendered = ''.join(traceback.format_exception(error))
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('secret-status', rendered)
        self.assertNotIn('secret-close-error', rendered)


if __name__ == '__main__':
    unittest.main()

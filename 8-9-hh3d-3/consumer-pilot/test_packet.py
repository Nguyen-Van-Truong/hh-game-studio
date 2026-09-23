"""Regression checks for the exact-byte S177 packet, without launching engines."""
import json
import unittest

from verify_packet import MANIFEST, PACKET, Reader, digest, verify


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.read = Reader()

    def override(self, path, data, rehash=False):
        manifest = json.loads(self.read(MANIFEST))
        if rehash:
            manifest['files'][path] = {'sha256': digest(data), 'bytes': len(data)}
        def read(relative):
            if relative == path:
                return data
            if relative == MANIFEST:
                return json.dumps(manifest).encode()
            return self.read(relative)
        return read

    def test_current_packet(self):
        self.assertTrue(verify(self.read)['integrity_verified'])

    def test_newline_conversion_is_not_exact_evidence(self):
        path = '8-9-hh3d-3/zdoc/reviews/20260923-consumer-pilot-s177-derived/author-binding-01.json'
        original = self.read(path)
        changed = original.replace(b'\r\n', b'\n')
        self.assertNotEqual(original, changed)
        with self.assertRaisesRegex(ValueError, 'packet drift'):
            verify(self.override(path, changed))

    def test_rehashed_scene_still_must_match_executed_source(self):
        path = '8-9-hh3d-3/consumer-pilot/main.tscn'
        with self.assertRaisesRegex(ValueError, 'executed runtime source differs'):
            verify(self.override(path, self.read(path).rstrip() + b'\n', rehash=True))

    def test_rehashed_receipt_cannot_change_actual_exit(self):
        path = PACKET + 'runtime/runtime-host.json'
        receipt = json.loads(self.read(path))
        receipt['exit_code'] = 1
        with self.assertRaisesRegex(ValueError, 'exit/cleanup mismatch'):
            verify(self.override(path, json.dumps(receipt).encode(), rehash=True))

    def test_cannot_relabel_original_collector_failure_as_success(self):
        path = PACKET + 'runtime/result.json'
        result = json.loads(self.read(path))
        result['runtime_checks_passed'] = True
        with self.assertRaisesRegex(ValueError, 'derived/raw binding'):
            verify(self.override(path, json.dumps(result).encode(), rehash=True))


if __name__ == '__main__':
    unittest.main()

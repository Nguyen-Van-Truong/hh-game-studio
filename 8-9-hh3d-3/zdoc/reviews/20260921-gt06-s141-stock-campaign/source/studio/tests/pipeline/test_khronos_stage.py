"""Pinned real Node/Khronos stage; tiny original bytes, no engine or network."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.native_job import StageFailed, run_trusted_stage


def triangle():
    binary = struct.pack('<9f3H', 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 2)
    document = {'asset': {'version': '2.0'}, 'scene': 0,
        'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1}]}],
        'buffers': [{'byteLength': len(binary)}],
        'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': 36},
                        {'buffer': 0, 'byteOffset': 36, 'byteLength': 6}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3',
                       'min': [0, 0, 0], 'max': [1, 1, 0]},
                      {'bufferView': 1, 'componentType': 5123, 'count': 3, 'type': 'SCALAR'}]}
    raw = json.dumps(document, separators=(',', ':')).encode()
    raw += b' ' * (-len(raw) % 4)
    binary += b'\0' * (-len(binary) % 4)
    return struct.pack('<4sII', b'glTF', 2, 28 + len(raw) + len(binary)) + \
        struct.pack('<II', len(raw), 0x4e4f534a) + raw + \
        struct.pack('<II', len(binary), 0x004e4942) + binary


@unittest.skipUnless(os.name == 'nt', 'Windows owned runner required')
class KhronosStageTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='gt05-khronos-test-', dir=STUDIO / '.local/reviews'))
        self.node = Path(shutil.which('node') or '')
        self.runtime = json.loads((STUDIO / 'pipeline/dependencies/node.lock.json').read_bytes())
        if not self.node.is_file():
            self.skipTest('SKIP_ENVIRONMENT: pinned Node executable unavailable')
        self.lock_path = STUDIO / 'pipeline/dependencies/gltf-validator.lock.json'
        self.lock = json.loads(self.lock_path.read_bytes())
        cache = STUDIO / '.local/tooling/gt05/gltf-validator-2.0.0-dev.3.10'
        for name, digest in self.lock['files'].items():
            source = cache / name
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
            destination = self.root / 'dependency' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        shutil.copyfile(self.lock_path, self.root / 'gltf-validator.lock.json')
        self.script = STUDIO / 'pipeline/validate_glb.cjs'

    def run_stage(self, raw):
        (self.root / 'fixture.glb').write_bytes(raw)
        (self.root / 'admission.json').write_text(json.dumps({
            'schema': 'HH-GT05-VALIDATOR-INPUT-1',
            'artifact_sha256': hashlib.sha256(raw).hexdigest()}), encoding='utf-8')
        return run_trusted_stage([str(self.node), '--max-old-space-size=256',
                                  str(self.script), str(self.root)],
            cwd=self.root, output=self.root / 'host', source_root=STUDIO,
            source_files={name: hashlib.sha256((STUDIO / name).read_bytes()).hexdigest()
                          for name in ('pipeline/validate_glb.cjs', 'pipeline/dependencies/node.lock.json',
                                       'pipeline/dependencies/gltf-validator.lock.json')},
            binary_sha256=self.runtime['binary_sha256'])

    def test_real_validator_accepts_original_triangle(self):
        host = self.run_stage(triangle())
        self.assertTrue(host['completed'])
        report = json.loads((self.root / 'validator.json').read_bytes())
        self.assertEqual(report['validator_version'], self.lock['version'])
        self.assertFalse(report['external_resource_requested'])
        self.assertEqual(report['result']['issues']['numErrors'], 0)
        self.assertEqual(report['result']['issues']['numWarnings'], 0)

    def test_malformed_asset_cannot_pass_on_wrapper_exit(self):
        with self.assertRaises(StageFailed):
            self.run_stage(b'bad-header')
        host = json.loads((self.root / 'host/capture.json').read_bytes())
        self.assertFalse(host['completed'])
        self.assertTrue(host['job']['closed'])
        self.assertTrue(host['job']['zero_observed'])

    def test_changed_dependency_is_rejected_before_require(self):
        (self.root / 'dependency/package/index.js').write_text('throw new Error("untrusted")')
        with self.assertRaises(StageFailed):
            self.run_stage(triangle())
        self.assertEqual((self.root / 'host/stderr.txt').read_text().strip(), 'DEPENDENCY_HASH')
        self.assertFalse((self.root / 'validator.json').exists())


if __name__ == '__main__':
    unittest.main()

"""P4 negative schema and untrusted-rollback checks. Not a native proof."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from studio.package.consumer_install import ConsumerInstall
from studio.package.release_contract import build_package
from studio.tests.conformance.gt10pc_p4_negative import (
    ROLLBACK_COMMAND_ID, SCHEMA_COMMAND_ID, build_bad_artifacts, run_negative, verify_negative,
)


class P4NegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.key = Ed25519PrivateKey.generate()
        cls.keys = {"test": cls.key.public_key().public_bytes_raw()}
        source = Path(__file__).resolve().parents[2]
        cls.good_path = root / "good.hhpkg"
        cls.upgrade_path = root / "upgrade.hhpkg"
        cls.good = build_package(source, cls.good_path, signer=cls.key.sign, key_id="test")
        cls.upgrade = build_package(source, cls.upgrade_path, signer=cls.key.sign,
                                    key_id="test", version="0.1.1")
        cls.install_root = root / "install"
        install = ConsumerInstall(cls.install_root, trusted_keys=cls.keys, target="Windows")
        install.install(cls.good_path, command_id="seed.install",
                        expected_state_sha256=install.snapshot()["state_sha256"])
        install.install(cls.upgrade_path, command_id="seed.upgrade",
                        expected_state_sha256=install.snapshot()["state_sha256"])
        cls.out = root / "negative"
        built = build_bad_artifacts(cls.good_path, cls.key.sign, cls.out)
        run_negative(cls.install_root, cls._open, built, cls.out)
        cls.result = verify_negative(cls.out, cls.keys)

    @classmethod
    def _open(cls) -> ConsumerInstall:
        return ConsumerInstall(cls.install_root, trusted_keys=cls.keys, target="Windows")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copy_out(self) -> Path:
        dest = Path(tempfile.mkdtemp())
        copied = dest / "negative"
        shutil.copytree(self.out, copied)
        self.addCleanup(lambda: shutil.rmtree(dest, ignore_errors=True))
        return copied

    def test_refused_schema_and_untrusted_rollback_keep_state(self):
        result = self.result
        self.assertEqual(result["status"], "P4_NEG_VERIFIED")
        self.assertEqual(result["authority"], 0)
        self.assertIs(result["acceptance"], False)
        schema = result["cases"]["incompatible-schema"]
        rollback = result["cases"]["untrusted-rollback"]
        self.assertEqual(schema["error"], "unsupported package schema")
        self.assertEqual(schema["command_id"], SCHEMA_COMMAND_ID)
        self.assertEqual(schema["active"], self.upgrade["manifest_sha256"])
        self.assertEqual(schema["previous"], self.good["manifest_sha256"])
        self.assertEqual(rollback["error"], "untrusted signing key")
        self.assertEqual(rollback["command_id"], ROLLBACK_COMMAND_ID)
        self.assertEqual(rollback["active"], self.upgrade["manifest_sha256"])
        self.assertEqual(rollback["previous"], rollback["manifest_sha256"])
        self.assertNotEqual(rollback["previous"], self.good["manifest_sha256"])
        for name in ("incompatible-schema", "untrusted-rollback"):
            case = self.out / name
            self.assertEqual((case / "state-before.install.json").read_bytes(),
                             (case / "state-after.install.json").read_bytes())

    def test_verify_rejects_changed_state_bytes(self):
        copied = self.copy_out()
        path = copied / "incompatible-schema" / "state-after.install.json"
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, r"^P4_NEG_STATE_BYTES$"):
            verify_negative(copied, self.keys)

    def test_verify_rejects_recorded_command_id(self):
        copied = self.copy_out()
        case = copied / "untrusted-rollback"
        raw = (case / "state-before.install.json").read_bytes()
        text = raw.decode("ascii")
        self.assertNotIn(ROLLBACK_COMMAND_ID, text)
        needle = '"commands":{'
        self.assertIn(needle, text)
        mutated = text.replace(needle, needle + '"' + ROLLBACK_COMMAND_ID + '":{},', 1)
        blob = mutated.encode("ascii")
        (case / "state-before.install.json").write_bytes(blob)
        (case / "state-after.install.json").write_bytes(blob)
        with self.assertRaisesRegex(ValueError, r"^P4_NEG_COMMAND_PRESENT$"):
            verify_negative(copied, self.keys)

    def test_verify_rejects_wrong_exception_text(self):
        copied = self.copy_out()
        (copied / "incompatible-schema" / "exception.txt").write_bytes(b"package signature invalid")
        with self.assertRaisesRegex(ValueError, r"^P4_NEG_EXCEPTION$"):
            verify_negative(copied, self.keys)


if __name__ == "__main__":
    unittest.main()

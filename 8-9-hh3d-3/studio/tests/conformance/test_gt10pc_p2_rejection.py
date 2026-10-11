"""Focused P2 installer boundary test; native proof remains a scheduled run."""
from pathlib import Path
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from studio.package.consumer_install import ConsumerInstall
from studio.package.release_contract import PackageError, build_package
from studio.tests.conformance.gt10pc_p2_native_rejection import tree_ledger


class P2VersionBoundaryTests(unittest.TestCase):
    def test_wrong_version_preserves_existing_installer_root_before_unpack(self):
        source = Path(__file__).resolve().parents[2]
        key = Ed25519PrivateKey.generate()
        keys = {"local-p2-test": key.public_key().public_bytes_raw()}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "release.hhpkg"
            build_package(source, artifact, signer=key.sign, key_id="local-p2-test")
            installer = ConsumerInstall(root / "install", trusted_keys=keys)
            installer.install(artifact, command_id="last-good", expected_state_sha256="ABSENT")
            token = installer.snapshot()["state_sha256"]
            before = tree_ledger(installer.root)
            with self.assertRaisesRegex(PackageError, "package version rejected"):
                installer.install(artifact, command_id="wrong-version",
                                  expected_state_sha256=token, expected_version="0.1.1")
            self.assertEqual(before, tree_ledger(installer.root))
            self.assertEqual(token, installer.snapshot()["state_sha256"])
            self.assertIsNone(installer.lookup("wrong-version"))


if __name__ == "__main__":
    unittest.main()

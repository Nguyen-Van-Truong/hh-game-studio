"""Export boundaries and hostile copies of native Linux evidence."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from studio.package.release_contract import PackageError
from studio.tests.conformance.gt10pc_linux_producer import export_public_evidence
from studio.tests.conformance.gt10pc_linux_worker import bind_negative_inputs


class LinuxEvidenceExportTests(unittest.TestCase):
    def test_install_phase_is_retained_private_nested_trees_are_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, exported = root / "output", root / "exported"
            public = (
                "linux.json", "consumer/gt09-arena/project-before.json",
                "consumer/gt09-arena/drivers/install/receipt.json",
                "consumer/gt09-arena/native/install/godot-stdout.txt",
                "consumer/gt09-room/native/reinstall/parse-host.json",
            )
            private = (
                "consumer/gt09-arena/install/releases/secret.json",
                "consumer/gt09-arena/project/save.dat",
                "consumer/gt09-arena/native/install/profile-owner/token.json",
                "consumer/gt09-room/native/install/godot-user/cache.json",
                "consumer/gt09-arena/.hh-studio-addon-test/backup/token.txt",
            )
            for name in (*public, *private):
                path = output / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            export_public_evidence(output, exported)
            self.assertEqual(set(public), {p.relative_to(exported).as_posix()
                                          for p in exported.rglob("*") if p.is_file()})
            for name in public:
                self.assertEqual((exported / name).read_bytes(), name.encode())

    def test_negative_evidence_is_exported_and_private_install_is_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, exported = root / "output", root / "exported"
            digest = "ab" * 32
            public = (
                "linux.json",
                "negative/incompatible-schema.hhpkg",
                "negative/incompatible-schema/exception.txt",
                "negative/untrusted-rollback/setup.json",
                "negative/untrusted-release/" + digest + "/manifest.json",
            )
            private = "consumer/negative/install/releases/secret.json"
            for name in (*public, private):
                path = output / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            export_public_evidence(output, exported)
            exported_names = {p.relative_to(exported).as_posix() for p in exported.rglob("*") if p.is_file()}
            self.assertTrue(set(public) <= exported_names)
            self.assertNotIn(private, exported_names)

    def test_negative_evidence_over_the_cap_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "output" / "negative" / "incompatible-schema.hhpkg"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"\0" * (16 * 1024 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "exceeds bound"):
                export_public_evidence(root / "output", root / "exported")

    def test_negative_input_pin_rejects_a_changed_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            archive = source / "negative" / "incompatible-schema.hhpkg"
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b"archive-bytes")
            manifest_bytes = b"manifest-bytes"
            archive_sha = hashlib.sha256(b"archive-bytes").hexdigest()
            manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
            manifest = source / "negative" / "untrusted-release" / manifest_sha / "manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_bytes(manifest_bytes)
            request = {"negative_incompatible_sha256": archive_sha,
                       "negative_manifest_sha256": manifest_sha}
            bound = bind_negative_inputs(source, request)
            self.assertEqual(bound["incompatible-schema.hhpkg"]["sha256"], archive_sha)
            archive.write_bytes(b"tampered")
            with self.assertRaises(PackageError):
                bind_negative_inputs(source, request)


if __name__ == "__main__":
    unittest.main()

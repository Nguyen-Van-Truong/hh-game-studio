"""Export boundaries and hostile copies of native Linux evidence."""
import tempfile
import unittest
from pathlib import Path

from studio.tests.conformance.gt10pc_linux_producer import export_public_evidence


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


if __name__ == "__main__":
    unittest.main()

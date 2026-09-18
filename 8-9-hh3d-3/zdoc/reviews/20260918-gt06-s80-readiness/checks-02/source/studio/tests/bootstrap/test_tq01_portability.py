import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[2]

def load(name):
    p = STUDIO / "build" / "bootstrap" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

VERIFY = load("verify_archive")


class TQ01Portability(unittest.TestCase):
    def test_lock_uses_portable_relative_names_and_bound_provenance(self):
        lock = json.loads((STUDIO / "toolchain.lock.json").read_text(encoding="utf-8"))
        g = lock["godot"]
        for value in (g["archive"]["name"], g["console_executable"], g["gui_executable"]):
            self.assertNotIn("\\", value); self.assertNotIn("/", value)
            self.assertNotRegex(value, r"(?i)([A-Z]:|/|\\\\|%USER%|/Users/|/home/)")
        self.assertRegex(g["source_commit"], r"^[0-9a-f]{40}$")
        version = g["version"]
        self.assertEqual(g["source"], f"https://github.com/godotengine/godot-builds/releases/tag/{version}")
        self.assertEqual(g["source_commit_url"], f"https://api.github.com/repos/godotengine/godot/git/ref/tags/{version}")
        self.assertEqual(g["archive"]["url"], f"https://github.com/godotengine/godot-builds/releases/download/{version}/{g['archive']['name']}")
        self.assertEqual(g["sha512_sums"]["url"], f"https://github.com/godotengine/godot-builds/releases/download/{version}/SHA512-SUMS.txt")

    def test_actual_archive_and_sums_verify_under_unicode_space_path(self):
        with tempfile.TemporaryDirectory(prefix="TQ01 Unicode 测试 ") as td:
            root = Path(td); archive = root / "Godot_v4.7.2-stable_win64.exe.zip"; sums = root / "SHA512-SUMS.txt"
            payload = b"portable-fixture"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as z:
                z.writestr("Godot_v4.7.2-stable_win64.exe", payload)
            digest = hashlib.sha512(archive.read_bytes()).hexdigest()
            sums.write_text(f"{digest} *{archive.name}\n", encoding="utf-8")
            lock = {"schema":"HH-STUDIO-TOOLCHAIN-LOCK-2", "status":"CANDIDATE", "godot": {
                "version":"4.7.2-stable", "source_tag":"4.7.2-stable", "source_commit":"e"*40,
                "source":"https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable",
                "source_commit_url":"https://api.github.com/repos/godotengine/godot/git/ref/tags/4.7.2-stable",
                "archive":{"name":archive.name,"url":"https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/"+archive.name,"sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),"sha512":digest,"size_bytes":archive.stat().st_size},
                "sha512_sums":{"url":"https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/SHA512-SUMS.txt","sha256":hashlib.sha256(sums.read_bytes()).hexdigest()}}}
            lp = root / "lock.json"; lp.write_text(json.dumps(lock), encoding="utf-8")
            self.assertEqual(VERIFY.verify_archive(lp, archive, sums)["status"], "VERIFIED_BYTES_ONLY")

    def test_digest_mismatch_fails_before_install_side_effects(self):
        with tempfile.TemporaryDirectory(prefix="TQ01 ") as td:
            root = Path(td); archive = root / "a.zip"; sums = root / "SHA512-SUMS.txt"; lock = root / "lock.json"
            archive.write_bytes(b"bytes"); sums.write_text("0"*128 + " *a.zip\n", encoding="utf-8")
            data = {"schema":"HH-STUDIO-TOOLCHAIN-LOCK-2", "status":"CANDIDATE", "godot":{"version":"4.7.2-stable","source_tag":"4.7.2-stable","source_commit":"e"*40,"source":"https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable","source_commit_url":"https://api.github.com/repos/godotengine/godot/git/ref/tags/4.7.2-stable","archive":{"name":"a.zip","url":"https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/a.zip","sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),"sha512":hashlib.sha512(archive.read_bytes()).hexdigest(),"size_bytes":archive.stat().st_size},"sha512_sums":{"url":"https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/SHA512-SUMS.txt","sha256":hashlib.sha256(sums.read_bytes()).hexdigest()}}}
            lock.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(VERIFY.VerificationError): VERIFY.verify_archive(lock, archive, sums)
            self.assertEqual(sorted(root.iterdir(), key=lambda p: p.name), sorted([archive, sums, lock], key=lambda p: p.name))

if __name__ == "__main__": unittest.main()

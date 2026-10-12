"""Transaction gaps: undo readback, GLB external URIs, template hashing, export cleanup."""

from __future__ import annotations

import io
import json
import os
import struct
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from studio.gamekit import common as C
from studio.gamekit import export as E
from studio.gamekit import media_inspect as M
from studio.gamekit import scene as S


def _glb(doc: dict, binary: bytes = b"") -> bytes:
    payload = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    chunks = struct.pack("<II", len(payload), 0x4E4F534A) + payload
    if binary:
        blob = binary + b"\x00" * ((4 - len(binary) % 4) % 4)
        chunks += struct.pack("<II", len(blob), 0x004E4942) + blob
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def _junction(link: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise OSError(completed.stderr or completed.stdout or "mklink failed")


class _TempState(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._old_state = os.environ.get("HH_GAMEKIT_STATE")
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "project.godot").write_text(
            'config_version=5\n\n[application]\n\nconfig/name="Game"\nrun/main_scene="res://main.tscn"\n',
            encoding="utf-8",
        )
        (self.game / "main.tscn").write_text('[gd_scene format=3]\n\n[node name="Main" type="Node"]\n', encoding="utf-8")
        self.project = C.register_project(self.game, "game")

    def tearDown(self) -> None:
        if self._old_state is None:
            os.environ.pop("HH_GAMEKIT_STATE", None)
        else:
            os.environ["HH_GAMEKIT_STATE"] = self._old_state
        self.tmp.cleanup()


class UndoReadbackTest(_TempState):
    def test_failed_readback_keeps_current_bytes_and_retry_works(self) -> None:
        scene = self.game / "main.tscn"
        before = b"BEFORE-BYTES"
        current = b"CURRENT-BYTES"
        scene.write_bytes(before)
        C.checkpoint(self.project, "cmd.probe.1", [scene])
        scene.write_bytes(current)
        C.Journal(self.project).append("cmd.probe.1", "apply-digest", {
            "ok": True,
            "kind": "scene.apply",
            "scene": "res://main.tscn",
            "before_sha256": C.sha256_bytes(before),
            "after_sha256": C.sha256_bytes(current),
        })

        def boom(*_args: object, **_kwargs: object) -> C.ProcessRun:
            raise C.GamekitError("TIMEOUT", "injected readback failure")

        with patch.object(S.C, "run_godot_tool", boom):
            with self.assertRaises(C.GamekitError) as cm:
                S.undo(self.project, "cmd.probe.1", allow_open_editor=True)
        self.assertEqual(cm.exception.code, "TIMEOUT")
        self.assertEqual(scene.read_bytes(), current)
        self.assertEqual([rec["command_id"] for rec in C.Journal(self.project).records()], ["cmd.probe.1"])

        def ok_tool(*_args: object, **_kwargs: object) -> C.ProcessRun:
            return C.ProcessRun(
                argv=["godot"], exit_code=0, seconds=0.01, stdout="", stderr="", result={"ok": True},
            )

        with patch.object(S.C, "run_godot_tool", ok_tool):
            out = S.undo(self.project, "cmd.probe.1", allow_open_editor=True)
        self.assertEqual(out["status"], "UNDONE")
        self.assertEqual(scene.read_bytes(), before)
        self.assertIn("undo.cmd.probe.1", [rec["command_id"] for rec in C.Journal(self.project).records()])


class GlbExternalUriTest(unittest.TestCase):
    def test_external_buffer_uri_is_validation_failed(self) -> None:
        external = {"asset": {"version": "2.0"}, "buffers": [{"uri": "../outside.bin", "byteLength": 4}]}
        with self.assertRaises(C.GamekitError) as cm:
            M.inspect_media(_glb(external), ".glb")
        self.assertEqual(cm.exception.code, "VALIDATION_FAILED")
        self.assertIn("external", cm.exception.detail)

        image = {"asset": {"version": "2.0"}, "images": [{"uri": "../outside.png"}]}
        with self.assertRaises(C.GamekitError) as cm_img:
            M.inspect_media(_glb(image), ".glb")
        self.assertEqual(cm_img.exception.code, "VALIDATION_FAILED")

        embedded = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}]}
        checks = M.inspect_media(_glb(embedded, b"\x00\x00\x00\x00"), ".glb")
        self.assertEqual(checks["format"], "glb")
        self.assertEqual(checks["external_uris"], [])


class TemplateHashTest(unittest.TestCase):
    def test_install_hashes_even_when_cache_matches(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        archive = root / "templates.tpz"
        archive.write_bytes(b"not-a-real-archive")
        templates = root / "export_templates" / "4.7.2.stable"
        templates.parent.mkdir(parents=True)
        st = archive.stat()
        C.atomic_write_json(templates.parent / E.CACHE_NAME, {
            "schema": "hh-gamekit-export-templates-1",
            "archive": archive.name,
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "sha256": E.ARCHIVE_SHA256,
        })
        seen: list[Path] = []

        def fake_sha(path: Path) -> str:
            seen.append(Path(path))
            return E.ARCHIVE_SHA256

        with patch.object(E, "templates_dir", lambda: templates), \
             patch.object(E, "_archive_path", lambda: archive), \
             patch.object(E, "_install_members", lambda _platform: ([], [])), \
             patch.object(E.C, "sha256_file", fake_sha):
            installed = E.templates(install=True, platform="windows")
            self.assertTrue(installed["archive_verified"])
            self.assertFalse(installed["archive_cached"])
            self.assertTrue(any(path.resolve() == archive.resolve() for path in seen))
            seen.clear()
            status = E.templates(install=False, platform="windows")
        self.assertFalse(status["archive_verified"])
        self.assertTrue(status["archive_cached"])
        self.assertEqual(seen, [])

    def test_same_size_member_is_extracted_when_bytes_differ(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("templates/payload.bin", b"aaaa")
        dest = Path(tempfile.mkdtemp()) / "payload.bin"
        self.addCleanup(lambda: dest.unlink(missing_ok=True))
        dest.write_bytes(b"bbbb")
        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf:
            info = zf.getinfo("templates/payload.bin")
            self.assertEqual(dest.stat().st_size, info.file_size)
            self.assertTrue(E._needs_extract(dest, zf, info))
            dest.write_bytes(b"aaaa")
            self.assertFalse(E._needs_extract(dest, zf, info))


class ExportFailureTest(_TempState):
    def setUp(self) -> None:
        super().setUp()
        self.preset = b'[preset.0]\n\nname="Player Build"\nplatform="Windows Desktop"\n'
        (self.game / "export_presets.cfg").write_bytes(self.preset)

    def _patches(self, smoke_out: Path | None = None):
        def fake_godot(_root: object, _script: object, _args: object, **kwargs: object) -> C.ProcessRun:
            extra = kwargs.get("extra") or ()
            target = Path(str(tuple(extra)[-1]))  # type: ignore[arg-type]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"E" * 1_000_000)
            (target.parent / "Game.pck").write_bytes(b"P" * 128)
            return C.ProcessRun(argv=["godot"], exit_code=0, seconds=0.01, stdout="", stderr="")

        def fake_smoke(exe: Path) -> dict:
            if smoke_out is not None and os.path.normcase(str(exe.parent)) == os.path.normcase(str(smoke_out)):
                raise AssertionError("smoke ran inside out-dir")
            raise C.GamekitError("GODOT_FAILED", "smoke failed")

        return (
            patch.object(E, "_require_installed", lambda _preset: None),
            patch("studio.gamekit.scene.refresh_import", return_value={"ok": True}),
            patch.object(E.C, "run_godot", fake_godot),
            patch.object(E, "_smoke_windows", fake_smoke),
        )

    def test_failed_smoke_leaves_out_dir_unchanged(self) -> None:
        out = self.root / "dist"
        out.mkdir()
        (out / "keep.txt").write_bytes(b"KEEP")
        (out / "Game.exe").write_bytes(b"OLD-EXE")
        before = {p.name: p.read_bytes() for p in out.iterdir()}
        patches = self._patches(out)
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(C.GamekitError) as cm:
                E.export_run(self.project, "windows", out, "cmd.export.fail1", allow_open_editor=True)
        self.assertEqual(cm.exception.code, "GODOT_FAILED")
        self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)
        self.assertEqual((self.game / "export_presets.cfg").read_bytes(), self.preset)
        self.assertEqual(C.Journal(self.project).records(), [])
        self.assertEqual(list(self.root.glob(".hh-export-*")), [])

        missing = self.root / "no-such-dist"
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(C.GamekitError) as cm2:
                E.export_run(self.project, "windows", missing, "cmd.export.fail2", allow_open_editor=True)
        self.assertEqual(cm2.exception.code, "GODOT_FAILED")
        self.assertFalse(missing.exists())
        self.assertEqual((self.game / "export_presets.cfg").read_bytes(), self.preset)
        self.assertEqual(list(self.root.glob(".hh-export-*")), [])


class OutDirReparseTest(_TempState):
    def test_junction_out_dir_is_refused(self) -> None:
        target = self.root / "real-dest"
        link = self.root / "jump"
        _junction(link, target)
        try:
            with self.assertRaises(C.GamekitError) as cm:
                E.validate_out_dir(self.project, link)
            self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")
            with self.assertRaises(C.GamekitError) as nested:
                E.validate_out_dir(self.project, link / "dist")
            self.assertEqual(nested.exception.code, "FORBIDDEN_PATH")
        finally:
            # Do not follow a junction just to remove it during cleanup.
            try:
                os.rmdir(link)
            except FileNotFoundError:
                pass

    def test_junction_is_checked_before_realpath(self) -> None:
        with patch.object(E, "_path_or_ancestor_reparse", return_value=True), patch.object(E.os.path, "realpath", side_effect=AssertionError("followed a junction")):
            with self.assertRaises(C.GamekitError) as caught:
                E.validate_out_dir(self.project, self.root / "junction")
        self.assertEqual(caught.exception.code, "FORBIDDEN_PATH")

    def test_unresolvable_out_dir_returns_stable_error(self) -> None:
        with patch.object(E, "_path_or_ancestor_reparse", return_value=False), patch.object(E.os.path, "realpath", side_effect=OSError(448, "reparse resolution failed")):
            with self.assertRaises(C.GamekitError) as caught:
                E.validate_out_dir(self.project, self.root / "dist")
        self.assertEqual(caught.exception.code, "FORBIDDEN_PATH")


if __name__ == "__main__":
    unittest.main()

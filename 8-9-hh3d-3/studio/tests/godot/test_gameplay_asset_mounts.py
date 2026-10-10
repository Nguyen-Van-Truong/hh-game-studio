"""Pure policy tests for gameplay-source asset mounts and sandbox paths.

These tests inspect Docker argv/metadata only.  They never start Docker or
Godot and deliberately keep the fixture's immutable ``/project`` bind mount
separate from the per-file asset binds.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

from tests.godot.test_linux_executor import CID, IMAGE_ENV, NAME, executor, inspected


ASSET_FILES = ("assets/avatar.glb", "assets/sprite_sheet.png")
ASSET_TMPFS_OPTIONS = (
    "rw,nosuid,nodev,noexec,size=4m,nr_inodes=512,"
    "uid=65532,gid=65532,mode=0700"
)


def _mounts(argv: list[str]) -> list[dict[str, str]]:
    """Decode only the stable mount fields emitted by ``docker create``."""
    values: list[dict[str, str]] = []
    for index, item in enumerate(argv):
        if item != "--mount":
            continue
        values.append(
            {
                part.split("=", 1)[0]: part.split("=", 1)[1]
                for part in argv[index + 1].split(",")
                if "=" in part
            }
            | {
                "readonly": "readonly" in argv[index + 1].split(","),
                "bind-propagation": next(
                    (
                        part.split("=", 1)[1]
                        for part in argv[index + 1].split(",")
                        if part.startswith("bind-propagation=")
                    ),
                    "",
                ),
            }
        )
    return values


def _gameplay_inspect(tool: Path, snapshot: Path) -> dict:
    """Build the exact inspected shape expected for a two-asset run."""
    value = inspected(NAME, CID, "gameplay-source", tool, snapshot)
    value["HostConfig"]["Tmpfs"] = dict(executor.TMPFS)
    value["HostConfig"]["Tmpfs"]["/project/assets"] = ASSET_TMPFS_OPTIONS
    value["Mounts"].extend(
        {
            "Type": "bind",
            "Source": str(snapshot / relative),
            "Destination": "/project/" + relative,
            "RW": False,
            "Propagation": "rprivate",
        }
        for relative in ASSET_FILES
    )
    value["Mounts"].append({
        "Type": "bind",
        "Source": str(snapshot.parent / "harness"),
        "Destination": "/harness",
        "RW": False,
        "Propagation": "rprivate",
    })
    return value


class GameplayAssetMountTests(unittest.TestCase):
    def test_gameplay_argv_keeps_project_readonly_and_adds_exact_asset_mounts(self):
        tool = Path("C:/tool")
        snapshot = Path("C:/snapshot")
        argv = executor._create_args(
            NAME,
            "gameplay-source",
            tool,
            snapshot,
            timeout_seconds=20,
            asset_files=ASSET_FILES,
        )
        self.assertIn("--read-only", argv)

        mounts = _mounts(argv)
        by_destination = {mount["dst"]: mount for mount in mounts}
        self.assertEqual(
            set(by_destination),
            {
                "/project",
                "/harness",
                "/project/assets/avatar.glb",
                "/project/assets/sprite_sheet.png",
            },
        )
        self.assertEqual(by_destination["/project"]["src"], str(snapshot))
        self.assertTrue(by_destination["/project"]["readonly"])
        self.assertEqual(by_destination["/project"]["bind-propagation"], "rprivate")
        for relative in ASSET_FILES:
            mount = by_destination["/project/" + relative]
            self.assertEqual(mount["src"], str(snapshot / relative))
            self.assertTrue(mount["readonly"])
            self.assertEqual(mount["bind-propagation"], "rprivate")

        tmpfs = {
            argv[index + 1].split(":", 1)[0]: argv[index + 1].split(":", 1)[1]
            for index, item in enumerate(argv)
            if item == "--tmpfs"
        }
        expected_tmpfs = dict(executor.TMPFS)
        expected_tmpfs["/project/assets"] = ASSET_TMPFS_OPTIONS
        self.assertEqual(tmpfs, expected_tmpfs)

    def test_asset_inventory_is_exact_tuple_and_gameplay_only(self):
        tool = Path("C:/tool")
        snapshot = Path("C:/snapshot")
        malformed = (
            [*ASSET_FILES],
            ("assets/sprite_sheet.png", "assets/avatar.glb"),
            ("assets/avatar.glb", "assets/avatar.glb"),
            ("assets/avatar.glb", "assets/unknown.bin"),
            ("assets/avatar.glb", "../assets/sprite_sheet.png"),
            ("/assets/avatar.glb", "assets/sprite_sheet.png"),
        )
        for inventory in malformed:
            with self.subTest(inventory=inventory), self.assertRaises(executor.ExecutorError):
                executor._create_args(
                    NAME,
                    "gameplay-source",
                    tool,
                    snapshot,
                    asset_files=inventory,
                )
        with self.assertRaises(executor.ExecutorError):
            executor._create_args(
                NAME,
                "parse",
                tool,
                snapshot,
                asset_files=ASSET_FILES,
            )

        valid = _gameplay_inspect(tool, snapshot)
        executor._validate_inspect(
            valid,
            name=NAME,
            container_id=CID,
            mode="gameplay-source",
            tool=tool,
            snapshot=snapshot,
            image_environment=IMAGE_ENV,
            asset_files=ASSET_FILES,
        )
        for inventory in malformed + ((),):
            with self.subTest(inspect_inventory=inventory), self.assertRaises(executor.ExecutorError):
                executor._validate_inspect(
                    valid,
                    name=NAME,
                    container_id=CID,
                    mode="gameplay-source",
                    tool=tool,
                    snapshot=snapshot,
                    image_environment=IMAGE_ENV,
                    asset_files=inventory,
                )
        with self.assertRaises(executor.ExecutorError):
            executor._validate_inspect(
                valid,
                name=NAME,
                container_id=CID,
                mode="parse",
                tool=tool,
                snapshot=snapshot,
                image_environment=IMAGE_ENV,
                asset_files=ASSET_FILES,
            )

    def test_inspector_rejects_asset_mount_and_tmpfs_tampering(self):
        tool = Path("C:/tool")
        snapshot = Path("C:/snapshot")
        baseline = _gameplay_inspect(tool, snapshot)
        args = dict(
            name=NAME,
            container_id=CID,
            mode="gameplay-source",
            tool=tool,
            snapshot=snapshot,
            image_environment=IMAGE_ENV,
            asset_files=ASSET_FILES,
        )
        executor._validate_inspect(baseline, **args)

        def without(destination: str, value: dict) -> dict:
            value["Mounts"] = [
                mount for mount in value["Mounts"] if mount["Destination"] != destination
            ]
            return value

        mutations = (
            lambda value: without("/project/assets/avatar.glb", value),
            lambda value: value["Mounts"].append(
                {
                    "Type": "bind",
                    "Source": str(snapshot / "assets/extra.bin"),
                    "Destination": "/project/assets/extra.bin",
                    "RW": False,
                    "Propagation": "rprivate",
                }
            ),
            lambda value: value["Mounts"][3].update(RW=True),
            lambda value: value["Mounts"][3].update(Source=str(snapshot / "other.glb")),
            lambda value: value["Mounts"][3].update(Propagation="rshared"),
            lambda value: value["HostConfig"]["Tmpfs"].pop("/project/assets"),
            lambda value: value["HostConfig"]["Tmpfs"].update(
                {"/project/assets": ASSET_TMPFS_OPTIONS.replace("size=4m", "size=8m")}
            ),
            lambda value: value["HostConfig"]["Tmpfs"].update(
                {"/project/assets": ASSET_TMPFS_OPTIONS.replace("mode=0700", "mode=0777")}
            ),
            lambda value: value["HostConfig"]["Tmpfs"].update(
                {"/project/assets/extra": ASSET_TMPFS_OPTIONS}
            ),
        )
        for index, mutate in enumerate(mutations):
            tampered = copy.deepcopy(baseline)
            mutate(tampered)
            with self.subTest(index=index), self.assertRaises(executor.ExecutorError):
                executor._validate_inspect(tampered, **args)

    def test_sandbox_command_uses_immutable_project_for_every_phase(self):
        sandbox_path = executor.STUDIO / "godot-addon/gameplay_sandbox.py"
        source = sandbox_path.read_text(encoding="utf-8")
        spec = importlib.util.spec_from_file_location("gameplay_asset_mount_sandbox", sandbox_path)
        sandbox = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(sandbox)

        self.assertNotIn("stage_project", source)
        self.assertFalse(hasattr(sandbox, "stage_project"))
        for phase in ("parse", "import", "play", "readback"):
            with self.subTest(phase=phase):
                argv = sandbox.command(phase)
                self.assertEqual(argv[argv.index("--path") + 1], "/project")
                self.assertNotIn("/tmp/gameplay-project", argv)


if __name__ == "__main__":
    unittest.main()

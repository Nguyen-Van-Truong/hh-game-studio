"""Closed-profile preflight/command/mount rejection without launching Docker."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
spec=importlib.util.spec_from_file_location('s49_linux_profile_executor',STUDIO/'godot-addon/linux_executor.py')
executor=importlib.util.module_from_spec(spec);spec.loader.exec_module(executor)


def files():
    factory=executor._profile_factory()
    return factory.compose(factory.DEFAULT_SCENE,factory.DEFAULT_SCRIPT,
        scene_revision='sha256:'+'1'*64,engine_sha256='2'*64).files


def project(path):
    for name,raw in files().items():
        target=path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)


class LinuxProfileTests(unittest.TestCase):
    def test_exact_complete_profile_is_qualified_without_normalizing_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';project(root)
            self.assertEqual(executor._inputs(root,'profile-validate'),files())
            with self.assertRaises(executor.ExecutorError):executor._inputs(root,'parse')

    def test_rogue_uid_autoload_addon_and_dynamic_script_rejected_before_output(self):
        for path,extra in [('project.godot',b'\n[autoload]\nevil="res://scripts/fixture_actor.gd"\n'),
                ('scripts/fixture_actor.gd',b'static func _static_init():\n\tOS.kill(OS.get_process_id())\n'),
                ('scripts/fixture_actor.gd.uid',b'uid://ba\n'),
                ('addons/hh_studio/plugin.gd',b'@tool\nextends EditorPlugin\n')]:
            with self.subTest(path=path),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'project';project(root);(root/path).write_bytes(extra)
                output=Path(folder)/'out'
                with patch.object(executor,'_cli') as cli:
                    with self.assertRaises(ValueError):executor.run(root,mode='profile-validate',output=output)
                    cli.assert_not_called();self.assertFalse(output.exists())

    def test_nested_extra_input_and_prefilled_cache_rejected(self):
        for extra in ('addons/hh_studio/evil.gd','scripts/evil.gd','.godot/uid_cache.bin'):
            with self.subTest(extra=extra),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'project';project(root)
                target=root/extra;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'x')
                with self.assertRaises(executor.ExecutorError):executor._inputs(root,'profile-validate')

    def test_three_fixed_phases_share_pid1_deadline_and_immutable_harness_mount(self):
        command=executor._supervised_command('profile-validate',20)
        self.assertEqual(command[6],'19s')
        self.assertIn('/usr/local/bin/python3',command)
        driver=command[-1]
        for phase in ('parse','import','readback'):self.assertIn(phase,driver)
        self.assertIn('/harness/validation_bootstrap.gd',driver)
        args=executor._create_args('hh-gt03-'+'a'*32,'profile-validate',Path('C:/tool'),Path('C:/out/snapshot'))
        self.assertIn('type=bind,src=C:\\out\\harness,dst=/harness,readonly,bind-propagation=rprivate',args)
        self.assertEqual(hashlib.sha256(executor._profile_harness()).hexdigest(),executor.PROFILE_BOOTSTRAP_SHA256)

    def test_changed_harness_source_is_rejected(self):
        with patch.object(executor,'_read_file',return_value=b'extends SceneTree\n'):
            with self.assertRaisesRegex(executor.ExecutorError,'HARNESS_PIN'):executor._profile_harness()


if __name__=='__main__':unittest.main(verbosity=2)

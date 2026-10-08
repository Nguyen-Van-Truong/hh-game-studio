"""Pure validation of the trusted GT-09 fixture registration policy."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


STUDIO = Path(__file__).resolve().parents[2]
PATH = STUDIO / "godot-addon/gameplay_fixture_profile.py"
spec = importlib.util.spec_from_file_location("hh_gameplay_fixture_profile_test", PATH)
subject = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = subject
assert spec.loader is not None
spec.loader.exec_module(subject)


class FixtureHostProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hh-fixture-host-profile-")
        self.addCleanup(self.temp.cleanup)
        self.policy = json.loads(subject.CONFIG_PATH.read_bytes())

    def altered_config(self, value):
        path = Path(self.temp.name) / "fixture_profile.json"
        path.write_bytes(value if type(value) is bytes else json.dumps(value).encode("utf-8"))
        return patch.object(subject, "CONFIG_PATH", path)

    def test_two_fixture_projects_load_enabled_authority_zero_profiles(self):
        for project, root in (("project.registered.arena", "Node2D"),
                              ("project.registered.room", "Node3D")):
            with self.subTest(project=project):
                profile = subject.load_fixture_profile(project)
                descriptor = subject.validate_fixture_profile(profile, project_id=project)
                self.assertEqual(descriptor["profile"], "hh-godot-gameplay-source-1")
                self.assertEqual(descriptor["version"], 1)
                self.assertEqual(descriptor["root_type"], root)
                self.assertTrue(descriptor["script_enabled"])
                self.assertFalse(descriptor["public_runtime_enabled"])
                self.assertEqual(descriptor["authority"], 0)
                self.assertIn("gameplay-source.publish", descriptor["operations"])
                self.assertIn("scene.node.create", descriptor["operations"])
                self.assertEqual(descriptor["config_sha256"],
                    hashlib.sha256(subject.CONFIG_PATH.read_bytes()).hexdigest())

    def test_default_and_other_project_have_no_profile(self):
        for project in (None, "", "project.adapter", "project.other", "project.registered"):
            self.assertIsNone(subject.load_fixture_profile(project))

    def test_config_cannot_widen_projects_or_global_authority(self):
        invalid = [
            ({"authority": 1}, "FIXTURE_PROFILE_AUTHORITY"),
            ({"authority": False}, "FIXTURE_PROFILE_AUTHORITY"),
            ({"public_runtime_enabled": True}, "FIXTURE_PROFILE_DISABLED"),
            ({"script_enabled": False}, "FIXTURE_PROFILE_DISABLED"),
            ({"version": True}, "FIXTURE_PROFILE_VERSION"),
            ({"profile": "unknown"}, "FIXTURE_CONFIG_IDENTITY"),
            ({"projects": {**self.policy["projects"], "project.other": {"root_type": "Node3D"}}}, "FIXTURE_PROJECTS"),
            ({"client_versions": ["future"]}, "FIXTURE_CLIENT_VERSIONS"),
            ({"operations": ["process.spawn"]}, "FIXTURE_PROFILE_OPERATIONS"),
            ({"enable": True}, "FIXTURE_CONFIG_FIELDS"),
        ]
        for changed, error in invalid:
            with self.subTest(error=error, changed=changed), self.altered_config({**self.policy, **changed}):
                with self.assertRaisesRegex(subject.FixtureProfileError, error):
                    subject.load_fixture_profile("project.registered.room")

    def test_duplicate_config_fields_rejected(self):
        raw = json.dumps(self.policy).encode("utf-8")
        duplicate = raw[:-1] + b', "authority": 0}'
        with self.altered_config(duplicate):
            with self.assertRaisesRegex(subject.FixtureProfileError, "FIXTURE_CONFIG_DUPLICATE_KEY"):
                subject.load_fixture_profile("project.registered.room")

    def test_issued_config_drift_and_foreign_project_rejected(self):
        profile = subject.load_fixture_profile("project.registered.room")
        with self.assertRaisesRegex(subject.FixtureProfileError, "FIXTURE_PROFILE_PROJECT"):
            subject.validate_fixture_profile(profile, project_id="project.registered.arena")
        with self.altered_config(subject.CONFIG_PATH.read_bytes() + b"\n"):
            with self.assertRaisesRegex(subject.FixtureProfileError, "FIXTURE_CONFIG_CHANGED"):
                subject.validate_fixture_profile(profile, project_id=profile.project_id)

    def test_descriptor_and_forged_type_are_not_host_registration(self):
        profile = subject.load_fixture_profile("project.registered.room")
        for untrusted in (profile.as_dict(), object(), None):
            with self.assertRaisesRegex(subject.FixtureProfileError, "FIXTURE_PROFILE_UNTRUSTED"):
                subject.validate_fixture_profile(untrusted, project_id=profile.project_id)

    def test_closure_must_include_current_module_and_config_bytes(self):
        profile = subject.load_fixture_profile("project.registered.room")
        files = {"godot-addon/gameplay_fixture_profile.py": hashlib.sha256(PATH.read_bytes()).hexdigest(),
                 "godot-addon/fixture_profile.json": profile.config_sha256}
        self.assertEqual(subject.validate_fixture_profile(profile, project_id=profile.project_id,
                                                          source_files=files), profile.as_dict())
        for invalid in ({}, {**files, "godot-addon/fixture_profile.json": "0" * 64},
                        {**files, "godot-addon/gameplay_fixture_profile.py": "0" * 64}):
            with self.assertRaisesRegex(subject.FixtureProfileError, "FIXTURE_PROFILE_CLOSURE"):
                subject.validate_fixture_profile(profile, project_id=profile.project_id,
                                                   source_files=invalid)

    def test_loaded_module_drift_rejected(self):
        profile = subject.load_fixture_profile("project.registered.room")
        path = Path(self.temp.name) / "changed_profile.py"
        path.write_bytes(PATH.read_bytes() + b"\n")
        with patch.object(subject, "_MODULE_PATH", path):
            with self.assertRaisesRegex(subject.FixtureProfileError, "FIXTURE_PROFILE_SOURCE_CHANGED"):
                subject.validate_fixture_profile(profile, project_id=profile.project_id)


if __name__ == "__main__":
    unittest.main()

"""Naming admission only; no claim of engine import or GT05 acceptance."""
import copy
import unittest

from pipeline.naming import NamingRejected, validate_catalog


def catalog():
    return {"schema": "HH-ASSET-NAMES-1", "assets": [{
        "asset_id": "chr_fixture_avatar", "class": "character",
        "nodes": [
            {"name": "chr_fixture_avatar_lod0", "role": "render", "lod": 0},
            {"name": "chr_fixture_avatar_lod1", "role": "render", "lod": 1},
            {"name": "chr_fixture_avatar_rig", "role": "rig"},
        ],
        "bones": ["bn_root", "bn_pelvis"], "clips": ["idle", "walk"],
        "materials": ["mat_fixture_cloth"], "sockets": ["socket_hand_r"],
    }]}


class NamingTests(unittest.TestCase):
    def rejects(self, data, code=None):
        with self.assertRaises(NamingRejected) as raised:
            validate_catalog(data)
        if code is not None:
            self.assertEqual(str(raised.exception), code)

    def test_declared_names_pass_without_mutation(self):
        value = catalog()
        before = copy.deepcopy(value)
        self.assertEqual(validate_catalog(value),
                         {"schema": "HH-ASSET-NAMES-1", "assets": 1, "nodes": 3})
        self.assertEqual(value, before)

    def test_empty_catalog_is_not_a_fixture_acceptance(self):
        self.assertEqual(validate_catalog({"schema": "HH-ASSET-NAMES-1", "assets": []})["assets"], 0)

    def test_host_paths_unicode_and_case_rejected(self):
        for bad in ("../outside", "chr_Case", "chr_аvatar", "chr_a/b", "chr_a:b",
                    "chr_a\\b", "chr_a\n", "chr_a ", "chr__a", "chr_a.", "chr_a\x00",
                    "chr_a__b", "chr_a_", "chr_", "chr_" + "a" * 61):
            with self.subTest(bad=repr(bad)):
                value = catalog()
                value["assets"][0]["asset_id"] = bad
                self.rejects(value)

    def test_class_prefix_and_reserved_suffixes(self):
        for bad in ("prp_fixture_avatar", "chr_a_lod0", "chr_a_lod999", "chr_a_nav",
                    "chr_a_collider", "chr_a_rig"):
            value = catalog()
            value["assets"][0]["asset_id"] = bad
            self.rejects(value)

    def test_node_cannot_claim_other_asset_or_role(self):
        for node in ({"name": "chr_other_lod0", "role": "render", "lod": 0},
                     {"name": "chr_fixture_avatar_nav", "role": "collider"},
                     {"name": "chr_fixture_avatar_lod0", "role": "render", "lod": True},
                     {"name": "chr_fixture_avatar_lod0", "role": "render", "lod": 0.0},
                     {"name": "chr_fixture_avatar_lod2", "role": "render", "lod": 2},
                     {"name": "chr_fixture_avatar_rig", "role": "rig", "lod": 0}):
            value = catalog()
            value["assets"][0]["nodes"] = [node]
            self.rejects(value)

    def test_duplicate_ids_nodes_and_names(self):
        value = catalog()
        value["assets"].append(copy.deepcopy(value["assets"][0]))
        self.rejects(value, "DUPLICATE_ASSET_ID")
        for key in ("nodes", "bones", "clips", "materials", "sockets"):
            value = catalog()
            value["assets"][0][key].append(copy.deepcopy(value["assets"][0][key][0]))
            self.rejects(value)

    def test_unknown_fields_fail_closed(self):
        for depth in (0, 1, 2):
            value = catalog()
            target = (value, value["assets"][0], value["assets"][0]["nodes"][0])[depth]
            target["source_path"] = "private-value-do-not-echo"
            self.rejects(value)

    def test_bad_types_raise_stable_rejection(self):
        for key in ("class", "asset_id", "nodes", "bones", "clips", "materials", "sockets"):
            for bad in (None, True, 5, {}, ("a",)):
                value = catalog()
                value["assets"][0][key] = bad
                self.rejects(value)
        for bad in (None, [], "data", {"schema": [], "assets": []}):
            self.rejects(bad)

    def test_namespace_and_clip_policy(self):
        for key, bad in (("bones", "root"), ("materials", "bn_root"),
                         ("sockets", "mat_cloth"), ("clips", "run")):
            value = catalog()
            value["assets"][0][key] = [bad]
            self.rejects(value)

    def test_caps_before_unbounded_iteration(self):
        value = catalog()
        value["assets"] *= 65
        self.rejects(value, "NAME_LIST_LIMIT_OR_TYPE")
        for key in ("nodes", "bones", "clips", "materials", "sockets"):
            value = catalog()
            value["assets"][0][key] = [None] * 257
            self.rejects(value, "NAME_LIST_LIMIT_OR_TYPE")

    def test_other_classes_and_explicit_proxy_roles(self):
        for kind, prefix in (("prop", "prp"), ("environment", "env"), ("ui", "ui")):
            value = catalog()
            asset = value["assets"][0]
            asset["class"], asset["asset_id"] = kind, prefix + "_fixture"
            asset["nodes"] = [{"name": prefix + "_fixture_" + role, "role": role}
                              for role in ("collider", "nav")]
            self.assertEqual(validate_catalog(value)["nodes"], 2)

    def test_longest_asset_preserves_proxy_suffix_headroom(self):
        value = catalog()
        asset = value["assets"][0]
        asset["asset_id"] = "chr_" + "a" * 51
        asset["nodes"] = [{"name": asset["asset_id"] + "_collider", "role": "collider"}]
        self.assertEqual(len(asset["nodes"][0]["name"]), 64)
        self.assertEqual(validate_catalog(value)["nodes"], 1)
        asset["asset_id"] += "a"
        asset["nodes"] = []
        self.rejects(value, "ASSET_SUFFIX_HEADROOM")


if __name__ == "__main__":
    unittest.main()

"""Pure trace admission checks; no engine execution or runtime PASS claim."""
import copy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay.trace import (
    FPS, KEYS, MAX_BYTES, MAX_CAPTURES, MAX_FRAMES, MAX_LABEL_CHARS, MAX_SEED,
    SCHEMA_ID, SCHEMA_VERSION, TraceRejected, ValidatedTrace, default_trace,
    validate_trace,
)


def encoded(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def idle(tick):
    return {"tick": tick, "pressed": [], "held": [], "released": []}


def sample(count=1):
    return {"schema_id": SCHEMA_ID, "schema_version": SCHEMA_VERSION,
            "fps": FPS, "seed": 0, "frames": [idle(tick) for tick in range(count)], "captures": []}


def press_release():
    value = sample(3)
    value["frames"][0].update(pressed=["RIGHT"], held=["RIGHT"])
    value["frames"][1].update(held=["RIGHT"])
    value["frames"][2].update(released=["RIGHT"])
    return value


class TraceTests(unittest.TestCase):
    def rejects(self, value, code=None):
        raw = value if type(value) is bytes else encoded(value)
        with self.assertRaises(TraceRejected) as result:
            validate_trace(raw)
        if code is not None:
            self.assertEqual(result.exception.code, code)
        self.assertEqual(str(result.exception), result.exception.code)
        return result.exception.code

    def test_exact_raw_hash_is_not_a_canonical_semantic_hash(self):
        first = encoded(sample())
        second = b" \n" + first + b"\t"
        a, b = validate_trace(first), validate_trace(second)
        self.assertEqual(a.as_dict(), b.as_dict())
        self.assertEqual(a.raw, first)
        self.assertEqual(a.raw_sha256, hashlib.sha256(first).hexdigest())
        self.assertEqual(b.raw_sha256, hashlib.sha256(second).hexdigest())
        self.assertNotEqual(a.raw_sha256, b.raw_sha256)

    def test_result_and_nested_values_are_immutable_and_copy_is_defensive(self):
        value = validate_trace(encoded(press_release()))
        with self.assertRaises(FrozenInstanceError):
            value.raw_sha256 = "0" * 64
        with self.assertRaises(TypeError):
            value.value["seed"] = 8
        with self.assertRaises(TypeError):
            value.value["frames"][0]["tick"] = 99
        with self.assertRaises(TypeError):
            value.value["frames"][0]["held"][0] = "LEFT"
        copied = value.as_dict()
        copied["frames"][0]["held"].append("LEFT")
        self.assertEqual(value.value["frames"][0]["held"], ("RIGHT",))
        self.assertEqual(value.raw_sha256, hashlib.sha256(value.raw).hexdigest())

    def test_direct_construction_also_validates_and_bytes_only_api(self):
        with self.assertRaises(TraceRejected) as error:
            ValidatedTrace(b'{}')
        self.assertEqual(error.exception.code, "TRACE_FIELDS")
        for bad in (sample(), bytearray(encoded(sample())), memoryview(encoded(sample())), "{}", None):
            with self.subTest(kind=type(bad).__name__):
                with self.assertRaises(TraceRejected) as error:
                    validate_trace(bad)
                self.assertEqual(error.exception.code, "TRACE_BYTES_REQUIRED")

    def test_byte_limit_is_inclusive_and_empty_rejected(self):
        raw = encoded(sample())
        bound = raw + b" " * (MAX_BYTES - len(raw))
        self.assertEqual(len(validate_trace(bound).raw), 256 * 1024)
        self.rejects(bound + b" ", "TRACE_BYTE_LIMIT")
        self.rejects(b"", "TRACE_BYTE_LIMIT")

    def test_duplicate_json_members_at_root_frame_and_capture_rejected(self):
        raw = encoded(sample())
        # An escaped spelling is still the same member after JSON decoding.
        self.rejects(raw.replace(b'"seed":0', b'"seed":0,"se\\u0065d":1'))
        self.rejects(raw.replace(b'"tick":0', b'"tick":0,"tick":0'), "TRACE_DUPLICATE_KEY")
        value = sample()
        value["captures"] = [{"tick": 0, "label": "menu"}]
        self.rejects(encoded(value).replace(b'"label":"menu"', b'"label":"menu","label":"other"'),
                     "TRACE_DUPLICATE_KEY")

    def test_nonfinite_and_noninteger_json_numbers_rejected(self):
        raw = encoded(sample())
        for token in (b"NaN", b"Infinity", b"-Infinity"):
            self.rejects(raw.replace(b'"seed":0', b'"seed":' + token), "TRACE_NONFINITE")
        for token in (b"0.0", b"1e0", b"1e9999"):
            self.rejects(raw.replace(b'"seed":0', b'"seed":' + token), "TRACE_INTEGER_REQUIRED")
        self.rejects(raw.replace(b'"seed":0', b'"seed":' + b"9" * 2000), "TRACE_NUMBER_LIMIT")

    def test_bad_utf8_malformed_json_trailing_values_and_root_types_rejected(self):
        self.rejects(b"\xff", "TRACE_UTF8")
        for raw in (b" ", b"{", b"{}{}", b"[", b"}", b"\xef\xbb\xbf{}"):
            self.rejects(raw, "TRACE_JSON")
        for raw in (b"[]", b"null", b"true", b'"text"', b"12"):
            self.rejects(raw, "TRACE_ROOT_OBJECT")

    def test_depth_guard_runs_before_json_decoder_recursion(self):
        self.rejects(b"[" * 2000 + b"0" + b"]" * 2000, "TRACE_DEPTH_LIMIT")
        raw = encoded(sample()).replace(b'"captures":[]', b'"captures":[[[[0]]]]')
        self.rejects(raw, "TRACE_DEPTH_LIMIT")
        # Braces inside a JSON string are not structural nesting.
        value = sample()
        value["captures"] = [{"tick": 0, "label": "{{{{{{"}]
        self.rejects(value, "TRACE_CAPTURE_LABEL")

    def test_unknown_or_missing_fields_in_each_record_are_rejected(self):
        for place in ("root", "frame", "capture"):
            value = sample()
            value["captures"] = [{"tick": 0, "label": "menu"}]
            target = value if place == "root" else value["frames"][0] if place == "frame" else value["captures"][0]
            target["command"] = "ignored"
            self.rejects(value)
        for name in sample():
            value = sample()
            del value[name]
            self.rejects(value, "TRACE_FIELDS")

    def test_schema_version_and_fps_are_exact(self):
        for key, bad in (("schema_id", "hh-studio.input-trace.v2"), ("schema_version", "1.0"),
                         ("schema_id", True), ("schema_version", 1)):
            value = sample(); value[key] = bad
            self.rejects(value, "TRACE_SCHEMA")
        for bad in (True, False, 0, 30, 59, 61, "60", None):
            value = sample(); value["fps"] = bad
            self.rejects(value, "TRACE_FPS")

    def test_uint32_seed_edges_and_bool_are_distinct(self):
        for seed in (0, MAX_SEED):
            value = sample(); value["seed"] = seed
            self.assertEqual(validate_trace(encoded(value)).value["seed"], seed)
        for bad in (-1, 1 << 32, True, False, None, "1"):
            value = sample(); value["seed"] = bad
            self.rejects(value, "TRACE_SEED")
            with self.assertRaises(TraceRejected) as error:
                default_trace(bad)
            self.assertEqual(error.exception.code, "TRACE_SEED")

    def test_frame_cap_is_600_without_changing_gt02_array_limits(self):
        from studio.host.core.limits import DEFAULT_LIMITS
        self.assertEqual(DEFAULT_LIMITS.max_array_items, 256)
        self.assertEqual(len(validate_trace(encoded(sample(MAX_FRAMES))).value["frames"]), 600)
        for bad in ([], sample(MAX_FRAMES + 1)["frames"], {}, None, True):
            value = sample(); value["frames"] = bad
            self.rejects(value, "TRACE_FRAME_LIMIT_OR_TYPE")
        self.assertEqual(DEFAULT_LIMITS.max_array_items, 256)

    def test_ticks_are_contiguous_zero_based_and_integer_only(self):
        for ticks in ((1, 2, 3), (0, 2, 3), (0, 0, 1), (0, 2, 1), (0, True, 2), (0, -1, 2)):
            value = sample(3)
            for frame, tick in zip(value["frames"], ticks):
                frame["tick"] = tick
            self.rejects(value, "TRACE_TICK_CONTIGUOUS")

    def test_all_allowed_keys_can_be_pressed_and_released_together(self):
        value = sample(2)
        value["frames"][0].update(pressed=list(KEYS), held=list(reversed(KEYS)))
        value["frames"][1].update(released=list(KEYS))
        self.assertEqual(len(validate_trace(encoded(value)).value["frames"][0]["pressed"]), 12)

    def test_key_caps_types_unknown_keys_and_duplicates(self):
        for field in ("pressed", "held", "released"):
            for bad in (list(KEYS) + ["RIGHT"], None, {}, "RIGHT"):
                value = sample(); value["frames"][0][field] = bad
                self.rejects(value, "TRACE_KEY_LIMIT_OR_TYPE")
            for bad in (["SPACE"], ["right"], ["../Q"], [True], [1], [None], [["RIGHT"]]):
                value = sample(); value["frames"][0][field] = bad
                self.rejects(value)
            value = sample(); value["frames"][0][field] = ["RIGHT", "RIGHT"]
            self.rejects(value, "TRACE_KEY_DUPLICATE")

    def test_press_release_overlap_is_never_a_shortcut_to_tap(self):
        value = sample(); value["frames"][0].update(pressed=["E"], released=["E"])
        self.rejects(value, "TRACE_EDGE_OVERLAP")

    def test_repeated_press_and_release_without_previous_hold_are_rejected(self):
        value = press_release(); value["frames"][1]["pressed"] = ["RIGHT"]
        self.rejects(value, "TRACE_REPEATED_PRESS")
        value = sample(); value["frames"][0]["released"] = ["RIGHT"]
        self.rejects(value, "TRACE_NONHELD_RELEASE")
        value = press_release(); value["frames"][2]["released"].append("E")
        self.rejects(value, "TRACE_NONHELD_RELEASE")

    def test_held_cannot_appear_disappear_or_survive_release_without_edges(self):
        value = sample(); value["frames"][0]["held"] = ["RIGHT"]
        self.rejects(value, "TRACE_HELD_STATE")
        value = press_release(); value["frames"][1]["held"] = []
        self.rejects(value, "TRACE_HELD_STATE")
        value = press_release(); value["frames"][2]["held"] = ["RIGHT"]
        self.rejects(value, "TRACE_HELD_STATE")

    def test_trace_must_release_all_keys_at_end(self):
        value = sample(); value["frames"][0].update(pressed=["Q"], held=["Q"])
        self.rejects(value, "TRACE_FINAL_HELD")
        value = press_release(); value["frames"].pop()
        self.rejects(value, "TRACE_FINAL_HELD")

    def test_repress_after_separate_release_and_switch_keys_is_valid(self):
        value = sample(4)
        value["frames"][0].update(pressed=["E"], held=["E"])
        value["frames"][1].update(pressed=["O"], held=["O"], released=["E"])
        value["frames"][2].update(pressed=["E"], held=["E"], released=["O"])
        value["frames"][3].update(released=["E"])
        self.assertEqual(validate_trace(encoded(value)).as_dict(), value)

    def test_capture_cap_shared_tick_and_unordered_requests(self):
        value = sample(2)
        value["captures"] = [{"tick": 1 - index % 2, "label": "view_" + str(index)}
                             for index in range(MAX_CAPTURES)]
        self.assertEqual(validate_trace(encoded(value)).as_dict()["captures"], value["captures"])
        value["captures"].append({"tick": 0, "label": "extra"})
        self.rejects(value, "TRACE_CAPTURE_LIMIT_OR_TYPE")
        for bad in (None, {}, True):
            value = sample(); value["captures"] = bad
            self.rejects(value, "TRACE_CAPTURE_LIMIT_OR_TYPE")

    def test_capture_tick_must_name_an_existing_frame(self):
        for bad in (-1, 1, True, False, "0", None):
            value = sample(); value["captures"] = [{"tick": bad, "label": "menu"}]
            self.rejects(value, "TRACE_CAPTURE_TICK")

    def test_capture_labels_are_safe_unique_lowercase_stable_identifiers(self):
        for bad in ("../menu", "a/b", "a\\b", "c:menu", ".", "a.png", "menu ", "MENU", "a__b", "a_",
                    "_a", "0a", "a\n", "a\0", "\u0430", "\ud800", "con", "nul", "com1", "lpt9", "", True,
                    "a" * (MAX_LABEL_CHARS + 1)):
            value = sample(); value["captures"] = [{"tick": 0, "label": bad}]
            self.rejects(value, "TRACE_CAPTURE_LABEL")
        value = sample(); value["captures"] = [{"tick": 0, "label": "a" * MAX_LABEL_CHARS}]
        self.assertEqual(validate_trace(encoded(value)).as_dict(), value)
        value["captures"].append(copy.deepcopy(value["captures"][0]))
        self.rejects(value, "TRACE_CAPTURE_DUPLICATE")

    def test_default_trace_seed_is_deterministic_and_does_not_retime_inputs(self):
        a, b, c = default_trace(123), default_trace(123), default_trace(124)
        self.assertEqual(a.raw, b.raw)
        self.assertEqual(a.raw_sha256, b.raw_sha256)
        self.assertNotEqual(a.raw_sha256, c.raw_sha256)
        self.assertEqual(a.value["frames"], c.value["frames"])
        self.assertEqual(a.value["captures"], c.value["captures"])
        self.assertEqual(len(a.value["frames"]), 360)
        self.assertEqual(a.value["seed"], 123)

    def test_default_intent_exercises_ordered_real_key_edges_and_pause_probe(self):
        value = default_trace().as_dict()
        frames = value["frames"]
        edges = [(row["tick"], row["pressed"]) for row in frames if row["pressed"]]
        self.assertEqual(edges, [(10, ["ENTER"]), (30, ["RIGHT"]), (80, ["E"]), (100, ["O"]),
                                (120, ["M"]), (150, ["ESCAPE"]), (160, ["RIGHT"]),
                                (200, ["ESCAPE"]), (230, ["C"]), (350, ["Q"])])
        self.assertEqual(sum("RIGHT" in row["held"] for row in frames[:150]), 30)
        captures = {row["label"]: row["tick"] for row in value["captures"]}
        self.assertLess(captures["menu"], 10)
        self.assertEqual(set(captures), {"menu", "moved", "interact", "paused_a", "paused_b", "resumed", "camera"})
        for label in ("paused_a", "paused_b"):
            self.assertTrue(151 < captures[label] < 180)
            self.assertEqual(frames[captures[label]]["held"], ["RIGHT"])
        self.assertGreater(captures["resumed"], 201)
        self.assertGreater(captures["camera"], 231)
        self.assertLess(max(captures.values()), 350)
        self.assertEqual(frames[351]["released"], ["Q"])
        self.assertEqual(frames[-1]["held"], [])

    def test_valid_bytes_tamper_changes_hash_and_invalid_edge_tamper_is_rejected(self):
        original = default_trace(9)
        changed = original.as_dict(); changed["seed"] = 10
        self.assertNotEqual(validate_trace(encoded(changed)).raw_sha256, original.raw_sha256)
        broken = original.as_dict(); broken["frames"][60]["released"] = []
        self.rejects(broken, "TRACE_HELD_STATE")
        self.assertEqual(original.value["frames"][60]["released"], ("RIGHT",))


if __name__ == "__main__":
    unittest.main()

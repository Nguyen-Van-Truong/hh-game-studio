"""Closed GT-06 local performance artifacts; no engine, process or wire authority.

Public API:
    summarize(frame_ms) -> independently derived statistics
    build_artifact(payload) -> artifact with fixed identities and new summary
    validate_artifact(value, *, expected=None) -> detached validated artifact
    parse_artifact(raw, *, expected=None) -> strict UTF-8/JSON validated artifact

``payload`` has every artifact field except schema_id, schema_version,
artifact_kind and summary. The first three may be supplied only if correct;
summary must be absent. ``expected`` is a recursively matched, trusted subset
of artifact fields, for example provenance and native process identity.

The JSON schema is the structural authority. This module also checks sequence,
clock, availability, counter and derived-statistic invariants. It does not
authenticate a caller's observations, open referenced files, prove a native
exit or authorize a performance claim. The native evidence verifier owns that
boundary. All SHA-256 strings are lowercase hex; closure/JCS and file-byte
domains are intentionally distinct. Shared protocol limits are never changed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


SCHEMA_ID = "hh-studio.perf-collector"
SCHEMA_VERSION = "1.0.0"
ARTIFACT_KIND = "runtime_frame_capture"
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 120_000
MAX_RSS_SAMPLES = 12_000
MAX_DURATION_MS = 600_000
SAFE_INTEGER = (1 << 53) - 1
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "perf-collector.schema.json"
_SCHEMA_BYTES = SCHEMA_PATH.read_bytes()
SCHEMA_SHA256 = hashlib.sha256(_SCHEMA_BYTES).hexdigest()
_SCHEMA = json.loads(_SCHEMA_BYTES)
_IDENTITIES = {"schema_id": SCHEMA_ID, "schema_version": SCHEMA_VERSION,
               "artifact_kind": ARTIFACT_KIND}
_COUNTERS = ("scene_triangles", "render_primitives", "draw_calls", "texture_bytes")
_DEVICE = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


def _check_schema_subset(schema: dict) -> None:
    """Fail closed if future schema edits require an unsupported keyword."""
    supported = {"$schema", "$id", "title", "description", "type", "properties",
        "required", "additionalProperties", "items", "minItems", "maxItems",
        "const", "enum", "minimum", "maximum", "exclusiveMinimum", "minLength",
        "maxLength", "pattern", "oneOf"}
    if type(schema) is not dict or set(schema) - supported:
        raise RuntimeError("Unsupported performance schema keyword")
    if schema.get("type") == "object":
        if schema.get("additionalProperties") is not False:
            raise RuntimeError("Performance schema objects must stay closed")
        for child in schema["properties"].values():
            _check_schema_subset(child)
    if "items" in schema:
        _check_schema_subset(schema["items"])
    if "oneOf" in schema:
        if set(schema) != {"oneOf"}:
            raise RuntimeError("Performance oneOf must contain complete closed variants")
        for child in schema["oneOf"]:
            _check_schema_subset(child)


_check_schema_subset(_SCHEMA)
if any(_SCHEMA["properties"][key].get("const") != value for key, value in _IDENTITIES.items()):
    raise RuntimeError("Performance schema identity/version differs from implementation")


class PerfError(ValueError):
    """Stable rejection code and bounded schema path, without payload values."""

    def __init__(self, code: str, path: str = "$") -> None:
        self.code, self.path = code, path
        super().__init__(f"{code}: {path}")


def _need(condition: bool, code: str, path: str) -> None:
    if not condition:
        raise PerfError(code, path)


def _type(value: Any, expected: str) -> bool:
    if expected == "object":
        return type(value) is dict
    if expected == "array":
        return type(value) is list
    if expected == "integer":
        return type(value) is int and abs(value) <= SAFE_INTEGER
    if expected == "number":
        return ((type(value) is int and abs(value) <= SAFE_INTEGER) or
                (type(value) is float and math.isfinite(value)))
    if expected == "string":
        return type(value) is str
    if expected == "boolean":
        return type(value) is bool
    if expected == "null":
        return value is None
    raise RuntimeError("Unsupported internal schema type")


def _structure(value: Any, schema: dict, path: str = "$") -> None:
    """Interpret precisely the closed schema subset used by this file."""
    if "oneOf" in schema:
        matches = 0
        for variant in schema["oneOf"]:
            try:
                _structure(value, variant, path)
            except PerfError:
                continue
            matches += 1
        _need(matches == 1, "INVALID_VARIANT", path)
        return
    expected = schema.get("type")
    if expected is not None:
        types = expected if type(expected) is list else [expected]
        _need(any(_type(value, kind) for kind in types), "INVALID_TYPE", path)
    if "const" in schema:
        const = schema["const"]
        _need(type(value) is type(const) and value == const, "INVALID_CONSTANT", path)
    if "enum" in schema:
        _need(value in schema["enum"], "INVALID_ENUM", path)
    if value is None:
        return
    if type(value) in (int, float):
        _need(math.isfinite(value), "NON_FINITE_NUMBER", path)
        for key, relation in (("minimum", lambda a, b: a >= b),
                              ("maximum", lambda a, b: a <= b),
                              ("exclusiveMinimum", lambda a, b: a > b)):
            if key in schema:
                _need(relation(value, schema[key]), "NUMBER_RANGE", path)
    elif type(value) is str:
        _need(not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "INVALID_UNICODE", path)
        _need(len(value) >= schema.get("minLength", 0) and
              len(value) <= schema.get("maxLength", MAX_ARTIFACT_BYTES), "STRING_LENGTH", path)
        if "pattern" in schema:
            _need(re.fullmatch(schema["pattern"], value) is not None, "STRING_PATTERN", path)
    elif type(value) is list:
        _need(schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 0),
              "ARRAY_SIZE", path)
        for index, item in enumerate(value):
            _structure(item, schema["items"], f"{path}[{index}]")
    elif type(value) is dict:
        properties = schema.get("properties", {})
        _need(all(type(key) is str for key in value), "INVALID_KEY", path)
        _need(not (set(value) - set(properties)), "UNKNOWN_FIELD", path)
        for key in schema.get("required", []):
            _need(key in value, "MISSING_FIELD", f"{path}.{key}")
        for key, item in value.items():
            _structure(item, properties[key], f"{path}.{key}")


def _close(actual: float, expected: float, path: str) -> None:
    _need(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-9),
          "DERIVED_VALUE_MISMATCH", path)


def summarize(frame_ms: Iterable[float]) -> dict[str, Any]:
    """Type-7 quantiles; 1% low = 1000 / mean(ceil(n*.01) worst frames).

    Values must be positive finite milliseconds. No intermediate rounding or
    sample trimming is performed. The iterable is consumed at most MAX_FRAMES
    plus one times, so callers cannot submit an unbounded generator.
    """
    values: list[float] = []
    try:
        iterator = iter(frame_ms)
    except TypeError as exc:
        raise PerfError("INVALID_TYPE", "$.frames") from exc
    for value in iterator:
        _need(len(values) < MAX_FRAMES, "ARRAY_SIZE", "$.frames")
        _need(_type(value, "number") and value > 0, "INVALID_FRAME_TIME", "$.frames")
        values.append(float(value))
    _need(bool(values), "EMPTY_FRAMES", "$.frames")
    ordered = sorted(values)
    count = len(values)

    def percentile(p: float) -> float:
        h = (count - 1) * p
        lower = math.floor(h)
        fraction = h - lower
        return ordered[lower] * (1 - fraction) + ordered[min(lower + 1, count - 1)] * fraction

    worst_count = (count + 99) // 100
    try:
        duration = math.fsum(values)
        worst_mean = math.fsum(ordered[-worst_count:]) / worst_count
        low = 1000.0 / worst_mean
    except (OverflowError, ZeroDivisionError) as exc:
        raise PerfError("INVALID_DERIVED_NUMBER", "$.summary") from exc
    _need(all(math.isfinite(x) and x > 0 for x in (duration, worst_mean, low)),
          "INVALID_DERIVED_NUMBER", "$.summary")
    return {"sample_count": count, "duration_ms": duration,
            "mean_frame_ms": duration / count,
            "p50_frame_ms": percentile(0.50), "p95_frame_ms": percentile(0.95),
            "p99_frame_ms": percentile(0.99), "one_percent_sample_count": worst_count,
            "one_percent_mean_frame_ms": worst_mean, "one_percent_low_fps": low,
            "percentile_method": "linear_type7",
            "one_percent_method": "ceil_largest_mean_reciprocal"}


def _expected(value: Any, expected: Any, path: str = "$") -> None:
    if isinstance(expected, Mapping):
        _need(type(value) is dict, "EXPECTED_BINDING_MISMATCH", path)
        for key, item in expected.items():
            _need(type(key) is str and key in value, "EXPECTED_BINDING_MISMATCH", path)
            _expected(value[key], item, f"{path}.{key}")
    else:
        _need(type(value) is type(expected) and value == expected, "EXPECTED_BINDING_MISMATCH", path)


def _semantics(value: dict) -> None:
    clock, sampling = value["clock"], value["sampling"]
    frames, counters, rss = value["frames"], value["godot_counters"], value["rss_samples"]
    config, process, definitions = value["configuration"], value["process"], value["counter_definitions"]
    _need(len(frames) <= sampling["max_frames"], "PROFILE_FRAME_LIMIT", "$.frames")
    _need(len(rss) <= sampling["max_rss_samples"], "PROFILE_RSS_LIMIT", "$.rss_samples")
    for start, end, factor in (("runtime_start_mono_us", "runtime_end_mono_us", 1000),
                               ("host_start_mono_us", "host_end_mono_us", 1000),
                               ("started_utc_ms", "ended_utc_ms", 1)):
        span = clock[end] - clock[start]
        _need(0 <= span <= sampling["max_duration_ms"] * factor, "CLOCK_RANGE", "$.clock." + end)
    prefix = "windows:" if config["platform"] == "windows" else "linux:"
    _need(process["process_start"].startswith(prefix), "PROCESS_IDENTITY_PLATFORM", "$.process.process_start")
    if process["window_status"] == "available":
        _need(type(process["window_id"]) is str and type(process["native_window_handle"]) is str
              and process["window_unavailable_reason"] is None, "WINDOW_BINDING", "$.process")
        _need(re.fullmatch(r"[0-9]{1,20}", process["window_id"]) is not None,
              "WINDOW_BINDING", "$.process.window_id")
        handle = process["native_window_handle"]
        _need(re.fullmatch(r"(?:0x[0-9a-fA-F]{1,16}|[0-9]{1,20})", handle) is not None,
              "WINDOW_BINDING", "$.process.native_window_handle")
        _need(0 < int(handle, 16 if handle.startswith("0x") else 10) < 1 << 64,
              "WINDOW_BINDING", "$.process.native_window_handle")
        _need(config["display_server"].lower() != "headless", "WINDOW_BINDING", "$.configuration.display_server")
    else:
        _need(process["window_id"] is None and process["native_window_handle"] is None
              and type(process["window_unavailable_reason"]) is str, "WINDOW_BINDING", "$.process")
    for name, definition in definitions.items():
        available = definition["availability"] == "available"
        _need((available and definition["reason"] is None) or
              (not available and type(definition["reason"]) is str),
              "COUNTER_AVAILABILITY", "$.counter_definitions." + name)
    rss_available = definitions["rss_bytes"]["availability"] == "available"
    expected_rss_provider = "GetProcessMemoryInfo.WorkingSetSize" if prefix == "windows:" else "proc_pid_statm.resident_pages"
    _need(definitions["rss_bytes"]["provider"] == expected_rss_provider,
          "RSS_PROVIDER_PLATFORM", "$.counter_definitions.rss_bytes.provider")
    _need(bool(rss) == rss_available, "RSS_AVAILABILITY", "$.rss_samples")
    _need(len(counters) == len(frames), "COUNTER_FRAME_COVERAGE", "$.godot_counters")
    previous_time = clock["runtime_start_mono_us"]
    previous = None
    for index, frame in enumerate(frames):
        path = f"$.frames[{index}]"
        _need(frame["seq"] == index, "FRAME_SEQUENCE", path + ".seq")
        _need(previous_time < frame["runtime_mono_us"] <= clock["runtime_end_mono_us"],
              "FRAME_CLOCK", path + ".runtime_mono_us")
        _close(frame["frame_ms"], (frame["runtime_mono_us"] - previous_time) / 1000.0, path + ".frame_ms")
        if previous is not None:
            _need(frame["engine_process_frame"] == previous["engine_process_frame"] + 1,
                  "ENGINE_FRAME_GAP", path + ".engine_process_frame")
            if sampling["hook"] == "frame_post_draw":
                _need(frame["engine_draw_frame"] == previous["engine_draw_frame"] + 1,
                      "DRAW_FRAME_GAP", path + ".engine_draw_frame")
            else:
                _need(frame["engine_draw_frame"] >= previous["engine_draw_frame"], "DRAW_FRAME_ORDER", path)
            _need(frame["ui_tick"] > previous["ui_tick"] and frame["sim_tick"] >= previous["sim_tick"],
                  "RUNTIME_CLOCK_ORDER", path)
            if frame["phase"] == previous["phase"] == "PAUSED":
                _need(frame["sim_tick"] == previous["sim_tick"], "PAUSE_SIM_TICK_CHANGED", path)
        counter = counters[index]
        counter_path = f"$.godot_counters[{index}]"
        _need(counter["sample_seq"] == index and counter["frame_seq"] == index
              and counter["runtime_mono_us"] == frame["runtime_mono_us"],
              "COUNTER_FRAME_BINDING", counter_path)
        for name in _COUNTERS:
            _need((counter[name] is not None) == (definitions[name]["availability"] == "available"),
                  "COUNTER_AVAILABILITY", counter_path + "." + name)
        previous, previous_time = frame, frame["runtime_mono_us"]
    _need(previous_time == clock["runtime_end_mono_us"], "FRAME_WINDOW_INCOMPLETE", "$.clock.runtime_end_mono_us")
    previous_rss = None
    for index, sample in enumerate(rss):
        path = f"$.rss_samples[{index}]"
        _need(sample["sample_seq"] == index, "RSS_SEQUENCE", path + ".sample_seq")
        observed = sample["host_mono_us"]
        _need(clock["host_start_mono_us"] <= observed <= clock["host_end_mono_us"]
              and (previous_rss is None or observed > previous_rss), "RSS_CLOCK", path + ".host_mono_us")
        previous_rss = observed
    calculated = summarize(frame["frame_ms"] for frame in frames)
    for key, expected in calculated.items():
        actual = value["summary"][key]
        if type(expected) is float:
            _close(actual, expected, "$.summary." + key)
        else:
            _need(type(actual) is type(expected) and actual == expected, "SUMMARY_MISMATCH", "$.summary." + key)
    ids, paths = set(), set()
    for index, reference in enumerate(value["references"]):
        path = f"$.references[{index}]"
        parts = reference["path"].split("/")
        _need(all(part not in ("", ".", "..") and not part.endswith((".", " "))
                  and not _DEVICE.match(part) for part in parts), "REFERENCE_PATH", path + ".path")
        _need(reference["reference_id"] not in ids and reference["path"].casefold() not in paths,
              "DUPLICATE_REFERENCE", path)
        ids.add(reference["reference_id"])
        paths.add(reference["path"].casefold())
    if "battery" in value:
        battery = value["battery"]
        _need(config["platform"] == "android", "BATTERY_PLATFORM", "$.battery")
        _need(clock["host_start_mono_us"] <= battery["started_host_mono_us"] <=
              battery["ended_host_mono_us"] <= clock["host_end_mono_us"], "BATTERY_CLOCK", "$.battery")


def validate_artifact(value: Any, *, expected: Mapping[str, Any] | None = None) -> dict:
    """Validate structure and recompute raw-derived values; return a deep copy.

    ``expected`` must come from the independent runner/freeze, not this artifact.
    Reference content, PID ownership, capture freshness and native exit/leftover
    verification remain the caller's responsibility.
    """
    _structure(value, _SCHEMA)
    _semantics(value)
    if expected is not None:
        _need(isinstance(expected, Mapping), "INVALID_EXPECTED_BINDINGS", "$")
        _expected(value, expected)
    try:
        size = len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PerfError("INVALID_JSON") from exc
    _need(size <= value["sampling"]["max_artifact_bytes"], "ARTIFACT_BYTE_LIMIT", "$")
    return copy.deepcopy(value)


def build_artifact(payload: Mapping[str, Any]) -> dict:
    """Add v1 identities and recomputed summary to the caller's raw payload."""
    _need(isinstance(payload, Mapping), "INVALID_TYPE", "$")
    _need("summary" not in payload, "FACTORY_SUMMARY_FORBIDDEN", "$.summary")
    value = copy.deepcopy(dict(payload))
    for key, expected in _IDENTITIES.items():
        _need(key not in value or value[key] == expected, "INVALID_CONSTANT", "$." + key)
        value[key] = expected
    _need(type(value.get("frames")) is list, "INVALID_TYPE", "$.frames")
    _need(all(type(frame) is dict and "frame_ms" in frame for frame in value["frames"]),
          "MISSING_FIELD", "$.frames.frame_ms")
    value["summary"] = summarize(frame["frame_ms"] for frame in value["frames"])
    return validate_artifact(value)


def parse_artifact(raw: bytes | str, *, expected: Mapping[str, Any] | None = None) -> dict:
    """Parse a <=64 MiB local artifact, rejecting ambiguous/nonfinite JSON."""
    _need(type(raw) in (bytes, str), "INVALID_TYPE", "$")
    try:
        encoded = raw.encode("utf-8", "strict") if type(raw) is str else raw
        _need(len(encoded) <= MAX_ARTIFACT_BYTES, "ARTIFACT_BYTE_LIMIT", "$")
        text = encoded.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise PerfError("INVALID_UTF8") from exc

    def pairs(items):
        result = {}
        for key, item in items:
            _need(key not in result, "DUPLICATE_KEY", "$")
            result[key] = item
        return result

    def constant(_value):
        raise PerfError("NON_FINITE_NUMBER")

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except PerfError:
        raise
    except (ValueError, RecursionError) as exc:
        raise PerfError("INVALID_JSON") from exc
    result = validate_artifact(value, expected=expected)
    _need(len(encoded) <= result["sampling"]["max_artifact_bytes"], "ARTIFACT_BYTE_LIMIT", "$")
    return result

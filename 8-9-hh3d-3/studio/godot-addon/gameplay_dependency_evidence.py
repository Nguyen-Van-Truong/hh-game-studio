"""Fail-closed validation for a future Godot dependency observation.

The validator consumes a *later trusted observation*; it never parses
GDScript/TSCN, reads project files, or starts Godot/Docker. It binds the
observed node graph to caller-supplied immutable bytes and can compare a
close/reopen observation. It intentionally never grants AUTH-02 or public
authority: native readback and executor attribution must be added separately.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
import unicodedata
from collections.abc import Mapping

SCHEMA = "hh-gameplay-dependency-observation-1"
VERSION = 1
_ROOTS = frozenset(("scripts", "scenes", "assets"))
_EDGE_KINDS = frozenset(("scene_ext_resource", "script_preload",
                         "dynamic_load", "asset_load"))
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_UID = re.compile(r"uid://[a-z0-9_-]{1,127}\Z")
_DEVICES = frozenset({"CON", "PRN", "AUX", "NUL",
                      *(f"COM{i}" for i in range(1, 10)),
                      *(f"LPT{i}" for i in range(1, 10))})


class DependencyEvidenceError(ValueError):
    pass


def _fail(code: str):
    raise DependencyEvidenceError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _path(value: object, *, code="DEPENDENCY_NODE_PATH") -> str:
    if (type(value) is not str or not value or value.startswith("res://")
            or "\\" in value or ":" in value or "\x00" in value
            or value != unicodedata.normalize("NFC", value)
            or value != value.casefold()):
        _fail(code)
    parts = value.split("/")
    if (len(parts) < 2 or parts[0] not in _ROOTS
            or any(not part or part in (".", "..") for part in parts[1:])):
        _fail(code)
    for part in parts[1:]:
        if any(ord(char) < 32 for char in part) or part[-1] in " .":
            _fail(code)
        if part.split(".", 1)[0].upper() in _DEVICES:
            _fail(code)
    if posixpath.normpath(value) != value:
        _fail(code)
    return value


def _uid(value: object) -> str:
    if type(value) is not str or _UID.fullmatch(value) is None:
        _fail("DEPENDENCY_UID_INVALID")
    return value


def _canonical_observation(value: Mapping) -> dict:
    if not isinstance(value, Mapping) or set(value) != {
            "schema", "version", "entrypoint", "nodes"}:
        _fail("DEPENDENCY_OBSERVATION_SHAPE")
    if value["schema"] != SCHEMA:
        _fail("DEPENDENCY_OBSERVATION_SCHEMA")
    if type(value["version"]) is not int or value["version"] != VERSION:
        _fail("DEPENDENCY_OBSERVATION_VERSION")
    entrypoint = _path(value["entrypoint"])
    nodes = value["nodes"]
    if type(nodes) is not list or not nodes:
        _fail("DEPENDENCY_NODE_SET")
    normalized, paths, folded, uids = [], set(), set(), set()
    for node in nodes:
        if not isinstance(node, Mapping) or set(node) != {
                "path", "kind", "size_bytes", "sha256", "uid", "edges"}:
            _fail("DEPENDENCY_NODE_FIELDS")
        path = _path(node["path"])
        if path in paths or path.casefold() in folded:
            _fail("DEPENDENCY_PATH_ALIAS")
        paths.add(path)
        folded.add(path.casefold())
        kind = node["kind"]
        suffix = path.rsplit(".", 1)[-1].lower()
        expected_kind = ("script" if suffix == "gd" else
                         "scene" if suffix == "tscn" else "asset")
        if type(kind) is not str or kind != expected_kind:
            _fail("DEPENDENCY_NODE_KIND")
        size = node["size_bytes"]
        if type(size) is not int or size < 1 or size > 2 * 1024 * 1024:
            _fail("DEPENDENCY_NODE_SIZE")
        digest = node["sha256"]
        if type(digest) is not str or _HASH.fullmatch(digest) is None:
            _fail("DEPENDENCY_NODE_HASH")
        uid = _uid(node["uid"])
        if uid in uids:
            _fail("DEPENDENCY_UID_DUPLICATE")
        uids.add(uid)
        edges = node["edges"]
        if type(edges) is not list:
            _fail("DEPENDENCY_EDGE_SET")
        normalized.append({"path": path, "kind": kind, "size_bytes": size,
                           "sha256": digest, "uid": uid,
                           "edges": sorted((dict(edge) for edge in edges),
                                           key=lambda edge: (str(edge.get("kind")),
                                                             str(edge.get("target"))))})
    if entrypoint not in paths:
        _fail("DEPENDENCY_ENTRYPOINT_MISSING")
    normalized.sort(key=lambda row: row["path"])
    return {"schema": SCHEMA, "version": VERSION, "entrypoint": entrypoint,
            "nodes": normalized}


def _bind_files(files: Mapping, graph: dict) -> dict[str, bytes]:
    if not isinstance(files, Mapping):
        _fail("DEPENDENCY_FILE_SET")
    actual, folded = {}, set()
    for name, raw in files.items():
        if type(name) is not str:
            _fail("DEPENDENCY_FILE_PATH")
        if name.casefold() in folded:
            _fail("DEPENDENCY_PATH_ALIAS")
        folded.add(name.casefold())
        _path(name, code="DEPENDENCY_FILE_PATH")
        if type(raw) is not bytes:
            _fail("DEPENDENCY_FILE_BYTES")
        actual[name] = raw
    paths = {row["path"] for row in graph["nodes"]}
    if set(actual) != paths:
        _fail("DEPENDENCY_NODE_SET")
    for row in graph["nodes"]:
        raw = actual[row["path"]]
        if row["size_bytes"] != len(raw):
            _fail("DEPENDENCY_NODE_SIZE")
        if row["sha256"] != _sha(raw):
            _fail("DEPENDENCY_NODE_HASH")
    return actual


def _bind_edges(graph: dict) -> None:
    nodes = {row["path"]: row for row in graph["nodes"]}
    folded_nodes = {path.casefold(): path for path in nodes}
    seen, adjacency = set(), {path: [] for path in nodes}
    for row in graph["nodes"]:
        source = row["path"]
        for edge in row["edges"]:
            if not isinstance(edge, Mapping) or set(edge) != {"kind", "target"}:
                _fail("DEPENDENCY_EDGE_FIELDS")
            kind, target = edge["kind"], edge["target"]
            if type(kind) is not str or kind not in _EDGE_KINDS:
                _fail("DEPENDENCY_EDGE_KIND")
            _path(target)
            if target not in nodes:
                if target.casefold() in folded_nodes:
                    _fail("DEPENDENCY_PATH_ALIAS")
                _fail("DEPENDENCY_EDGE_MISSING")
            if (kind == "scene_ext_resource" and row["kind"] != "scene") or \
                    (kind == "script_preload" and row["kind"] != "script") or \
                    (kind == "asset_load" and nodes[target]["kind"] != "asset"):
                _fail("DEPENDENCY_EDGE_KIND")
            key = (source, kind, target)
            if key in seen:
                _fail("DEPENDENCY_EDGE_DUPLICATE")
            seen.add(key)
            adjacency[source].append(target)
    active, done = set(), set()
    def visit(path: str) -> None:
        if path in active:
            _fail("DEPENDENCY_CYCLE")
        if path in done:
            return
        active.add(path)
        for target in sorted(adjacency[path]):
            visit(target)
        active.remove(path)
        done.add(path)
    for path in sorted(nodes):
        visit(path)


def _graph_digest(graph: dict) -> str:
    encoded = json.dumps(graph, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_dependency_observation(files: Mapping, observation: Mapping,
                                    *, reopened_files=None,
                                    reopened_observation=None) -> dict:
    """Validate a byte-bound graph while retaining authority zero."""
    graph = _canonical_observation(observation)
    actual = _bind_files(files, graph)
    _bind_edges(graph)
    digest = _graph_digest(graph)
    reopen_match = False
    if (reopened_files is None) != (reopened_observation is None):
        _fail("DEPENDENCY_REOPEN_BINDING")
    if reopened_files is not None:
        reopened = _canonical_observation(reopened_observation)
        reopened_actual = _bind_files(reopened_files, reopened)
        _bind_edges(reopened)
        if (actual != reopened_actual or graph != reopened
                or _graph_digest(reopened) != digest):
            _fail("DEPENDENCY_REOPEN_MISMATCH")
        reopen_match = True
    return {"schema": SCHEMA, "graph_sha256": digest,
            "native_observation_verified": False,
            "reopen_match": reopen_match,
            "dependency_closure_verified": False,
            "public_ack": False, "authority": 0}


def graph_digest(files: Mapping, observation: Mapping) -> str:
    """Expose the deterministic digest without changing the authority boundary."""
    return validate_dependency_observation(files, observation)["graph_sha256"]

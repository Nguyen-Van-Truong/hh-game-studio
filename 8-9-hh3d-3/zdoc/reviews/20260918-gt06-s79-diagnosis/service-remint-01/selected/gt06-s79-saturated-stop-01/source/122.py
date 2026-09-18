"""Bounded, data-only lint for contracts/naming-convention-v1.md.

Callers must decode bounded strict JSON first. This module performs no I/O and
grants no path, engine, geometry, license or publication authority.
"""
from __future__ import annotations

import re
from typing import Any

MAX_ASSETS = 64
MAX_NAMES = 256
MAX_NAME_LENGTH = 64
MAX_ASSET_ID_LENGTH = MAX_NAME_LENGTH - len("_collider")
CLASSES = {"character": "chr", "prop": "prp", "environment": "env", "ui": "ui"}
WORD = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", re.ASCII)
RESERVED_TAIL = re.compile(r"_(?:lod[0-9]+|collider|nav|rig)$", re.ASCII)
ASSET_FIELDS = {"asset_id", "class", "nodes", "bones", "clips", "materials", "sockets"}


class NamingRejected(ValueError):
    """Stable error code only; never echo an untrusted path/name."""


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise NamingRejected(code)


def _fields(value: Any, required: set[str], code: str) -> None:
    _need(type(value) is dict and set(value) == required, code)


def _name(value: Any, prefix: str = "") -> str:
    _need(type(value) is str and 0 < len(value) <= MAX_NAME_LENGTH, "NAME_LENGTH_OR_TYPE")
    _need(value.startswith(prefix) and WORD.fullmatch(value[len(prefix):]) is not None,
          "NAME_GRAMMAR")
    return value


def _rows(value: Any, cap: int = MAX_NAMES) -> list:
    _need(type(value) is list and len(value) <= cap, "NAME_LIST_LIMIT_OR_TYPE")
    return value


def _unique_names(value: Any, prefix: str = "") -> list[str]:
    names = [_name(row, prefix) for row in _rows(value)]
    _need(len(names) == len(set(names)), "DUPLICATE_NAME")
    return names


def validate_catalog(value: Any) -> dict[str, int | str]:
    """Validate declared names, returning counts rather than an acceptance flag.

    Empty optional namespaces and an empty catalog are syntactically legal.
    Required fixture coverage is a separate GT05 integration check.
    """
    _fields(value, {"schema", "assets"}, "CATALOG_FIELDS")
    _need(value["schema"] == "HH-ASSET-NAMES-1", "CATALOG_SCHEMA")
    assets = _rows(value["assets"], MAX_ASSETS)
    ids: set[str] = set()
    node_count = 0
    for asset in assets:
        _fields(asset, ASSET_FIELDS, "ASSET_FIELDS")
        kind = asset["class"]
        _need(type(kind) is str and kind in CLASSES, "ASSET_CLASS")
        asset_id = _name(asset["asset_id"], CLASSES[kind] + "_")
        _need(len(asset_id) <= MAX_ASSET_ID_LENGTH, "ASSET_SUFFIX_HEADROOM")
        _need(RESERVED_TAIL.search(asset_id) is None, "RESERVED_ASSET_SUFFIX")
        _need(asset_id not in ids, "DUPLICATE_ASSET_ID")
        ids.add(asset_id)
        node_names: set[str] = set()
        for node in _rows(asset["nodes"]):
            _need(type(node) is dict and type(node.get("role")) is str, "NODE_FIELDS")
            role = node["role"]
            if role == "render":
                _fields(node, {"name", "role", "lod"}, "NODE_FIELDS")
                lod = node["lod"]
                _need(type(lod) is int and lod in (0, 1), "NODE_LOD")
                expected = f"{asset_id}_lod{lod}"
            else:
                _fields(node, {"name", "role"}, "NODE_FIELDS")
                _need(role in ("collider", "nav", "rig"), "NODE_ROLE")
                expected = f"{asset_id}_{role}"
            name = _name(node["name"])
            _need(name == expected, "NODE_ASSET_ROLE_BINDING")
            _need(name not in node_names, "DUPLICATE_NODE")
            node_names.add(name)
        node_count += len(node_names)
        _unique_names(asset["bones"], "bn_")
        clips = _unique_names(asset["clips"])
        _need(all(clip in ("idle", "walk") for clip in clips), "CLIP_UNSUPPORTED")
        _unique_names(asset["materials"], "mat_")
        _unique_names(asset["sockets"], "socket_")
    return {"schema": "HH-ASSET-NAMES-1", "assets": len(ids), "nodes": node_count}

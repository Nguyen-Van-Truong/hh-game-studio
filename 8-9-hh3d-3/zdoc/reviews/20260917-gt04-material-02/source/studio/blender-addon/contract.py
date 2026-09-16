"""Private GT04 fixture commands; not the public studio protocol."""
from __future__ import annotations

import hashlib
import json
import math
import re

SCHEMA = "HH-BLENDER-FIXTURE-COMMAND-1"
MAX_BYTES = 4096
MAX_COMMANDS = 64
MAX_OBJECTS = 16
ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
REVISION = re.compile(r"sha256:[0-9a-f]{64}\Z")


class Rejected(ValueError):
    pass


def exact(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise Rejected(label + ": exact fields required")


def identifier(value):
    if type(value) is not str or not ID.fullmatch(value):
        raise Rejected("invalid identifier")
    return value


def vector(value, lower, upper):
    if type(value) is not list or len(value) != 3:
        raise Rejected("expected three numbers")
    for item in value:
        if type(item) not in (int, float) or not lower <= item <= upper or not math.isfinite(item):
            raise Rejected("number out of bounds")
    return [float(item) for item in value]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def _pairs(rows):
    value = {}
    for key, item in rows:
        if key in value:
            raise Rejected("duplicate JSON field")
        value[key] = item
    return value


def parse(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise Rejected("bounded bytes required")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(Rejected("nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Rejected("invalid JSON") from exc
    return validate(value)


def validate(value):
    exact(value, ("schema", "command_id", "operation", "expected_revision", "expected_context", "payload"), "command")
    if value["schema"] != SCHEMA or type(value["schema"]) is not str:
        raise Rejected("unknown schema")
    identifier(value["command_id"])
    operation = value["operation"]
    if type(operation) is not str or operation not in ("scene.inspect", "mesh.create_box", "object.transform.set", "material.set_principled"):
        raise Rejected("unsupported operation")
    payload = value["payload"]
    if operation == "scene.inspect":
        exact(payload, (), "inspect")
        if value["expected_revision"] is not None or value["expected_context"] is not None:
            raise Rejected("inspect preconditions must be null")
    else:
        if type(value["expected_revision"]) is not str or not REVISION.fullmatch(value["expected_revision"]):
            raise Rejected("revision required")
        context = value["expected_context"]
        exact(context, ("mode", "active_id", "selected_ids"), "context")
        if context["mode"] not in ("OBJECT", "EDIT_MESH"):
            raise Rejected("unsupported mode")
        if context["active_id"] is not None:
            identifier(context["active_id"])
        ids = context["selected_ids"]
        if type(ids) is not list or len(ids) > MAX_OBJECTS:
            raise Rejected("selection limit")
        for item in ids:
            identifier(item)
        if ids != sorted(set(ids)) or (context["mode"] == "EDIT_MESH" and context["active_id"] not in ids):
            raise Rejected("invalid selection")
        fields = (("object_id", "size") if operation == "mesh.create_box" else
                  ("object_id", "material_id", "base_color", "metallic", "roughness") if operation == "material.set_principled" else
                  ("object_id", "location", "rotation", "scale"))
        exact(payload, fields, "payload")
        identifier(payload["object_id"])
        if operation == "mesh.create_box":
            vector(payload["size"], 0.001, 1000.0)
        elif operation == "material.set_principled":
            identifier(payload['material_id']);vector(payload['base_color'],0.0,1.0)
            for name in ('metallic','roughness'):
                item=payload[name]
                if type(item) not in (int,float) or not math.isfinite(item) or not 0<=item<=1:
                    raise Rejected('material scalar range')
        else:
            vector(payload["location"], -10000.0, 10000.0)
            vector(payload["rotation"], -6.283185307179586, 6.283185307179586)
            vector(payload["scale"], 0.001, 1000.0)
    try:
        raw = canonical(value)
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise Rejected("invalid data") from exc
    if len(raw) > MAX_BYTES:
        raise Rejected("command limit")
    return json.loads(raw)

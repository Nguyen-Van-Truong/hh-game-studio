"""Closed GT-09 content recipe and independent binary postconditions.

The fixture profile is a trusted host recipe, never arbitrary Python, input
Blends, paths, shader graphs or rig weights supplied by a client. Native work
and immutable publication are owned by ``fixture_content_job``. This module
performs no mutation and grants no public capability or acceptance.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import math
from pathlib import Path
import struct
import sys
import zlib

from studio.protocol.core import Request, canonical_bytes, parse_json

STUDIO = Path(__file__).resolve().parents[2]
PROFILE = "hh-blender-gt09-fixture-content-1"
SCHEMA = "HH-BLENDER-FIXTURE-CONTENT-1"
PROJECT = "project.registered.blender"
MAX_ARTIFACT = 1024 * 1024
MAX_COMMANDS = 64
BONE_NAMES = ("root", "spine", "leg.l", "leg.r")
OBJECTS = ("torso", "head", "leg_left", "leg_right")
FIXED_ARTIFACTS = ("scene.glb", "sprite_sheet.png", "checkpoint.blend", "transcript.json")
EVIDENCE_FILES = ("native.json", "host-process.json", "process-start.json", "process-exit.json",
                  "stdout.txt", "stderr.txt", "recipe.json", "source-closure.json")


class ContentError(ValueError):
    pass


def need(value, code):
    if not value:
        raise ContentError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return "sha256:" + sha(canonical_bytes(value))


def load(relative):
    path = STUDIO / relative
    key = "_hh_fixture_content_" + sha(str(path).encode() + path.read_bytes())
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def recipe():
    """Return a detached recipe: atlas source is then edited into the avatar.

    The existing four-material limit is preserved. All box/material/transform
    writes use the accepted validator and native FixtureAdapter. The O2 rig
    commands use authoring_contract unchanged. Three fixed artifact presets
    are confined to this fixture profile, not the general write catalog.
    """
    contract = load("blender-addon/authoring_contract.py")
    template = next(row for row in contract.load_catalog().as_dict()["templates"]
                    if row["template_id"] == "quadruped-lite")
    rows = []

    def add(operation, target, payload):
        rows.append({"command_id": "content-%02d" % (len(rows) + 1),
                     "operation": operation, "target": target, "payload": payload})

    colors = ((0.9, 0.1, 0.1), (0.1, 0.9, 0.1), (0.1, 0.2, 0.9), (0.9, 0.8, 0.1))
    positions = ((-1, 1, 0), (1, 1, 0), (-1, -1, 0), (1, -1, 0))
    for name, color, position in zip(OBJECTS, colors, positions):
        add("mesh.create_box", name, {"object_id": name, "size": [2, 2, 2]})
        add("material.set_principled", name,
            {"object_id": name, "material_id": name, "base_color": list(color),
             "metallic": 0, "roughness": 0.65})
        add("object.transform.set", name,
            {"object_id": name, "location": list(position), "rotation": [0, 0, 0],
             "scale": [0.92, 0.92, 0.05]})
    add("sprite_sheet.render", "root", {"preset": "four-cell-rgba128"})
    avatar = (((0, 1.1, 0), (0.42, 0.5, 0.24)),
              ((0, 1.8, 0), (0.32, 0.28, 0.22)),
              ((-0.3, 0.4, 0), (0.16, 0.38, 0.2)),
              ((0.3, 0.4, 0), (0.16, 0.38, 0.2)))
    for name, (position, scale) in zip(OBJECTS, avatar):
        add("object.transform.set", name,
            {"object_id": name, "location": list(position), "rotation": [0, 0, 0],
             "scale": list(scale)})
    add("armature.from_template", "root", {"stable_id": "avatar.rig",
        "template_id": template["template_id"], "template_sha256": template["template_sha256"]})
    add("animation.action.create", "avatar.rig", {"stable_id": "walk"})
    for frame, direction in ((1, -1), (7, 1), (13, -1), (19, 1), (25, -1)):
        for bone, sign in (("leg.l", 1), ("leg.r", -1)):
            add("animation.keyframe.set", "walk", {"bone_id": bone,
                "channel": "rotation_euler", "frame": frame,
                "values": [0.45 * direction * sign, 0, 0], "interpolation": "LINEAR"})
    add("avatar.bind", "avatar.rig", {"preset": "four-box-rigid-template"})
    add("content.export", "root", {"preset": "glb-skin-walk-and-checkpoint"})
    return {"schema": SCHEMA, "profile": PROFILE, "project_id": PROJECT,
            "commands": rows, "authority": 0, "public_ack": False}


def validate_recipe(value):
    """Validate the closed preset and independently exercise existing schemas."""
    need(type(value) is dict and canonical_bytes(value) == canonical_bytes(recipe()),
         "CONTENT_RECIPE_NOT_HOST_PRESET")
    need(len(value["commands"]) <= MAX_COMMANDS, "CONTENT_COMMAND_CAP")
    base = load("blender-addon/contract.py")
    authoring = load("blender-addon/authoring_contract.py")
    catalog = authoring.load_catalog()
    ctx = authoring.ValidationContext(PROJECT, "sha256:" + "0" * 64, 1,
        "lease.fixture.content", 1, 31000, 1000)
    for row in value["commands"]:
        if row["operation"] in authoring.OPERATIONS:
            payload = dict(row["payload"], expected_generation=1)
            request = Request(command_id=row["command_id"], project_id=PROJECT,
                operation=row["operation"], lease_id=ctx.lease_id, fencing_epoch=ctx.fencing_epoch,
                expected_revision=ctx.revision, target={"stable_id": row["target"]},
                payload=payload, payload_hash=digest(payload), deadline_ms=2000)
            proposal = authoring.validate_request(request, ctx, catalog).proposal
            after = proposal["after"]
            if row["operation"] == "armature.from_template":
                ctx = replace(ctx, armatures=ctx.armatures + (authoring.ArmatureState(
                    after["stable_id"], after["template_id"], after["template_sha256"]),))
            elif row["operation"] == "animation.action.create":
                ctx = replace(ctx, actions=(authoring.ActionState(after["stable_id"], after["armature_id"]),))
            else:
                key = authoring.KeyframeState(after["bone_id"], after["channel"], after["frame"],
                                             tuple(after["values"]), after["interpolation"])
                ctx = replace(ctx, actions=(replace(ctx.actions[0], keyframes=ctx.actions[0].keyframes + (key,)),))
        elif row["operation"] in ("mesh.create_box", "object.transform.set", "material.set_principled"):
            base.validate({"schema": base.SCHEMA, "command_id": row["command_id"],
                "operation": row["operation"], "expected_revision": ctx.revision,
                "expected_context": {"mode": "OBJECT", "active_id": None, "selected_ids": []},
                "payload": row["payload"]})
    return {"recipe_sha256": sha(canonical_bytes(value)), "commands": len(value["commands"]),
            "catalog_digest": catalog.digest, "template_sha256": ctx.armatures[0].template_sha256,
            "keyframes": len(ctx.actions[0].keyframes)}


def inspect_png(raw):
    """Decode only the fixed RGBA8 PNG profile, with CRC and inflate bounds."""
    need(type(raw) is bytes and 57 <= len(raw) <= MAX_ARTIFACT
         and raw[:8] == b"\x89PNG\r\n\x1a\n", "CONTENT_PNG_HEADER")
    offset, data, header, ended = 8, bytearray(), None, False
    while offset < len(raw):
        need(offset + 12 <= len(raw) and not ended, "CONTENT_PNG_CHUNK")
        size, kind = struct.unpack_from(">I4s", raw, offset)
        offset += 8
        need(size <= MAX_ARTIFACT and offset + size + 4 <= len(raw), "CONTENT_PNG_BOUNDS")
        payload = raw[offset:offset + size]
        crc = struct.unpack_from(">I", raw, offset + size)[0]
        need(zlib.crc32(kind + payload) & 0xffffffff == crc, "CONTENT_PNG_CRC")
        offset += size + 4
        if kind == b"IHDR":
            need(header is None and size == 13, "CONTENT_PNG_IHDR")
            header = struct.unpack(">IIBBBBB", payload)
            need(header == (128, 128, 8, 6, 0, 0, 0), "CONTENT_PNG_PROFILE")
        elif kind == b"IDAT":
            need(header is not None, "CONTENT_PNG_ORDER")
            data.extend(payload)
        elif kind == b"IEND":
            need(size == 0 and header is not None and data, "CONTENT_PNG_END")
            ended = True
        else:
            # Blender 5.2's fixed Workbench renderer emits these bounded,
            # non-pixel metadata chunks in addition to the colour/profile
            # chunks.  They carry no external references or executable data;
            # keep the parser closed over this exact native output profile.
            need(kind in (b"pHYs", b"gAMA", b"cHRM", b"sRGB", b"sBIT", b"tEXt",
                          b"eXIf", b"oFFs"),
                 "CONTENT_PNG_UNSUPPORTED_CHUNK")
    need(ended, "CONTENT_PNG_END")
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(bytes(data), 128 * 513 + 1)
    need(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
         and len(pixels) == 128 * 513, "CONTENT_PNG_INFLATE_CAP")
    rows, previous = [], bytearray(512)
    for y in range(128):
        kind = pixels[y * 513]
        row = bytearray(pixels[y * 513 + 1:(y + 1) * 513])
        need(kind <= 4, "CONTENT_PNG_FILTER")
        for x in range(512):
            a, b, c = (row[x - 4] if x >= 4 else 0), previous[x], (previous[x - 4] if x >= 4 else 0)
            if kind == 4:
                p = a + b - c
                distances = (abs(p - a), abs(p - b), abs(p - c))
                predictor = (a, b, c)[distances.index(min(distances))]
            else:
                predictor = (0, a, b, (a + b) // 2)[kind]
            row[x] = (row[x] + predictor) & 255
        rows.append(row)
        previous = row
    # The shared pixel oracle uses Blender's bottom-left ordering.
    floats = [item / 255 for row in reversed(rows) for item in row]
    observation = load("tests/blender/sprite_sheet_pixels.py").inspect_pixels(128, 128, floats)
    need(observation["passed"], "CONTENT_PNG_CELLS_OR_GUTTERS")
    return {"sha256": sha(raw), "size_bytes": len(raw), "width": 128, "height": 128,
            "pixels": observation}


def inspect_glb(raw):
    """Inspect actual skin and changing walk channels; reject external intake.

    This is a closed producer profile, not a general glTF validator or proof of
    Godot import. Godot remains a separate native consumer postcondition.
    """
    need(type(raw) is bytes and 28 <= len(raw) <= MAX_ARTIFACT, "CONTENT_GLB_CAP")
    need(struct.unpack_from("<4sII", raw) == (b"glTF", 2, len(raw)), "CONTENT_GLB_HEADER")
    chunks, offset = [], 12
    while offset < len(raw):
        need(offset + 8 <= len(raw) and len(chunks) < 2, "CONTENT_GLB_CHUNKS")
        size, kind = struct.unpack_from("<II", raw, offset)
        offset += 8
        need(size % 4 == 0 and offset + size <= len(raw), "CONTENT_GLB_BOUNDS")
        chunks.append((kind, raw[offset:offset + size]))
        offset += size
    need(len(chunks) == 2 and [r[0] for r in chunks] == [0x4e4f534a, 0x004e4942], "CONTENT_GLB_CHUNKS")
    value, binary = parse_json(chunks[0][1]), chunks[1][1]
    allowed = {"asset", "scene", "scenes", "nodes", "meshes", "accessors", "bufferViews",
               "buffers", "materials", "skins", "animations"}
    need(type(value) is dict and set(value) <= allowed, "CONTENT_GLB_DEPENDENCY")

    def integer(number, limit):
        return type(number) is int and 0 <= number < limit

    need(value.get("asset", {}).get("version") == "2.0", "CONTENT_GLB_ASSET")
    buffers = value.get("buffers")
    need(type(buffers) is list and len(buffers) == 1 and set(buffers[0]) == {"byteLength"}, "CONTENT_GLB_EXTERNAL_BUFFER")
    size = buffers[0]["byteLength"]
    need(integer(size, MAX_ARTIFACT) and 0 <= len(binary) - size <= 3 and not any(binary[size:]), "CONTENT_GLB_BINARY_SIZE")
    views, accessors = value.get("bufferViews"), value.get("accessors")
    need(type(views) is list and 1 <= len(views) <= 128 and type(accessors) is list
         and 1 <= len(accessors) <= 128, "CONTENT_GLB_ACCESSOR_CAP")
    for view in views:
        need(type(view) is dict and set(view) <= {"buffer", "byteOffset", "byteLength", "byteStride", "target"}
             and view.get("buffer") == 0, "CONTENT_GLB_VIEW")
        start, length = view.get("byteOffset", 0), view.get("byteLength")
        need(integer(start, size) and type(length) is int and 1 <= length <= size - start, "CONTENT_GLB_VIEW_BOUNDS")
    decoded = []
    for accessor in accessors:
        need(type(accessor) is dict and set(accessor) <= {"bufferView", "byteOffset", "componentType", "count", "type", "min", "max"},
             "CONTENT_GLB_ACCESSOR")
        view_id, component, count = accessor.get("bufferView"), accessor.get("componentType"), accessor.get("count")
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}.get(accessor.get("type"))
        need(integer(view_id, len(views)) and component in (5121, 5123, 5125, 5126)
             and type(count) is int and 1 <= count <= 4096 and width is not None, "CONTENT_GLB_ACCESSOR_TYPE")
        fmt = {5121: "B", 5123: "H", 5125: "I", 5126: "f"}[component]
        width_bytes = struct.calcsize(fmt) * width
        view = views[view_id]
        start, stride = accessor.get("byteOffset", 0), view.get("byteStride", width_bytes)
        need(integer(start, size) and type(stride) is int and width_bytes <= stride <= 256
             and start + (count - 1) * stride + width_bytes <= view["byteLength"], "CONTENT_GLB_ACCESSOR_BOUNDS")
        rows = [struct.unpack_from("<" + fmt * width, binary, view.get("byteOffset", 0) + start + i * stride) for i in range(count)]
        need(all(math.isfinite(x) and abs(x) <= 1e6 for row in rows for x in row), "CONTENT_GLB_NONFINITE")
        decoded.append(rows)

    def data(index):
        need(integer(index, len(decoded)), "CONTENT_GLB_ACCESSOR_REFERENCE")
        return decoded[index]

    nodes, meshes, skins, animations = (value.get(key) for key in ("nodes", "meshes", "skins", "animations"))
    need(type(nodes) is list and 5 <= len(nodes) <= 32 and type(meshes) is list and len(meshes) == 4
         and type(skins) is list and len(skins) == 1 and type(animations) is list and len(animations) == 1,
         "CONTENT_GLB_PROFILE")
    for node in nodes:
        need(type(node) is dict and set(node) <= {"name", "mesh", "skin", "children", "translation", "rotation", "scale", "matrix"},
             "CONTENT_GLB_NODE")
        children = node.get("children", [])
        need(type(children) is list and len(children) <= 16 and all(integer(x, len(nodes)) for x in children), "CONTENT_GLB_HIERARCHY")
    skin = skins[0]
    need(type(skin) is dict and set(skin) <= {"name", "inverseBindMatrices", "joints", "skeleton"}, "CONTENT_GLB_SKIN")
    joints = skin.get("joints")
    need(type(joints) is list and len(joints) == 4 and len(set(joints)) == 4
         and all(integer(x, len(nodes)) for x in joints)
         and {nodes[x].get("name") for x in joints} == set(BONE_NAMES), "CONTENT_GLB_TEMPLATE_BONES")
    matrices = data(skin.get("inverseBindMatrices"))
    need(len(matrices) == 4 and all(len(row) == 16 for row in matrices), "CONTENT_GLB_BIND_MATRICES")
    skinned = [node for node in nodes if "mesh" in node]
    need(len(skinned) == 4 and all(node.get("skin") == 0 and integer(node["mesh"], 4) for node in skinned), "CONTENT_GLB_SKIN_BINDING")
    for mesh in meshes:
        need(type(mesh) is dict and set(mesh) <= {"name", "primitives"}
             and type(mesh.get("primitives")) is list and len(mesh["primitives"]) == 1, "CONTENT_GLB_MESH")
        primitive = mesh["primitives"][0]
        need(set(primitive) <= {"attributes", "indices", "material", "mode"}
             and primitive.get("mode", 4) == 4, "CONTENT_GLB_PRIMITIVE")
        attributes = primitive.get("attributes", {})
        need(set(attributes) == {"POSITION", "NORMAL", "JOINTS_0", "WEIGHTS_0"}, "CONTENT_GLB_ATTRIBUTES")
        positions, weights, joint_ids = (data(attributes[key]) for key in ("POSITION", "WEIGHTS_0", "JOINTS_0"))
        need(8 <= len(positions) <= 36 and len(weights) == len(joint_ids) == len(positions), "CONTENT_GLB_VERTEX_COUNT")
        need(all(len(row) == 4 and abs(sum(row) - 1) < 1e-6 and all(0 <= x <= 1 for x in row) for row in weights), "CONTENT_GLB_WEIGHTS")
        need(all(len(row) == 4 and all(integer(x, 4) for x in row) for row in joint_ids), "CONTENT_GLB_JOINT_INDEX")
        indices = data(primitive.get("indices"))
        need(len(indices) == 36 and all(len(row) == 1 and integer(row[0], len(positions)) for row in indices), "CONTENT_GLB_INDICES")
    animation = animations[0]
    need(set(animation) <= {"name", "channels", "samplers"} and animation.get("name") == "walk", "CONTENT_GLB_WALK_NAME")
    channels, samplers = animation.get("channels"), animation.get("samplers")
    need(type(channels) is list and 2 <= len(channels) <= 16 and type(samplers) is list
         and 2 <= len(samplers) <= 16, "CONTENT_GLB_ANIMATION_CAP")
    changed = set()
    for channel in channels:
        need(set(channel) == {"sampler", "target"} and integer(channel["sampler"], len(samplers)), "CONTENT_GLB_CHANNEL")
        target, sampler = channel["target"], samplers[channel["sampler"]]
        need(set(target) == {"node", "path"} and target["node"] in joints
             and target["path"] in ("translation", "rotation", "scale"), "CONTENT_GLB_ANIMATION_TARGET")
        need(set(sampler) <= {"input", "output", "interpolation"} and sampler.get("interpolation", "LINEAR") == "LINEAR", "CONTENT_GLB_SAMPLER")
        times, values = data(sampler.get("input")), data(sampler.get("output"))
        need(len(times) == len(values) and 2 <= len(times) <= 64 and all(len(row) == 1 for row in times)
             and all(a[0] < b[0] for a, b in zip(times, times[1:]))
             and abs(times[0][0]) < 1e-6 and abs(times[-1][0] - 1) < 1e-6, "CONTENT_GLB_WALK_TIME")
        if target["path"] == "rotation" and any(sum((a - b) ** 2 for a, b in zip(values[0], row)) > 1e-4 for row in values[1:]):
            changed.add(nodes[target["node"]]["name"])
    need({"leg.l", "leg.r"} <= changed, "CONTENT_GLB_WALK_STATIC")
    return {"sha256": sha(raw), "size_bytes": len(raw), "mesh_count": 4,
            "bone_names": list(BONE_NAMES), "clip": "walk", "duration_seconds": 1,
            "changing_rotation_bones": sorted(changed), "external_dependencies": []}

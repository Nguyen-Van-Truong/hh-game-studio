"""O2 proposals only: trusted template armature and bounded action/keyframe data.

No bpy import, file write, capability registration, execution or commit ACK.
The context is a host observation, never a request-provided assertion. Native
apply must recheck lease/revision and prove readback/undo before registration.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re

from studio.protocol.core import Request, ValidationError, canonical_bytes, parse_json

SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'contracts/blender-authoring-schema-v1.json'
PROFILE = 'hh-blender-authoring-source-1'
OPERATIONS = ('armature.from_template', 'animation.action.create', 'animation.keyframe.set')
NATIVE_GATES = ('BLEND-AUTH-01', 'BLEND-AUTH-02', 'BLEND-AUTH-03', 'BLEND-AUTH-04')
LIMITS = dict(max_armatures=16, max_bones=32, max_actions=32, max_keyframes=256, max_frame=10000)
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')
_CHANNELS = {'location': (-1000, 1000), 'rotation_euler': (-math.tau, math.tau), 'scale': (0.001, 1000)}


class ContractError(ValidationError):
    def __init__(self, code):
        super().__init__(code, 'O2 Blender candidate; no effect authorized')


def _need(value, code):
    if not value:
        raise ContractError(code)


def _shape(value, keys):
    _need(type(value) is dict and set(value) == set(keys), 'BLEND_AUTH_SHAPE')


def _id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _digest(value):
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _int(value, low=0, high=2147483647):
    return type(value) is int and low <= value <= high


def _vector(value, low, high):
    return type(value) in (list, tuple) and len(value) == 3 and all(
        type(x) in (int, float) and low <= x <= high and math.isfinite(x) for x in value)


def template_digest(template_id, bones):
    """Shared canonical-wire domain, independent of JSON whitespace/order."""
    return 'sha256:' + hashlib.sha256(canonical_bytes(dict(template_id=template_id, bones=bones))).hexdigest()


@dataclass(frozen=True, slots=True)
class Catalog:
    digest: str
    _encoded: bytes

    def as_dict(self):
        return parse_json(self._encoded)


def load_catalog(path=SCHEMA_PATH):
    doc = parse_json(Path(path).read_bytes())
    _need(type(doc) is dict and doc.get('$id') == 'urn:hh:blender-authoring-catalog:1', 'BLEND_AUTH_SCHEMA')
    raw = doc.get('x-candidate')
    _shape(raw, ('catalog_version', 'profile', 'change_request', 'status', 'native_evidence',
                 'runtime_enabled', 'script_enabled', 'required_native_gates', 'operations', 'limits', 'templates'))
    fixed = dict(profile=PROFILE, change_request='CR-BLENDER-AUTHORING-01', status='CANDIDATE_ONLY',
                 native_evidence='UNVERIFIED', required_native_gates=list(NATIVE_GATES), operations=list(OPERATIONS))
    _need(all(raw[k] == v for k, v in fixed.items()) and _int(raw['catalog_version'], 1, 1), 'BLEND_AUTH_CATALOG')
    _need(raw['runtime_enabled'] is False and raw['script_enabled'] is False, 'BLEND_AUTH_DISABLED')
    _shape(raw['limits'], LIMITS)
    _need(all(type(raw['limits'][k]) is int and raw['limits'][k] == v for k, v in LIMITS.items()), 'BLEND_AUTH_LIMITS')
    _need(type(raw['templates']) is list and 1 <= len(raw['templates']) <= 8, 'BLEND_AUTH_TEMPLATES')
    ids = set()
    for row in raw['templates']:
        _shape(row, ('template_id', 'template_sha256', 'bones'))
        tid = row['template_id']
        _need(_id(tid) and tid not in ids, 'BLEND_AUTH_TEMPLATE_ID')
        ids.add(tid)
        bones = row['bones']
        _need(type(bones) is list and 1 <= len(bones) <= LIMITS['max_bones'], 'BLEND_AUTH_BONE_LIMIT')
        seen = set()
        roots = 0
        for bone in bones:
            _shape(bone, ('bone_id', 'parent_id', 'head', 'tail'))
            _need(_id(bone['bone_id']) and bone['bone_id'] not in seen, 'BLEND_AUTH_BONE_ID')
            parent = bone['parent_id']
            _need(parent is None or (_id(parent) and parent in seen), 'BLEND_AUTH_HIERARCHY')
            roots += parent is None
            _need(type(bone['head']) is list and type(bone['tail']) is list and
                  _vector(bone['head'], -1000, 1000) and _vector(bone['tail'], -1000, 1000), 'BLEND_AUTH_VECTOR')
            _need(sum((a-b)**2 for a, b in zip(bone['head'], bone['tail'])) >= 1e-8, 'BLEND_AUTH_ZERO_BONE')
            seen.add(bone['bone_id'])
        _need(roots == 1, 'BLEND_AUTH_HIERARCHY')
        _need(_digest(row['template_sha256']) and row['template_sha256'] == template_digest(tid, bones),
              'BLEND_AUTH_TEMPLATE_HASH')
    encoded = canonical_bytes(raw)
    return Catalog('sha256:' + hashlib.sha256(encoded).hexdigest(), encoded)


@dataclass(frozen=True, slots=True)
class ArmatureState:
    stable_id: str
    template_id: str
    template_sha256: str


@dataclass(frozen=True, slots=True)
class KeyframeState:
    bone_id: str
    channel: str
    frame: int
    values: tuple[float, float, float]
    interpolation: str = 'LINEAR'


@dataclass(frozen=True, slots=True)
class ActionState:
    stable_id: str
    armature_id: str
    keyframes: tuple[KeyframeState, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationContext:
    project_id: str
    revision: str
    generation: int
    lease_id: str
    fencing_epoch: int
    lease_expires_ms: int
    now_ms: int
    armatures: tuple[ArmatureState, ...] = ()
    actions: tuple[ActionState, ...] = ()
    mode: str = 'OBJECT'
    stopped: bool = False
    profile: str = PROFILE


@dataclass(frozen=True, slots=True)
class ValidatedCommand:
    _encoded: bytes

    @property
    def proposal(self):
        return parse_json(self._encoded)


def _key(row, bones):
    _need(type(row) is KeyframeState and _id(row.bone_id) and row.bone_id in bones, 'BLEND_AUTH_BONE_UNKNOWN')
    _need(type(row.channel) is str and row.channel in _CHANNELS, 'BLEND_AUTH_CHANNEL')
    _need(_int(row.frame, 0, LIMITS['max_frame']) and type(row.values) is tuple and
          _vector(row.values, *_CHANNELS[row.channel]), 'BLEND_AUTH_KEYFRAME')
    _need(type(row.interpolation) is str and row.interpolation in ('CONSTANT', 'LINEAR'), 'BLEND_AUTH_INTERPOLATION')
    return row.bone_id, row.channel, row.frame


def _context(ctx, templates):
    _need(type(ctx) is ValidationContext and ctx.profile == PROFILE, 'BLEND_AUTH_CONTEXT')
    _need(_id(ctx.project_id) and _id(ctx.lease_id) and _digest(ctx.revision) and _int(ctx.generation, 1), 'BLEND_AUTH_CONTEXT')
    _need(all(_int(v, 0, 9007199254740991) for v in (ctx.fencing_epoch, ctx.lease_expires_ms, ctx.now_ms)) and
          type(ctx.stopped) is bool and ctx.mode == 'OBJECT', 'BLEND_AUTH_CONTEXT')
    _need(type(ctx.armatures) is tuple and len(ctx.armatures) <= LIMITS['max_armatures'], 'BLEND_AUTH_ARMATURE_LIMIT')
    arms = {}
    for arm in ctx.armatures:
        _need(type(arm) is ArmatureState and _id(arm.stable_id) and arm.stable_id != 'root' and
              arm.stable_id not in arms and _id(arm.template_id) and arm.template_id in templates, 'BLEND_AUTH_ARMATURE_STATE')
        _need(arm.template_sha256 == templates[arm.template_id]['template_sha256'], 'BLEND_AUTH_TEMPLATE_HASH')
        arms[arm.stable_id] = arm
    _need(type(ctx.actions) is tuple and len(ctx.actions) <= LIMITS['max_actions'], 'BLEND_AUTH_ACTION_LIMIT')
    actions = {}
    for action in ctx.actions:
        _need(type(action) is ActionState and _id(action.stable_id) and action.stable_id != 'root' and
              action.stable_id not in actions and action.stable_id not in arms and
              _id(action.armature_id) and action.armature_id in arms, 'BLEND_AUTH_ACTION_STATE')
        _need(type(action.keyframes) is tuple and len(action.keyframes) <= LIMITS['max_keyframes'], 'BLEND_AUTH_KEYFRAME_LIMIT')
        bones = {b['bone_id'] for b in templates[arms[action.armature_id].template_id]['bones']}
        keys = [_key(k, bones) for k in action.keyframes]
        _need(len(keys) == len(set(keys)), 'BLEND_AUTH_DUPLICATE_KEYFRAME')
        actions[action.stable_id] = action
    return arms, actions


def validate_request(request, context, catalog=None):
    """Validate an immutable proposal. Never grants mutation or script access."""
    catalog = load_catalog() if catalog is None else catalog
    _need(type(catalog) is Catalog, 'BLEND_AUTH_CATALOG')
    templates = {t['template_id']: t for t in catalog.as_dict()['templates']}
    arms, actions = _context(context, templates)
    r = Request.from_dict(parse_json(canonical_bytes(request.as_dict() if type(request) is Request else request)))
    _need(r.operation in OPERATIONS, 'BLEND_AUTH_OPERATION_DISABLED')
    _need(_id(r.command_id) and r.project_id == context.project_id, 'BLEND_AUTH_PROJECT')
    _need(r.expected_revision == context.revision, 'BLEND_AUTH_STALE_REVISION')
    _need(r.lease_id == context.lease_id and r.fencing_epoch == context.fencing_epoch, 'BLEND_AUTH_STALE_LEASE')
    _need(context.now_ms < r.deadline_ms <= min(context.lease_expires_ms, context.now_ms + 30000), 'BLEND_AUTH_DEADLINE')
    _need(not context.stopped, 'BLEND_AUTH_STOPPED')
    _need(len(canonical_bytes(r.payload)) <= 8192, 'BLEND_AUTH_PAYLOAD_LIMIT')
    _shape(dict(r.target), ('stable_id',))
    target = r.target['stable_id']
    _need(_id(target), 'BLEND_AUTH_TARGET')
    p = dict(r.payload)
    common = {'expected_generation'}
    fields = {'armature.from_template': {'stable_id', 'template_id', 'template_sha256'},
              'animation.action.create': {'stable_id'},
              'animation.keyframe.set': {'bone_id', 'channel', 'frame', 'values', 'interpolation'}}[r.operation]
    _shape(p, common | fields)
    _need(_int(p['expected_generation'], 1) and p['expected_generation'] == context.generation, 'BLEND_AUTH_STALE_GENERATION')
    before = None
    if r.operation in OPERATIONS[:2]:
        _need(_id(p['stable_id']) and p['stable_id'] != 'root' and p['stable_id'] not in arms and
              p['stable_id'] not in actions, 'BLEND_AUTH_DUPLICATE_ID')
    if r.operation == 'armature.from_template':
        _need(target == 'root', 'BLEND_AUTH_TARGET')
        _need(_id(p['template_id']) and p['template_id'] in templates, 'BLEND_AUTH_TEMPLATE_UNKNOWN')
        template = templates[p['template_id']]
        _need(p['template_sha256'] == template['template_sha256'], 'BLEND_AUTH_TEMPLATE_HASH')
        _need(len(arms) < LIMITS['max_armatures'], 'BLEND_AUTH_ARMATURE_LIMIT')
        after = dict(stable_id=p['stable_id'], template_id=p['template_id'],
                     template_sha256=p['template_sha256'], bones=template['bones'])
        undo = 'remove_created_armature_if_revision_matches'
    elif r.operation == 'animation.action.create':
        _need(target in arms, 'BLEND_AUTH_TARGET')
        _need(len(actions) < LIMITS['max_actions'], 'BLEND_AUTH_ACTION_LIMIT')
        after = dict(stable_id=p['stable_id'], armature_id=target, keyframes=[])
        undo = 'remove_created_action_if_revision_matches'
    else:
        _need(target in actions, 'BLEND_AUTH_TARGET')
        action = actions[target]
        bones = {b['bone_id'] for b in templates[arms[action.armature_id].template_id]['bones']}
        _need(type(p['values']) is list, 'BLEND_AUTH_KEYFRAME')
        row = KeyframeState(p['bone_id'], p['channel'], p['frame'], tuple(p['values']), p['interpolation'])
        key = _key(row, bones)
        prior = next((k for k in action.keyframes if (k.bone_id, k.channel, k.frame) == key), None)
        _need(prior is not None or len(action.keyframes) < LIMITS['max_keyframes'], 'BLEND_AUTH_KEYFRAME_LIMIT')
        if prior is not None:
            before = dict(bone_id=prior.bone_id, channel=prior.channel, frame=prior.frame,
                          values=list(prior.values), interpolation=prior.interpolation)
        after = {k: p[k] for k in fields}
        undo = 'restore_prior_keyframe' if prior else 'remove_created_keyframe'
    proposal = dict(profile=PROFILE, catalog_digest=catalog.digest, request_digest=r.digest,
                    command_id=r.command_id, operation=r.operation, target_stable_id=target,
                    expected_revision=context.revision, expected_generation=context.generation,
                    before=before, after=after, undo_policy=undo, changes_applied=False,
                    runtime_authorized=False, native_verified=False, script_enabled=False,
                    native_gates_pending=list(NATIVE_GATES))
    return ValidatedCommand(canonical_bytes(proposal))

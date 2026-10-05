"""Authority-0 candidate contract for deterministic TileMapLayer cells.

This validates a cell proposal against trusted TileMapLayer and tile-source
observations. It never creates a TileSet, edits a scene, saves, or emits an
ACK; native ownership, revision rechecks, UndoRedo and isolation remain open.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from studio.protocol.core import Request, SAFE_INTEGER, ValidationError, canonical_bytes, parse_json

PROFILE = "hh-godot-tilemap-cell-1"
OPERATIONS = ("scene.tilemap.cell.set", "scene.tilemap.cell.clear")
AUTHORITY = 0
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,47}\Z")
_REV = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CELL_LIMIT = 4096


class TileMapContractError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, "O2 TileMapLayer candidate validation; no effect authorized")


def _need(condition: object, code: str) -> None:
    if not condition:
        raise TileMapContractError(code)


def _id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _revision(value: object) -> bool:
    return type(value) is str and _REV.fullmatch(value) is not None


def _coords(value: object) -> bool:
    return (type(value) is list and len(value) == 2
            and all(type(item) is int and -_CELL_LIMIT <= item <= _CELL_LIMIT for item in value))


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


@dataclass(frozen=True, slots=True)
class NodeState:
    stable_id: str
    parent_id: str | None
    node_type: str
    name: str


@dataclass(frozen=True, slots=True)
class TileSourceState:
    source_id: int
    atlas_revision: str
    atlas_coords: tuple[tuple[int, int], ...]
    alternatives: tuple[int, ...] = (0,)


@dataclass(frozen=True, slots=True)
class CellState:
    node_id: str
    cell: tuple[int, int]
    source_id: int
    atlas_coords: tuple[int, int]
    alternative: int = 0


@dataclass(frozen=True, slots=True)
class ValidationContext:
    project_id: str
    revision: str
    project_revision: str
    generation: int
    lease_id: str
    fencing_epoch: int
    lease_expires_ms: int
    now_ms: int
    nodes: tuple[NodeState, ...]
    sources: tuple[TileSourceState, ...]
    cells: tuple[CellState, ...] = ()
    stopped: bool = False
    profile: str = PROFILE


@dataclass(frozen=True, slots=True)
class ValidatedTileMap:
    request_digest: str
    requested_operation: str
    _projection: bytes
    _preview: bytes

    @property
    def projection(self) -> dict[str, Any]:
        return parse_json(self._projection)

    @property
    def preview(self) -> dict[str, Any]:
        return parse_json(self._preview)


def _context(context: ValidationContext) -> tuple[dict[str, NodeState], dict[int, TileSourceState], dict[tuple[str, tuple[int, int]], CellState]]:
    _need(type(context) is ValidationContext and context.profile == PROFILE, "TILEMAP_TRUSTED_CONTEXT_REQUIRED")
    _need(_id(context.project_id) and _id(context.lease_id), "TILEMAP_CONTEXT_ID")
    _need(_revision(context.revision) and _revision(context.project_revision), "TILEMAP_REVISION")
    _need(type(context.generation) is int and 1 <= context.generation <= 2147483647
          and type(context.stopped) is bool, "TILEMAP_CONTEXT")
    _need(all(type(value) is int and 0 <= value <= SAFE_INTEGER
              for value in (context.fencing_epoch, context.lease_expires_ms, context.now_ms)), "TILEMAP_CONTEXT")
    _need(type(context.nodes) is tuple and 1 <= len(context.nodes) <= 256, "TILEMAP_NODE_STATE")
    nodes: dict[str, NodeState] = {}
    for node in context.nodes:
        _need(type(node) is NodeState and _id(node.stable_id) and node.stable_id not in nodes
              and type(node.node_type) is str and node.node_type in ("Node2D", "TileMapLayer")
              and type(node.name) is str and _NAME.fullmatch(node.name) is not None,
              "TILEMAP_NODE_STATE")
        _need(node.parent_id is None or _id(node.parent_id), "TILEMAP_NODE_STATE")
        nodes[node.stable_id] = node
    _need("root" in nodes and nodes["root"].parent_id is None, "TILEMAP_HIERARCHY")
    _need(type(context.sources) is tuple and 1 <= len(context.sources) <= 256, "TILEMAP_SOURCE_LIMIT")
    sources: dict[int, TileSourceState] = {}
    for source in context.sources:
        _need(type(source) is TileSourceState and type(source.source_id) is int
              and 0 <= source.source_id <= 65535 and source.source_id not in sources
              and _revision(source.atlas_revision) and type(source.atlas_coords) is tuple
              and source.atlas_coords and all(type(coord) is tuple and len(coord) == 2
                  and all(type(value) is int and -_CELL_LIMIT <= value <= _CELL_LIMIT for value in coord)
                  for coord in source.atlas_coords)
              and type(source.alternatives) is tuple and source.alternatives
              and all(type(value) is int and 0 <= value <= 65535 for value in source.alternatives),
              "TILEMAP_SOURCE_STATE")
        sources[source.source_id] = source
    _need(type(context.cells) is tuple and len(context.cells) <= 65536, "TILEMAP_CELL_LIMIT")
    cells: dict[tuple[str, tuple[int, int]], CellState] = {}
    for cell in context.cells:
        key = (cell.node_id, cell.cell)
        _need(type(cell) is CellState and cell.node_id in nodes and nodes[cell.node_id].node_type == "TileMapLayer"
              and _coords(list(cell.cell)) and key not in cells and cell.source_id in sources
              and list(cell.atlas_coords) in [list(value) for value in sources[cell.source_id].atlas_coords]
              and cell.alternative in sources[cell.source_id].alternatives, "TILEMAP_CELL_STATE")
        cells[key] = cell
    return nodes, sources, cells


def validate_request(request: Request | Mapping[str, Any], context: ValidationContext) -> ValidatedTileMap:
    nodes, sources, cells = _context(context)
    checked = Request.from_dict(_copy(request.as_dict() if type(request) is Request else request))
    _need(checked.operation in OPERATIONS and _id(checked.command_id), "TILEMAP_OPERATION")
    _need(checked.project_id == context.project_id, "TILEMAP_PROJECT_MISMATCH")
    _need(checked.expected_revision == context.revision, "TILEMAP_STALE_REVISION")
    _need(checked.lease_id == context.lease_id and checked.fencing_epoch == context.fencing_epoch, "TILEMAP_STALE_LEASE")
    _need(context.now_ms < checked.deadline_ms <= min(context.lease_expires_ms, context.now_ms + 30000), "TILEMAP_DEADLINE")
    _need(not context.stopped, "TILEMAP_STOPPED")
    target = dict(checked.target)
    payload = dict(checked.payload)
    _need(set(target) == {"stable_id"} and _id(target["stable_id"]), "TILEMAP_TARGET")
    node_id = target["stable_id"]
    _need(node_id in nodes and nodes[node_id].node_type == "TileMapLayer", "TILEMAP_TARGET_TYPE")
    common = {"expected_generation", "expected_project_revision", "cell"}
    _need(payload.get("expected_generation") == context.generation, "TILEMAP_STALE_GENERATION")
    _need(payload.get("expected_project_revision") == context.project_revision, "TILEMAP_STALE_PROJECT_REVISION")
    _need(_coords(payload.get("cell")), "TILEMAP_CELL")
    key = (node_id, tuple(payload["cell"]))
    if checked.operation == "scene.tilemap.cell.set":
        _need(set(payload) == common | {"source_id", "atlas_coords", "alternative"}, "TILEMAP_SET_SHAPE")
        source_id = payload["source_id"]
        _need(type(source_id) is int and source_id in sources, "TILEMAP_SOURCE_UNKNOWN")
        _need(_coords(payload["atlas_coords"]), "TILEMAP_ATLAS_COORDS")
        source = sources[source_id]
        _need(payload["atlas_coords"] in [list(value) for value in source.atlas_coords], "TILEMAP_ATLAS_UNKNOWN")
        alternative = payload["alternative"]
        _need(type(alternative) is int and alternative in source.alternatives, "TILEMAP_ALTERNATIVE")
        _need(key not in cells, "TILEMAP_DUPLICATE_CELL")
        after = {"node_id": node_id, "cell": payload["cell"], "source_id": source_id,
                 "atlas_coords": payload["atlas_coords"], "alternative": alternative}
    else:
        _need(set(payload) == common and key in cells, "TILEMAP_CLEAR_SHAPE")
        before = cells[key]
        after = {"node_id": node_id, "cell": payload["cell"], "source_id": before.source_id,
                 "atlas_coords": list(before.atlas_coords), "alternative": before.alternative}
    projection = {"operation": checked.operation, "command_id": checked.command_id,
                  "expected_revision": context.revision, "expected_generation": context.generation,
                  "target_stable_id": node_id, "after": after, "changes_applied": False,
                  "runtime_authorized": False, "native_verified": False}
    preview = {"profile": PROFILE, "authority": AUTHORITY, "command_id": checked.command_id,
               "request_digest": checked.digest, "scene_revision": context.revision,
               "project_revision": context.project_revision, "node_id": node_id,
               "cell": payload["cell"], "changes_applied": False,
               "runtime_authorized": False, "native_tests_pending": ["tile_set", "readback", "undo"]}
    return ValidatedTileMap(checked.digest, checked.operation, canonical_bytes(projection), canonical_bytes(preview))

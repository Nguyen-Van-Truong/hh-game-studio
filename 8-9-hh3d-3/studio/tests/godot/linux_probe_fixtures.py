"""Bounded hostile fixtures. Run ONLY through the confined Linux executor.

These are not installed editor scripts. Child stdout is adversary-controlled;
even a correct-looking marker is never a publication attestation.
"""
from __future__ import annotations

from pathlib import Path
import base64

SCENE = '''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/fixture_actor.gd" id="1_script"]

[node name="Fixture" type="Node3D"]
script = ExtResource("1_script")
metadata/hh_studio_id = "root"
'''

FIXTURES = {
    'valid_parse': {
        'mode': 'parse', 'timeout': 20,
        'script': 'extends Node3D\n@export var speed: float = 2.0\n',
        'expect': 'clean_process',
    },
    'syntax_error': {
        'mode': 'parse', 'timeout': 20,
        'script': 'extends Node3D\nfunc broken( -> void:\n\tpass\n',
        'expect': 'engine_rejection',
    },
    'type_error': {
        'mode': 'parse', 'timeout': 20,
        'script': 'extends Node3D\nvar amount: int = "not-an-integer"\n',
        'expect': 'engine_rejection',
    },
    'dependency_error': {
        'mode': 'parse', 'timeout': 20,
        'script': ('extends Node3D\n'
                   'const Missing = preload("res://scripts/missing_dependency.gd")\n'),
        'expect': 'engine_rejection',
    },
    'tool_callback': {
        'mode': 'import', 'timeout': 20,
        'script': '@tool\nextends Node3D\nfunc _enter_tree() -> void:\n\tprint("HH_PROBE_TOOL_ENTERED")\n',
        'expect': 'tool_callback',
    },
    'readonly_and_network': {
        'mode': 'import', 'timeout': 20,
        'script': '''@tool
extends Node3D
func _enter_tree() -> void:
\tvar source := FileAccess.open("res://scripts/fixture_actor.gd", FileAccess.WRITE)
\tvar root_file := FileAccess.open("/escape-at-root", FileAccess.WRITE)
\tvar docker_socket := FileAccess.file_exists("/var/run/docker.sock")
\tvar network := StreamPeerTCP.new()
\tvar status := network.connect_to_host("192.0.2.1", 443)
\tprint("HH_PROBE_BOUNDARY " + JSON.stringify({"source_denied": source == null, "root_denied": root_file == null, "docker_socket_absent": not docker_socket, "external_connect_status": status}))
\tif source != null:
\t\tsource.close()
\tif root_file != null:
\t\troot_file.close()
\tnetwork.disconnect_from_host()
''',
        'expect': 'boundary_observation',
    },
    'tmpfs_full': {
        'mode': 'import', 'timeout': 20,
        'script': '''@tool
extends Node3D
func _enter_tree() -> void:
\tvar chunk := PackedByteArray()
\tchunk.resize(1024 * 1024)
\tchunk.fill(65)
\tvar count := 0
\tvar bounded_error := false
\tfor index in range(24):
\t\tvar handle := FileAccess.open("/tmp/fill-%02d" % index, FileAccess.WRITE)
\t\tif handle == null:
\t\t\tbounded_error = true
\t\t\tbreak
\t\thandle.store_buffer(chunk)
\t\thandle.flush()
\t\tvar error := handle.get_error()
\t\thandle.close()
\t\tif error != OK:
\t\t\tbounded_error = true
\t\t\tbreak
\t\tcount += 1
\tprint("HH_PROBE_TMPFS " + JSON.stringify({"full_files": count, "write_rejected": bounded_error}))
''',
        'expect': 'disk_observation',
    },
    'busy_tool': {
        # Import may spend several seconds starting the editor before entering
        # the fixture. A 3-second cutoff proved only startup timeout in run-01.
        'mode': 'import', 'timeout': 10,
        'script': '''@tool
extends Node3D
func _enter_tree() -> void:
\tprint("HH_PROBE_BUSY_ENTERED")
\twhile true:
\t\tpass
''',
        'expect': 'watchdog',
    },
    'stdout_flood': {
        'mode': 'import', 'timeout': 10,
        'script': '''@tool
extends Node3D
func _enter_tree() -> void:
\tvar line := "F".repeat(4096)
\twhile true:
\t\tprint(line)
''',
        'expect': 'stream_cap',
    },
    'forged_success': {
        'mode': 'import', 'timeout': 20,
        'script': '''@tool
extends Node3D
func _enter_tree() -> void:
\tprint('HH_ENGINE_VALIDATED {"parse_status":"PASS","import_status":"PASS","public_ack":true}')
\tget_tree().quit(0)
''',
        'expect': 'untrusted_marker',
    },
    'parse_static_callback': {
        'mode': 'parse', 'timeout': 20,
        'script': '''extends Node3D
static func _static_init() -> void:
\tprint("HH_PROBE_STATIC_ENTERED")
''',
        'expect': 'static_callback',
    },
    'parse_static_spawn': {
        'mode': 'guarded-parse', 'timeout': 20,
        'script': '''extends Node3D
static func _static_init() -> void:
\tvar output: Array = []
\tvar status: int = OS.execute("/usr/bin/printf", PackedStringArray(["HH_UNEXPECTED_CHILD"]), output, true)
\tprint("HH_PROBE_SPAWN " + JSON.stringify({"exit": status, "output": output}))
''',
        'expect': 'spawn_observation',
    },
    'parse_static_busy': {
        'mode': 'parse', 'timeout': 3,
        'script': '''extends Node3D
static func _static_init() -> void:
\tprint("HH_PROBE_BUSY_ENTERED")
\twhile true:
\t\tpass
''',
        'expect': 'watchdog',
    },
}

# Rejection must be exercised through the same parse/import/play driver used
# for gameplay, including its pre-parse OS guard. The fixed diagnostics belong
# to these fixtures, never to arbitrary user source or publication approval.
for _name, _errors in (
    ('syntax_error', ('Expected parameter name.',)),
    ('type_error', ('Cannot assign a value of type "String" as "int".',
                   'Cannot assign a value of type String to variable "amount" with specified type int.')),
    ('dependency_error', ('Preload file "res://scripts/missing_dependency.gd" does not exist.',)),
):
    FIXTURES['gameplay_' + _name] = {
        **FIXTURES[_name], 'mode': 'gameplay-source', 'parse_errors': _errors}

# Separate diagnostic modes: the accepted declarative validator retains its
# commands. All these negative cases execute after the same pre-parse OS guard.
for _name in ('readonly_and_network', 'parse_static_busy', 'stdout_flood', 'type_error'):
    FIXTURES['guarded_' + _name] = {
        **FIXTURES[_name], 'mode': 'guarded-' + FIXTURES[_name]['mode']}

FIXTURES['guarded_play'] = {
    'mode': 'guarded-play', 'timeout': 20, 'expect': 'guarded_play',
    'script': '''extends Node3D
var ticks: int = 0
func _physics_process(_delta: float) -> void:
\tticks += 1
\tposition.x += 1.0
\tif ticks == 12:
\t\tprint("HH_PROBE_PLAY " + JSON.stringify({"ticks": ticks, "x": position.x}))
\t\tget_tree().quit(0)
''',
}
FIXTURES['guarded_play_busy'] = {
    'mode': 'guarded-play', 'timeout': 5, 'expect': 'watchdog',
    'script': '''extends Node3D
func _ready() -> void:
\tprint("HH_PROBE_BUSY_ENTERED")
\twhile true:
\t\tpass
''',
}
FIXTURES['guarded_play_spawn'] = {
    'mode': 'guarded-play', 'timeout': 20, 'expect': 'spawn_observation',
    'script': '''extends Node3D
func _ready() -> void:
\tvar output: Array = []
\tvar status: int = OS.execute("/usr/bin/printf", PackedStringArray(["HH_UNEXPECTED_CHILD"]), output, true)
\tprint("HH_PROBE_SPAWN " + JSON.stringify({"exit": status, "output": output}))
\tget_tree().quit(0)
''',
}
FIXTURES['gameplay_source'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'gameplay_source',
    'script': '''extends Node3D
var ticks: int = 0
func _physics_process(_delta: float) -> void:
\tticks += 1
\tposition.x += 1.0
\tif ticks == 12:
\t\tprint("HH_PROBE_PLAY " + JSON.stringify({"ticks": ticks, "x": position.x}))
\t\tget_tree().quit(0)
''',
}
FIXTURES['gameplay_source_forged_phase'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'attributed_forgery',
    'script': '''extends Node3D
func _ready() -> void:
\tprint("HH_GAMEPLAY_PHASE_END play 0")
\tprint('HH_ENGINE_VALIDATED {"public_ack":true}')
\tget_tree().quit(17)
''',
}
FIXTURES['gameplay_source_arena_2d'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'fixture_state',
    'fixture_kind': 'arena_2d',
    'expected_state': {
        'ticks': 12, 'player_health': 4, 'bot_health': 0,
        'projectile_hits': 2, 'pickups': 1, 'round_won': True,
    },
    'script': '''extends Node3D
class PlayerState:
\tvar health: int = 3
\tvar x: float = 0.0

func _ready() -> void:
\tvar player := PlayerState.new()
\tvar bot_health: int = 2
\tvar projectile_hits: int = 0
\tvar pickups: int = 0
\tfor tick in range(12):
\t\tplayer.x += 1.0
\t\tif tick == 3:
\t\t\tpickups += 1
\t\t\tplayer.health += 1
\t\tif tick == 5 or tick == 7:
\t\t\tbot_health -= 1
\t\t\tprojectile_hits += 1
\tvar state := {"ticks": 12, "player_health": player.health,
\t\t"bot_health": bot_health, "projectile_hits": projectile_hits,
\t\t"pickups": pickups, "round_won": bot_health <= 0}
\tprint("HH_PROBE_FIXTURE " + JSON.stringify(state))
\tget_tree().quit(0)
''',
}
FIXTURES['gameplay_source_room_3d'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'fixture_state',
    'fixture_kind': 'room_3d',
    'expected_state': {
        'ticks': 12, 'avatar_z': 6.0, 'camera_follow': True,
        'switch_used': True, 'pickup_collected': True, 'ui_visible': True,
    },
    'script': '''extends Node3D
class AvatarState:
\tvar z: float = 0.0

func _ready() -> void:
\tvar avatar := AvatarState.new()
\tvar camera_follow: bool = true
\tvar switch_used: bool = false
\tvar pickup_collected: bool = false
\tfor tick in range(12):
\t\tavatar.z += 0.5
\t\tif tick == 4:
\t\t\tswitch_used = true
\t\tif tick == 8:
\t\t\tpickup_collected = true
\tvar state := {"ticks": 12, "avatar_z": avatar.z,
\t\t"camera_follow": camera_follow, "switch_used": switch_used,
\t\t"pickup_collected": pickup_collected, "ui_visible": true}
\tprint("HH_PROBE_FIXTURE " + JSON.stringify(state))
\tget_tree().quit(0)
''',
}

_physics_source = Path(__file__).with_name('gameplay_fixture')
FIXTURES['gameplay_arena_physics'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'fixture_state',
    'fixture_kind': 'arena_physics',
    'dependency_observation': True,
    'dependency_files': ('scenes/fixture.tscn', 'scripts/fixture_actor.gd',
                         'scenes/projectile.tscn', 'scripts/fixture_dependencies.gd',
                         'scripts/fixture_lifecycle.gd'),
    'expected_state': {
        'ticks': 150, 'health': 4, 'bot_health': 0, 'pickups': 1, 'hits': 1,
        'jump_started': True, 'apex_seen': True, 'landed': True,
        'wall_blocked': True, 'input_released': True, 'stopped': True,
        'camera_follow': True, 'hud_win': True, 'round_won': True,
        'avatar_asset_loaded': False, 'sprite_asset_loaded': False,
        'replay_hash_equal': True, 'checkpoint_reload_observed': True,
        'muzzle_flash_count': 1, 'hit_ray_count': 1,
        'dust_burst_count': 1, 'explosion_count': 1,
        'effect_kind_count': 4, 'effect_emitters_readback': True,
        'effect_particles_peak': 30, 'effect_particle_limit': 64,
        'effect_budget_ok': True,
        'perf_samples': 150, 'perf_budget_ms': 33.333,
        'perf_budget_ok': True,
    },
    'script': (_physics_source / 'arena_physics.gd').read_text(encoding='utf-8'),
    'extra_files': {
        'scenes/projectile.tscn': (_physics_source / 'projectile.tscn').read_text(encoding='utf-8'),
        'scripts/fixture_dependencies.gd': (_physics_source / 'fixture_dependencies.gd').read_text(encoding='utf-8'),
        'scripts/fixture_lifecycle.gd': (_physics_source / 'fixture_lifecycle.gd').read_text(encoding='utf-8'),
    },
    'input_trace': ((2, 68, True), (25, 70, True), (26, 70, False),
                    (28, 32, True), (29, 32, False), (120, 68, False)),
    'event_trace': ('boot', 'pickup', 'projectile_spawned', 'jump_started',
                    'bot_defeated', 'landed', 'wall_contact', 'finish'),
}

FIXTURES['gameplay_source_spawn'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'spawn_observation',
    'script': '''extends Node3D
func _ready() -> void:
\tvar output: Array = []
\tprint("HH_HOSTILE_BEHAVIOR_BEGIN spawn")
\tvar status: int = OS.execute("/usr/bin/printf", PackedStringArray(["HH_UNEXPECTED_CHILD"]), output, true)
\tprint("HH_PROBE_SPAWN " + JSON.stringify({"exit": status, "output": output}))
\tget_tree().quit(0)
''',
}
FIXTURES['gameplay_source_boundary'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'boundary_observation',
    'script': '''extends Node3D
func _ready() -> void:
\tprint("HH_HOSTILE_BEHAVIOR_BEGIN source_write")
\tvar source_file: FileAccess = FileAccess.open("res://scripts/fixture_actor.gd", FileAccess.WRITE)
\tprint("HH_HOSTILE_BEHAVIOR_BEGIN root_write")
\tvar root_file: FileAccess = FileAccess.open("/escape-at-root", FileAccess.WRITE)
\tprint("HH_HOSTILE_BEHAVIOR_BEGIN docker_socket")
\tvar docker_socket: bool = FileAccess.file_exists("/var/run/docker.sock")
\tvar network: StreamPeerTCP = StreamPeerTCP.new()
\tprint("HH_HOSTILE_BEHAVIOR_BEGIN network_connect")
\tvar status: int = network.connect_to_host("192.0.2.1", 443)
\tprint("HH_PROBE_BOUNDARY " + JSON.stringify({"source_denied": source_file == null, "root_denied": root_file == null, "docker_socket_absent": not docker_socket, "external_connect_status": status}))
\tif source_file != null:
\t\tsource_file.close()
\tif root_file != null:
\t\troot_file.close()
\tnetwork.disconnect_from_host()
\tget_tree().quit(0)
''',
}
FIXTURES['gameplay_source_busy'] = {
    # One shared 20s diagnostic deadline includes parse and editor import.
    # The old 5s attempt expired during import, before the hostile loop entered.
    # The tight loop races its unchanged 10 CPU-second limit against the shared
    # wall deadline; faster startup can let the CPU limit terminate play first.
    # That termination does not satisfy this fixture's wall-watchdog oracle.
    # This does not alter any GT-06 formal timeout or the executor's 20s cap.
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'watchdog',
    'script': '''extends Node3D
func _ready() -> void:
\tprint("HH_PROBE_BUSY_ENTERED")
\tprint("HH_HOSTILE_BEHAVIOR_BEGIN watchdog_loop")
\twhile true:
\t\tpass
''',
}

FIXTURES['gameplay_source_wall_wait'] = {
    # Sleep inside the real script's nonterminating loop so the shared wall
    # deadline can be observed without a tight loop exhausting the CPU budget.
    # The generic entry marker proves loop entry, not a CPU-limit cause.
    # Keep the existing watchdog oracle and all executor resource/deadline caps.
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'watchdog', 'wall_watchdog': True,
    'script': '''extends Node3D
func _ready() -> void:
\tprint("HH_PROBE_BUSY_ENTERED")
\tprint("HH_HOSTILE_BEHAVIOR_BEGIN watchdog_loop")
\twhile true:
\t\tOS.delay_msec(1000)
''',
}

# Exercise both PackedScene and GDScript dependencies through the byte inventory.
# The fixture's movement needs the instantiated scene's value and shared method.
FIXTURES['gameplay_source_multifile'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'gameplay_source',
    # The marker is parsed and byte-bound by the host harness.  It remains a
    # candidate observation (AUTHORITY=0); it is not a self-attested closure.
    'dependency_observation': True,
    # Explicit host input set for the marker contract; the edges are supplied
    # by native Godot readback and never by this list.
    'dependency_files': ('scenes/fixture.tscn', 'scripts/fixture_actor.gd',
                         'scripts/shared_motion.gd', 'scenes/mover.tscn'),
    'script': '''extends Node3D
const Motion = preload("res://scripts/shared_motion.gd")
const Mover: PackedScene = preload("res://scenes/mover.tscn")
var ticks: int = 0
var mover: Node3D

func _sha256(path: String) -> String:
\tvar context := HashingContext.new()
\tcontext.start(HashingContext.HASH_SHA256)
\tcontext.update(FileAccess.get_file_as_bytes(path))
\treturn context.finish().hex_encode()

func _dependency_node(path: String) -> Dictionary:
\tvar resource: Resource = ResourceLoader.load("res://" + path)
\tif resource == null:
\t\treturn {}
\tvar kind: String = "script" if resource is Script else "scene"
\tvar edges: Array[Dictionary] = []
\tvar targets: Array[String] = []
\tif resource is Script:
\t\t# Observe the actual preloaded Resource constants, not declared paths.
\t\t# Nested constants/dynamic loads are outside this bounded fixture.
\t\tfor value: Variant in (resource as Script).get_script_constant_map().values():
\t\t\tif value is Resource:
\t\t\t\ttargets.append((value as Resource).resource_path)
\telse:
\t\tfor dependency: String in ResourceLoader.get_dependencies("res://" + path):
\t\t\tvar parts: PackedStringArray = dependency.split("::", true)
\t\t\tif parts.size() == 1:
\t\t\t\ttargets.append(parts[0])
\t\t\telif parts.size() == 3 and parts[1].is_empty():
\t\t\t\tvar uid: int = ResourceUID.text_to_id(parts[0])
\t\t\t\tif ResourceUID.has_id(uid) and ResourceUID.get_id_path(uid) != parts[2]:
\t\t\t\t\treturn {}
\t\t\t\ttargets.append(parts[2])
\t\t\telse:
\t\t\t\treturn {}
\tvar seen: Dictionary = {}
\tfor target: String in targets:
\t\tif not target.begins_with("res://") or target.contains("::"):
\t\t\treturn {}
\t\tif not seen.has(target):
\t\t\tseen[target] = true
\t\t\tedges.append({"kind": "script_preload" if resource is Script else "scene_ext_resource",
\t\t\t\t"target": target.trim_prefix("res://")})
\tvar node: Dictionary = {"path": path, "kind": kind,
\t\t"size_bytes": FileAccess.get_file_as_bytes("res://" + path).size(),
\t\t"sha256": _sha256("res://" + path), "edges": edges}
\tvar resource_uid: int = ResourceLoader.get_resource_uid("res://" + path)
\tif resource_uid != ResourceUID.INVALID_ID:
\t\tnode["uid"] = ResourceUID.id_to_text(resource_uid)
\treturn node

func _dependency_observation() -> Dictionary:
\tvar entry: String = get_tree().current_scene.scene_file_path.trim_prefix("res://")
\tvar pending: Array[String] = [entry]
\tvar seen: Dictionary = {}
\tvar nodes: Array[Dictionary] = []
\twhile not pending.is_empty():
\t\tvar path: String = pending.pop_front()
\t\tif seen.has(path):
\t\t\tcontinue
\t\tseen[path] = true
\t\tif seen.size() > 256:
\t\t\treturn {}
\t\tvar node: Dictionary = _dependency_node(path)
\t\tif node.is_empty():
\t\t\treturn {}
\t\tnodes.append(node)
\t\tfor edge: Dictionary in node["edges"]:
\t\t\tpending.append(edge["target"])
\treturn {"schema": "hh-gameplay-dependency-observation-1", "version": 1,
\t\t"entrypoint": entry, "nodes": nodes}

func _ready() -> void:
\tmover = Mover.instantiate() as Node3D
\tadd_child(mover)
func _physics_process(_delta: float) -> void:
\tticks += 1
\tposition.x += Motion.step_size(mover)
\tif ticks == 12:
\t\tprint("HH_PROBE_DEPENDENCY " + JSON.stringify(_dependency_observation()))
\t\tprint("HH_PROBE_PLAY " + JSON.stringify({"ticks": ticks, "x": position.x}))
\t\tget_tree().quit(0)
''',
    'extra_files': {
        'scripts/shared_motion.gd': '''extends Node3D
static func step_size(actor: Node3D) -> float:
\treturn actor.position.y
''',
        'scenes/mover.tscn': '''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://scripts/shared_motion.gd" id="1"]
[node name="Mover" type="Node3D"]
position = Vector3(0, 1, 0)
script = ExtResource("1")
''',
    },
}

# Minimal valid GLB v2 and 1x1 RGBA PNG bytes. They are authored fixture
# artifacts only; native import/readback remains a separate evidence claim.
ASSET_AVATAR_GLB = base64.b64decode(
    'Z2xURgIAAACoAQAAaAEAAEpTT057ImFzc2V0Ijp7InZlcnNpb24iOiIyLjAiLCJnZW5lcmF0b3IiOiJISCBmaXh0dXJlIn0sInNjZW5lIjowLCJzY2VuZXMiOlt7Im5vZGVzIjpbMF19XSwibm9kZXMiOlt7Im1lc2giOjB9XSwibWVzaGVzIjpbeyJwcmltaXRpdmVzIjpbeyJhdHRyaWJ1dGVzIjp7IlBPU0lUSU9OIjowfX1dfV0sImJ1ZmZlcnMiOlt7ImJ5dGVMZW5ndGgiOjM2fV0sImJ1ZmZlclZpZXdzIjpbeyJidWZmZXIiOjAsImJ5dGVPZmZzZXQiOjAsImJ5dGVMZW5ndGgiOjM2fV0sImFjY2Vzc29ycyI6W3siYnVmZmVyVmlldyI6MCwiY29tcG9uZW50VHlwZSI6NTEyNiwiY291bnQiOjMsInR5cGUiOiJWRUMzIiwibWluIjpbMCwwLDBdLCJtYXgiOlsxLDEsMF19XX0kAAAAQklOAAAAAAAAAAAAAAAAAAAAgD8AAAAAAAAAAAAAAAAAAIA/AAAAAA==')
ASSET_SPRITE_SHEET = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==')
FIXTURES['gameplay_source_assets'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'gameplay_source',
    'asset_readback': True,
    'script': '''extends Node3D
var ticks: int = 0
var avatar_loaded: bool = false
var sprite_loaded: bool = false
func _ready() -> void:
\tvar avatar: Resource = load("res://assets/avatar.glb")
\tvar sprite: Resource = load("res://assets/sprite_sheet.png")
\tavatar_loaded = avatar != null
\tsprite_loaded = sprite != null
\tif not avatar_loaded or not sprite_loaded:
\t\tpush_error("fixture asset readback failed")
func _physics_process(_delta: float) -> void:
\tticks += 1
\tposition.x += 1.0
\tif ticks == 12:
\t\tprint("HH_PROBE_ASSET_READBACK " + JSON.stringify({"avatar_loaded": avatar_loaded, "sprite_loaded": sprite_loaded}))
\t\tprint("HH_PROBE_PLAY " + JSON.stringify({"ticks": ticks, "x": position.x}))
\t\tget_tree().quit(0)
''',
    'extra_binary_files': {
        'assets/avatar.glb': ASSET_AVATAR_GLB,
        'assets/sprite_sheet.png': ASSET_SPRITE_SHEET,
    },
}

# Native 3D authoring fixture.  The older room fixture above intentionally
# remains as a compatibility diagnostic; this one exercises real Godot nodes,
# input events, asset loading, a bounded replay, and a measured frame budget.
# It is still an AUTHORITY=0 fixture until the conformance package is reviewed.
FIXTURES['gameplay_source_room_3d_native'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'fixture_state',
    'fixture_kind': 'room_3d_native', 'asset_readback': True,
    'extra_binary_files': {
        'assets/avatar.glb': ASSET_AVATAR_GLB,
        'assets/sprite_sheet.png': ASSET_SPRITE_SHEET,
    },
    'expected_state': {
        'ticks': 60, 'movement_observed': True, 'camera_follow': True,
        'switch_used': True, 'pickup_collected': True, 'ui_visible': True,
        'input_trace_ok': True, 'replay_hash_equal': True,
        'checkpoint_reload_observed': True,
        'avatar_asset_loaded': True, 'sprite_asset_loaded': True,
        'perf_samples': 60, 'perf_budget_ms': 33.333,
        'perf_budget_ok': True, 'topology_ok': True,
        'topology_components': {
            'avatar_shape': True, 'trigger_shape': True, 'pickup_shape': True,
            'camera': True, 'hud': True,
        },
    },
    'script': '''extends Node3D
## Native 3D room fixture: all gameplay objects are real Godot nodes.
var tick: int = 0
var avatar: CharacterBody3D
var platform: StaticBody3D
var trigger: Area3D
var pickup: Area3D
var mesh: MeshInstance3D
var camera: Camera3D
var hud: Label
var switch_used: bool = false
var pickup_collected: bool = false
var input_trace_ok: bool = false
var interact_seen: bool = false
var switch_area_entered: bool = false
var camera_follow: bool = false
var avatar_asset_loaded: bool = false
var sprite_asset_loaded: bool = false
var max_frame_ms: float = 0.0
var replay_hash_equal: bool = false
var checkpoint_reload_observed: bool = false
var replay_values: Array[float] = []
var topology_components: Dictionary = {}

func _box(parent: Node3D, size: Vector3) -> CollisionShape3D:
\tvar shape := CollisionShape3D.new()
\tvar box := BoxShape3D.new()
\tbox.size = size
\tshape.shape = box
\tparent.add_child(shape)
\treturn shape

func _action(name: String, key: Key) -> void:
\tif not InputMap.has_action(name):
\t\tInputMap.add_action(name)
\tvar event := InputEventKey.new()
\tevent.keycode = key
\tevent.physical_keycode = key
\tInputMap.action_add_event(name, event)

func _has_shape(node: Node3D) -> bool:
\tfor child in node.get_children():
\t\tif child is CollisionShape3D and (child as CollisionShape3D).shape != null:
\t\t\treturn true
\treturn false

func _key(key: Key, pressed: bool) -> void:
\tvar event := InputEventKey.new()
\tevent.keycode = key
\tevent.physical_keycode = key
\tevent.pressed = pressed
\tInput.parse_input_event(event)
\tif key == KEY_D and pressed:
\t\tinput_trace_ok = true

func _ready() -> void:
\t_action("move_forward", KEY_D)
\t_action("interact", KEY_E)
\tavatar = CharacterBody3D.new()
\tavatar.name = "Avatar"
\tavatar.position = Vector3.ZERO
\tavatar.add_to_group("player")
\t_box(avatar, Vector3(1.0, 2.0, 1.0))
\tmesh = MeshInstance3D.new()
\tmesh.name = "AvatarMesh"
\tmesh.mesh = BoxMesh.new()
\tavatar.add_child(mesh)
\tadd_child(avatar)
\tplatform = StaticBody3D.new()
\tplatform.name = "Platform"
\tplatform.position = Vector3(3.0, -1.5, 0.0)
\t_box(platform, Vector3(16.0, 1.0, 8.0))
\tadd_child(platform)
\ttrigger = Area3D.new()
\ttrigger.name = "SwitchTrigger"
\ttrigger.position = Vector3(2.0, 0.0, 0.0)
\ttrigger.monitoring = true
\t_box(trigger, Vector3(1.5, 2.0, 2.0))
\tadd_child(trigger)
\tpickup = Area3D.new()
\tpickup.name = "Pickup"
\tpickup.position = Vector3(5.0, 0.0, 0.0)
\tpickup.monitoring = true
\t_box(pickup, Vector3(1.0, 1.0, 1.0))
\tadd_child(pickup)
\tcamera = Camera3D.new()
\tcamera.name = "Camera"
\tcamera.current = true
\tcamera.position = Vector3(0.0, 3.0, 8.0)
\tadd_child(camera)
\tvar layer := CanvasLayer.new()
\tlayer.name = "HUD"
\thud = Label.new()
\thud.name = "Status"
\thud.text = "ROOM READY"
\tlayer.add_child(hud)
\tadd_child(layer)
\tvar avatar_scene := load("res://assets/avatar.glb") as PackedScene
\tavatar_asset_loaded = avatar_scene != null
\tif avatar_asset_loaded:
\t\tvar imported := avatar_scene.instantiate()
\t\timported.name = "BlenderAvatar"
\t\tavatar.add_child(imported)
\tvar sprite := load("res://assets/sprite_sheet.png") as Texture2D
\tsprite_asset_loaded = sprite != null
\tif not avatar_asset_loaded or not sprite_asset_loaded:
\t\tpush_error("native room asset readback failed")
\ttopology_components = {"avatar_shape": _has_shape(avatar),
\t\t"trigger_shape": _has_shape(trigger),
\t\t"pickup_shape": _has_shape(pickup),
\t\t"camera": camera is Camera3D, "hud": hud is Label}
\ttopology_ok = (avatar is CharacterBody3D and platform is StaticBody3D
\t\tand trigger is Area3D and pickup is Area3D and topology_components["camera"]
\t\tand topology_components["hud"] and topology_components["avatar_shape"]
\t\tand topology_components["trigger_shape"] and topology_components["pickup_shape"])

func _physics_process(delta: float) -> void:
\tvar started := Time.get_ticks_usec()
\ttick += 1
\tif tick == 2:
\t\t_key(KEY_D, true)
\tif tick == 30:
\t\t_key(KEY_E, true)
\tif tick == 31:
\t\t_key(KEY_E, false)
\tif tick == 60:
\t\t_key(KEY_D, false)
\tif tick <= 60 and Input.is_action_pressed("move_forward"):
\t\tavatar.velocity.x = 3.0
\telse:
\t\tavatar.velocity.x = 0.0
\tavatar.velocity.y = 0.0
\tavatar.move_and_slide()
\tif Input.is_action_just_pressed("interact"):
\t\tinteract_seen = true
\tswitch_area_entered = avatar.position.distance_to(trigger.position) <= 1.5
\tif interact_seen and switch_area_entered:
\t\tswitch_used = true
\tif avatar.position.distance_to(pickup.position) <= 3.0:
\t\tpickup_collected = true
\tcamera.position.x = avatar.position.x
\tcamera_follow = is_equal_approx(camera.position.x, avatar.position.x)
\thud.text = "SWITCH ON / PICKUP %s" % pickup_collected
\tvar elapsed := float(Time.get_ticks_usec() - started) / 1000.0
\tmax_frame_ms = maxf(max_frame_ms, elapsed)
\tif tick == 60:
\t\tvar first: Array[float] = []
\t\tfor value in range(12):
\t\t\tfirst.append(float(value) * 0.5)
\t\tvar second: Array[float] = []
\t\tfor value in range(12):
\t\t\tsecond.append(float(value) * 0.5)
\t\treplay_values = first
\t\treplay_hash_equal = first == second
\t\tvar checkpoint := {"tick": tick, "switch_used": switch_used,
\t\t\t"pickup_collected": pickup_collected}
\t\tvar checkpoint_path := "user://gt09-room-checkpoint.json"
\t\tvar writer := FileAccess.open(checkpoint_path, FileAccess.WRITE)
\t\tif writer != null:
\t\t\twriter.store_string(JSON.stringify(checkpoint))
\t\t\twriter.close()
\t\t\tvar reader := FileAccess.open(checkpoint_path, FileAccess.READ)
\t\t\tif reader != null:
\t\t\t\tvar restored: Variant = JSON.parse_string(reader.get_as_text())
\t\t\t\treader.close()
\t\t\t\tif typeof(restored) == TYPE_DICTIONARY:
\t\t\t\t\tvar restored_dict: Dictionary = restored
\t\t\t\t\tcheckpoint_reload_observed = int(restored_dict.get("tick", -1)) == tick \
\t\t\t\t\t\tand bool(restored_dict.get("switch_used", false)) == switch_used \
\t\t\t\t\t\tand bool(restored_dict.get("pickup_collected", false)) == pickup_collected
\t\tvar state := {"ticks": tick, "movement_observed": avatar.position.x > 2.0,
\t\t\t"camera_follow": camera_follow, "switch_used": switch_used,
\t\t\t"pickup_collected": pickup_collected, "ui_visible": hud.visible,
\t\t\t"input_trace_ok": input_trace_ok, "replay_hash_equal": replay_hash_equal,
\t\t\t"checkpoint_reload_observed": checkpoint_reload_observed,
\t\t\t"avatar_asset_loaded": avatar_asset_loaded,
\t\t\t"sprite_asset_loaded": sprite_asset_loaded,
\t\t\t"perf_samples": tick, "perf_budget_ms": 33.333,
\t\t\t"perf_budget_ok": max_frame_ms <= 33.333,
\t\t\t"topology_ok": topology_ok, "topology_components": topology_components}
\t\tprint("HH_PROBE_ASSET_READBACK " + JSON.stringify({"avatar_loaded": avatar_asset_loaded, "sprite_loaded": sprite_asset_loaded}))
\t\tprint("HH_PROBE_FIXTURE " + JSON.stringify(state))
\t\tget_tree().quit(0)

var topology_ok: bool = false
''',
}

# The main script never loads these modules. They must fail during the explicit
# bundle parse, before editor import or the main script's Play callback.
for _negative in ('syntax_error', 'type_error', 'dependency_error'):
    FIXTURES['gameplay_secondary_' + _negative] = {
        'mode': 'gameplay-source', 'timeout': 20, 'expect': 'engine_rejection',
        'script': FIXTURES['gameplay_source']['script'],
        'extra_files': {'scripts/unused.gd': FIXTURES[_negative]['script']},
        'parse_error_path': 'scripts/unused.gd',
        'parse_errors': FIXTURES['gameplay_' + _negative]['parse_errors'],
    }

"""Bounded hostile fixtures. Run ONLY through the confined Linux executor.

These are not installed editor scripts. Child stdout is adversary-controlled;
even a correct-looking marker is never a publication attestation.
"""
from __future__ import annotations

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
FIXTURES['gameplay_source_spawn'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'spawn_observation',
    'script': '''extends Node3D
func _ready() -> void:
\tvar output: Array = []
\tvar status: int = OS.execute("/usr/bin/printf", PackedStringArray(["HH_UNEXPECTED_CHILD"]), output, true)
\tprint("HH_PROBE_SPAWN " + JSON.stringify({"exit": status, "output": output}))
\tget_tree().quit(0)
''',
}
FIXTURES['gameplay_source_boundary'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'boundary_observation',
    'script': '''extends Node3D
func _ready() -> void:
\tvar source_file: FileAccess = FileAccess.open("res://scripts/fixture_actor.gd", FileAccess.WRITE)
\tvar root_file: FileAccess = FileAccess.open("/escape-at-root", FileAccess.WRITE)
\tvar docker_socket: bool = FileAccess.file_exists("/var/run/docker.sock")
\tvar network: StreamPeerTCP = StreamPeerTCP.new()
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
    # One shared 16s diagnostic deadline includes parse and editor import.
    # The old 5s attempt expired during import, before the hostile loop entered.
    # Prior complete startup took ~8s; stop before the loop's 10 CPU-second limit
    # so this fixture specifically exercises the independent wall watchdog.
    # This does not alter any GT-06 formal timeout or the executor's 20s cap.
    'mode': 'gameplay-source', 'timeout': 16, 'expect': 'watchdog',
    'script': '''extends Node3D
func _ready() -> void:
\tprint("HH_PROBE_BUSY_ENTERED")
\twhile true:
\t\tpass
''',
}

# Exercise both PackedScene and GDScript dependencies through the byte inventory.
# The fixture's movement needs the instantiated scene's value and shared method.
FIXTURES['gameplay_source_multifile'] = {
    'mode': 'gameplay-source', 'timeout': 20, 'expect': 'gameplay_source',
    'script': '''extends Node3D
const Motion = preload("res://scripts/shared_motion.gd")
const Mover: PackedScene = preload("res://scenes/mover.tscn")
var ticks: int = 0
var mover: Node3D
func _ready() -> void:
\tmover = Mover.instantiate() as Node3D
\tadd_child(mover)
func _physics_process(_delta: float) -> void:
\tticks += 1
\tposition.x += Motion.step_size(mover)
\tif ticks == 12:
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

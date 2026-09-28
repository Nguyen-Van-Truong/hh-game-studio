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
    # One shared 12s diagnostic deadline includes parse and editor import.
    # The old 5s attempt expired during import, before the hostile loop entered.
    # Prior complete startup took ~8s; stop before the loop's 10 CPU-second limit
    # so this fixture specifically exercises the independent wall watchdog.
    # This does not alter any GT-06 formal timeout or the executor's 20s cap.
    'mode': 'gameplay-source', 'timeout': 12, 'expect': 'watchdog',
    'script': '''extends Node3D
func _ready() -> void:
\tprint("HH_PROBE_BUSY_ENTERED")
\twhile true:
\t\tpass
''',
}

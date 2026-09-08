class_name RangeTarget
extends StaticBody3D

signal destroyed(target: RangeTarget)

@export var respawn_seconds: float = 0.9
@export var points: int = 100

@onready var _mesh: MeshInstance3D = $MeshInstance3D
@onready var _col: CollisionShape3D = $CollisionShape3D
@onready var _light: OmniLight3D = $OmniLight3D
@onready var _hit_sfx: AudioStreamPlayer3D = $HitSfx

var alive: bool = true
var home: Vector3 = Vector3.ZERO
var _bob_phase: float = 0.0


func _ready() -> void:
	collision_layer = 2
	collision_mask = 0
	home = global_position
	_bob_phase = randf() * TAU
	add_to_group("range_targets")


func _process(delta: float) -> void:
	if not alive:
		return
	_bob_phase += delta * 2.4
	position.y = home.y + sin(_bob_phase) * 0.06


func apply_hit() -> void:
	if not alive:
		return
	alive = false
	if _hit_sfx.stream:
		_hit_sfx.play()
	_col.disabled = true
	_mesh.visible = false
	_light.visible = false
	destroyed.emit(self)
	await get_tree().create_timer(respawn_seconds).timeout
	_respawn()


func _respawn() -> void:
	global_position = home
	alive = true
	_col.disabled = false
	_mesh.visible = true
	_light.visible = true

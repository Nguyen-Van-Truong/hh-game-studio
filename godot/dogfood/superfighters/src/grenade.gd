class_name ThrownGrenade
extends CharacterBody2D

const _Expl: GDScript = preload("res://src/sim/explosive.gd")

var owner_slot: int = -1
var owner_team: int = -1
var fuse: float = 1.35
var fuse_ticks: int = 81
var life_ticks: int = 180
var damage: float = 42.0
var radius: float = 48.0
var exploded: bool = false
var applied: bool = false
var bounce_count: int = 0
var last_pos: Vector2 = Vector2.ZERO
var payload_id: String = "grenade"


func setup(at: Vector2, dir: Vector2, slot: int, team: int, p_id: String = "grenade") -> void:
	global_position = at
	last_pos = at
	owner_slot = slot
	owner_team = team
	payload_id = p_id if p_id != "" else "grenade"
	name = "Grenade" if payload_id == "grenade" else "Throw_%s" % payload_id
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	collision_layer = Maps.COL_HURT
	collision_mask = Maps.COL_WORLD | Maps.COL_PROP | Maps.COL_PLATFORM
	var spec: Dictionary = _Expl.throwable(payload_id)
	_apply_spec(spec)
	velocity = _Expl.throw_velocity_of(dir, spec)
	var shape: CollisionShape2D = CollisionShape2D.new()
	var circle: CircleShape2D = CircleShape2D.new()
	circle.radius = 4.0
	shape.shape = circle
	add_child(shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(8, 8)
	body.position = Vector2(-4, -4)
	body.color = Color(0.25, 0.35, 0.3, 1.0)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(body)
	Visuals.attach_sprite(self, str(spec.get("icon", "res://assets/art/item_grenade.png")))


func _apply_spec(spec: Dictionary) -> void:
	fuse_ticks = maxi(int(spec.get("fuse_ticks", 81)), 1)
	life_ticks = maxi(int(spec.get("life_ticks", 180)), fuse_ticks)
	fuse = float(fuse_ticks) * SimConstants.TICK_DT
	damage = float(spec.get("damage", 42.0))
	radius = float(spec.get("radius", 48.0))


func predicted_pos(delta: float) -> Vector2:
	return _Expl.predicted_pos(global_position, velocity, delta)


func predicted_vel(delta: float) -> Vector2:
	return _Expl.predicted_velocity(velocity, delta)


func commit_step(at: Vector2, vel: Vector2, _delta: float) -> void:
	if exploded or applied:
		return
	last_pos = global_position
	global_position = at
	velocity = vel
	fuse_ticks = maxi(fuse_ticks - 1, 0)
	life_ticks = maxi(life_ticks - 1, 0)
	fuse = float(fuse_ticks) * SimConstants.TICK_DT
	if fuse_ticks <= 0:
		exploded = true
	if life_ticks <= 0:
		exploded = true

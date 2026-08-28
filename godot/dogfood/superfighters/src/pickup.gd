class_name Pickup
extends Area2D

var weapon_id: String = "pistol"
var from_world: bool = true
var home: Vector2 = Vector2.ZERO


func setup(p_id: String, at: Vector2) -> void:
	weapon_id = p_id
	name = "Pickup_%s" % p_id
	global_position = at
	collision_layer = Maps.COL_PICKUP
	collision_mask = 0
	monitoring = false
	monitorable = true
	var shape: CollisionShape2D = CollisionShape2D.new()
	var rect: RectangleShape2D = RectangleShape2D.new()
	rect.size = Vector2(14, 10)
	shape.shape = rect
	add_child(shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(14, 10)
	body.position = Vector2(-7, -5)
	body.color = Color(0.7, 0.6, 0.2, 1.0)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(body)
	var spec: Dictionary = WeaponDefs.data(p_id)
	Visuals.attach_sprite(self, str(spec.get("icon", "res://assets/ui/ui_icon_fist.png")))

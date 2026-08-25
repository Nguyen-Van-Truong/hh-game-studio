class_name Player
extends CharacterBody2D


func _ready() -> void:
	name = "Player"
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	collision_layer = VaultMap.COL_PLAYER
	collision_mask = VaultMap.COL_WORLD | VaultMap.COL_DOOR
	var shape: CollisionShape2D = CollisionShape2D.new()
	var rect: RectangleShape2D = RectangleShape2D.new()
	rect.size = Vector2(12, 12)
	shape.shape = rect
	add_child(shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(float(VaultMap.ACTOR), float(VaultMap.ACTOR))
	body.position = Vector2(-float(VaultMap.ACTOR) * 0.5, -float(VaultMap.ACTOR) * 0.5)
	body.color = Color(0.93, 0.86, 0.70)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(body)
	var cam: Camera2D = Camera2D.new()
	cam.name = "Camera"
	cam.zoom = Vector2(VaultMap.CAMERA_ZOOM, VaultMap.CAMERA_ZOOM)
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = VaultMap.MAP_W * VaultMap.TILE
	cam.limit_bottom = VaultMap.MAP_H * VaultMap.TILE
	cam.position_smoothing_enabled = false
	add_child(cam)
	if is_inside_tree():
		cam.make_current()


func step_move(delta: float, dir: Vector2) -> void:
	velocity = dir * VaultMap.PLAYER_SPEED
	move_and_slide()

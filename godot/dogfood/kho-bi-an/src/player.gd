class_name Player
extends CharacterBody2D

var facing: Vector2 = Vector2.DOWN
var sprite: AnimatedSprite2D
var lantern: PointLight2D


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
	sprite = Visuals.attach_actor(self, Visuals.PLAYER_FRAMES)
	sprite.play("idle_down")
	lantern = Visuals.make_lantern("Lantern", 0.85, 1.7)
	add_child(lantern)
	var cam: Camera2D = Camera2D.new()
	cam.name = "Camera"
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = VaultMap.MAP_W * VaultMap.TILE
	cam.limit_bottom = VaultMap.MAP_H * VaultMap.TILE
	cam.position_smoothing_enabled = false
	add_child(cam)
	var vp: Viewport = get_viewport()
	if vp != null:
		fit_camera(vp.get_visible_rect().size)
	else:
		fit_camera(VaultMap.DESIGNED_VIEW)


func fit_camera(vp_size: Vector2) -> void:
	var cam: Camera2D = get_node_or_null("Camera") as Camera2D
	if cam == null:
		return
	var z: float = VaultMap.zoom_for_size(vp_size)
	cam.zoom = Vector2(z, z)
	if is_inside_tree():
		cam.make_current()
		cam.force_update_scroll()


func step_move(delta: float, dir: Vector2) -> void:
	velocity = dir * VaultMap.PLAYER_SPEED
	move_and_slide()
	if dir != Vector2.ZERO:
		facing = dir
	Visuals.play_actor(sprite, facing, dir != Vector2.ZERO)


func pulse() -> void:
	if sprite == null:
		return
	sprite.modulate = Color(1.18, 1.08, 0.88)

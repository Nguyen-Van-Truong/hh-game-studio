class_name Fighter
extends CharacterBody2D
## Playable port of the Code.Data.Players.Player loop: run, jump, punch, shoot, roll, burn.

signal died(id: int)
signal health_changed(id: int, health: int)

const SPRITE_PATH: String = "res://reference/flash/sprites/DefineSprite_2075/731.png"
const PUNCH_SFX: String = "res://reference/flash/sounds/2539_punch00.mp3"
const GUN_SFX: String = "res://reference/flash/sounds/2530_gun00.mp3"
const JUMP_SFX: String = "res://reference/flash/sounds/2535_jump_00.mp3"

var player_id: int = 1
var health: int = Tuning.HEALTH
var facing: int = 1
var ammo: int = Tuning.MAGAZINE
var burning: float = 0.0

var _punch_left: float = 0.0
var _shoot_left: float = 0.0
var _roll_left: float = 0.0
var _sprite: Sprite2D
var _audio: AudioStreamPlayer

func _ready() -> void:
	collision_layer = 2
	collision_mask = 1
	var body := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = Vector2(28, 48)
	body.shape = shape
	body.position = Vector2(0, -24)
	add_child(body)
	_sprite = Sprite2D.new()
	if ResourceLoader.exists(SPRITE_PATH):
		_sprite.texture = load(SPRITE_PATH) as Texture2D
		_sprite.scale = Vector2(0.35, 0.35)
	_sprite.position = Vector2(0, -28)
	_sprite.modulate = Color(0.45, 0.75, 1.0) if player_id == 1 else Color(1.0, 0.62, 0.28)
	add_child(_sprite)
	_audio = AudioStreamPlayer.new()
	add_child(_audio)

func _physics_process(delta: float) -> void:
	if health <= 0:
		return
	_punch_left = maxf(0.0, _punch_left - delta)
	_shoot_left = maxf(0.0, _shoot_left - delta)
	_roll_left = maxf(0.0, _roll_left - delta)
	if burning > 0.0:
		burning = maxf(0.0, burning - delta)
		if int(burning * 2.0) % 2 == 0:
			health -= 1
			health_changed.emit(player_id, health)
			if health <= 0:
				died.emit(player_id)
				return
		if _down() and is_on_floor():
			burning = 0.0
	var axis: float = Input.get_axis(_act("left"), _act("right"))
	if _roll_left > 0.0:
		velocity.x = float(facing) * Tuning.units_to_px_per_sec(Tuning.ROLL_SPEED)
	else:
		velocity.x = axis * Tuning.units_to_px_per_sec(Tuning.RUN_SPEED)
		if axis != 0.0:
			facing = 1 if axis > 0.0 else -1
	if not is_on_floor():
		velocity.y += Tuning.gravity_px() * delta
	elif Input.is_action_just_pressed(_act("up")):
		velocity.y = Tuning.units_to_px_per_sec(Tuning.JUMP_POWER)
		_play(JUMP_SFX)
	if Input.is_action_just_pressed(_act("down")) and is_on_floor() and absf(axis) > 0.1:
		_roll_left = 0.35
	if Input.is_action_just_pressed(_act("punch")) and _punch_left <= 0.0:
		_punch()
	if Input.is_action_just_pressed(_act("shoot")) and _shoot_left <= 0.0:
		_shoot()
	_sprite.flip_h = facing < 0
	_sprite.modulate.a = 0.55 if burning > 0.0 else 1.0
	move_and_slide()
	if position.y > 820.0:
		health = 0
		died.emit(player_id)

func damage(amount: int) -> void:
	if health <= 0:
		return
	health = maxi(0, health - amount)
	health_changed.emit(player_id, health)
	if health <= 0:
		died.emit(player_id)

func ignite(seconds: float) -> void:
	burning = maxf(burning, seconds)

func _punch() -> void:
	_punch_left = Tuning.PUNCH_COOLDOWN
	_play(PUNCH_SFX)
	var hit := Rect2(global_position + Vector2(float(facing) * 8.0, -40.0), Vector2(36, 28))
	for node: Node in get_tree().get_nodes_in_group("fighters"):
		var other: Fighter = node as Fighter
		if other == null or other == self or other.health <= 0:
			continue
		if hit.has_point(other.global_position + Vector2(0, -24)):
			other.damage(Tuning.PUNCH_DAMAGE)

func _shoot() -> void:
	if ammo <= 0:
		return
	ammo -= 1
	_shoot_left = Tuning.SHOOT_COOLDOWN
	_play(GUN_SFX)
	var bullet := Bullet.new()
	bullet.owner_id = player_id
	bullet.direction = float(facing)
	bullet.global_position = global_position + Vector2(float(facing) * 20.0, -28.0)
	get_parent().add_child(bullet)

func _play(path: String) -> void:
	if not ResourceLoader.exists(path):
		return
	var stream: AudioStream = load(path) as AudioStream
	if stream == null:
		return
	_audio.stream = stream
	_audio.play()

func _act(suffix: String) -> StringName:
	return StringName("p%d_%s" % [player_id, suffix])

func _down() -> bool:
	return Input.is_action_pressed(_act("down"))

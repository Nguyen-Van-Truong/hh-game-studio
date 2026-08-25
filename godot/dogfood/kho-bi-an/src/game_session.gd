class_name GameSession
extends Node2D

signal won
signal lost

var state: GameState = GameState.new()
var inventory: Inventory = Inventory.new()
var player: Player
var warden: Warden
var world: Node2D
var hud: Hud
var pause_screen: PauseScreen
var test_driven: bool = false
var _first_move_done: bool = false
var _first_interact_done: bool = false


func setup(saved: Dictionary) -> void:
	name = "GameSession"
	process_mode = Node.PROCESS_MODE_PAUSABLE
	var builder: WorldBuilder = WorldBuilder.new()
	world = builder.build()
	add_child(world)
	player = Player.new()
	add_child(player)
	warden = Warden.new()
	add_child(warden)
	warden.set_patrol(VaultMap.tile_center(VaultMap.WARDEN_A), VaultMap.tile_center(VaultMap.WARDEN_B))
	hud = Hud.new()
	add_child(hud)
	pause_screen = PauseScreen.new()
	pause_screen.resume_pressed.connect(set_paused.bind(false))
	add_child(pause_screen)
	_apply_saved(saved)
	hud.set_has_key(inventory.has_item("key"))
	hud.set_hint("WASD / stick: move")


func _physics_process(delta: float) -> void:
	if test_driven:
		return
	if state.outcome != "play":
		return
	var move: Vector2 = InputActions.read_move()
	var interact: bool = Input.is_action_just_pressed("interact")
	step_fixed(delta, move, interact)


func step_fixed(delta: float, move: Vector2, interact: bool) -> void:
	if state.outcome != "play":
		return
	var dir: Vector2 = InputActions.cardinal(move)
	if dir != Vector2.ZERO and not _first_move_done:
		_first_move_done = true
		hud.set_hint("E / South: interact")
	player.step_move(delta, dir)
	warden.step_patrol(delta)
	state.room_id = VaultMap.room_id_at(player.global_position)
	if warden.touches_player(player):
		_set_lose()
		return
	if interact:
		_interact()
	hud.set_has_key(inventory.has_item("key"))


func set_paused(active: bool) -> void:
	if state.outcome != "play" and active:
		return
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	tree.paused = active
	if active:
		pause_screen.show_pause()
	else:
		pause_screen.hide_pause()


func snapshot() -> Dictionary:
	var data: Dictionary = state.to_dict()
	data["outcome"] = state.outcome
	data["win"] = state.is_win()
	data["player_x"] = player.global_position.x
	data["player_y"] = player.global_position.y
	data["inventory_key"] = inventory.has_item("key")
	return data


func _apply_saved(saved: Dictionary) -> void:
	state.reset()
	inventory.clear()
	if saved.is_empty():
		player.global_position = VaultMap.tile_center(VaultMap.PLAYER_SPAWN)
		return
	state.apply_dict(saved)
	if state.has_key:
		inventory.add("key")
		_set_prop_visible("Key", false)
	if state.door_open:
		_open_door_collision()
	_place_in_room(state.room_id)


func _place_in_room(room_id: String) -> void:
	if room_id == "relic" and state.door_open:
		player.global_position = VaultMap.tile_center(VaultMap.RELIC_ENTER)
	elif room_id == "door":
		player.global_position = VaultMap.tile_center(VaultMap.DOOR_ROOM)
	else:
		player.global_position = VaultMap.tile_center(VaultMap.PLAYER_SPAWN)


func _interact() -> void:
	if not _first_interact_done:
		_first_interact_done = true
		hud.set_hint("")
	var kind: String = _nearest_kind()
	if kind == "key":
		_pickup_key()
	elif kind == "door":
		_try_open_door()
	elif kind == "relic":
		_reach_relic()


func _nearest_kind() -> String:
	var best: String = ""
	var best_d: float = VaultMap.INTERACT_REACH
	var names: PackedStringArray = PackedStringArray(["Key", "Door", "Relic"])
	var kinds: PackedStringArray = PackedStringArray(["key", "door", "relic"])
	var i: int = 0
	while i < names.size():
		var node: Node2D = world.get_node_or_null(String(names[i])) as Node2D
		var kind: String = String(kinds[i])
		i += 1
		if node == null:
			continue
		if kind == "key" and inventory.has_item("key"):
			continue
		if kind == "door" and state.door_open:
			continue
		if kind == "relic" and state.relic_reached:
			continue
		var dist: float = player.global_position.distance_to(node.global_position)
		if dist <= best_d:
			best_d = dist
			best = kind
	return best


func _pickup_key() -> void:
	inventory.add("key")
	state.has_key = true
	_set_prop_visible("Key", false)
	hud.set_hint("Key taken")
	_persist()


func _try_open_door() -> void:
	if not inventory.has_item("key"):
		hud.set_hint("Need the key")
		return
	state.door_open = true
	_open_door_collision()
	hud.set_hint("Door open")
	_persist()


func _reach_relic() -> void:
	if not state.door_open:
		hud.set_hint("Door still closed")
		return
	state.relic_reached = true
	state.outcome = "win"
	_persist()
	won.emit()


func _set_lose() -> void:
	state.outcome = "lose"
	lost.emit()


func _open_door_collision() -> void:
	var door: StaticBody2D = world.get_node_or_null("Door") as StaticBody2D
	if door == null:
		return
	door.collision_layer = 0
	var body: ColorRect = door.get_node_or_null("Body") as ColorRect
	if body != null:
		body.color = Color(0.40, 0.34, 0.22, 0.45)


func _set_prop_visible(prop_name: String, on: bool) -> void:
	var node: Node2D = world.get_node_or_null(prop_name) as Node2D
	if node != null:
		node.visible = on


func _persist() -> void:
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	var saver: Node = tree.root.get_node_or_null("SaveService")
	if saver != null:
		saver.call("autosave", state)

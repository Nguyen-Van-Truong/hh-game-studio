class_name App
extends Node

var title: TitleScreen
var win_screen: WinScreen
var lose_screen: LoseScreen
var remap_screen: RemapScreen
var session: GameSession
var test_driven: bool = false
var mode: String = "vs1"
var map_id: String = "rooftops"
var stage_index: int = 0
var runtime: RuntimeApi = RuntimeApi.new()


func _enter_tree() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	RenderingServer.set_default_clear_color(UiTheme.INDIGO)
	if title != null:
		return
	InputActions.install()
	if not test_driven:
		InputMapStore.apply_saved_if_any()
	seed(1)
	runtime.bind(self, OS.get_environment("HH_VF_RUNTIME_TOKEN"))
	title = TitleScreen.new()
	title.vs_one_pressed.connect(_on_vs_one)
	title.vs_two_pressed.connect(_on_vs_two)
	title.stage_pressed.connect(_on_stage)
	title.map_cycle_pressed.connect(_on_map_cycle)
	title.controls_pressed.connect(_on_controls)
	add_child(title)
	remap_screen = RemapScreen.new()
	add_child(remap_screen)
	win_screen = WinScreen.new()
	win_screen.restart_pressed.connect(restart_to_title)
	add_child(win_screen)
	lose_screen = LoseScreen.new()
	lose_screen.restart_pressed.connect(restart_to_title)
	add_child(lose_screen)


func _input(event: InputEvent) -> void:
	if remap_screen != null and remap_screen.visible:
		return
	if session == null or session.outcome != "play":
		return
	if event.is_echo() or not event.is_pressed():
		return
	if not event.is_action("pause"):
		return
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	session.set_paused(not tree.paused, RuntimeConstants.REASON_PLAYER)
	get_viewport().set_input_as_handled()


func start_fight(p_mode: String, p_map: String, p_stage: int) -> void:
	mode = p_mode
	map_id = p_map
	stage_index = p_stage
	_clear_session()
	if title != null:
		title.visible = false
	if win_screen != null:
		win_screen.visible = false
	if lose_screen != null:
		lose_screen.visible = false
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.paused = false
	session = GameSession.new()
	session.test_driven = test_driven
	session.won.connect(_on_won)
	session.lost.connect(_on_lost)
	add_child(session)
	session.setup(p_mode, p_map, p_stage)
	if session.pause_screen != null:
		session.pause_screen.controls_pressed.connect(_on_controls)


func restart_to_title() -> void:
	_clear_session()
	if win_screen != null:
		win_screen.visible = false
	if lose_screen != null:
		lose_screen.visible = false
	if title != null:
		title.visible = true
		title.set_map_id(map_id)
		title.vs_one_btn.grab_focus()
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.paused = false


func restart_same() -> void:
	start_fight(mode, map_id if mode != "stage" else Maps.stage_map_at(0), 0 if mode == "stage" else stage_index)


func _on_vs_one() -> void:
	start_fight("vs1", map_id, 0)


func _on_vs_two() -> void:
	start_fight("vs2", map_id, 0)


func _on_stage() -> void:
	start_fight("stage", Maps.stage_map_at(0), 0)


func _on_map_cycle() -> void:
	map_id = Maps.next_vs_map(map_id)
	if title != null:
		title.set_map_id(map_id)


func _on_controls() -> void:
	if remap_screen != null:
		remap_screen.show_remap()


func _on_won() -> void:
	if mode == "stage" and stage_index + 1 < Maps.stage_count():
		call_deferred("_advance_stage")
		return
	call_deferred("_show_win")


func _advance_stage() -> void:
	stage_index += 1
	start_fight("stage", Maps.stage_map_at(stage_index), stage_index)


func _show_win() -> void:
	var headline: String = "Last standing"
	var detail: String = "The arena is yours."
	if mode == "stage":
		headline = "Stage cleared"
		detail = "Skyline Relay → Pallet Annex → Signal Court → Vitriol Sump."
	if win_screen != null:
		win_screen.show_win(headline, detail)


func _on_lost() -> void:
	if lose_screen != null:
		lose_screen.show_lose("Down", "Pits and bullets end the run. Restart from title.")


func shutdown() -> void:
	_clear_session()
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.paused = false


func _exit_tree() -> void:
	if session == null or not is_instance_valid(session):
		session = null
		return
	_disconnect_session(session)
	session.shutdown()
	session = null


func release_session() -> void:
	if session == null:
		return
	var old: GameSession = session
	session = null
	if not is_instance_valid(old):
		return
	_disconnect_session(old)
	old.shutdown()
	old.free()


func _clear_session() -> void:
	if session == null:
		return
	var old: GameSession = session
	session = null
	if not is_instance_valid(old):
		return
	_disconnect_session(old)
	old.shutdown()
	old.queue_free()


func _disconnect_session(old: GameSession) -> void:
	if old.won.is_connected(_on_won):
		old.won.disconnect(_on_won)
	if old.lost.is_connected(_on_lost):
		old.lost.disconnect(_on_lost)
	if old.pause_screen != null and old.pause_screen.controls_pressed.is_connected(_on_controls):
		old.pause_screen.controls_pressed.disconnect(_on_controls)

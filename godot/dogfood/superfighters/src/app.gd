class_name App
extends Node

const _TieScreen: GDScript = preload("res://src/ui/tie_screen.gd")

var title: TitleScreen
var win_screen: WinScreen
var lose_screen: LoseScreen
var tie_screen
var remap_screen: RemapScreen
var session: GameSession
var test_driven: bool = false
var mode: String = "vs1"
var map_id: String = "rooftops"
var stage_index: int = 0
var next_round_id: int = 1
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
	tie_screen = _TieScreen.new()
	tie_screen.restart_pressed.connect(restart_to_title)
	add_child(tie_screen)


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
		title.clear_status()
	if win_screen != null:
		win_screen.visible = false
	if lose_screen != null:
		lose_screen.visible = false
	if tie_screen != null:
		tie_screen.visible = false
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.paused = false
	session = GameSession.new()
	session.test_driven = test_driven
	session.match_rules.round_id = next_round_id
	next_round_id += 1
	session.won.connect(_on_won)
	session.lost.connect(_on_lost)
	session.tied.connect(_on_tied)
	session.quit_match.connect(_on_quit_match)
	add_child(session)
	session.setup(p_mode, p_map, p_stage)
	if session.pause_screen != null:
		session.pause_screen.controls_pressed.connect(_on_controls)
		session.pause_screen.restart_pressed.connect(_on_pause_restart)
		session.pause_screen.quit_pressed.connect(_on_pause_quit)


func restart_to_title() -> void:
	_clear_session()
	if win_screen != null:
		win_screen.visible = false
	if lose_screen != null:
		lose_screen.visible = false
	if tie_screen != null:
		tie_screen.visible = false
	if title != null:
		title.visible = true
		title.set_map_id(map_id)
		title.clear_status()
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
	var reason: String = "last_standing"
	var team: int = -1
	if session != null and session.match_rules != null:
		if session.match_rules.end_reason != "":
			reason = session.match_rules.end_reason
		team = session.match_rules.winner_team
	var detail: String = "You won. End reason: %s. Winner team %d. Restart from title." % [reason, team]
	if mode == "stage":
		headline = "Stage cleared"
		detail = "Stage win. End reason: %s. Next arena or title restart." % reason
	if win_screen != null:
		win_screen.show_win(headline, detail)


func _on_lost() -> void:
	if lose_screen != null:
		var reason: String = ""
		if session != null and session.match_rules != null:
			reason = session.match_rules.end_reason
		var detail: String = "Pits and bullets end the run. Restart from title."
		if reason != "":
			detail = "End reason: %s. Restart from title." % reason
		lose_screen.show_lose("Down", detail)


func _on_tied() -> void:
	if tie_screen != null:
		var reason: String = "all_down"
		if session != null and session.match_rules != null and session.match_rules.end_reason != "":
			reason = session.match_rules.end_reason
		var detail: String = "Last standing wiped. End reason: %s." % reason
		if reason == "timeout":
			detail = "Round timer ended with more than one side standing (approximation, not observed)."
		tie_screen.show_tie("Draw", detail)


func _on_quit_match() -> void:
	# Player quit always returns to title. Official LIVE proof requires
	# title_visible_after=true; test_driven must not swallow the transition.
	quit_to_title()


func quit_to_title() -> void:
	if session != null:
		session.set_paused(false)
	restart_to_title()
	if title != null:
		title.set_status("Last match ended: quit. Choose a mode to start again.")


func _on_pause_restart() -> void:
	if session != null:
		session.set_paused(false)
	restart_same()


func _on_pause_quit() -> void:
	if session != null:
		session.request_quit()
	else:
		quit_to_title()


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
	if old.tied.is_connected(_on_tied):
		old.tied.disconnect(_on_tied)
	if old.quit_match.is_connected(_on_quit_match):
		old.quit_match.disconnect(_on_quit_match)
	if old.pause_screen != null:
		if old.pause_screen.controls_pressed.is_connected(_on_controls):
			old.pause_screen.controls_pressed.disconnect(_on_controls)
		if old.pause_screen.restart_pressed.is_connected(_on_pause_restart):
			old.pause_screen.restart_pressed.disconnect(_on_pause_restart)
		if old.pause_screen.quit_pressed.is_connected(_on_pause_quit):
			old.pause_screen.quit_pressed.disconnect(_on_pause_quit)

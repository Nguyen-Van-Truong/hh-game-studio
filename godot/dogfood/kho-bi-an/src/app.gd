class_name App
extends Node

var title: TitleScreen
var win_screen: WinScreen
var lose_screen: LoseScreen
var session: GameSession
var test_driven: bool = false


func _enter_tree() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	RenderingServer.set_default_clear_color(UiTheme.INDIGO)
	if title != null:
		return
	InputActions.install()
	seed(1)
	title = TitleScreen.new()
	title.play_pressed.connect(start_new_run)
	title.continue_pressed.connect(continue_run)
	title.restart_pressed.connect(_title_restart)
	add_child(title)
	win_screen = WinScreen.new()
	win_screen.restart_pressed.connect(start_new_run)
	add_child(win_screen)
	lose_screen = LoseScreen.new()
	lose_screen.restart_pressed.connect(start_new_run)
	add_child(lose_screen)


func _ready() -> void:
	_refresh_title()


func _input(event: InputEvent) -> void:
	if session == null or session.state.outcome != "play":
		return
	if event.is_echo() or not event.is_pressed():
		return
	if not event.is_action("pause"):
		return
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	session.set_paused(not tree.paused)
	get_viewport().set_input_as_handled()


func start_new_run() -> void:
	_begin_run({})


func continue_run() -> void:
	var data: Dictionary = _load_slot()
	if data.is_empty() or bool(data.get("relic_reached", false)):
		_begin_run({})
		return
	_begin_run(data)


func _title_restart() -> void:
	var saver: Node = _save_service()
	if saver != null:
		saver.call("clear_slot")
	_begin_run({})


func _begin_run(saved: Dictionary) -> void:
	_clear_session()
	if title == null or win_screen == null or lose_screen == null:
		push_error("App UI was not built")
		return
	title.visible = false
	win_screen.visible = false
	lose_screen.visible = false
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.paused = false
	session = GameSession.new()
	session.test_driven = test_driven
	session.won.connect(_on_won)
	session.lost.connect(_on_lost)
	add_child(session)
	session.setup(saved)


func _clear_session() -> void:
	if session == null:
		return
	session.queue_free()
	session = null


func _on_won() -> void:
	win_screen.show_win()


func _on_lost() -> void:
	lose_screen.show_lose()


func _refresh_title() -> void:
	var data: Dictionary = _load_slot()
	var can_continue: bool = not data.is_empty() and not bool(data.get("relic_reached", false))
	title.set_continue_enabled(can_continue)


func _save_service() -> Node:
	var tree: SceneTree = get_tree()
	if tree == null:
		return null
	return tree.root.get_node_or_null("SaveService")


func _load_slot() -> Dictionary:
	var saver: Node = _save_service()
	if saver == null:
		return {}
	return saver.call("load_slot") as Dictionary

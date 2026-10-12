# HH gamekit kit pause v1 - self-made (HH Studio)
extends CanvasLayer
## Pause overlay. Instance this scene in the game; it is not an autoload.

func _enter_tree() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process_unhandled_input(true)
	_hide_panel()
	var resume_button: Button = get_node_or_null("Panel/Resume") as Button
	if resume_button != null and not resume_button.pressed.is_connected(_on_resume):
		@warning_ignore("return_value_discarded") # a missed signal leaves Resume on its default action
		resume_button.pressed.connect(_on_resume)
	var quit_button: Button = get_node_or_null("Panel/Quit") as Button
	if quit_button != null and not quit_button.pressed.is_connected(_on_quit):
		@warning_ignore("return_value_discarded") # a missed signal leaves Quit on its default action
		quit_button.pressed.connect(_on_quit)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_echo():
		return
	var action: StringName = &"pause" if InputMap.has_action(&"pause") else &"ui_cancel"
	if event.is_action_pressed(action):
		toggle()
		get_viewport().set_input_as_handled()


func toggle() -> void:
	var tree: SceneTree = get_tree()
	var paused: bool = not tree.paused
	tree.paused = paused
	var panel: CanvasItem = get_node_or_null("Panel") as CanvasItem
	if panel != null:
		panel.visible = paused


func resume() -> void:
	get_tree().paused = false
	_hide_panel()


func quit_game() -> void:
	get_tree().quit()


func _on_resume() -> void:
	resume()


func _on_quit() -> void:
	quit_game()


func _hide_panel() -> void:
	var panel: CanvasItem = get_node_or_null("Panel") as CanvasItem
	if panel != null:
		panel.visible = false

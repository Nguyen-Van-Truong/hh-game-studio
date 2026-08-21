class_name HHAgentHealthDock
extends VBoxContainer

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")

## Health dock: version, project, bridge, policy, queue, red Pause.
## Never displays the session token.

signal pause_requested

var _title: Label
var _version: Label
var _project: Label
var _bridge: Label
var _policy: Label
var _queue: Label
var _pause: Label
var _pause_btn: Button


func _ready() -> void:
	name = "HHAgentHealth"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_theme_constant_override("separation", 6)
	_title = _add_label("HH Agent")
	_title.add_theme_font_size_override("font_size", 16)
	_version = _add_label("version: —")
	_project = _add_label("project: —")
	_bridge = _add_label("bridge: disconnected")
	_policy = _add_label("policy: —")
	_queue = _add_label("queue: 0")
	_pause = _add_label("pause: inactive")
	_pause_btn = Button.new()
	_pause_btn.text = "Pause"
	_pause_btn.tooltip_text = "Close the mutation gate (A14)"
	_pause_btn.add_theme_color_override("font_color", Color(1.0, 0.12, 0.12))
	_pause_btn.add_theme_color_override("font_hover_color", Color(1.0, 0.28, 0.28))
	_pause_btn.add_theme_color_override("font_pressed_color", Color(0.85, 0.05, 0.05))
	_pause_btn.add_theme_color_override("font_focus_color", Color(1.0, 0.12, 0.12))
	_pause_btn.pressed.connect(_on_pause_pressed)
	add_child(_pause_btn)


func set_status(info: Dictionary) -> void:
	if _version == null:
		return
	_version.text = "version: %s" % str(info.get("version", "—"))
	_project.text = "project: %s" % str(info.get("project", "—"))
	_bridge.text = "bridge: %s" % str(info.get("bridge", "disconnected"))
	_policy.text = "policy: %s" % str(info.get("policy", HHAgentConstants.POLICY_DISPLAY))
	_queue.text = "queue: %s" % str(info.get("queue", 0))
	_pause.text = "pause: %s" % str(info.get("pause", "inactive"))
	if _pause_btn != null:
		var active: bool = str(info.get("pause", "inactive")) == "active"
		_pause_btn.text = "Resume" if active else "Pause"


func _on_pause_pressed() -> void:
	pause_requested.emit()


func _add_label(text: String) -> Label:
	var label: Label = Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(label)
	return label

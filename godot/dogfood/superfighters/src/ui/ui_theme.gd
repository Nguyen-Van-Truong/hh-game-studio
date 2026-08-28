class_name UiTheme
extends RefCounted

const CREAM: Color = Color8(236, 228, 208)
const INDIGO: Color = Color8(18, 28, 48)
const INDIGO_PANEL: Color = Color(0.07, 0.11, 0.19, 0.86)
const BRASS: Color = Color8(232, 168, 48)
const BRASS_DARK: Color = Color8(168, 112, 24)
const TEAL: Color = Color8(36, 148, 132)
const RUST: Color = Color8(196, 48, 52)
const BLUE: Color = Color8(48, 98, 196)

static var _cached: Theme


static func shared() -> Theme:
	if _cached == null:
		_cached = make()
	return _cached


static func apply(control: Control) -> void:
	control.theme = shared()


static func make() -> Theme:
	var theme: Theme = Theme.new()
	theme.set_color("font_color", "Label", CREAM)
	theme.set_color("font_shadow_color", "Label", Color(0, 0, 0, 0.55))
	theme.set_constant("shadow_offset_x", "Label", 1)
	theme.set_constant("shadow_offset_y", "Label", 1)
	theme.set_font_size("font_size", "Label", 20)
	theme.set_color("font_color", "Button", INDIGO)
	theme.set_color("font_hover_color", "Button", INDIGO)
	theme.set_color("font_focus_color", "Button", INDIGO)
	theme.set_color("font_pressed_color", "Button", CREAM)
	theme.set_color("font_disabled_color", "Button", Color(0.45, 0.42, 0.38))
	theme.set_font_size("font_size", "Button", 20)
	var btn: StyleBoxFlat = _box(BRASS, 0)
	theme.set_stylebox("normal", "Button", btn)
	var hover: StyleBoxFlat = _box(Color8(240, 196, 90), 0)
	theme.set_stylebox("hover", "Button", hover)
	var focus: StyleBoxFlat = _box(CREAM, 2)
	focus.border_color = BRASS
	theme.set_stylebox("focus", "Button", focus)
	var pressed: StyleBoxFlat = _box(BRASS_DARK, 0)
	theme.set_stylebox("pressed", "Button", pressed)
	var disabled: StyleBoxFlat = _box(Color8(72, 82, 128), 0)
	theme.set_stylebox("disabled", "Button", disabled)
	return theme


static func _box(color: Color, border: int) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = color
	box.set_corner_radius_all(4)
	box.content_margin_left = 12
	box.content_margin_right = 12
	box.content_margin_top = 8
	box.content_margin_bottom = 8
	if border > 0:
		box.set_border_width_all(border)
		box.border_color = BRASS
	return box

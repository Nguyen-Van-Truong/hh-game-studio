class_name Hud
extends CanvasLayer

var _panel: ColorRect
var _key_icon: TextureRect
var _hint: Label


func _ready() -> void:
	name = "Hud"
	follow_viewport_enabled = false
	_panel = ColorRect.new()
	_panel.name = "Panel"
	_panel.color = UiTheme.INDIGO_PANEL
	_panel.size = Vector2(560, 48)
	_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_panel)
	_key_icon = TextureRect.new()
	_key_icon.name = "KeyIcon"
	_key_icon.size = Vector2(24, 24)
	_key_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_key_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_key_icon.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_key_icon.texture = load(Visuals.KEY_ICON) as Texture2D
	_key_icon.modulate = Color(0.40, 0.40, 0.44)
	_key_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_key_icon)
	_hint = Label.new()
	_hint.name = "Hint"
	_hint.size = Vector2(500, 32)
	_hint.text = "WASD / stick: move"
	UiTheme.apply(_hint)
	_hint.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(_hint)
	layout_on_playfield(Rect2(Vector2.ZERO, Vector2(1280, 720)))


func layout_on_playfield(rect: Rect2) -> void:
	if _panel == null or _key_icon == null or _hint == null:
		return
	var origin: Vector2 = Vector2(16, 16)
	if rect.size.x >= 80.0 and rect.size.y >= 40.0:
		origin = rect.position + Vector2(16, 16)
	_panel.position = origin
	_key_icon.position = origin + Vector2(12, 12)
	_hint.position = origin + Vector2(44, 8)


func set_has_key(has_key: bool) -> void:
	if has_key:
		_key_icon.modulate = Color.WHITE
	else:
		_key_icon.modulate = Color(0.40, 0.40, 0.44)


func set_hint(text: String) -> void:
	_hint.text = text

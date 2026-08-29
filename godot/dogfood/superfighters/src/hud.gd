class_name Hud
extends CanvasLayer

var _lines: Array[Label] = []
var _map_label: Label
var _hint: Label


func _ready() -> void:
	name = "Hud"
	follow_viewport_enabled = false
	var i: int = 0
	while i < 4:
		var line: Label = Label.new()
		line.name = "Bar_%d" % i
		line.position = Vector2(16, 12 + float(i) * 28)
		line.size = Vector2(780, 26)
		UiTheme.apply(line)
		line.add_theme_font_size_override("font_size", 16)
		add_child(line)
		_lines.append(line)
		i += 1
	_map_label = Label.new()
	_map_label.name = "MapName"
	_map_label.position = Vector2(900, 12)
	_map_label.size = Vector2(360, 28)
	UiTheme.apply(_map_label)
	_map_label.add_theme_color_override("font_color", UiTheme.BRASS)
	add_child(_map_label)
	_hint = Label.new()
	_hint.name = "Hint"
	_hint.position = Vector2(16, 680)
	_hint.size = Vector2(1240, 28)
	UiTheme.apply(_hint)
	_hint.add_theme_font_size_override("font_size", 16)
	add_child(_hint)


func set_map_name(text: String) -> void:
	if _map_label != null:
		_map_label.text = text


func set_hint(text: String) -> void:
	if _hint != null:
		_hint.text = text


func refresh(fighters: Array) -> void:
	var i: int = 0
	while i < _lines.size():
		var line: Label = _lines[i]
		if i >= fighters.size():
			line.text = ""
			i += 1
			continue
		var f: Fighter = fighters[i] as Fighter
		if f == null or f.dead:
			line.text = ""
			i += 1
			continue
		var melee: Dictionary = WeaponDefs.data(f.melee_id)
		var gun: Dictionary = WeaponDefs.data(f.gun_id)
		var who: String = "P1"
		if f.slot == 1 and f.is_human:
			who = "P2"
		elif f.is_bot:
			who = "Bot%d" % f.slot
		var pose: String = ""
		if f.rolling:
			pose = " ROLL"
		elif f.sprinting:
			pose = " SPRINT"
		line.text = "%s  HP %d  ST %d%s  %s / %s x%d  G%d" % [
			who,
			int(f.health),
			int(f.stamina),
			pose,
			str(melee.get("name", "Fists")),
			str(gun.get("name", "Pistol")),
			f.ammo,
			f.grenades
		]
		if f.team == 0:
			line.add_theme_color_override("font_color", UiTheme.BLUE)
		elif f.team == 1:
			line.add_theme_color_override("font_color", UiTheme.RUST)
		elif f.team == 2:
			line.add_theme_color_override("font_color", UiTheme.BRASS)
		else:
			line.add_theme_color_override("font_color", UiTheme.TEAL)
		i += 1

@tool
extends Node2D

const CELL: int = 48
const COLS: int = 16
const ROWS: int = 12
const PAD_X: int = 24
const PAD_Y: int = 56

var _dir: Vector2i = Vector2i(1, 0)
var _pending: Vector2i = Vector2i(1, 0)
var _body: Array[Vector2i] = [Vector2i(5, 6), Vector2i(4, 6), Vector2i(3, 6), Vector2i(2, 6)]
var _food: Vector2i = Vector2i(11, 6)
var _accum: float = 0.0
var _step: float = 0.14
var _alive: bool = true
var _score: int = 0


func _ready() -> void:
	_layout_hud()
	_paint()


func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	if not _alive or _food.x < 0:
		if Input.is_key_pressed(KEY_ENTER) or Input.is_key_pressed(KEY_SPACE):
			_restart()
		return
	_read_turn()
	_accum += delta
	if _accum < _step:
		return
	_accum = 0.0
	_dir = _pending
	var nxt: Vector2i = _body[0] + _dir
	if nxt.x < 0 or nxt.y < 0 or nxt.x >= COLS or nxt.y >= ROWS:
		_die()
		return
	var grow: bool = nxt == _food
	var tail: Vector2i = _body[_body.size() - 1]
	if _body.has(nxt) and (grow or nxt != tail):
		_die()
		return
	_body.insert(0, nxt)
	if grow:
		_score += 1
		_food = _spawn_food()
	else:
		_body.pop_back()
	_paint()


func _read_turn() -> void:
	var want: Vector2i = _pending
	if Input.is_key_pressed(KEY_UP):
		want = Vector2i(0, -1)
	elif Input.is_key_pressed(KEY_DOWN):
		want = Vector2i(0, 1)
	elif Input.is_key_pressed(KEY_LEFT):
		want = Vector2i(-1, 0)
	elif Input.is_key_pressed(KEY_RIGHT):
		want = Vector2i(1, 0)
	if want + _dir != Vector2i.ZERO:
		_pending = want


func _die() -> void:
	_alive = false
	_paint()


func _restart() -> void:
	_dir = Vector2i(1, 0)
	_pending = Vector2i(1, 0)
	_body = [Vector2i(5, 6), Vector2i(4, 6), Vector2i(3, 6), Vector2i(2, 6)]
	_food = Vector2i(11, 6)
	_accum = 0.0
	_alive = true
	_score = 0
	_paint()


func _spawn_food() -> Vector2i:
	var empty: Array[Vector2i] = []
	var y: int = 0
	while y < ROWS:
		var x: int = 0
		while x < COLS:
			var cell := Vector2i(x, y)
			if not _body.has(cell):
				empty.append(cell)
			x += 1
		y += 1
	if empty.is_empty():
		return Vector2i(-1, -1)
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	return empty[rng.randi_range(0, empty.size() - 1)]


func _paint() -> void:
	_layout_hud()
	queue_redraw()


func _layout_hud() -> void:
	var label: Node = get_node_or_null("Score")
	if label is Label:
		var hud: Label = label
		hud.position = Vector2(float(PAD_X), 12.0)
		hud.size = Vector2(float(COLS * CELL), 36.0)
		hud.add_theme_font_size_override("font_size", 24)
		hud.add_theme_color_override("font_color", Color(0.92, 0.96, 0.9, 1))
		if Engine.is_editor_hint():
			hud.text = "Snake    editor preview    press F6 to play"
		elif _food.x < 0:
			hud.text = "You win  %d    Enter / Space to retry" % _score
		elif _alive:
			hud.text = "Snake    score %d    arrows move" % _score
		else:
			hud.text = "Game over  %d    Enter / Space to retry" % _score


func _draw() -> void:
	var origin := Vector2(float(PAD_X), float(PAD_Y))
	var board_size := Vector2(float(COLS * CELL), float(ROWS * CELL))
	draw_rect(Rect2(origin + Vector2(6, 8), board_size), Color(0.02, 0.04, 0.03, 0.55), true)
	draw_rect(Rect2(origin, board_size), Color(0.06, 0.11, 0.09, 1), true)
	var gy: int = 0
	while gy < ROWS:
		var gx: int = 0
		while gx < COLS:
			if (gx + gy) % 2 == 0:
				draw_rect(
					Rect2(origin + Vector2(float(gx * CELL), float(gy * CELL)), Vector2(float(CELL), float(CELL))),
					Color(0.09, 0.16, 0.12, 1),
					true
				)
			gx += 1
		gy += 1
	draw_rect(Rect2(origin, board_size), Color(0.35, 0.92, 0.55, 0.95), false, 4.0)
	var i: int = _body.size() - 1
	while i >= 1:
		_draw_link(_body[i], _body[i - 1], _seg_color(i))
		i -= 1
	i = _body.size() - 1
	while i >= 0:
		_draw_seg(_body[i], _seg_color(i), i == 0)
		i -= 1
	if not _body.is_empty():
		_draw_eyes(_body[0])
		_draw_tongue(_body[0])
	if _food.x >= 0:
		_draw_food(_food)
	if not Engine.is_editor_hint() and (not _alive or _food.x < 0):
		_draw_game_over(origin, board_size)


func _seg_color(i: int) -> Color:
	if i == 0:
		return Color(0.55, 0.98, 0.42, 1)
	var t: float = 1.0
	if _body.size() > 1:
		t = 1.0 - float(i) / float(_body.size())
	return Color(0.12 + 0.38 * t, 0.62 + 0.28 * t, 0.22 + 0.08 * t, 1)


func _cell_center(cell: Vector2i) -> Vector2:
	return Vector2(
		float(PAD_X + cell.x * CELL) + float(CELL) * 0.5,
		float(PAD_Y + cell.y * CELL) + float(CELL) * 0.5
	)


func _draw_link(a: Vector2i, b: Vector2i, fill: Color) -> void:
	draw_line(_cell_center(a), _cell_center(b), fill, 28.0)


func _draw_seg(cell: Vector2i, fill: Color, head: bool) -> void:
	var c: Vector2 = _cell_center(cell)
	var r: float = 18.0 if head else 16.0
	draw_circle(c + Vector2(1.5, 2.5), r, Color(0.02, 0.08, 0.04, 0.35))
	draw_circle(c, r, fill)
	draw_circle(c + Vector2(-5, -6), r * 0.35, Color(1, 1, 1, 0.18))


func _draw_eyes(head: Vector2i) -> void:
	var c: Vector2 = _cell_center(head)
	var along := Vector2(float(_dir.x), float(_dir.y))
	var side := Vector2(float(-_dir.y), float(_dir.x))
	var base: Vector2 = c + along * 8.0
	_draw_eye(base + side * 7.0)
	_draw_eye(base - side * 7.0)


func _draw_eye(pos: Vector2) -> void:
	draw_circle(pos, 4.6, Color(0.95, 0.98, 0.92, 1))
	draw_circle(pos + Vector2(float(_dir.x) * 1.6, float(_dir.y) * 1.6), 2.3, Color(0.05, 0.08, 0.06, 1))


func _draw_tongue(head: Vector2i) -> void:
	if not _alive or _food.x < 0:
		return
	var c: Vector2 = _cell_center(head)
	var along := Vector2(float(_dir.x), float(_dir.y))
	var side := Vector2(float(-_dir.y), float(_dir.x))
	var tip: Vector2 = c + along * 24.0
	draw_line(c + along * 16.0, tip + side * 4.0, Color(0.95, 0.2, 0.28, 1), 2.0)
	draw_line(c + along * 16.0, tip - side * 4.0, Color(0.95, 0.2, 0.28, 1), 2.0)


func _draw_food(cell: Vector2i) -> void:
	var c: Vector2 = _cell_center(cell)
	draw_circle(c + Vector2(2, 3), 15.0, Color(0.15, 0.04, 0.04, 0.4))
	draw_circle(c, 14.5, Color(0.86, 0.14, 0.18, 1))
	draw_circle(c + Vector2(-3, 4), 8.0, Color(0.7, 0.08, 0.12, 1))
	draw_circle(c + Vector2(-5, -5), 4.5, Color(1, 0.55, 0.55, 0.45))
	draw_line(c + Vector2(0, -14), c + Vector2(2, -20), Color(0.35, 0.22, 0.08, 1), 2.4)
	draw_circle(c + Vector2(7, -18), 4.5, Color(0.28, 0.75, 0.32, 1))


func _draw_game_over(origin: Vector2, board_size: Vector2) -> void:
	var banner := Rect2(origin + Vector2(64, board_size.y * 0.36), Vector2(board_size.x - 128, 88))
	var won: bool = _food.x < 0
	draw_rect(banner, Color(0, 0, 0, 0.62), true)
	draw_rect(banner, Color(0.35, 0.88, 0.5, 1) if won else Color(0.95, 0.38, 0.32, 1), false, 3.0)
	var font: Font = ThemeDB.fallback_font
	var title := "YOU WIN" if _food.x < 0 else "GAME OVER"
	var hint := "Enter / Space to retry"
	draw_string(
		font,
		banner.position + Vector2(0, 38),
		title,
		HORIZONTAL_ALIGNMENT_CENTER,
		banner.size.x,
		32,
		Color(1, 0.92, 0.9, 1)
	)
	draw_string(
		font,
		banner.position + Vector2(0, 70),
		hint,
		HORIZONTAL_ALIGNMENT_CENTER,
		banner.size.x,
		18,
		Color(0.85, 0.88, 0.82, 1)
	)

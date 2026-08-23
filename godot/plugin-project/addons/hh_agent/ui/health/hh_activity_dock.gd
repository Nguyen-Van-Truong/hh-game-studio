class_name HHAgentActivityDock
extends VBoxContainer

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _HealthScript: GDScript = preload("res://addons/hh_agent/ui/health/hh_health_dock.gd")
const _OverlayScript: GDScript = preload("res://addons/hh_agent/ui/overlay/hh_overlay.gd")

## Activity dock: health + task/job/elapsed + always-visible Pause/Resume/Watch/Fast/Replay.
## Timeline is virtualized (one page of rows). Never displays the session token.

signal pause_requested
signal pause_on_requested
signal resume_requested
signal mode_changed(mode: String)

var _health: HHAgentHealthDock
var _task: Label
var _agent: Label
var _job: Label
var _elapsed: Label
var _mode_label: Label
var _pause_btn: Button
var _resume_btn: Button
var _watch_btn: Button
var _fast_btn: Button
var _replay_btn: Button
var _timeline_meta: Label
var _list: ItemList
var _plan_meta: Label
var _plan_list: ItemList
var _summary: Label
var _links: Label
var _replay_note: Label

static var _current: HHAgentActivityDock


func _ready() -> void:
	_current = self
	name = "HHAgentActivity"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_theme_constant_override("separation", 6)
	_health = HHAgentHealthDock.new()
	_health.pause_requested.connect(_on_health_pause)
	add_child(_health)
	_task = _add_label("task: idle")
	_agent = _add_label("agent: hh_agent")
	_job = _add_label("job: —")
	_elapsed = _add_label("elapsed: 0 ms")
	_mode_label = _add_label("mode: watch")
	var bar: HBoxContainer = HBoxContainer.new()
	bar.add_theme_constant_override("separation", 6)
	_pause_btn = _add_button(bar, "Pause")
	_resume_btn = _add_button(bar, "Resume")
	_watch_btn = _add_button(bar, "Watch")
	_fast_btn = _add_button(bar, "Fast")
	_replay_btn = _add_button(bar, "Replay")
	_pause_btn.pressed.connect(_on_pause_on)
	_resume_btn.pressed.connect(_on_resume)
	_watch_btn.pressed.connect(_on_watch)
	_fast_btn.pressed.connect(_on_fast)
	_replay_btn.pressed.connect(_on_replay)
	add_child(bar)
	_timeline_meta = _add_label("timeline: 0–0 of 0")
	_list = ItemList.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_list.custom_minimum_size = Vector2(0, 180)
	_list.max_text_lines = 1
	add_child(_list)
	_plan_meta = _add_label("plan cards: 0")
	_plan_list = ItemList.new()
	_plan_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_plan_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_plan_list.custom_minimum_size = Vector2(0, 120)
	_plan_list.max_text_lines = 1
	add_child(_plan_list)
	_summary = _add_label("summary: —")
	_links = _add_label("undo / checkpoint / evidence: —")
	_replay_note = _add_label("Replay: presentation only (does not call the command router)")
	_force_buttons_visible()


func _exit_tree() -> void:
	if _current == self:
		_current = null


static func current() -> HHAgentActivityDock:
	return _current


func plan_list_snapshot() -> Dictionary:
	var items: Array = []
	if _plan_list == null:
		return {"count": 0, "items": items, "bound": false}
	var n: int = _plan_list.item_count
	var i: int = 0
	while i < n:
		items.append(_plan_list.get_item_text(i))
		i += 1
	return {"count": n, "items": items, "bound": true}


func health() -> HHAgentHealthDock:
	return _health


func buttons_visible() -> Dictionary:
	return {
		"pause": _is_visible(_pause_btn),
		"resume": _is_visible(_resume_btn),
		"watch": _is_visible(_watch_btn),
		"fast": _is_visible(_fast_btn),
		"replay": _is_visible(_replay_btn),
	}


func set_status(info: Dictionary) -> void:
	if _health != null:
		_health.set_status(info)
	if _task == null:
		return
	_task.text = "task: %s" % str(info.get("task", "idle"))
	_agent.text = "agent: %s" % str(info.get("agent", "hh_agent"))
	_job.text = "job: %s" % str(info.get("job", "—"))
	_elapsed.text = "elapsed: %s ms" % str(info.get("elapsed_ms", info.get("elapsed", 0)))
	_mode_label.text = "mode: %s" % str(info.get("mode", HHAgentConstants.MODE_WATCH))
	_refresh_page(info)
	_refresh_plan(info)
	_force_buttons_visible()


func _refresh_page(info: Dictionary) -> void:
	if _list == null:
		return
	var dock_v: Variant = info.get("dock", {})
	var dock: Dictionary = dock_v if dock_v is Dictionary else {}
	var rows_v: Variant = dock.get("rows", info.get("rows", {}))
	var rows: Dictionary = rows_v if rows_v is Dictionary else {}
	var items_v: Variant = rows.get("items", [])
	var items: Array = items_v if items_v is Array else []
	if items.size() > HHAgentConstants.MAX_PAGE:
		items = items.slice(0, HHAgentConstants.MAX_PAGE)
	var total: int = int(rows.get("total", items.size()))
	var offset: int = int(rows.get("offset", 0))
	var shown: int = items.size()
	var start_n: int = 0 if shown == 0 else offset + 1
	var end_n: int = offset + shown
	_timeline_meta.text = "timeline: %d–%d of %d" % [start_n, end_n, total]
	_list.clear()
	var i: int = 0
	while i < items.size():
		var item_v: Variant = items[i]
		if item_v is Dictionary:
			var item: Dictionary = item_v
			var line: String = "%s  %s  %s  %s" % [
				str(item.get("status", "")),
				str(item.get("action", "")),
				str(item.get("command_id", "")),
				str(item.get("summary", "")),
			]
			_list.add_item(line)
		i += 1
	if items.is_empty():
		_summary.text = "summary: —"
		_links.text = "undo / checkpoint / evidence: —"
		return
	var last_v: Variant = items[items.size() - 1]
	if last_v is Dictionary:
		var last: Dictionary = last_v
		_summary.text = "summary: %s" % str(last.get("summary", "—"))
		_links.text = "undo / checkpoint / evidence: %s | %s | %s" % [
			str(last.get("undo", "—")),
			str(last.get("checkpoint", "—")),
			str(last.get("evidence", "—")),
		]


func _refresh_plan(info: Dictionary) -> void:
	if _plan_list == null:
		return
	var dock_v: Variant = info.get("dock", {})
	var dock: Dictionary = dock_v if dock_v is Dictionary else {}
	var plan_v: Variant = dock.get("plan", info.get("plan", {}))
	var plan: Dictionary = plan_v if plan_v is Dictionary else {}
	var cards_v: Variant = plan.get("cards", [])
	var cards: Array = cards_v if cards_v is Array else []
	if cards.size() > HHAgentConstants.MAX_PAGE:
		cards = cards.slice(0, HHAgentConstants.MAX_PAGE)
	_plan_meta.text = "plan cards: %d  status=%s" % [int(plan.get("task_count", cards.size())), str(plan.get("status", "—"))]
	_plan_list.clear()
	var i: int = 0
	while i < cards.size():
		var card_v: Variant = cards[i]
		if card_v is Dictionary:
			var card: Dictionary = card_v
			_plan_list.add_item("%s  %s  %s" % [
				str(card.get("kind", "")),
				str(card.get("id", "")),
				str(card.get("summary", "")),
			])
		i += 1


func _force_buttons_visible() -> void:
	if _pause_btn != null:
		_pause_btn.visible = true
	if _resume_btn != null:
		_resume_btn.visible = true
	if _watch_btn != null:
		_watch_btn.visible = true
	if _fast_btn != null:
		_fast_btn.visible = true
	if _replay_btn != null:
		_replay_btn.visible = true
	if _health != null:
		_health.visible = true


func _is_visible(btn: Button) -> bool:
	return btn != null and btn.visible and not btn.text.is_empty()


func _on_health_pause() -> void:
	pause_requested.emit()


func _on_pause_on() -> void:
	pause_on_requested.emit()


func _on_resume() -> void:
	resume_requested.emit()


func _on_watch() -> void:
	mode_changed.emit(HHAgentConstants.MODE_WATCH)


func _on_fast() -> void:
	mode_changed.emit(HHAgentConstants.MODE_FAST)


func _on_replay() -> void:
	var overlay: HHAgentOverlay = HHAgentOverlay.current()
	if overlay != null:
		overlay.replay_last()
	_replay_note.text = "Replay: presentation only (does not call the command router)"


func _add_button(parent: HBoxContainer, text: String) -> Button:
	var btn: Button = Button.new()
	btn.text = text
	btn.visible = true
	parent.add_child(btn)
	return btn


func _add_label(text: String) -> Label:
	var label: Label = Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(label)
	return label

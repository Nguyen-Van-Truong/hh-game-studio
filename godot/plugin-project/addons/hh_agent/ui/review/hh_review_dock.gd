class_name HHAgentReviewDock
extends VBoxContainer

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _OverlayScript: GDScript = preload("res://addons/hh_agent/ui/overlay/hh_overlay.gd")

## Review Center next to Activity Dock: milestone card, before/after/diff, replay, revert.
## Review is async. Pause stays global on the Activity/Health dock.
## Never displays the session token.

signal view_changed(view: String)
signal replay_requested
signal revert_requested

var _title: Label
var _status: Label
var _goal: Label
var _assumptions: Label
var _files: Label
var _tests: Label
var _screenshots: Label
var _perf: Label
var _license: Label
var _gaps: Label
var _checkpoint: Label
var _diff_meta: Label
var _diff_list: ItemList
var _note: Label
var _before_btn: Button
var _after_btn: Button
var _diff_btn: Button
var _replay_btn: Button
var _revert_btn: Button


func _ready() -> void:
	name = "HHAgentReview"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_theme_constant_override("separation", 6)
	_title = _add_label("Review Center")
	_title.add_theme_font_size_override("font_size", 16)
	_status = _add_label("artifact: missing")
	_goal = _add_label("goal: —")
	_assumptions = _add_label("assumptions: —")
	_files = _add_label("files / scenes / assets: —")
	_tests = _add_label("tests: —")
	_screenshots = _add_label("screenshots: —")
	_perf = _add_label("perf: —")
	_license = _add_label("license: —")
	_gaps = _add_label("known gaps: —")
	_checkpoint = _add_label("checkpoint: —")
	var bar: HBoxContainer = HBoxContainer.new()
	bar.add_theme_constant_override("separation", 6)
	_before_btn = _add_button(bar, "Before")
	_after_btn = _add_button(bar, "After")
	_diff_btn = _add_button(bar, "Diff")
	_replay_btn = _add_button(bar, "Replay")
	_revert_btn = _add_button(bar, "Revert checkpoint")
	_before_btn.pressed.connect(_on_before)
	_after_btn.pressed.connect(_on_after)
	_diff_btn.pressed.connect(_on_diff)
	_replay_btn.pressed.connect(_on_replay)
	_revert_btn.pressed.connect(_on_revert)
	add_child(bar)
	_diff_meta = _add_label("diff: 0–0 of 0")
	_diff_list = ItemList.new()
	_diff_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_diff_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_diff_list.custom_minimum_size = Vector2(0, 120)
	_diff_list.max_text_lines = 1
	add_child(_diff_list)
	_note = _add_label("Review is async. Agent continues allowed work. Pause is global. Replay is presentation only.")
	_force_buttons_visible()


func buttons_visible() -> Dictionary:
	return {
		"before": _is_visible(_before_btn),
		"after": _is_visible(_after_btn),
		"diff": _is_visible(_diff_btn),
		"replay": _is_visible(_replay_btn),
		"revert": _is_visible(_revert_btn),
	}


func set_status(info: Dictionary) -> void:
	if _goal == null:
		return
	var ok: bool = info.get("artifact_ok", false) == true
	if ok:
		_status.text = "artifact: ok"
	else:
		var err_v: Variant = info.get("error", {})
		var code: String = ""
		if err_v is Dictionary:
			code = str((err_v as Dictionary).get("code", ""))
		_status.text = "artifact: missing/corrupt %s" % code
	_goal.text = "goal: %s" % _dash(info.get("goal", ""))
	_assumptions.text = "assumptions: %s" % _join(info.get("assumptions", []))
	_files.text = "files / scenes / assets: %s | %s | %s" % [
		_join(info.get("files", [])),
		_join(info.get("scenes", [])),
		_join(info.get("assets", [])),
	]
	_tests.text = "tests: %s" % _join(info.get("tests", []))
	_screenshots.text = "screenshots: %s" % _screenshot_line(info.get("screenshots", []))
	var perf_v: Variant = info.get("perf", {})
	if perf_v is Dictionary:
		_perf.text = "perf: %s" % str((perf_v as Dictionary).get("notes", perf_v))
	else:
		_perf.text = "perf: %s" % _dash(perf_v)
	_license.text = "license: %s" % _dash(info.get("license", ""))
	_gaps.text = "known gaps: %s" % _join(info.get("gaps", info.get("known_gaps", [])))
	var ckpt_v: Variant = info.get("checkpoint", {})
	if ckpt_v is Dictionary:
		var ckpt: Dictionary = ckpt_v
		_checkpoint.text = "checkpoint: %s dest_sha=%s" % [
			_dash(ckpt.get("id", ckpt.get("ref", ""))),
			_dash(ckpt.get("dest_sha", "")),
		]
	else:
		_checkpoint.text = "checkpoint: %s" % _dash(ckpt_v)
	_refresh_diff(info)
	_force_buttons_visible()


func _refresh_diff(info: Dictionary) -> void:
	if _diff_list == null:
		return
	var diff_v: Variant = info.get("diff", {})
	var diff: Dictionary = diff_v if diff_v is Dictionary else {}
	var items_v: Variant = diff.get("items", [])
	var items: Array = items_v if items_v is Array else []
	if items.size() > HHAgentConstants.REVIEW_DIFF_CAP:
		items = items.slice(0, HHAgentConstants.REVIEW_DIFF_CAP)
	var total: int = int(diff.get("total", items.size()))
	var offset: int = int(diff.get("offset", 0))
	var shown: int = items.size()
	var start_n: int = 0 if shown == 0 else offset + 1
	_diff_meta.text = "diff: %d–%d of %d" % [start_n, offset + shown, total]
	_diff_list.clear()
	var i: int = 0
	while i < items.size():
		_diff_list.add_item(str(items[i]))
		i += 1


func _screenshot_line(raw: Variant) -> String:
	if not (raw is Array) or (raw as Array).is_empty():
		return "none listed"
	var parts: PackedStringArray = PackedStringArray()
	for item_v: Variant in raw:
		if item_v is Dictionary:
			var item: Dictionary = item_v
			var status_s: String = str(item.get("status", "missing"))
			parts.append("%s (%s)" % [str(item.get("path", "")), status_s])
		else:
			parts.append(str(item_v))
	return ", ".join(parts)


func _force_buttons_visible() -> void:
	if _before_btn != null:
		_before_btn.visible = true
	if _after_btn != null:
		_after_btn.visible = true
	if _diff_btn != null:
		_diff_btn.visible = true
	if _replay_btn != null:
		_replay_btn.visible = true
	if _revert_btn != null:
		_revert_btn.visible = true


func _is_visible(btn: Button) -> bool:
	return btn != null and btn.visible and not btn.text.is_empty()


func _on_before() -> void:
	view_changed.emit("before")


func _on_after() -> void:
	view_changed.emit("after")


func _on_diff() -> void:
	view_changed.emit("diff")


func _on_replay() -> void:
	var overlay: HHAgentOverlay = HHAgentOverlay.current()
	if overlay != null:
		overlay.replay_last()
	replay_requested.emit()


func _on_revert() -> void:
	revert_requested.emit()


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


func _dash(raw: Variant) -> String:
	var text: String = str(raw)
	if text.is_empty():
		return "—"
	return text


func _join(raw: Variant) -> String:
	var items: Array = raw if raw is Array else []
	if items.is_empty():
		return "—"
	var parts: PackedStringArray = PackedStringArray()
	for item_v: Variant in items:
		parts.append(str(item_v))
	return ", ".join(parts)

class_name HHAgentScheduler
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _PresenterScript: GDScript = preload("res://addons/hh_agent/core/hh_presenter.gd")
const _OverlayScript: GDScript = preload("res://addons/hh_agent/ui/overlay/hh_overlay.gd")
const _StoreScript: GDScript = preload("res://addons/hh_agent/core/hh_activity_store.gd")

## Presentation scheduler. Queues overlay/present OFF the mutation ACK path.
## Coalesces spam property/cell presents (last-write-wins). Drops PRESENT frames
## only under backpressure. Never drops audit/mutation/ledger rows.

static var _current: HHAgentScheduler

var _presenter: HHAgentPresenter = HHAgentPresenter.new()
var _mode: String = HHAgentConstants.MODE_WATCH
var _queue: Array[Dictionary] = []
var _events: Array[Dictionary] = []
var _dropped_present: int = 0
var _dropped_audit: int = 0
var _coalesced: int = 0
var _applied_present: int = 0
var _focus_id: String = ""
var _lanes: Dictionary = {}
var _idle_ms: float = 0.0


static func current() -> HHAgentScheduler:
	return _current


func attach() -> void:
	_current = self
	_ensure_lane(HHAgentConstants.OBSERVER_ACTOR)


func detach() -> void:
	if _current == self:
		_current = null
	_queue.clear()
	_events.clear()
	_lanes.clear()
	_focus_id = ""


func set_mode(mode: String) -> void:
	if mode == HHAgentConstants.MODE_FAST:
		_mode = HHAgentConstants.MODE_FAST
		_abandon_present_queue()
	else:
		_mode = HHAgentConstants.MODE_WATCH


func mode() -> String:
	return _mode


func after_success(
	result: Dictionary,
	method: String,
	action: String,
	params: Dictionary,
	envelope: Dictionary,
) -> Dictionary:
	_sync_mode(envelope)
	if result.get("ok", false) != true:
		return result
	var overlay: HHAgentOverlay = _overlay()
	if overlay == null or not overlay.is_presentable_mutate(method, action):
		return result
	var record: Dictionary = overlay.event_from_mutate(method, action, params, result)
	if record.is_empty():
		return result
	var actor: String = _actor_of(params)
	record["actor"] = actor
	record["color"] = str(_ensure_lane(actor).get("color", HHAgentConstants.LANE_COLOR_AGENT))
	overlay.record_event(record)
	_append_event(record)
	if _mode == HHAgentConstants.MODE_FAST or _mode_of(envelope) == HHAgentConstants.MODE_FAST:
		return result
	var frame: Dictionary = {
		"command_id": str(record.get("command_id", result.get("command_id", ""))),
		"coalesce_key": _coalesce_key(method, action, params),
		"hint": _presenter.hint_from_mutation(method, action, params, result),
		"record": record,
		"envelope": envelope.duplicate(true),
		"actor": actor,
		"method": method,
		"action": action,
	}
	_enqueue_present(frame)
	return result


func tick(delta: float, inbound_this_frame: bool) -> void:
	if inbound_this_frame:
		return
	if _mode != HHAgentConstants.MODE_WATCH:
		return
	_idle_ms += delta * 1000.0
	var overlay: HHAgentOverlay = _overlay()
	if overlay != null and overlay.is_animating():
		return
	if _applied_present > 0 and _idle_ms < float(HHAgentConstants.WATCH_STEP_MS):
		return
	if _queue.is_empty():
		return
	var frame: Dictionary = _queue.pop_front()
	_apply_frame(frame, true)
	_idle_ms = 0.0


func flush_model() -> void:
	var record: Dictionary = {}
	var actor: String = HHAgentConstants.OBSERVER_ACTOR
	var focus: String = ""
	if not _queue.is_empty():
		var frame: Dictionary = _queue[_queue.size() - 1]
		var rec_v: Variant = frame.get("record", {})
		if rec_v is Dictionary:
			record = rec_v
		actor = str(frame.get("actor", actor))
		focus = str(frame.get("command_id", ""))
	else:
		var overlay: HHAgentOverlay = _overlay()
		if overlay != null:
			record = overlay.last_event()
			actor = str(record.get("actor", actor))
			focus = str(record.get("command_id", ""))
	if record.is_empty():
		return
	_present_overlay(record, actor, focus, false, {})


func stress(count: int, unique_keys: bool) -> Dictionary:
	var n: int = count
	if n < 0:
		n = 0
	if n > HHAgentConstants.OBSERVER_RETENTION:
		n = HHAgentConstants.OBSERVER_RETENTION
	var overlay: HHAgentOverlay = _overlay()
	var i: int = 0
	while i < n:
		var actor: String = HHAgentConstants.OBSERVER_ACTOR
		if i % 2 == 1:
			actor = "peer"
		var cell_x: int = i % 100
		var cell_y: int = int(i / 100)
		if not unique_keys:
			cell_x = 0
			cell_y = 0
		var command_id: String = "01R4WP4STRESS%012d" % i
		var path_s: String = "Cell"
		var key: String = "c|res://r4w4/sched.tscn|%s|%d,%d" % [path_s, cell_x, cell_y]
		var record: Dictionary = {
			"command_id": command_id,
			"action": "tilemap.cell",
			"method": "godot.tilemap",
			"scene": "res://r4w4/sched.tscn",
			"path": path_s,
			"uid": "",
			"label": "cell %d,%d" % [cell_x, cell_y],
			"kind": "cell",
			"property": "cell",
			"actor": actor,
			"color": str(_ensure_lane(actor).get("color", HHAgentConstants.LANE_COLOR_AGENT)),
			"start": Vector2(float(cell_x), float(cell_y)),
			"end": Vector2(float(cell_x), float(cell_y)),
		}
		if overlay != null:
			overlay.record_event(record)
		_append_event(record)
		_enqueue_present({
			"command_id": command_id,
			"coalesce_key": key,
			"hint": {},
			"record": record,
			"envelope": {"presentation": {"mode": _mode}},
			"actor": actor,
			"method": "godot.tilemap",
			"action": "cell",
		})
		i += 1
	return snapshot()


func replay_from_log(command_id: String, envelope: Dictionary) -> Dictionary:
	var overlay: HHAgentOverlay = _overlay()
	if overlay == null:
		return {"ok": true, "drawn": false, "walked": 0}
	var record: Dictionary = {}
	var i: int = _events.size() - 1
	while i >= 0:
		var item: Dictionary = _events[i]
		if command_id.is_empty() or str(item.get("command_id", "")) == command_id:
			record = item
			break
		i -= 1
	if record.is_empty():
		record = overlay.last_event()
	if record.is_empty():
		return {"ok": true, "drawn": false, "walked": _events.size()}
	var actor: String = str(record.get("actor", HHAgentConstants.OBSERVER_ACTOR))
	var start_anim: bool = _mode == HHAgentConstants.MODE_WATCH
	_present_overlay(record, actor, str(record.get("command_id", "")), start_anim, envelope)
	return {
		"ok": true,
		"drawn": start_anim and overlay.is_draw_enabled_for(envelope),
		"walked": _events.size(),
		"command_id": str(record.get("command_id", "")),
	}


func snapshot() -> Dictionary:
	return _redact({
		"mode": _mode,
		"queue_depth": _queue.size(),
		"dropped_present": _dropped_present,
		"dropped_audit": _dropped_audit,
		"coalesced": _coalesced,
		"applied_present": _applied_present,
		"focus_id": _focus_id,
		"lanes": _lanes_json(),
		"event_count": _events.size(),
	})


func _enqueue_present(frame: Dictionary) -> void:
	var key: String = str(frame.get("coalesce_key", ""))
	if not key.is_empty():
		var i: int = _queue.size() - 1
		while i >= 0:
			if str(_queue[i].get("coalesce_key", "")) == key:
				_queue[i] = frame
				_coalesced += 1
				return
			i -= 1
	_queue.append(frame)
	while _queue.size() > HHAgentConstants.PRESENT_QUEUE_CAP:
		_queue.pop_front()
		_dropped_present += 1


func _abandon_present_queue() -> void:
	var n: int = _queue.size()
	if n <= 0:
		return
	_dropped_present += n
	_queue.clear()


func _apply_frame(frame: Dictionary, start_anim: bool) -> void:
	var record_v: Variant = frame.get("record", {})
	var record: Dictionary = record_v if record_v is Dictionary else {}
	var actor: String = str(frame.get("actor", HHAgentConstants.OBSERVER_ACTOR))
	var focus: String = str(frame.get("command_id", ""))
	var env_v: Variant = frame.get("envelope", {})
	var envelope: Dictionary = env_v if env_v is Dictionary else {}
	_present_overlay(record, actor, focus, start_anim, envelope)
	var hint_v: Variant = frame.get("hint", {})
	if hint_v is Dictionary and not (hint_v as Dictionary).is_empty():
		_presenter.apply_presentation(hint_v as Dictionary, envelope, false)
	_applied_present += 1


func _present_overlay(
	record: Dictionary,
	actor: String,
	focus: String,
	start_anim: bool,
	envelope: Dictionary,
) -> void:
	var overlay: HHAgentOverlay = _overlay()
	if overlay == null:
		return
	overlay.clear_focus()
	_set_only_focus(actor, focus)
	var color: String = str(record.get("color", _ensure_lane(actor).get("color", "")))
	overlay.set_lane_color(color)
	overlay.apply_event(record, start_anim, envelope)


func _set_only_focus(actor: String, focus: String) -> void:
	_ensure_lane(actor)
	for key_v: Variant in _lanes.keys():
		var key: String = str(key_v)
		var lane_v: Variant = _lanes[key]
		if lane_v is Dictionary:
			var lane: Dictionary = lane_v
			lane["focus"] = key == actor
			_lanes[key] = lane
	_focus_id = focus


func _ensure_lane(actor: String) -> Dictionary:
	var id_s: String = actor if not actor.is_empty() else HHAgentConstants.OBSERVER_ACTOR
	if _lanes.has(id_s):
		var existing_v: Variant = _lanes[id_s]
		if existing_v is Dictionary:
			return existing_v
	var color: String = HHAgentConstants.LANE_COLOR_AGENT
	var n: int = _lanes.size()
	if n == 1:
		color = HHAgentConstants.LANE_COLOR_PEER
	elif n == 2:
		color = HHAgentConstants.LANE_COLOR_C
	elif n >= 3:
		color = HHAgentConstants.LANE_COLOR_D
	var lane: Dictionary = {"id": id_s, "color": color, "focus": false}
	_lanes[id_s] = lane
	return lane


func _lanes_json() -> Array:
	var out: Array = []
	for key_v: Variant in _lanes.keys():
		var lane_v: Variant = _lanes[str(key_v)]
		if lane_v is Dictionary:
			out.append((lane_v as Dictionary).duplicate(true))
	return out


func _append_event(record: Dictionary) -> void:
	_events.append(record.duplicate(true))


func _coalesce_key(method: String, action: String, params: Dictionary) -> String:
	if method == "godot.property" and (action == "set" or action == "batch"):
		return "p|%s|%s|%s" % [
			str(params.get("scene", "")),
			str(params.get("node_path", "")),
			str(params.get("property", "")),
		]
	if method == "godot.tilemap":
		return "c|%s|%s|%s,%s" % [
			str(params.get("scene", "")),
			str(params.get("node_path", "")),
			str(params.get("x", "")),
			str(params.get("y", "")),
		]
	return ""


func _actor_of(params: Dictionary) -> String:
	var actor: String = str(params.get("actor", ""))
	if actor.is_empty():
		return HHAgentConstants.OBSERVER_ACTOR
	return actor


func _sync_mode(envelope: Dictionary) -> void:
	var mode_s: String = _mode_of(envelope)
	if mode_s.is_empty():
		return
	set_mode(mode_s)
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store != null:
		store.set_mode(mode_s)
	var overlay: HHAgentOverlay = _overlay()
	if overlay != null:
		overlay.set_mode(mode_s)


func _mode_of(envelope: Dictionary) -> String:
	var pres_v: Variant = envelope.get("presentation", {})
	if pres_v is Dictionary:
		var mode_s: String = str((pres_v as Dictionary).get("mode", ""))
		if mode_s == HHAgentConstants.MODE_FAST:
			return HHAgentConstants.MODE_FAST
		if mode_s == HHAgentConstants.MODE_WATCH:
			return HHAgentConstants.MODE_WATCH
	return ""


func _overlay() -> HHAgentOverlay:
	return HHAgentOverlay.current()


func _redact(after: Dictionary) -> Dictionary:
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store == null:
		return after
	var text: String = JSON.stringify(after)
	var cleaned: String = store.redact_text(text)
	if cleaned == text:
		return after
	var parsed: Variant = JSON.parse_string(cleaned)
	if parsed is Dictionary:
		return parsed
	return after

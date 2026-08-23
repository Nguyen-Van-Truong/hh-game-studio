class_name HHAgentActivityStore
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")

## In-memory ring of observer rows. Persist last N under .hh-agent/observer/.
## Never stores or returns the session token (A8).

static var _current: HHAgentActivityStore

var _rows: Array[Dictionary] = []
var _secrets: PackedStringArray = PackedStringArray()
var _session_prefixes: PackedStringArray = PackedStringArray()
var _task: String = "idle"
var _agent: String = "hh_agent"
var _policy: String = HHAgentConstants.POLICY_DISPLAY
var _queue: int = 0
var _job: String = "—"
var _elapsed_ms: int = 0
var _pause: String = "inactive"
var _mode: String = HHAgentConstants.MODE_WATCH
var _replay_code: String = ""
var _plan: Dictionary = {}
var _orch: Dictionary = {}
var _session_re: RegEx = RegEx.new()
var _bearer_re: RegEx = RegEx.new()


static func current() -> HHAgentActivityStore:
	return _current


func attach() -> void:
	_current = self


func detach() -> void:
	if _current == self:
		_current = null


func _init() -> void:
	var sess_err: Error = _session_re.compile("(?i)HHGodotAgent[/\\\\]sessions[/\\\\][^\\s\"']+")
	if sess_err != OK:
		push_warning("hh_agent: observer session-path regex failed")
	var bear_err: Error = _bearer_re.compile("(?i)bearer\\s+[A-Za-z0-9._\\-]+")
	if bear_err != OK:
		push_warning("hh_agent: observer bearer regex failed")
	_prime_session_prefixes()


func add_secret(secret: String) -> void:
	if secret.is_empty():
		return
	if secret.length() < 8:
		return
	for existing: String in _secrets:
		if existing == secret:
			return
	_secrets.append(secret)


func set_runtime(info: Dictionary) -> void:
	if info.has("task"):
		_task = redact_text(str(info.get("task", "idle")))
	if info.has("agent"):
		_agent = redact_text(str(info.get("agent", "hh_agent")))
	if info.has("policy"):
		_policy = redact_text(str(info.get("policy", HHAgentConstants.POLICY_DISPLAY)))
	if info.has("queue"):
		_queue = int(info.get("queue", 0))
	if info.has("job"):
		_job = redact_text(str(info.get("job", "—")))
	if info.has("elapsed_ms"):
		_elapsed_ms = int(info.get("elapsed_ms", 0))
	if info.has("pause"):
		_pause = str(info.get("pause", "inactive"))


func set_mode(mode: String) -> void:
	if mode == HHAgentConstants.MODE_FAST:
		_mode = HHAgentConstants.MODE_FAST
	else:
		_mode = HHAgentConstants.MODE_WATCH


func mode() -> String:
	return _mode


func mark_replay_unverified() -> void:
	_replay_code = "E_UNVERIFIED"


func mark_replay_ready() -> void:
	_replay_code = ""


func set_plan(plan: Dictionary) -> void:
	_plan = plan.duplicate(true)
	_task = "job.plan"
	if plan.has("run_id"):
		_job = redact_text(str(plan.get("run_id", _job)))


func set_orch(view: Dictionary) -> void:
	_orch = view.duplicate(true)
	_task = "job.run"
	if view.has("job_id"):
		_job = redact_text(str(view.get("job_id", _job)))


func orch_snapshot() -> Dictionary:
	return {
		"job_id": redact_text(str(_orch.get("job_id", ""))),
		"state": str(_orch.get("state", "")),
		"current_task_id": str(_orch.get("current_task_id", "")),
		"blocked_reason": str(_orch.get("blocked_reason", "")),
		"cancelled": _orch.get("cancelled", false) == true,
		"fixture": str(_orch.get("fixture", "")),
	}


func plan_snapshot() -> Dictionary:
	var cards_v: Variant = _plan.get("cards", [])
	var cards: Array = cards_v if cards_v is Array else []
	var shown: Array = cards
	if shown.size() > HHAgentConstants.MAX_PAGE:
		shown = shown.slice(0, HHAgentConstants.MAX_PAGE)
	return {
		"run_id": redact_text(str(_plan.get("run_id", ""))),
		"status": str(_plan.get("status", "")),
		"complete": _plan.get("complete", false) == true,
		"acyclic": _plan.get("acyclic", false) == true,
		"task_count": int(_plan.get("tasks", []).size()) if _plan.get("tasks", []) is Array else 0,
		"blocker_count": int(_plan.get("blockers", []).size()) if _plan.get("blockers", []) is Array else 0,
		"cards": shown,
	}


func record_planned(row: Dictionary) -> void:
	var next_row: Dictionary = _normalize_row(row, HHAgentConstants.STATUS_PLANNED)
	_upsert(next_row, false)
	_task = str(next_row.get("action", _task))
	_job = str(next_row.get("command_id", _job))


func settle(row: Dictionary) -> void:
	var status: String = str(row.get("status", ""))
	if status != HHAgentConstants.STATUS_VERIFIED and status != HHAgentConstants.STATUS_FAILED:
		if row.get("ok", false) == true:
			status = HHAgentConstants.STATUS_VERIFIED
		else:
			status = HHAgentConstants.STATUS_FAILED
	var next_row: Dictionary = _normalize_row(row, status)
	_upsert(next_row, true)
	_task = str(next_row.get("action", _task))
	_job = str(next_row.get("command_id", _job))
	_elapsed_ms = int(next_row.get("elapsed_ms", _elapsed_ms))


func append_synthetic(count: int, actor: String = "", scene: String = "") -> int:
	var n: int = count
	if n < 1:
		return 0
	if n > HHAgentConstants.OBSERVER_RETENTION:
		n = HHAgentConstants.OBSERVER_RETENTION
	var actor_s: String = actor if not actor.is_empty() else HHAgentConstants.OBSERVER_ACTOR
	var scene_s: String = scene
	var i: int = 0
	while i < n:
		_rows.append({
			"command_id": "01R4WP1SYNTH%012d" % i,
			"action": "observer.append",
			"method": "godot.observer",
			"status": HHAgentConstants.STATUS_VERIFIED,
			"scene": scene_s,
			"actor": actor_s,
			"elapsed_ms": 0,
			"summary": "synthetic %d" % i,
			"diff": "",
			"undo": "",
			"checkpoint": "",
			"evidence": "",
			"error": "",
		})
		i += 1
	_trim()
	persist()
	return n


func reload_from_disk() -> int:
	var loaded: Dictionary = _read_persisted()
	if loaded.get("ok", false) != true:
		return _rows.size()
	var rows_v: Variant = loaded.get("rows", [])
	if rows_v is Array:
		var next_rows: Array[Dictionary] = []
		for item_v: Variant in rows_v:
			if item_v is Dictionary:
				next_rows.append(item_v as Dictionary)
		_rows = next_rows
	var mode_s: String = str(loaded.get("mode", _mode))
	if mode_s == HHAgentConstants.MODE_FAST or mode_s == HHAgentConstants.MODE_WATCH:
		_mode = mode_s
	_trim()
	return _rows.size()


func load_from_disk() -> int:
	var loaded: Dictionary = _read_persisted()
	if loaded.get("ok", false) != true:
		return 0
	var rows_v: Variant = loaded.get("rows", [])
	if rows_v is Array:
		for item_v: Variant in rows_v:
			if item_v is Dictionary:
				_upsert(item_v as Dictionary, false)
	var mode_s: String = str(loaded.get("mode", _mode))
	if mode_s == HHAgentConstants.MODE_FAST or mode_s == HHAgentConstants.MODE_WATCH:
		_mode = mode_s
	_trim()
	return _rows.size()


func persist() -> bool:
	var dest: String = _persist_path()
	if dest.is_empty():
		return false
	var dir_path: String = dest.get_base_dir()
	var mk: Error = DirAccess.make_dir_recursive_absolute(dir_path)
	if mk != OK and not DirAccess.dir_exists_absolute(dir_path):
		return false
	_ensure_gdignore(dir_path)
	var tmp: String = dest + ".tmp"
	var bak: String = dest + ".bak"
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp)
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return false
	var header: Dictionary = {
		"schema": HHAgentConstants.OBSERVER_SCHEMA,
		"mode": _mode,
		"task": redact_text(_task),
		"agent": redact_text(_agent),
		"count": _rows.size(),
	}
	f.store_line(_redact_json(JSON.stringify(header)))
	for row: Dictionary in _rows:
		f.store_line(_redact_json(JSON.stringify(_plain_row(row))))
	f.flush()
	f.close()
	if FileAccess.file_exists(dest):
		if FileAccess.file_exists(bak):
			DirAccess.remove_absolute(bak)
		var park: Error = DirAccess.rename_absolute(dest, bak)
		if park != OK:
			DirAccess.remove_absolute(tmp)
			return false
	var ren: Error = DirAccess.rename_absolute(tmp, dest)
	if ren != OK:
		if FileAccess.file_exists(bak):
			DirAccess.rename_absolute(bak, dest)
		DirAccess.remove_absolute(tmp)
		return false
	if FileAccess.file_exists(bak):
		DirAccess.remove_absolute(bak)
	return true


func _read_persisted() -> Dictionary:
	var dest: String = _persist_path()
	if dest.is_empty() or not FileAccess.file_exists(dest):
		return {"ok": false}
	var f: FileAccess = FileAccess.open(dest, FileAccess.READ)
	if f == null:
		return {"ok": false}
	var header_line: String = f.get_line()
	var header_v: Variant = JSON.parse_string(header_line)
	if typeof(header_v) != TYPE_DICTIONARY:
		f.close()
		return {"ok": false}
	var header: Dictionary = header_v
	if str(header.get("schema", "")) != HHAgentConstants.OBSERVER_SCHEMA:
		f.close()
		return {"ok": false}
	var dest_rows: Array[Dictionary] = []
	while not f.eof_reached():
		var line: String = f.get_line()
		if line.is_empty():
			continue
		var parsed: Variant = JSON.parse_string(line)
		if parsed is Dictionary:
			dest_rows.append(_normalize_row(parsed as Dictionary, str((parsed as Dictionary).get("status", HHAgentConstants.STATUS_VERIFIED))))
	f.close()
	return {"ok": true, "mode": str(header.get("mode", "")), "rows": dest_rows}


func _redact_json(text: String) -> String:
	var out: String = text
	for secret: String in _secrets:
		if secret.is_empty():
			continue
		if out.contains(secret):
			out = out.replace(secret, "[redacted]")
	return out


func _plain_row(row: Dictionary) -> Dictionary:
	return {
		"command_id": str(row.get("command_id", "")),
		"action": str(row.get("action", "")),
		"method": str(row.get("method", "")),
		"status": str(row.get("status", "")),
		"scene": str(row.get("scene", "")),
		"actor": str(row.get("actor", "")),
		"elapsed_ms": int(row.get("elapsed_ms", 0)),
		"summary": str(row.get("summary", "")),
		"diff": str(row.get("diff", "")),
		"undo": str(row.get("undo", "")),
		"checkpoint": str(row.get("checkpoint", "")),
		"evidence": str(row.get("evidence", "")),
		"error": str(row.get("error", "")),
	}


func snapshot(params: Dictionary) -> Dictionary:
	if params.get("reload", false) == true:
		reload_from_disk()
	var filtered: Array[Dictionary] = _filter_rows(params)
	var page: Dictionary = _page(filtered, params)
	return {
		"task": redact_text(_task),
		"agent": redact_text(_agent),
		"policy": redact_text(_policy),
		"queue": _queue,
		"job": redact_text(_job),
		"elapsed": _elapsed_ms,
		"elapsed_ms": _elapsed_ms,
		"pause": _pause,
		"mode": _mode,
		"modes": {
			"watch": true,
			"fast": true,
			"replay": true,
		},
		"buttons": {
			"pause": {"visible": true, "label": "Pause"},
			"resume": {"visible": true, "label": "Resume"},
			"watch": {"visible": true, "label": "Watch"},
			"fast": {"visible": true, "label": "Fast"},
			"replay": {"visible": true, "label": "Replay", "ready": _replay_code.is_empty(), "code": _replay_code},
		},
		"rows": page,
		"filters": {
			"actor": str(params.get("actor", "")),
			"scene": str(params.get("scene", "")),
			"status": str(params.get("status", "")),
		},
		"replay": {
			"ready": _replay_code.is_empty(),
			"code": _replay_code,
			"message": "replay is presentation-only; does not call the command router",
		},
		"plan": plan_snapshot(),
		"orch": orch_snapshot(),
	}


func last_command_ids(limit: int) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var n: int = _rows.size()
	var take: int = limit
	if take < 1:
		return out
	var i: int = maxi(0, n - take)
	while i < n:
		out.append(str(_rows[i].get("command_id", "")))
		i += 1
	return out


func row_count() -> int:
	return _rows.size()


func redact_text(text: String) -> String:
	var out: String = text
	for secret: String in _secrets:
		if secret.is_empty():
			continue
		if out.contains(secret):
			out = out.replace(secret, "[redacted]")
	for prefix: String in _session_prefixes:
		if prefix.is_empty():
			continue
		if out.contains(prefix):
			out = out.replace(prefix, "[redacted-session-path]")
	if _session_re.is_valid():
		out = _session_re.sub(out, "[redacted-session-path]", true)
	if _bearer_re.is_valid():
		out = _bearer_re.sub(out, "[redacted-bearer]", true)
	return out


func _prime_session_prefixes() -> void:
	var local: String = OS.get_environment("LOCALAPPDATA")
	if local.is_empty():
		return
	var prefix: String = local.replace("\\", "/") + "/HHGodotAgent/sessions"
	_session_prefixes.append(prefix)
	_session_prefixes.append(local + "\\HHGodotAgent\\sessions")


func _persist_path() -> String:
	var root: String = ProjectSettings.globalize_path("res://").rstrip("/\\")
	if root.is_empty():
		return ""
	return root.path_join(".hh-agent").path_join("observer").path_join(HHAgentConstants.OBSERVER_FILE)


func _normalize_row(row: Dictionary, status: String) -> Dictionary:
	var out: Dictionary = {
		"command_id": redact_text(str(row.get("command_id", ""))),
		"action": redact_text(str(row.get("action", ""))),
		"method": redact_text(str(row.get("method", ""))),
		"status": status,
		"scene": redact_text(str(row.get("scene", ""))),
		"actor": redact_text(str(row.get("actor", HHAgentConstants.OBSERVER_ACTOR))),
		"elapsed_ms": int(row.get("elapsed_ms", 0)),
		"summary": redact_text(str(row.get("summary", ""))),
		"diff": redact_text(str(row.get("diff", ""))),
		"undo": redact_text(str(row.get("undo", ""))),
		"checkpoint": redact_text(str(row.get("checkpoint", ""))),
		"evidence": redact_text(str(row.get("evidence", ""))),
		"error": redact_text(str(row.get("error", ""))),
	}
	if str(out.get("actor", "")).is_empty():
		out["actor"] = HHAgentConstants.OBSERVER_ACTOR
	return out


func _upsert(row: Dictionary, persist_now: bool) -> void:
	var command_id: String = str(row.get("command_id", ""))
	if command_id.is_empty():
		return
	var i: int = _rows.size() - 1
	while i >= 0:
		if str(_rows[i].get("command_id", "")) == command_id:
			_rows[i] = row
			_trim()
			if persist_now:
				persist()
			return
		i -= 1
	_rows.append(row)
	_trim()
	if persist_now:
		persist()


func _trim() -> void:
	var overflow: int = _rows.size() - HHAgentConstants.OBSERVER_RETENTION
	if overflow <= 0:
		return
	_rows = _rows.slice(overflow)


func _ensure_gdignore(dir_path: String) -> void:
	var ignore_path: String = dir_path.path_join(".gdignore")
	if FileAccess.file_exists(ignore_path):
		return
	var f: FileAccess = FileAccess.open(ignore_path, FileAccess.WRITE)
	if f == null:
		return
	f.store_string("\n")
	f.flush()
	f.close()


func _filter_rows(params: Dictionary) -> Array[Dictionary]:
	var actor: String = str(params.get("actor", ""))
	var scene: String = str(params.get("scene", ""))
	var status: String = str(params.get("status", ""))
	if actor.is_empty() and scene.is_empty() and status.is_empty():
		return _rows
	var out: Array[Dictionary] = []
	for row: Dictionary in _rows:
		if not actor.is_empty() and str(row.get("actor", "")) != actor:
			continue
		if not scene.is_empty() and str(row.get("scene", "")) != scene:
			continue
		if not status.is_empty() and str(row.get("status", "")) != status:
			continue
		out.append(row)
	return out


func _page(items: Array[Dictionary], params: Dictionary) -> Dictionary:
	var limit: int = HHAgentConstants.DEFAULT_PAGE
	if params.has("limit"):
		limit = int(params.get("limit"))
	if limit < 1:
		limit = 1
	if limit > HHAgentConstants.MAX_PAGE:
		limit = HHAgentConstants.MAX_PAGE
	var offset: int = 0
	if params.has("cursor"):
		var raw: String = str(params.get("cursor"))
		if raw.is_valid_int():
			offset = maxi(0, int(raw))
	var total: int = items.size()
	var end: int = mini(offset + limit, total)
	var page: Array = []
	var i: int = offset
	while i < end:
		page.append(items[i].duplicate(true))
		i += 1
	var next_cursor: String = ""
	if end < total:
		next_cursor = str(end)
	return {
		"items": page,
		"total": total,
		"offset": offset,
		"limit": limit,
		"next_cursor": next_cursor,
		"has_more": end < total,
	}

class_name HHAgentSoakAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")

## Jailed r7w5 state resource. Sidecar compact is the writer; plugin reads status.

static var _current: HHAgentSoakAdapter

var _errors: HHAgentErrors = HHAgentErrors.new()


static func current() -> HHAgentSoakAdapter:
	return _current


func attach() -> void:
	_current = self


func detach() -> void:
	if _current == self:
		_current = null


func shutdown() -> void:
	detach()


func handles(action: String) -> bool:
	return action == "compact"


func exists(job_id: String) -> bool:
	if not _job_id_ok(job_id):
		return false
	var jailed: Dictionary = _jail("%s/%s/state.json" % [HHAgentConstants.SOAK_DIR, job_id])
	if jailed.get("ok", false) != true:
		return false
	return FileAccess.file_exists(str(jailed.get("abs", "")))


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	_actions: HHAgentActions,
	_precondition: Dictionary,
) -> Dictionary:
	if method != "godot.job":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a soak verb", "")
	if action == "status":
		return _status(command_id, params)
	if action != "compact":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a soak verb", "")
	return _compact(command_id, params)


func _now_ms() -> int:
	return int(Time.get_unix_time_from_system() * 1000.0)


func _job_id_ok(job_id: String) -> bool:
	if job_id.is_empty() or job_id.length() > 64:
		return false
	var re: RegEx = RegEx.new()
	if re.compile("^[A-Za-z0-9_-]+$") != OK:
		return false
	return re.search(job_id) != null


func _jail(rel: String) -> Dictionary:
	var p: String = rel.replace("\\", "/").strip_edges()
	if p.contains("..") or p.contains("addons/") or p.begins_with(".hh-agent") or p.contains("/.hh-agent"):
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "soak path escapes jail", "path": rel}
	if not p.begins_with("%s/" % HHAgentConstants.SOAK_DIR):
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "soak writes only under r7w5/", "path": rel}
	var res_path: String = "res://%s" % p
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	var root: String = ProjectSettings.globalize_path("res://").replace("\\", "/").rstrip("/")
	if not abs_path.replace("\\", "/").begins_with(root):
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "soak path leaves project", "path": rel}
	return {"ok": true, "abs": abs_path, "rel": p}


func _atomic_text(abs_path: String, text: String) -> bool:
	DirAccess.make_dir_recursive_absolute(abs_path.get_base_dir())
	var tmp: String = abs_path + ".tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(text)
	f.flush()
	f.close()
	if FileAccess.file_exists(abs_path):
		DirAccess.remove_absolute(abs_path)
	return DirAccess.rename_absolute(tmp, abs_path) == OK


func _empty() -> Dictionary:
	return {
		"schema": HHAgentConstants.SOAK_SCHEMA,
		"job_id": "",
		"session_id": "",
		"task_id": "",
		"command_id": "",
		"brief": "",
		"context_summary": "",
		"progress": {
			"applied": 0,
			"play_runs": 0,
			"next_step": 0,
			"restarts": {"sidecar": 0, "editor": 0, "host": 0},
		},
		"committed_command_ids": [],
		"checkpoint_refs": [],
		"compacted": false,
		"transcript": [],
		"phase": "running",
		"blocked_reason": "",
		"heartbeat_at_ms": _now_ms(),
		"started_at_ms": _now_ms(),
		"version_pin": HHAgentConstants.PINNED_GODOT,
		"project_hash": "",
		"scene_hash": "",
	}


func _load(job_id: String) -> Dictionary:
	if not _job_id_ok(job_id):
		return {}
	var jailed: Dictionary = _jail("%s/%s/state.json" % [HHAgentConstants.SOAK_DIR, job_id])
	if jailed.get("ok", false) != true:
		return {}
	var abs_p: String = str(jailed.get("abs", ""))
	if not FileAccess.file_exists(abs_p):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(abs_p))
	if not (parsed is Dictionary):
		return {}
	var rec: Dictionary = parsed
	if str(rec.get("schema", "")) != HHAgentConstants.SOAK_SCHEMA:
		return {}
	if str(rec.get("job_id", "")) != job_id:
		return {}
	rec["transcript"] = []
	return rec


func _save(rec: Dictionary) -> Dictionary:
	var job_id: String = str(rec.get("job_id", ""))
	rec["transcript"] = []
	var jailed: Dictionary = _jail("%s/%s/state.json" % [HHAgentConstants.SOAK_DIR, job_id])
	if jailed.get("ok", false) != true:
		return jailed
	if not _atomic_text(str(jailed.get("abs", "")), JSON.stringify(rec, "\t")):
		return {"ok": false, "code": HHAgentErrors.E_UNVERIFIED, "message": "soak persist failed", "path": str(jailed.get("rel", ""))}
	var cur: Dictionary = _jail("%s/current.json" % HHAgentConstants.SOAK_DIR)
	if cur.get("ok", false) == true:
		_atomic_text(str(cur.get("abs", "")), JSON.stringify({"job_id": job_id, "schema": HHAgentConstants.SOAK_SCHEMA}, "\t"))
	return {"ok": true, "rel": str(jailed.get("rel", ""))}


func _view(rec: Dictionary) -> Dictionary:
	return {
		"job_id": rec.get("job_id", ""),
		"kind": "soak",
		"session_id": rec.get("session_id", ""),
		"task_id": rec.get("task_id", ""),
		"command_id": rec.get("command_id", ""),
		"brief": rec.get("brief", ""),
		"context_summary": rec.get("context_summary", ""),
		"progress": rec.get("progress", {}),
		"committed_count": (rec.get("committed_command_ids", []) as Array).size() if rec.get("committed_command_ids", []) is Array else 0,
		"checkpoint_refs": rec.get("checkpoint_refs", []),
		"compacted": rec.get("compacted", false) == true,
		"transcript": [],
		"phase": rec.get("phase", "idle"),
		"blocked_reason": rec.get("blocked_reason", ""),
		"heartbeat_at_ms": rec.get("heartbeat_at_ms", 0),
		"state": rec.get("phase", "idle"),
		"resource_uri": "session://state",
		"resource_path": "%s/%s/state.json" % [HHAgentConstants.SOAK_DIR, str(rec.get("job_id", ""))],
	}


func _stale_not_blocked(reason: String) -> bool:
	return reason.is_empty() or reason == "unchanged" or reason == "stale" or reason == "no_change" or reason == "idle" or reason == "heartbeat"


func _compact(command_id: String, params: Dictionary) -> Dictionary:
	var job_id: String = str(params.get("job_id", ""))
	if job_id.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "missing required param job_id", "params.job_id")
	if not _job_id_ok(job_id):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "invalid job_id", "params.job_id")
	var rec: Dictionary = _load(job_id)
	if rec.is_empty():
		rec = _empty()
		rec["job_id"] = job_id
	var op: String = str(params.get("op", "compact"))
	if params.has("session_id"):
		rec["session_id"] = str(params.get("session_id", ""))
	if params.has("task_id"):
		rec["task_id"] = str(params.get("task_id", ""))
	if params.has("command_id"):
		rec["command_id"] = str(params.get("command_id", ""))
	if params.has("brief"):
		rec["brief"] = str(params.get("brief", ""))
	if params.has("context_summary"):
		rec["context_summary"] = str(params.get("context_summary", ""))
	if params.has("phase"):
		var want: String = str(params.get("phase", ""))
		if want == "blocked" and _stale_not_blocked(str(params.get("blocked_reason", rec.get("blocked_reason", "")))):
			rec["phase"] = "idle"
			rec["blocked_reason"] = ""
		elif want == "running" or want == "idle" or want == "done" or want == "blocked":
			rec["phase"] = want
	if op == "wake":
		if str(rec.get("phase", "")) == "blocked" and _stale_not_blocked(str(rec.get("blocked_reason", ""))):
			rec["phase"] = "idle"
			rec["blocked_reason"] = ""
		elif str(rec.get("phase", "")) != "done" and str(rec.get("phase", "")) != "blocked":
			if str(rec.get("phase", "")) != "running":
				rec["phase"] = "idle"
	if op == "compact":
		rec["compacted"] = true
		rec["transcript"] = []
		if str(rec.get("phase", "")) == "running" or (str(rec.get("phase", "")) == "blocked" and _stale_not_blocked(str(rec.get("blocked_reason", "")))):
			rec["phase"] = "idle"
			rec["blocked_reason"] = ""
	rec["heartbeat_at_ms"] = _now_ms()
	rec["context_summary"] = "task=%s command=%s brief=%s" % [str(rec.get("task_id", "")), str(rec.get("command_id", "")), str(rec.get("brief", ""))]
	var saved: Dictionary = _save(rec)
	if saved.get("ok", false) != true:
		return _errors.fail(command_id, str(saved.get("code", HHAgentErrors.E_UNVERIFIED)), str(saved.get("message", "soak persist failed")), str(saved.get("path", "")))
	return _errors.ok_changed(command_id, PackedStringArray(["soak_state_compacted"]), _view(rec), true)


func _status(command_id: String, params: Dictionary) -> Dictionary:
	var job_id: String = str(params.get("job_id", ""))
	var rec: Dictionary = _load(job_id)
	if rec.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "job %s not found" % job_id, "job_id")
	if str(rec.get("phase", "")) == "blocked" and _stale_not_blocked(str(rec.get("blocked_reason", ""))):
		rec["phase"] = "idle"
		rec["blocked_reason"] = ""
	rec["heartbeat_at_ms"] = _now_ms()
	_save(rec)
	return _errors.ok_read(command_id, PackedStringArray(["job_status_known"]), _view(rec))


func list_jobs() -> Array:
	var jobs: Array = []
	var root: String = ProjectSettings.globalize_path("res://%s" % HHAgentConstants.SOAK_DIR)
	var da: DirAccess = DirAccess.open(root)
	if da == null:
		return jobs
	da.list_dir_begin()
	var name_s: String = da.get_next()
	while not name_s.is_empty():
		if da.current_is_dir() and not name_s.begins_with("."):
			var rec: Dictionary = _load(name_s)
			if not rec.is_empty():
				jobs.append(_view(rec))
		name_s = da.get_next()
	da.list_dir_end()
	return jobs

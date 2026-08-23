class_name HHAgentMultiAgentAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")

## Plugin adapter for the single Godot mutation lane + file leases.
## Four worker roles (research / code_staging / asset_generation / test_analysis)
## run on the sidecar. This adapter does not fake overlap. Coordinator owns
## registry/generated/progress; other agents send a change proposal.

const EMPTY_SHA: String = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

static var _current: HHAgentMultiAgentAdapter
static var _lane_busy: bool = false

var _errors: HHAgentErrors = HHAgentErrors.new()
var _actions: HHAgentActions = HHAgentActions.new()


static func current() -> HHAgentMultiAgentAdapter:
	return _current


static func lane_is_busy() -> bool:
	return _lane_busy


func attach() -> void:
	_current = self
	if not _actions.loaded:
		_actions.load_from_res()


func detach() -> void:
	if _current == self:
		_current = null


func shutdown() -> void:
	detach()


func handles(action: String) -> bool:
	return action == "schedule"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	_precondition: Dictionary,
) -> Dictionary:
	if method != "godot.job" or action != "schedule":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a scheduler verb", "")
	_actions = actions
	var job_id: String = str(params.get("job_id", ""))
	var op: String = str(params.get("op", ""))
	if job_id.is_empty() or op.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "job_id and op required", "params")
	if op == "run":
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"four worker roles run on the sidecar scheduler, not the plugin",
			"op",
		)
	if op == "status":
		return _status(command_id, job_id)
	if op == "propose":
		return _propose(command_id, job_id, params)
	if op == "lease" or op == "heartbeat" or op == "release":
		return _lease(command_id, job_id, op, params)
	if op == "merge" or op == "apply":
		return _merge(command_id, job_id, params)
	if op == "hold_lane":
		if _lane_busy:
			return _errors.fail(command_id, HHAgentErrors.E_BUSY, "godot mutation lane held by another writer", "lane")
		_lane_busy = true
		return _errors.ok_changed(command_id, PackedStringArray(["scheduler_job_persisted"]), {"lane_busy": true, "op": op}, true)
	if op == "release_lane":
		_lane_busy = false
		return _errors.ok_changed(command_id, PackedStringArray(["scheduler_job_persisted"]), {"lane_busy": false, "op": op}, true)
	return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unknown scheduler op", "params.op")


func _jail(rel: String) -> Dictionary:
	var p: String = rel.replace("\\", "/").strip_edges()
	if p.begins_with("res://"):
		p = p.substr(6)
	if p.contains("..") or p.contains("addons/") or p.begins_with(".hh-agent"):
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "scheduler path escapes jail", "path": rel}
	if not p.begins_with("%s/" % HHAgentConstants.SCHED_DIR):
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "scheduler writes only under r7w4/", "path": rel}
	var res_path: String = "res://%s" % p
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	var root: String = ProjectSettings.globalize_path("res://").replace("\\", "/").rstrip("/")
	if not abs_path.replace("\\", "/").begins_with(root):
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "scheduler path leaves project", "path": rel}
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


func _sha256_file(abs_path: String) -> String:
	if not FileAccess.file_exists(abs_path):
		return EMPTY_SHA
	return FileAccess.get_sha256(abs_path)


func _coordinator_owned(rel: String) -> bool:
	return rel.contains("/generated/") or rel.contains("/registry/") or rel.ends_with("/progress.json")


func _leases_path(job_id: String) -> String:
	return "%s/%s/locks/file-leases.json" % [HHAgentConstants.SCHED_DIR, job_id]


func _load_leases(job_id: String) -> Dictionary:
	var jailed: Dictionary = _jail(_leases_path(job_id))
	if jailed.get("ok", false) != true:
		return {}
	var abs_p: String = str(jailed.get("abs", ""))
	if not FileAccess.file_exists(abs_p):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(abs_p))
	return parsed if parsed is Dictionary else {}


func _save_leases(job_id: String, files: Dictionary) -> bool:
	var jailed: Dictionary = _jail(_leases_path(job_id))
	if jailed.get("ok", false) != true:
		return false
	return _atomic_text(str(jailed.get("abs", "")), JSON.stringify(files))


func _now_ms() -> int:
	return int(Time.get_unix_time_from_system() * 1000.0)


func _role_names() -> PackedStringArray:
	return PackedStringArray(["research", "code_staging", "asset_generation", "test_analysis"])


func _lease(command_id: String, job_id: String, op: String, params: Dictionary) -> Dictionary:
	var writer_id: String = str(params.get("writer_id", ""))
	var raw: String = str(params.get("path", ""))
	if writer_id.is_empty() or raw.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "lease needs writer_id and path", "params")
	var rel: String = raw.replace("res://", "")
	if not rel.begins_with("%s/" % HHAgentConstants.SCHED_DIR):
		rel = "%s/%s/%s" % [HHAgentConstants.SCHED_DIR, job_id, rel]
	var jailed: Dictionary = _jail(rel)
	if jailed.get("ok", false) != true:
		return _errors.fail(command_id, str(jailed.get("code", HHAgentErrors.E_PATH)), str(jailed.get("message", "")), rel)
	var files: Dictionary = _load_leases(job_id)
	var key: String = str(jailed.get("rel", rel))
	var now: int = _now_ms()
	var held_v: Variant = files.get(key, {})
	var held: Dictionary = held_v if held_v is Dictionary else {}
	var ttl: int = int(params.get("ttl_ms", 30000))
	if op == "release":
		if not held.is_empty() and str(held.get("writer_id", "")) != writer_id and int(held.get("expires_at", 0)) > now:
			return _errors.fail(command_id, HHAgentErrors.E_LEASE, "cannot release a file lease held by another writer", key)
		files.erase(key)
		_save_leases(job_id, files)
		return _errors.ok_changed(command_id, PackedStringArray(["scheduler_job_persisted"]), {"released": true, "path": key}, true)
	if op == "heartbeat":
		if held.is_empty() or str(held.get("writer_id", "")) != writer_id or int(held.get("expires_at", 0)) <= now:
			return _errors.fail(command_id, HHAgentErrors.E_LEASE, "cannot heartbeat a file lease this writer does not hold", key)
		held["expires_at"] = now + ttl
		held["heartbeat_at"] = now
		files[key] = held
		_save_leases(job_id, files)
		return _errors.ok_changed(command_id, PackedStringArray(["scheduler_job_persisted"]), {"lease": held, "heartbeat": true}, true)
	if not held.is_empty() and str(held.get("writer_id", "")) != writer_id and int(held.get("expires_at", 0)) > now:
		return _errors.fail(command_id, HHAgentErrors.E_LEASE, "file/scene lease held by another writer", key)
	var lease: Dictionary = {
		"writer_id": writer_id,
		"hash": _sha256_file(str(jailed.get("abs", ""))),
		"expires_at": now + ttl,
		"rel": key,
		"heartbeat_at": now,
	}
	files[key] = lease
	_save_leases(job_id, files)
	return _errors.ok_changed(command_id, PackedStringArray(["scheduler_job_persisted"]), {"lease": lease}, true)


func _merge(command_id: String, job_id: String, params: Dictionary) -> Dictionary:
	var writer_id: String = str(params.get("writer_id", HHAgentConstants.SCHED_COORDINATOR))
	var raw: String = str(params.get("path", ""))
	var base_hash: String = str(params.get("base_hash", ""))
	var contents: String = str(params.get("contents", ""))
	if raw.is_empty() or base_hash.is_empty() or contents.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "merge needs path/base_hash/contents", "params")
	var rel: String = raw.replace("res://", "")
	if not rel.begins_with("%s/" % HHAgentConstants.SCHED_DIR):
		rel = "%s/%s/%s" % [HHAgentConstants.SCHED_DIR, job_id, rel]
	if _coordinator_owned(rel) and writer_id != HHAgentConstants.SCHED_COORDINATOR:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_POLICY,
			"registry/generated/progress is coordinator-owned; send a change proposal",
			rel,
		)
	var jailed: Dictionary = _jail(rel)
	if jailed.get("ok", false) != true:
		return _errors.fail(command_id, str(jailed.get("code", HHAgentErrors.E_PATH)), str(jailed.get("message", "")), rel)
	var abs_p: String = str(jailed.get("abs", ""))
	var current: String = _sha256_file(abs_p)
	if current != base_hash:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "base hash mismatch; pause/resync, not auto-resolve", rel)
	var files: Dictionary = _load_leases(job_id)
	var key: String = str(jailed.get("rel", rel))
	var held_v: Variant = files.get(key, {})
	var held: Dictionary = held_v if held_v is Dictionary else {}
	var now: int = _now_ms()
	if not held.is_empty() and str(held.get("writer_id", "")) != writer_id and int(held.get("expires_at", 0)) > now:
		return _errors.fail(command_id, HHAgentErrors.E_LEASE, "file/scene lease held by another writer", key)
	if _lane_busy:
		return _errors.fail(command_id, HHAgentErrors.E_BUSY, "godot mutation lane held by another writer", "lane")
	_lane_busy = true
	var wrote: bool = _atomic_text(abs_p, contents)
	_lane_busy = false
	if not wrote:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "merge did not persist", rel)
	return _errors.ok_changed(
		command_id,
		PackedStringArray(["scheduler_job_persisted"]),
		{"merged": true, "path": rel, "hash": _sha256_file(abs_p), "roles": _role_names()},
		true,
	)


func _propose(command_id: String, job_id: String, params: Dictionary) -> Dictionary:
	var writer_id: String = str(params.get("writer_id", ""))
	if writer_id == HHAgentConstants.SCHED_COORDINATOR:
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "coordinator applies merges; workers send proposals", "writer_id")
	var rel: String = "%s/%s/proposals/%s.json" % [HHAgentConstants.SCHED_DIR, job_id, writer_id]
	var jailed: Dictionary = _jail(rel)
	if jailed.get("ok", false) != true:
		return _errors.fail(command_id, str(jailed.get("code", HHAgentErrors.E_PATH)), str(jailed.get("message", "")), rel)
	if not _atomic_text(str(jailed.get("abs", "")), JSON.stringify(params)):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "proposal persist failed", rel)
	return _errors.ok_changed(command_id, PackedStringArray(["scheduler_job_persisted"]), {"proposal": true, "path": rel}, true)


func _status(command_id: String, job_id: String) -> Dictionary:
	var rel: String = "%s/%s/state.json" % [HHAgentConstants.SCHED_DIR, job_id]
	var jailed: Dictionary = _jail(rel)
	if jailed.get("ok", false) != true or not FileAccess.file_exists(str(jailed.get("abs", ""))):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "scheduler job not found", "job_id")
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(str(jailed.get("abs", ""))))
	var after: Dictionary = parsed if parsed is Dictionary else {}
	after["kind"] = "scheduler"
	return _errors.ok_changed(command_id, PackedStringArray(["scheduler_job_persisted"]), after, false)

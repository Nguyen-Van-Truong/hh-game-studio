class_name HHAgentOrchestratorAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _PauseScript: GDScript = preload("res://addons/hh_agent/core/hh_pause.gd")
const _PlanScript: GDScript = preload("res://addons/hh_agent/core/hh_plan_adapter.gd")
const _StoreScript: GDScript = preload("res://addons/hh_agent/core/hh_activity_store.gd")
const _ActivityDockScript: GDScript = preload("res://addons/hh_agent/ui/health/hh_activity_dock.gd")

## Persistable orchestrator: inspect→plan→checkpoint→execute→verify→repair.
## Reuses hh_plan_adapter.compile_brief. Does not overload job.transaction.

const INSPECT_ROOT: String = "inspect_root"
const CROCKFORD: String = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

static var _current: HHAgentOrchestratorAdapter

var _errors: HHAgentErrors = HHAgentErrors.new()
var _actions: HHAgentActions = HHAgentActions.new()
var _ulid_seq: int = 0


static func current() -> HHAgentOrchestratorAdapter:
	return _current


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
	return (
		action == "run"
		or action == "status"
		or action == "list"
		or action == "cancel"
		or action == "wait"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	_precondition: Dictionary,
) -> Dictionary:
	if method != "godot.job" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not an orchestrator verb", "")
	_actions = actions
	if action == "run":
		return _run(command_id, params)
	if action == "status":
		return _status(command_id, params)
	if action == "list":
		return _list(command_id, params)
	if action == "cancel":
		return _cancel(command_id, params)
	return _wait(command_id, params)


func _now_ms() -> int:
	return int(Time.get_unix_time_from_system() * 1000.0)


func _paused() -> bool:
	return HHAgentPauseGate.last_paused


func _job_id_ok(job_id: String) -> bool:
	if job_id.is_empty() or job_id.length() > 64:
		return false
	var re: RegEx = RegEx.new()
	if re.compile("^[A-Za-z0-9_-]+$") != OK:
		return false
	return re.search(job_id) != null


func _jail(rel: String) -> Dictionary:
	var p: String = rel.replace("\\", "/").strip_edges()
	if p.contains("..") or p.contains("addons/") or p.begins_with(".hh-agent"):
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "orchestrator path escapes jail", "path": rel}
	if not p.begins_with("%s/" % HHAgentConstants.ORCH_DIR):
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "orchestrator writes only under r7w2/", "path": rel}
	var res_path: String = "res://%s" % p
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	var root: String = ProjectSettings.globalize_path("res://").replace("\\", "/").rstrip("/")
	if not abs_path.replace("\\", "/").begins_with(root):
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "orchestrator path leaves project", "path": rel}
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


func _load(job_id: String) -> Dictionary:
	if not _job_id_ok(job_id):
		return {}
	var jailed: Dictionary = _jail("%s/%s/state.json" % [HHAgentConstants.ORCH_DIR, job_id])
	if jailed.get("ok", false) != true:
		return {}
	var abs_p: String = str(jailed.get("abs", ""))
	if not FileAccess.file_exists(abs_p):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(abs_p))
	if not (parsed is Dictionary):
		return {}
	var rec: Dictionary = parsed
	if str(rec.get("schema", "")) != HHAgentConstants.ORCH_SCHEMA:
		return {}
	if str(rec.get("job_id", "")) != job_id:
		return {}
	return rec


func _save(rec: Dictionary) -> Dictionary:
	var job_id: String = str(rec.get("job_id", ""))
	rec["used"] = rec.get("used", {}) if rec.get("used", {}) is Dictionary else {}
	(rec["used"] as Dictionary)["context_tokens"] = JSON.stringify(rec).length()
	var jailed: Dictionary = _jail("%s/%s/state.json" % [HHAgentConstants.ORCH_DIR, job_id])
	if jailed.get("ok", false) != true:
		return jailed
	if not _atomic_text(str(jailed.get("abs", "")), JSON.stringify(rec, "\t")):
		return {"ok": false, "code": HHAgentErrors.E_UNVERIFIED, "message": "orchestrator persist failed", "path": str(jailed.get("rel", ""))}
	_publish(rec)
	return {"ok": true}


func _publish(rec: Dictionary) -> void:
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store == null:
		return
	var view: Dictionary = _view(rec, _now_ms())
	store.set_orch(view)
	var dock: HHAgentActivityDock = HHAgentActivityDock.current()
	if dock != null:
		dock.set_status({"dock": store.snapshot({}), "orch": view})


func _write_evidence(job_id: String, rel_name: String, body: Dictionary) -> String:
	var jailed: Dictionary = _jail("%s/%s/%s" % [HHAgentConstants.ORCH_DIR, job_id, rel_name])
	if jailed.get("ok", false) != true:
		return ""
	if not _atomic_text(str(jailed.get("abs", "")), JSON.stringify(body, "\t")):
		return ""
	return str(jailed.get("rel", ""))


func _read_evidence(job_id: String, rel_name: String) -> Dictionary:
	var jailed: Dictionary = _jail("%s/%s/%s" % [HHAgentConstants.ORCH_DIR, job_id, rel_name])
	if jailed.get("ok", false) != true:
		return {}
	var abs_p: String = str(jailed.get("abs", ""))
	if not FileAccess.file_exists(abs_p):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(abs_p))
	if parsed is Dictionary:
		return parsed
	return {}


func _digest(command_id: String, task_id: String, action: String) -> String:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(("%s:%s:%s" % [command_id, task_id, action]).to_utf8_buffer())
	return ctx.finish().hex_encode()


func _last_task_file(rec: Dictionary, tid: String) -> String:
	var cmd_map: Dictionary = rec.get("task_commands", {}) if rec.get("task_commands", {}) is Dictionary else {}
	var rows_v: Variant = cmd_map.get(tid, [])
	if not (rows_v is Array):
		return ""
	var rows: Array = rows_v
	var i: int = rows.size() - 1
	while i >= 0:
		if rows[i] is Dictionary and (rows[i] as Dictionary).get("committed", false) == true:
			return "tasks/%s-%s.json" % [tid, str((rows[i] as Dictionary).get("command_id", ""))]
		i -= 1
	return ""


func _new_ulid() -> String:
	_ulid_seq += 1
	var t: int = _now_ms() + _ulid_seq
	var chars: String = ""
	var i: int = 0
	var acc: int = t
	while i < 10:
		chars = CROCKFORD.substr(acc % 32, 1) + chars
		acc = int(acc / 32)
		i += 1
	var tail: String = "%x" % (t * 17 + _ulid_seq)
	tail = tail.to_upper().replace("I", "X").replace("L", "X").replace("O", "X").replace("U", "X")
	while tail.length() < 16:
		tail = "0" + tail
	if tail.length() > 16:
		tail = tail.substr(0, 16)
	return (chars + tail).substr(0, 26)


func _new_record(job_id: String, now_ms: int, budgets: Dictionary) -> Dictionary:
	return {
		"schema": HHAgentConstants.ORCH_SCHEMA,
		"job_id": job_id,
		"state": "inspect",
		"current_task_id": INSPECT_ROOT,
		"current_command_id": "",
		"committed_command_ids": [],
		"tasks": [],
		"task_status": {},
		"task_commands": {},
		"started_at_ms": now_ms,
		"heartbeat_at_ms": now_ms,
		"budgets": {
			"commands": int(budgets.get("commands", 64)),
			"wall_ms": int(budgets.get("wall_ms", 600000)),
			"retries": int(budgets.get("retries", 8)),
			"context_tokens": int(budgets.get("context_tokens", 250000)),
		},
		"used": {"commands": 0, "wall_ms": 0, "retries": 0, "context_tokens": 0},
		"repair": {"error_key": "", "same_error_count": 0, "loops": 0, "root_cause": ""},
		"checkpoint_ref": "",
		"fixture": "",
		"hold_after": "",
		"blocked_reason": "",
		"cancel_requested": false,
		"cancelled": false,
		"brief_hash": "",
		"applied_state": "",
	}


func _view(rec: Dictionary, now_ms: int) -> Dictionary:
	var hb: int = int(rec.get("heartbeat_at_ms", 0))
	var age: int = maxi(0, now_ms - hb)
	var status_v: Variant = rec.get("task_status", {})
	var status: Dictionary = status_v if status_v is Dictionary else {}
	var executed: Array = []
	for key_v: Variant in status.keys():
		var st: String = str(status.get(key_v, ""))
		if st == "ok" or st == "running":
			executed.append(str(key_v))
	return {
		"job_id": str(rec.get("job_id", "")),
		"state": str(rec.get("state", "")),
		"current_task_id": str(rec.get("current_task_id", "")),
		"current_command_id": str(rec.get("current_command_id", "")),
		"committed_command_ids": (rec.get("committed_command_ids", []) as Array).duplicate() if rec.get("committed_command_ids", []) is Array else [],
		"heartbeat_at_ms": hb,
		"heartbeat_age_ms": age,
		"stale": age > HHAgentConstants.ORCH_HEARTBEAT_STALE_MS,
		"budgets": (rec.get("budgets", {}) as Dictionary).duplicate(true) if rec.get("budgets", {}) is Dictionary else {},
		"used": (rec.get("used", {}) as Dictionary).duplicate(true) if rec.get("used", {}) is Dictionary else {},
		"blocked_reason": str(rec.get("blocked_reason", "")),
		"cancelled": rec.get("cancelled", false) == true,
		"fixture": str(rec.get("fixture", "")),
		"checkpoint_ref": str(rec.get("checkpoint_ref", "")),
		"repair": (rec.get("repair", {}) as Dictionary).duplicate(true) if rec.get("repair", {}) is Dictionary else {},
		"task_status": status.duplicate(true),
		"tasks_executed": executed,
	}


func _can_transition(from_s: String, to_s: String) -> bool:
	if from_s == to_s:
		return true
	if from_s == "done" or from_s == "blocked" or from_s == "cancelled":
		return false
	if to_s == "cancelled" or to_s == "blocked":
		return true
	if from_s == "inspect" and to_s == "plan":
		return true
	if from_s == "plan" and to_s == "checkpoint":
		return true
	if from_s == "checkpoint" and to_s == "execute":
		return true
	if from_s == "execute" and to_s == "verify":
		return true
	if from_s == "verify" and (to_s == "repair" or to_s == "execute" or to_s == "review-ready" or to_s == "done"):
		return true
	if from_s == "repair" and (to_s == "verify" or to_s == "blocked"):
		return true
	if from_s == "review-ready" and to_s == "done":
		return true
	return false


func _enter(rec: Dictionary, next_s: String) -> String:
	var from_s: String = str(rec.get("state", ""))
	if not _can_transition(from_s, next_s):
		return "illegal transition %s → %s" % [from_s, next_s]
	if from_s != next_s:
		rec["state"] = next_s
		rec["applied_state"] = ""
	return ""


func _already(rec: Dictionary) -> bool:
	return str(rec.get("applied_state", "")) == str(rec.get("state", "")) and not str(rec.get("state", "")).is_empty()


func _mark(rec: Dictionary) -> void:
	rec["applied_state"] = str(rec.get("state", ""))


func _block(rec: Dictionary, reason: String) -> void:
	rec["blocked_reason"] = reason
	rec["state"] = "blocked"


func _budget_block(rec: Dictionary) -> String:
	var used: Dictionary = rec.get("used", {}) if rec.get("used", {}) is Dictionary else {}
	var budgets: Dictionary = rec.get("budgets", {}) if rec.get("budgets", {}) is Dictionary else {}
	if int(used.get("commands", 0)) > int(budgets.get("commands", 64)):
		return "budget_commands"
	if int(used.get("wall_ms", 0)) > int(budgets.get("wall_ms", 600000)):
		return "budget_wall"
	if int(used.get("retries", 0)) > int(budgets.get("retries", 8)):
		return "budget_retry"
	if int(used.get("context_tokens", 0)) > int(budgets.get("context_tokens", 250000)):
		return "budget_context"
	return ""


func _fixture_tasks(fixture: String) -> Array:
	if fixture == "infinite_repair":
		return [{"id": "task_a", "kind": "verify", "deps": [], "commands": ["orch.mark"], "verify": "always_fail"}]
	if fixture == "dep_fail":
		return [
			{"id": "task_a", "kind": "produce", "deps": [], "commands": ["orch.mark"], "verify": "fail"},
			{"id": "task_b", "kind": "produce", "deps": ["task_a"], "commands": ["orch.mark"], "verify": "ok"},
		]
	return [
		{"id": "task_a", "kind": "produce", "deps": [], "commands": ["orch.mark"], "verify": "ok"},
		{"id": "task_b", "kind": "produce", "deps": ["task_a"], "commands": ["orch.mark"], "verify": "ok"},
	]


func _install_tasks(rec: Dictionary, tasks: Array) -> void:
	rec["tasks"] = tasks
	var status: Dictionary = {}
	var cmds: Dictionary = {}
	for t_v: Variant in tasks:
		if not (t_v is Dictionary):
			continue
		var t: Dictionary = t_v
		var tid: String = str(t.get("id", ""))
		status[tid] = "pending"
		var rows: Array = []
		var c_v: Variant = t.get("commands", [])
		if c_v is Array:
			for a_v: Variant in c_v:
				rows.append({"action": str(a_v), "command_id": _new_ulid(), "committed": false})
		cmds[tid] = rows
	rec["task_status"] = status
	rec["task_commands"] = cmds
	var ready: String = _next_ready(rec)
	if ready.is_empty() and not tasks.is_empty() and tasks[0] is Dictionary:
		ready = str((tasks[0] as Dictionary).get("id", INSPECT_ROOT))
	rec["current_task_id"] = ready if not ready.is_empty() else INSPECT_ROOT
	_write_seed(rec)


func _write_seed(rec: Dictionary) -> void:
	var fixture: String = str(rec.get("fixture", ""))
	var fail_tasks: Array = []
	var always: bool = fixture == "infinite_repair"
	var tasks_v: Variant = rec.get("tasks", [])
	if tasks_v is Array:
		for t_v: Variant in tasks_v:
			if not (t_v is Dictionary):
				continue
			var t: Dictionary = t_v
			if always or str(t.get("verify", "")) == "fail" or str(t.get("verify", "")) == "always_fail":
				fail_tasks.append(str(t.get("id", "")))
	if fixture == "ok_slice" or fixture.is_empty():
		fail_tasks.clear()
		always = false
	_write_evidence(str(rec.get("job_id", "")), "seed.json", {
		"always_fail": always,
		"fail_tasks": fail_tasks,
	})


func _task_status(rec: Dictionary, tid: String) -> String:
	var status: Dictionary = rec.get("task_status", {}) if rec.get("task_status", {}) is Dictionary else {}
	return str(status.get(tid, "pending"))


func _set_status(rec: Dictionary, tid: String, st: String) -> void:
	var status: Dictionary = rec.get("task_status", {}) if rec.get("task_status", {}) is Dictionary else {}
	status[tid] = st
	rec["task_status"] = status


func _dep_problem(rec: Dictionary, task: Dictionary) -> String:
	var deps_v: Variant = task.get("deps", [])
	if not (deps_v is Array):
		return ""
	for dep_v: Variant in deps_v:
		var st: String = _task_status(rec, str(dep_v))
		if st == "failed":
			return "dependency_failed"
		if st == "cancelled":
			return "dependency_cancelled"
		if st == "skipped":
			return "dependency_failed"
		if st != "ok":
			return "dependency_unready"
	return ""


func _next_ready(rec: Dictionary) -> String:
	var tasks_v: Variant = rec.get("tasks", [])
	if not (tasks_v is Array):
		return ""
	for t_v: Variant in tasks_v:
		if not (t_v is Dictionary):
			continue
		var t: Dictionary = t_v
		var tid: String = str(t.get("id", ""))
		if _task_status(rec, tid) != "pending":
			continue
		if _dep_problem(rec, t) != "":
			continue
		return tid
	return ""


func _skip_dependents(rec: Dictionary, reason: String) -> void:
	var tasks_v: Variant = rec.get("tasks", [])
	if not (tasks_v is Array):
		return
	for t_v: Variant in tasks_v:
		if not (t_v is Dictionary):
			continue
		var t: Dictionary = t_v
		var tid: String = str(t.get("id", ""))
		if _task_status(rec, tid) != "pending":
			continue
		var problem: String = _dep_problem(rec, t)
		if problem == "dependency_failed" or problem == "dependency_cancelled":
			_set_status(rec, tid, "skipped")
			if str(rec.get("blocked_reason", "")).is_empty():
				rec["blocked_reason"] = reason if not reason.is_empty() else problem


func _commit(rec: Dictionary, command_id: String) -> bool:
	var committed: Array = rec.get("committed_command_ids", []) if rec.get("committed_command_ids", []) is Array else []
	if committed.has(command_id):
		return false
	committed.append(command_id)
	rec["committed_command_ids"] = committed
	var used: Dictionary = rec.get("used", {}) if rec.get("used", {}) is Dictionary else {}
	used["commands"] = int(used.get("commands", 0)) + 1
	rec["used"] = used
	rec["current_command_id"] = command_id
	return true


func _find_task(rec: Dictionary, tid: String) -> Dictionary:
	var tasks_v: Variant = rec.get("tasks", [])
	if not (tasks_v is Array):
		return {}
	for t_v: Variant in tasks_v:
		if t_v is Dictionary and str((t_v as Dictionary).get("id", "")) == tid:
			return t_v
	return {}


func _apply_inspect(rec: Dictionary, params: Dictionary) -> void:
	if str(rec.get("current_task_id", "")).is_empty():
		rec["current_task_id"] = INSPECT_ROOT
	if params.has("fixture"):
		rec["fixture"] = str(params.get("fixture", ""))
	if params.has("brief"):
		rec["brief_hash"] = str(str(params.get("brief", "")).hash())


func _apply_plan(rec: Dictionary, params: Dictionary) -> String:
	var fixture: String = str(rec.get("fixture", params.get("fixture", "")))
	if fixture == "ok_slice" or fixture == "infinite_repair" or fixture == "dep_fail":
		rec["fixture"] = fixture
		_install_tasks(rec, _fixture_tasks(fixture))
		_write_evidence(str(rec.get("job_id", "")), "plan.json", {"fixture": fixture, "tasks": rec.get("tasks", [])})
		return ""
	var brief_s: String = str(params.get("brief", ""))
	if not brief_s.is_empty():
		var planner: HHAgentPlanAdapter = HHAgentPlanAdapter.current()
		if planner == null:
			planner = HHAgentPlanAdapter.new()
		var plan: Dictionary = planner.compile_brief(brief_s, {}, str(params.get("run_id", "")), false)
		if plan.get("ok", false) != true:
			return str((plan.get("error", {}) as Dictionary).get("message", "plan compile failed")) if plan.get("error", {}) is Dictionary else "plan compile failed"
		var mapped: Array = []
		var tasks_v: Variant = plan.get("tasks", [])
		if tasks_v is Array:
			for t_v: Variant in tasks_v:
				if not (t_v is Dictionary):
					continue
				var t: Dictionary = t_v
				mapped.append({
					"id": str(t.get("id", "")),
					"kind": str(t.get("kind", "")),
					"deps": (t.get("deps", []) as Array).duplicate() if t.get("deps", []) is Array else [],
					"commands": (t.get("commands", []) as Array).duplicate() if t.get("commands", []) is Array else [],
					"verify": str(t.get("verify", "")),
				})
		if mapped.is_empty():
			return "empty DAG"
		_install_tasks(rec, mapped)
		_write_evidence(str(rec.get("job_id", "")), "plan.json", {"tasks": rec.get("tasks", [])})
		return ""
	var existing: Variant = rec.get("tasks", [])
	if existing is Array and not (existing as Array).is_empty():
		return ""
	rec["fixture"] = "ok_slice"
	_install_tasks(rec, _fixture_tasks("ok_slice"))
	_write_evidence(str(rec.get("job_id", "")), "plan.json", {"fixture": "ok_slice", "tasks": rec.get("tasks", [])})
	return ""


func _apply_checkpoint(rec: Dictionary) -> String:
	if _already(rec) and not str(rec.get("checkpoint_ref", "")).is_empty():
		return ""
	var cid: String = _new_ulid()
	if _commit(rec, cid):
		rec["checkpoint_ref"] = _write_evidence(str(rec.get("job_id", "")), "checkpoint.json", {
			"command_id": cid,
			"current_task_id": str(rec.get("current_task_id", "")),
		})
	if str(rec.get("checkpoint_ref", "")).is_empty():
		rec["checkpoint_ref"] = "%s/checkpoint" % str(rec.get("job_id", ""))
	return ""


func _apply_execute(rec: Dictionary, params: Dictionary) -> String:
	var tid: String = str(rec.get("current_task_id", ""))
	var task: Dictionary = _find_task(rec, tid)
	if task.is_empty():
		return "current task missing"
	var problem: String = _dep_problem(rec, task)
	if problem == "dependency_failed" or problem == "dependency_cancelled":
		_set_status(rec, tid, "skipped")
		_skip_dependents(rec, problem)
		return problem
	_set_status(rec, tid, "running")
	var cmd_map: Dictionary = rec.get("task_commands", {}) if rec.get("task_commands", {}) is Dictionary else {}
	var rows_v: Variant = cmd_map.get(tid, [])
	var rows: Array = rows_v if rows_v is Array else []
	var committed: Array = rec.get("committed_command_ids", []) if rec.get("committed_command_ids", []) is Array else []
	for row_v: Variant in rows:
		if not (row_v is Dictionary):
			continue
		var row: Dictionary = row_v
		var cid: String = str(row.get("command_id", ""))
		if committed.has(cid):
			row["committed"] = true
			continue
		var digest: String = _digest(cid, tid, str(row.get("action", "")))
		var rel: String = _write_evidence(str(rec.get("job_id", "")), "tasks/%s-%s.json" % [tid, cid], {
			"task_id": tid,
			"action": str(row.get("action", "")),
			"command_id": cid,
			"digest": digest,
		})
		if rel.is_empty():
			return "execute evidence write failed"
		_commit(rec, cid)
		row["committed"] = true
	cmd_map[tid] = rows
	rec["task_commands"] = cmd_map
	if str(params.get("fail_task", "")) == tid:
		_set_status(rec, tid, "failed")
	return ""


func _apply_verify(rec: Dictionary, params: Dictionary) -> String:
	var tid: String = str(rec.get("current_task_id", ""))
	var task: Dictionary = _find_task(rec, tid)
	if task.is_empty():
		return "fail"
	if _task_status(rec, tid) == "failed":
		return "fail"
	if str(params.get("fail_task", "")) == tid:
		_set_status(rec, tid, "failed")
		return "fail"
	var rel: String = _last_task_file(rec, tid)
	var body: Dictionary = _read_evidence(str(rec.get("job_id", "")), rel) if not rel.is_empty() else {}
	if body.is_empty():
		_set_status(rec, tid, "failed")
		var repair0: Dictionary = rec.get("repair", {}) if rec.get("repair", {}) is Dictionary else {}
		repair0["root_cause"] = "missing execute evidence"
		rec["repair"] = repair0
		return "fail"
	var expect: String = _digest(str(body.get("command_id", "")), str(body.get("task_id", "")), str(body.get("action", "")))
	var committed: Array = rec.get("committed_command_ids", []) if rec.get("committed_command_ids", []) is Array else []
	if str(body.get("digest", "")) != expect or not committed.has(str(body.get("command_id", ""))):
		_set_status(rec, tid, "failed")
		var repair1: Dictionary = rec.get("repair", {}) if rec.get("repair", {}) is Dictionary else {}
		repair1["root_cause"] = "execute digest mismatch"
		rec["repair"] = repair1
		return "fail"
	var seed: Dictionary = _read_evidence(str(rec.get("job_id", "")), "seed.json")
	var fail_tasks: Array = seed.get("fail_tasks", []) if seed.get("fail_tasks", []) is Array else []
	if seed.get("always_fail", false) == true or fail_tasks.has(tid):
		_set_status(rec, tid, "failed")
		var repair2: Dictionary = rec.get("repair", {}) if rec.get("repair", {}) is Dictionary else {}
		repair2["root_cause"] = "%s:seed fail" % tid
		rec["repair"] = repair2
		return "fail"
	_set_status(rec, tid, "ok")
	return "pass"


func _note_fail(rec: Dictionary) -> void:
	var repair: Dictionary = rec.get("repair", {}) if rec.get("repair", {}) is Dictionary else {}
	var key: String = "verify:%s" % str(rec.get("current_task_id", ""))
	if str(rec.get("fixture", "")) == "infinite_repair":
		key = "infinite_repair:same"
	if str(repair.get("error_key", "")) == key or str(repair.get("error_key", "")).is_empty():
		repair["error_key"] = key
		repair["same_error_count"] = int(repair.get("same_error_count", 0)) + 1
	else:
		repair["error_key"] = key
		repair["same_error_count"] = 1
	repair["root_cause"] = key
	rec["repair"] = repair


func _apply_repair(rec: Dictionary) -> void:
	if _already(rec):
		return
	var repair: Dictionary = rec.get("repair", {}) if rec.get("repair", {}) is Dictionary else {}
	repair["loops"] = int(repair.get("loops", 0)) + 1
	rec["repair"] = repair
	var used: Dictionary = rec.get("used", {}) if rec.get("used", {}) is Dictionary else {}
	used["retries"] = int(used.get("retries", 0)) + 1
	rec["used"] = used
	var from_task: String = _last_task_file(rec, str(rec.get("current_task_id", "")))
	var failed: Dictionary = _read_evidence(str(rec.get("job_id", "")), from_task) if not from_task.is_empty() else {}
	if not failed.is_empty():
		repair["root_cause"] = str(failed.get("verify", repair.get("root_cause", "")))
	rec["repair"] = repair
	_write_evidence(str(rec.get("job_id", "")), "repair/%d.json" % int(repair.get("loops", 0)), {
		"loop": int(repair.get("loops", 0)),
		"error_key": str(repair.get("error_key", "")),
		"root_cause": str(repair.get("root_cause", "")),
		"same_error_count": int(repair.get("same_error_count", 0)),
		"from_task": from_task,
	})


func _after_verify(rec: Dictionary, params: Dictionary, verdict: String) -> String:
	if verdict == "fail":
		_note_fail(rec)
		_skip_dependents(rec, "dependency_failed")
		var skipped := false
		var status0: Dictionary = rec.get("task_status", {}) if rec.get("task_status", {}) is Dictionary else {}
		for sk_v: Variant in status0.keys():
			if str(status0.get(sk_v, "")) == "skipped":
				skipped = true
				break
		if skipped or str(params.get("fail_task", "")) == str(rec.get("current_task_id", "")):
			_block(rec, str(rec.get("blocked_reason", "dependency_failed")))
			return "blocked"
		var same_n: int = int((rec.get("repair", {}) as Dictionary).get("same_error_count", 0)) if rec.get("repair", {}) is Dictionary else 0
		if same_n > HHAgentConstants.ORCH_MAX_SAME_REPAIR:
			_block(rec, "repair_cap")
			return "blocked"
		var err: String = _enter(rec, "repair")
		return "repair" if err.is_empty() else err
	var nxt: String = _next_ready(rec)
	if not nxt.is_empty():
		rec["current_task_id"] = nxt
		var err2: String = _enter(rec, "execute")
		return "execute" if err2.is_empty() else err2
	var status: Dictionary = rec.get("task_status", {}) if rec.get("task_status", {}) is Dictionary else {}
	for key_v: Variant in status.keys():
		var st: String = str(status.get(key_v, ""))
		if st == "skipped" or st == "failed":
			_block(rec, str(rec.get("blocked_reason", "dependency_failed")))
			return "blocked"
	var err3: String = _enter(rec, "review-ready")
	return "review-ready" if err3.is_empty() else err3


func _advance(rec: Dictionary, params: Dictionary, hold: String, paused: bool) -> String:
	if rec.get("cancel_requested", false) == true and str(rec.get("state", "")) != "done" and str(rec.get("state", "")) != "blocked" and str(rec.get("state", "")) != "cancelled":
		rec["cancelled"] = true
		rec["state"] = "cancelled"
		rec["blocked_reason"] = "cancelled"
		return "cancelled"
	var billed: String = _budget_block(rec)
	if not billed.is_empty() and str(rec.get("state", "")) != "done" and str(rec.get("state", "")) != "blocked" and str(rec.get("state", "")) != "cancelled":
		_block(rec, billed)
		return "blocked"
	var state: String = str(rec.get("state", ""))
	if state == "done" or state == "blocked" or state == "cancelled":
		return state
	if paused and (state == "checkpoint" or state == "execute" or state == "repair" or state == "review-ready"):
		return "paused"
	if hold.is_empty():
		hold = str(rec.get("hold_after", ""))
	if state == "inspect":
		if not _already(rec):
			_apply_inspect(rec, params)
			_mark(rec)
		if hold == "inspect":
			return "hold"
		var e1: String = _enter(rec, "plan")
		return "plan" if e1.is_empty() else e1
	if state == "plan":
		if not _already(rec):
			var perr: String = _apply_plan(rec, params)
			if not perr.is_empty():
				_block(rec, perr)
				return "blocked"
			_mark(rec)
		if hold == "plan":
			return "hold"
		if paused:
			return "paused"
		var e2: String = _enter(rec, "checkpoint")
		return "checkpoint" if e2.is_empty() else e2
	if state == "checkpoint":
		if paused:
			return "paused"
		if not _already(rec):
			_apply_checkpoint(rec)
			_mark(rec)
		if hold == "checkpoint":
			return "hold"
		var e3: String = _enter(rec, "execute")
		return "execute" if e3.is_empty() else e3
	if state == "execute":
		if paused:
			return "paused"
		if not _already(rec):
			var xerr: String = _apply_execute(rec, params)
			if xerr == "dependency_failed" or xerr == "dependency_cancelled":
				_block(rec, xerr)
				return "blocked"
			if not xerr.is_empty():
				_block(rec, xerr)
				return "blocked"
			_mark(rec)
		if hold == "execute":
			return "hold"
		var e4: String = _enter(rec, "verify")
		return "verify" if e4.is_empty() else e4
	if state == "verify":
		var verdict: String = "fail"
		if not _already(rec):
			verdict = _apply_verify(rec, params)
			_mark(rec)
		elif _task_status(rec, str(rec.get("current_task_id", ""))) == "ok":
			verdict = "pass"
		if hold == "verify":
			return "hold"
		return _after_verify(rec, params, verdict)
	if state == "repair":
		if paused:
			return "paused"
		var same_n: int = int((rec.get("repair", {}) as Dictionary).get("same_error_count", 0)) if rec.get("repair", {}) is Dictionary else 0
		if same_n > HHAgentConstants.ORCH_MAX_SAME_REPAIR:
			_block(rec, "repair_cap")
			return "blocked"
		_apply_repair(rec)
		_mark(rec)
		if hold == "repair":
			return "hold"
		var e5: String = _enter(rec, "verify")
		return "verify" if e5.is_empty() else e5
	if state == "review-ready":
		if hold == "review-ready":
			return "hold"
		var e6: String = _enter(rec, "done")
		return "done" if e6.is_empty() else e6
	return state


func _ack(command_id: String, rec: Dictionary, now_ms: int, changed: bool, extra: Dictionary = {}) -> Dictionary:
	var after: Dictionary = _view(rec, now_ms)
	for key_v: Variant in extra.keys():
		after[str(key_v)] = extra[key_v]
	return _errors.ok_changed(command_id, PackedStringArray(["orchestrator_state_persisted"]), after, changed)


func _fail_after(command_id: String, code: String, message: String, path_s: String, rec: Dictionary, now_ms: int) -> Dictionary:
	return _errors.fail_after(command_id, code, message, path_s, _view(rec, now_ms))


func _run(command_id: String, params: Dictionary) -> Dictionary:
	var job_id: String = str(params.get("job_id", ""))
	if not _job_id_ok(job_id):
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "job_id required", "job_id")
	var now_ms: int = _now_ms()
	var rec: Dictionary = _load(job_id)
	var budgets: Dictionary = params.get("budgets", {}) if params.get("budgets", {}) is Dictionary else {}
	if rec.is_empty():
		rec = _new_record(job_id, now_ms, budgets)
		if params.has("fixture"):
			rec["fixture"] = str(params.get("fixture", ""))
		var entered: String = _enter(rec, "inspect")
		if not entered.is_empty():
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, entered, "state")
	elif not budgets.is_empty():
		var b: Dictionary = rec.get("budgets", {}) if rec.get("budgets", {}) is Dictionary else {}
		for k_v: Variant in budgets.keys():
			b[str(k_v)] = budgets[k_v]
		rec["budgets"] = b
	rec["heartbeat_at_ms"] = now_ms
	if params.get("resume", false) == true and not params.has("hold_after"):
		rec["hold_after"] = ""
	if params.get("inject_illegal", false) == true:
		var illegal: String = _enter(rec, "execute")
		if not illegal.is_empty():
			return _fail_after(command_id, HHAgentErrors.E_CONFLICT, illegal, "state", rec, now_ms)
	var used: Dictionary = rec.get("used", {}) if rec.get("used", {}) is Dictionary else {}
	used["wall_ms"] = maxi(0, now_ms - int(rec.get("started_at_ms", now_ms)))
	rec["used"] = used
	if rec.get("cancelled", false) == true or str(rec.get("state", "")) == "cancelled":
		rec["cancelled"] = true
		rec["state"] = "cancelled"
		var saved0: Dictionary = _save(rec)
		if saved0.get("ok", false) != true:
			return _errors.fail(command_id, str(saved0.get("code", HHAgentErrors.E_UNVERIFIED)), str(saved0.get("message", "persist")), str(saved0.get("path", "")))
		return _fail_after(command_id, HHAgentErrors.E_POLICY, "job is cancelled; resume will not execute", "job_id", rec, now_ms)
	if str(rec.get("state", "")) == "done":
		_save(rec)
		return _ack(command_id, rec, now_ms, false)
	if str(rec.get("state", "")) == "blocked":
		_save(rec)
		var code_b: String = HHAgentErrors.E_POLICY if str(rec.get("blocked_reason", "")) == "repair_cap" else HHAgentErrors.E_UNVERIFIED
		return _fail_after(command_id, code_b, str(rec.get("blocked_reason", "blocked")), "state", rec, now_ms)
	var hold: String = str(params.get("hold_after", rec.get("hold_after", "")))
	if params.has("hold_after"):
		rec["hold_after"] = str(params.get("hold_after", ""))
	var max_steps: int = int(params.get("max_steps", 32))
	if max_steps < 1:
		max_steps = 1
	if max_steps > 64:
		max_steps = 64
	var steps: int = 0
	while steps < max_steps:
		var state: String = str(rec.get("state", ""))
		if state == "done" or state == "blocked" or state == "cancelled":
			break
		var last: String = state
		var paused: bool = _paused()
		var outcome: String = _advance(rec, params, hold, paused)
		steps += 1
		used = rec.get("used", {}) if rec.get("used", {}) is Dictionary else {}
		used["wall_ms"] = maxi(0, now_ms - int(rec.get("started_at_ms", now_ms)))
		rec["used"] = used
		var billed: String = _budget_block(rec)
		if not billed.is_empty() and str(rec.get("state", "")) != "done" and str(rec.get("state", "")) != "blocked" and str(rec.get("state", "")) != "cancelled":
			_block(rec, billed)
		if outcome == "paused":
			_save(rec)
			return _fail_after(command_id, HHAgentErrors.E_PAUSED, "pause blocks %s" % last, "pause", rec, now_ms)
		if outcome.begins_with("illegal"):
			return _fail_after(command_id, HHAgentErrors.E_CONFLICT, outcome, "state", rec, now_ms)
		if outcome == "hold":
			break
		if hold != "" and str(rec.get("state", "")) == hold:
			break
	var saved: Dictionary = _save(rec)
	if saved.get("ok", false) != true:
		return _errors.fail(command_id, str(saved.get("code", HHAgentErrors.E_UNVERIFIED)), str(saved.get("message", "persist")), str(saved.get("path", "")))
	if str(rec.get("state", "")) == "blocked":
		var code2: String = HHAgentErrors.E_POLICY if str(rec.get("blocked_reason", "")) == "repair_cap" else HHAgentErrors.E_UNVERIFIED
		return _fail_after(command_id, code2, str(rec.get("blocked_reason", "blocked")), "state", rec, now_ms)
	if str(rec.get("state", "")) == "cancelled":
		return _fail_after(command_id, HHAgentErrors.E_POLICY, "job is cancelled; resume will not execute", "job_id", rec, now_ms)
	return _ack(command_id, rec, now_ms, true, {"steps": steps})


func _status(command_id: String, params: Dictionary) -> Dictionary:
	var job_id: String = str(params.get("job_id", ""))
	var rec: Dictionary = _load(job_id)
	if rec.is_empty():
		var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
		if play != null and play.current_run_id() == job_id and not job_id.is_empty():
			return _errors.ok_read(command_id, PackedStringArray(["job_status_known"]), {
				"job_id": job_id,
				"kind": "play",
				"state": "play",
				"current_task_id": job_id,
			})
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "job %s not found" % job_id, "job_id")
	return _errors.ok_read(command_id, PackedStringArray(["job_status_known"]), _view(rec, _now_ms()))


func _list(command_id: String, params: Dictionary) -> Dictionary:
	var limit_n: int = int(params.get("limit", 20))
	if limit_n < 1:
		limit_n = 1
	if limit_n > 100:
		limit_n = 100
	var jobs: Array = []
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play != null and not play.current_run_id().is_empty():
		jobs.append({"id": play.current_run_id(), "kind": "play", "run_id": play.current_run_id()})
	var root: String = ProjectSettings.globalize_path("res://%s" % HHAgentConstants.ORCH_DIR)
	var da: DirAccess = DirAccess.open(root)
	if da != null:
		da.list_dir_begin()
		var name_s: String = da.get_next()
		while not name_s.is_empty():
			if da.current_is_dir() and not name_s.begins_with("."):
				var rec: Dictionary = _load(name_s)
				if not rec.is_empty():
					var row: Dictionary = _view(rec, _now_ms())
					row["kind"] = "orchestrator"
					jobs.append(row)
			name_s = da.get_next()
		da.list_dir_end()
	var soak: HHAgentSoakAdapter = HHAgentSoakAdapter.current()
	if soak == null:
		soak = HHAgentSoakAdapter.new()
	for row_v: Variant in soak.list_jobs():
		if row_v is Dictionary:
			jobs.append(row_v)
	if jobs.size() > limit_n:
		jobs = jobs.slice(0, limit_n)
	return _errors.ok_read(command_id, PackedStringArray(["job_list_returned"]), {"jobs": jobs, "total": jobs.size()})


func _cancel(command_id: String, params: Dictionary) -> Dictionary:
	var job_id: String = str(params.get("job_id", ""))
	var rec: Dictionary = _load(job_id)
	if rec.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "job %s not found" % job_id, "job_id")
	rec["cancel_requested"] = true
	rec["cancelled"] = true
	rec["state"] = "cancelled"
	rec["blocked_reason"] = "cancelled"
	rec["heartbeat_at_ms"] = _now_ms()
	var tid: String = str(rec.get("current_task_id", ""))
	var st: String = _task_status(rec, tid)
	if st == "pending" or st == "running":
		_set_status(rec, tid, "cancelled")
	_skip_dependents(rec, "dependency_cancelled")
	var saved: Dictionary = _save(rec)
	if saved.get("ok", false) != true:
		return _errors.fail(command_id, str(saved.get("code", HHAgentErrors.E_UNVERIFIED)), str(saved.get("message", "persist")), str(saved.get("path", "")))
	return _errors.ok_changed(command_id, PackedStringArray(["job_cancelled"]), _view(rec, _now_ms()), true)


func _wait(command_id: String, params: Dictionary) -> Dictionary:
	var job_id: String = str(params.get("job_id", ""))
	var rec: Dictionary = _load(job_id)
	if rec.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "job %s not found" % job_id, "job_id")
	var timeout_sec: float = float(params.get("timeout_sec", 0))
	if timeout_sec < 0.0:
		timeout_sec = 0.0
	var deadline: int = _now_ms() + int(timeout_sec * 1000.0)
	var state: String = str(rec.get("state", ""))
	while state != "done" and state != "blocked" and state != "cancelled" and rec.get("cancelled", false) != true:
		var continued: Dictionary = _run(command_id, {"job_id": job_id, "resume": true, "max_steps": 16})
		rec = _load(job_id)
		if rec.is_empty():
			return continued
		state = str(rec.get("state", ""))
		if state == "done" or state == "blocked" or state == "cancelled":
			break
		if _now_ms() >= deadline:
			break
		OS.delay_msec(20)
	if state == "done" or state == "blocked" or state == "cancelled":
		return _errors.ok_changed(command_id, PackedStringArray(["job_terminal_state"]), _view(rec, _now_ms()), true)
	return _errors.fail_after(command_id, HHAgentErrors.E_TIMEOUT, "job has not reached a terminal state", "job_id", _view(rec, _now_ms()))

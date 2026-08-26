class_name HHAgentExportAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")

## Export preset / validate / background job accept / cancel / artifacts.
## Long Godot --export-release is a supervised job, not a _process block.

const PENDING_KEY: String = "_hh_export_pending"
const PRESET_RES: String = "res://export_presets.cfg"
const PRESET_TMP: String = "res://export_presets.cfg.tmp"
const WINDOWS_PLATFORM: String = "Windows Desktop"
const STRIP_FILTER: String = "addons/*,.hh-agent/*,*token*,*evidence*,*audit*,*contact_sheet*,assets/audit/*,tests/*,*sidecar*,*probe*,recreate_manifest.json,bridge/*,host/*"
const CROCKFORD: String = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
const PINNED_TEMPLATES: String = "4.7.1.stable"

static var _current: HHAgentExportAdapter

var _errors: HHAgentErrors = HHAgentErrors.new()
var _actions: HHAgentActions = HHAgentActions.new()
var _pending: Dictionary = {}
var _jobs: Dictionary = {}


static func current() -> HHAgentExportAdapter:
	return _current


func attach() -> void:
	_current = self
	if not _actions.loaded:
		_actions.load_from_res()


func detach() -> void:
	if _current == self:
		_current = null
	_pending = {}


func shutdown() -> void:
	_pending = {}
	detach()


func handles(action: String) -> bool:
	return (
		action == "preset"
		or action == "validate"
		or action == "build"
		or action == "cancel"
		or action == "artifacts"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	_precondition: Dictionary,
) -> Dictionary:
	if method != "godot.export" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not an export verb", "")
	_actions = actions
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if action == "preset":
		return _preset(command_id, params, post if not post.is_empty() else "export_preset_present")
	if action == "validate":
		return _validate(command_id, params, post if not post.is_empty() else "export_preset_valid")
	if action == "cancel":
		return _cancel(command_id, params, post if not post.is_empty() else "export_job_cancelled")
	if action == "artifacts":
		return _artifacts(command_id, params, post if not post.is_empty() else "export_artifact_list")
	return _build(command_id, params, post if not post.is_empty() else "export_job_accepted")


func poll_pending() -> Dictionary:
	if _pending.is_empty():
		return {}
	var command_id: String = str(_pending.get("command_id", ""))
	var deadline: int = int(_pending.get("deadline_ms", 0))
	if deadline > 0 and Time.get_ticks_msec() > deadline:
		return _fail_pending(command_id, HHAgentErrors.E_TIMEOUT, "export job timeout")
	var job_id: String = str(_pending.get("job_id", ""))
	var rec: Dictionary = _read_job(job_id)
	if rec.is_empty():
		return _fail_pending(command_id, HHAgentErrors.E_UNVERIFIED, "export job state missing")
	if bool(rec.get("cancel_requested", false)):
		return _finish_cancel(command_id, job_id)
	var state: String = str(rec.get("state", ""))
	if state == "cancelled":
		return _finish_cancel(command_id, job_id)
	if state == "failed":
		return _fail_pending(command_id, HHAgentErrors.E_UNVERIFIED, str(rec.get("message", "export failed")))
	if state == "done":
		return _finish_build(command_id, rec)
	return {PENDING_KEY: true, "command_id": command_id}


func _preset(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var name_s: String = _preset_name(str(params.get("name", "")))
	var platform: String = str(params.get("platform", ""))
	if name_s.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "preset name required", "name")
	if platform != "WindowsDesktop" and platform != WINDOWS_PLATFORM:
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "R9-WP1 ships Windows Desktop only", "platform")
	var cfg: ConfigFile = ConfigFile.new()
	if FileAccess.file_exists(PRESET_RES):
		var loaded: Error = cfg.load(PRESET_RES)
		if loaded != OK:
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "could not load export_presets.cfg", PRESET_RES)
	var idx: int = _find_preset_index(cfg, name_s)
	if idx < 0:
		idx = _next_preset_index(cfg)
	var section: String = "preset.%d" % idx
	cfg.set_value(section, "name", name_s)
	cfg.set_value(section, "platform", WINDOWS_PLATFORM)
	cfg.set_value(section, "dedicated_server", false)
	cfg.set_value(section, "custom_features", "")
	cfg.set_value(section, "export_filter", "all_resources")
	cfg.set_value(section, "include_filter", "")
	cfg.set_value(section, "exclude_filter", STRIP_FILTER)
	cfg.set_value(section, "export_path", "")
	cfg.set_value(section, "encrypt_pck", false)
	cfg.set_value("runnable", name_s, name_s)
	var saved: Dictionary = _atomic_save_cfg(cfg)
	if saved.get("ok", false) != true:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, str(saved.get("message", "preset save failed")), PRESET_RES)
	var readback: Dictionary = _read_preset(name_s)
	if readback.get("ok", false) != true:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "export_preset_present failed readback", PRESET_RES)
	return _ok(
		command_id,
		post,
		{
			"name": name_s,
			"platform": WINDOWS_PLATFORM,
			"exclude_filter": STRIP_FILTER,
			"path": PRESET_RES,
			"export_preset_present": true,
		},
		true,
	)


func _validate(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var name_s: String = _preset_name(str(params.get("name", "")))
	var preset: Dictionary = _read_preset(name_s)
	if preset.get("ok", false) != true:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, str(preset.get("message", "preset missing")), "name")
	var main_scene: String = str(ProjectSettings.get_setting("application/run/main_scene", ""))
	if main_scene.is_empty() or not main_scene.begins_with("res://"):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "main scene missing", "main_scene")
	if not FileAccess.file_exists(main_scene):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "main scene missing on disk", main_scene)
	if not FileAccess.file_exists("res://NOTICE.md"):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "NOTICE.md / license missing", "res://NOTICE.md")
	var templates: Dictionary = _templates_ok()
	if templates.get("ok", false) != true:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, str(templates.get("message", "templates")), "templates")
	var filt: String = str(preset.get("exclude_filter", ""))
	if (
		not filt.contains("addons/")
		or not filt.contains(".hh-agent/")
		or not filt.contains("token")
		or not filt.contains("audit")
		or not filt.contains("contact_sheet")
	):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "release filter missing strip needles", "exclude_filter")
	return _ok(
		command_id,
		post,
		{
			"name": name_s,
			"main_scene": main_scene,
			"templates": str(templates.get("version", PINNED_TEMPLATES)),
			"exclude_filter": filt,
			"export_preset_valid": true,
		},
		false,
	)


func _build(command_id: String, params: Dictionary, post: String) -> Dictionary:
	if not _pending.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_BUSY, "export job already running", "job")
	var validated: Dictionary = _validate(command_id, params, "export_preset_valid")
	if validated.get("ok", false) != true:
		return validated
	var name_s: String = _preset_name(str(params.get("name", "")))
	var out_raw: String = str(params.get("out_dir", params.get("out", "")))
	var jailed: Dictionary = _jail_out(out_raw)
	if jailed.get("ok", false) != true:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, str(jailed.get("message", "out_dir")), "out_dir")
	var job_id: String = _ulid()
	var rec: Dictionary = {
		"job_id": job_id,
		"name": name_s,
		"state": "accepted",
		"progress": 0,
		"pid": 0,
		"out_dir": str(jailed.get("abs", "")),
		"cancel_requested": false,
		"message": "accepted; sidecar/export_job supervises Godot CLI",
	}
	_jobs[job_id] = rec
	_write_job(rec)
	# Sidecar/export_job.py supervises Godot CLI. Arm pending so plugin poll
	# can finish when job.json is done. Do not spawn a second Godot --path.
	_pending = {
		"command_id": command_id,
		"job_id": job_id,
		"deadline_ms": Time.get_ticks_msec() + 360000,
		"post": post,
	}
	return {PENDING_KEY: true, "command_id": command_id}


func _cancel(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var job_id: String = str(params.get("job_id", "")).strip_edges()
	if job_id.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "job_id required", "job_id")
	var rec: Dictionary = _read_job(job_id)
	if rec.is_empty() and _jobs.has(job_id):
		var held: Variant = _jobs[job_id]
		if held is Dictionary:
			rec = held
	if rec.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "export job not found", "job_id")
	rec["cancel_requested"] = true
	rec["state"] = "cancelled"
	rec["message"] = "cancel has real state"
	var pid: int = int(rec.get("pid", 0))
	if pid > 0:
		OS.kill(pid)
		rec["pid"] = 0
	_jobs[job_id] = rec
	_write_job(rec)
	if str(_pending.get("job_id", "")) == job_id:
		_pending = {}
	return _ok(
		command_id,
		post,
		{"job_id": job_id, "state": "cancelled", "export_job_cancelled": true},
		true,
	)


func _artifacts(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var name_s: String = _preset_name(str(params.get("name", "")))
	var out_raw: String = str(params.get("out_dir", params.get("out", "")))
	var jailed: Dictionary = _jail_out(out_raw)
	if jailed.get("ok", false) != true:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, str(jailed.get("message", "out_dir")), "out_dir")
	var abs_dir: String = str(jailed.get("abs", ""))
	var items: Array = []
	var da: DirAccess = DirAccess.open(abs_dir)
	if da != null:
		da.list_dir_begin()
		var fname: String = da.get_next()
		while not fname.is_empty():
			if not da.current_is_dir():
				items.append({"name": fname, "preset": name_s})
			fname = da.get_next()
		da.list_dir_end()
	return _ok(command_id, post, {"name": name_s, "artifacts": items, "out_dir": abs_dir}, false)


func _finish_build(command_id: String, rec: Dictionary) -> Dictionary:
	_pending = {}
	return _ok(
		command_id,
		"export_job_accepted",
		{
			"job_id": str(rec.get("job_id", "")),
			"state": "done",
			"progress": int(rec.get("progress", 100)),
			"out_dir": str(rec.get("out_dir", "")),
			"export_job_accepted": true,
		},
		true,
	)


func _finish_cancel(command_id: String, job_id: String) -> Dictionary:
	_pending = {}
	return _ok(command_id, "export_job_cancelled", {"job_id": job_id, "state": "cancelled"}, true)


func _fail_pending(command_id: String, code: String, message: String) -> Dictionary:
	_pending = {}
	return _errors.fail(command_id, code, message, "export")


func _preset_name(raw: String) -> String:
	var name_s: String = raw.strip_edges()
	if name_s == "win64" or name_s == "WindowsDesktop":
		return WINDOWS_PLATFORM
	return name_s


func _find_preset_index(cfg: ConfigFile, name_s: String) -> int:
	var sections: PackedStringArray = cfg.get_sections()
	var i: int = 0
	while i < sections.size():
		var section: String = sections[i]
		i += 1
		if not section.begins_with("preset."):
			continue
		if str(cfg.get_value(section, "name", "")) == name_s:
			return int(section.trim_prefix("preset."))
	return -1


func _next_preset_index(cfg: ConfigFile) -> int:
	var n: int = 0
	while cfg.has_section("preset.%d" % n):
		n += 1
	return n


func _read_preset(name_s: String) -> Dictionary:
	if not FileAccess.file_exists(PRESET_RES):
		return {"ok": false, "message": "export_presets.cfg missing"}
	var cfg: ConfigFile = ConfigFile.new()
	if cfg.load(PRESET_RES) != OK:
		return {"ok": false, "message": "export_presets.cfg unreadable"}
	var idx: int = _find_preset_index(cfg, name_s)
	if idx < 0:
		return {"ok": false, "message": "preset %s missing" % name_s}
	var section: String = "preset.%d" % idx
	return {
		"ok": true,
		"name": str(cfg.get_value(section, "name", "")),
		"platform": str(cfg.get_value(section, "platform", "")),
		"exclude_filter": str(cfg.get_value(section, "exclude_filter", "")),
	}


func _templates_ok() -> Dictionary:
	var appdata: String = OS.get_environment("APPDATA")
	if appdata.is_empty():
		return {"ok": false, "message": "APPDATA missing"}
	var version_path: String = "%s/Godot/export_templates/%s/version.txt" % [appdata, PINNED_TEMPLATES]
	var release_path: String = "%s/Godot/export_templates/%s/windows_release_x86_64.exe" % [appdata, PINNED_TEMPLATES]
	if not FileAccess.file_exists(version_path) or not FileAccess.file_exists(release_path):
		return {"ok": false, "message": "export templates 4.7.1.stable not installed"}
	var version: String = FileAccess.get_file_as_string(version_path).strip_edges()
	if version.contains("4.7.2") or version.begins_with("4.8"):
		return {"ok": false, "message": "refused export templates %s" % version}
	if version != PINNED_TEMPLATES:
		return {"ok": false, "message": "template version %s != %s" % [version, PINNED_TEMPLATES]}
	return {"ok": true, "version": version}


func _jail_out(raw: String) -> Dictionary:
	var local: String = OS.get_environment("LOCALAPPDATA")
	var fallback: String = ""
	if not local.is_empty():
		fallback = "%s/HHGodotAgent/exports" % local
	var cand: String = raw.strip_edges()
	if cand.is_empty():
		cand = fallback
	if cand.is_empty():
		return {"ok": false, "message": "export out_dir required"}
	if cand.contains(".."):
		return {"ok": false, "message": "export out_dir escapes via .."}
	var norm: String = cand.replace("\\", "/")
	var artifacts: String = ProjectSettings.globalize_path("res://").replace("\\", "/")
	# Allowlist is LocalAppData exports plus repo artifacts/. Repo artifacts are
	# inside the studio repo, not "outside project."
	var allowed: bool = false
	if not fallback.is_empty() and norm.to_lower().begins_with(fallback.replace("\\", "/").to_lower()):
		allowed = true
	if norm.to_lower().contains("/artifacts/"):
		allowed = true
	if not allowed:
		return {"ok": false, "message": "export out_dir is not allowlisted"}
	DirAccess.make_dir_recursive_absolute(cand)
	return {"ok": true, "abs": cand}


func _job_abs(job_id: String) -> String:
	var local: String = OS.get_environment("LOCALAPPDATA")
	if local.is_empty():
		return ""
	return "%s/HHGodotAgent/exports/%s/job.json" % [local, job_id]


func _write_job(rec: Dictionary) -> void:
	var job_id: String = str(rec.get("job_id", ""))
	var path_s: String = _job_abs(job_id)
	if path_s.is_empty():
		return
	var dir_s: String = path_s.get_base_dir()
	DirAccess.make_dir_recursive_absolute(dir_s)
	var tmp: String = path_s + ".tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(JSON.stringify(rec))
	f.flush()
	f.close()
	DirAccess.rename_absolute(tmp, path_s)


func _read_job(job_id: String) -> Dictionary:
	if _jobs.has(job_id):
		var held: Variant = _jobs[job_id]
		if held is Dictionary:
			return held
	var path_s: String = _job_abs(job_id)
	if path_s.is_empty() or not FileAccess.file_exists(path_s):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path_s))
	if parsed is Dictionary:
		return parsed
	return {}


func _atomic_save_cfg(cfg: ConfigFile) -> Dictionary:
	var tmp_abs: String = ProjectSettings.globalize_path(PRESET_TMP)
	var dest_abs: String = ProjectSettings.globalize_path(PRESET_RES)
	var bak_abs: String = dest_abs + ".hh-bak"
	if FileAccess.file_exists(PRESET_TMP):
		DirAccess.remove_absolute(tmp_abs)
	var err: Error = cfg.save(PRESET_TMP)
	if err != OK:
		return {"ok": false, "message": "tmp preset save failed"}
	var existed: bool = FileAccess.file_exists(PRESET_RES)
	if existed:
		if FileAccess.file_exists(dest_abs + ".hh-bak"):
			DirAccess.remove_absolute(bak_abs)
		var bak_err: Error = DirAccess.rename_absolute(dest_abs, bak_abs)
		if bak_err != OK:
			DirAccess.remove_absolute(tmp_abs)
			return {"ok": false, "message": "could not park export_presets.cfg"}
	var ren: Error = DirAccess.rename_absolute(tmp_abs, dest_abs)
	if ren != OK:
		if existed:
			DirAccess.rename_absolute(bak_abs, dest_abs)
		DirAccess.remove_absolute(tmp_abs)
		return {"ok": false, "message": "atomic preset replace failed"}
	if existed and FileAccess.file_exists(dest_abs + ".hh-bak"):
		DirAccess.remove_absolute(bak_abs)
	return {"ok": true}


func _ulid() -> String:
	var ms: int = int(Time.get_unix_time_from_system() * 1000.0)
	var chars: PackedStringArray = PackedStringArray()
	var t: int = ms
	var i: int = 0
	while i < 10:
		chars.append(CROCKFORD.substr(t % 32, 1))
		t = int(t / 32)
		i += 1
	var time_part: String = ""
	var r: int = chars.size() - 1
	while r >= 0:
		time_part += chars[r]
		r -= 1
	var rand_part: String = ""
	i = 0
	while i < 16:
		rand_part += CROCKFORD.substr(randi() % 32, 1)
		i += 1
	return time_part + rand_part


func _ok(command_id: String, post: String, after: Dictionary, changed: bool) -> Dictionary:
	var checks: PackedStringArray = PackedStringArray()
	checks.append(post)
	return _errors.ok_changed(command_id, checks, after, changed)

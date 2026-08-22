class_name HHAgentReviewStore
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _StoreScript: GDScript = preload("res://addons/hh_agent/core/hh_activity_store.gd")

## Milestone review card + paged unified diff. Reads only `.hh-agent/review/`.
## Missing/corrupt artifacts stay honest: artifact_ok=false + typed error.
## Never stores or returns the session token (A8). No per-action approve.

static var _current: HHAgentReviewStore

var _cached: Dictionary = {}
var _view: String = ""
var _paged_diff: Dictionary = {}
var _last_revert: Dictionary = {}
var _last_press: String = ""


static func current() -> HHAgentReviewStore:
	return _current


func attach() -> void:
	_current = self
	_cached = _card_snapshot({})
	_view = ""
	_paged_diff = {}
	_last_revert = {}
	_last_press = ""


func detach() -> void:
	if _current == self:
		_current = null
	_cached = {}
	_view = ""
	_paged_diff = {}
	_last_revert = {}
	_last_press = ""


func last_card() -> Dictionary:
	if _cached.is_empty():
		_cached = _card_snapshot({})
	var out: Dictionary = _cached.duplicate(true)
	if not _view.is_empty():
		out["view"] = _view
		out["opened"] = _view
	if not _paged_diff.is_empty():
		out["diff"] = _paged_diff
	if _view == "before":
		out["opened_text"] = str(out.get("before", ""))
	elif _view == "after":
		out["opened_text"] = str(out.get("after", ""))
	if not _last_revert.is_empty():
		out["last_revert"] = _last_revert
	if not _last_press.is_empty():
		out["dock_pressed"] = _last_press
	return out


func last_revert() -> Dictionary:
	return _last_revert.duplicate(true)


func remember_press(press: String) -> void:
	_last_press = press


func snapshot(params: Dictionary) -> Dictionary:
	_cached = _card_snapshot(params)
	return _redact(last_card())


func page_diff(params: Dictionary) -> Dictionary:
	var page: Dictionary = _diff_snapshot(params)
	if page.get("diff") is Dictionary:
		_paged_diff = page.get("diff") as Dictionary
		_view = "diff"
	_cached = page
	return _redact(page)


func open_view(params: Dictionary) -> Dictionary:
	var view_s: String = str(params.get("view", "diff"))
	var card: Dictionary = _card_snapshot(params)
	_cached = card
	_view = view_s
	card["view"] = view_s
	card["opened"] = view_s
	if view_s == "diff":
		var diff_params: Dictionary = params.duplicate(true)
		if not diff_params.has("offset"):
			diff_params["offset"] = 0
		if not diff_params.has("limit"):
			diff_params["limit"] = HHAgentConstants.DEFAULT_PAGE
		var page: Dictionary = _diff_snapshot(diff_params)
		var diff_v: Variant = page.get("diff", {})
		_paged_diff = diff_v if diff_v is Dictionary else {}
		card["diff"] = _paged_diff
		card["diff_ok"] = page.get("diff_ok", false) == true
		if page.get("diff_ok", false) != true:
			card["diff_ok"] = false
			if page.has("error"):
				card["error"] = page.get("error", {})
	elif view_s == "before":
		var before_s: String = str(card.get("before", ""))
		card["opened_text"] = before_s
		_paged_diff = _lines_page(before_s if not before_s.is_empty() else "before: —")
		card["diff"] = _paged_diff
	elif view_s == "after":
		var after_s: String = str(card.get("after", ""))
		card["opened_text"] = after_s
		_paged_diff = _lines_page(after_s if not after_s.is_empty() else "after: —")
		card["diff"] = _paged_diff
	return _redact(card)


func _card_snapshot(params: Dictionary) -> Dictionary:
	var resolved: Dictionary = _resolve_artifact(params)
	if resolved.get("ok", false) != true:
		return _fail_card(resolved)
	var abs_path: String = str(resolved.get("abs", ""))
	var rel_path: String = str(resolved.get("rel", ""))
	if not FileAccess.file_exists(abs_path):
		return _fail_card({
			"code": HHAgentErrors.E_UNVERIFIED,
			"message": "review artifact missing",
			"path": rel_path,
		})
	var raw: String = FileAccess.get_file_as_string(abs_path)
	var parsed: Variant = JSON.parse_string(raw)
	if not (parsed is Dictionary):
		return _fail_card({
			"code": HHAgentErrors.E_INVALID_TYPE,
			"message": "review artifact corrupt",
			"path": rel_path,
		})
	var body: Dictionary = parsed
	if not _body_has_required(body):
		return _fail_card({
			"code": HHAgentErrors.E_UNVERIFIED,
			"message": "review card needs goal and files/scenes/tests",
			"path": rel_path,
		})
	var screenshots: Array = _screenshot_status(body.get("screenshots", []))
	var gaps: Array = _as_str_array(body.get("gaps", body.get("known_gaps", [])))
	var checkpoint: Dictionary = _checkpoint_of(body.get("checkpoint", {}))
	var listed_diff: Dictionary = _listed_diff_state(body, abs_path)
	return {
		"artifact_ok": true,
		"schema": str(body.get("schema", HHAgentConstants.REVIEW_SCHEMA)),
		"path": rel_path,
		"goal": str(body.get("goal", "")),
		"assumptions": _as_str_array(body.get("assumptions", [])),
		"files": _as_str_array(body.get("files", [])),
		"scenes": _as_str_array(body.get("scenes", [])),
		"assets": _as_str_array(body.get("assets", [])),
		"tests": _as_str_array(body.get("tests", [])),
		"screenshots": screenshots,
		"screenshots_ok": _screenshots_all_ok(screenshots),
		"diff_ok": listed_diff.get("ok", false) == true,
		"diff_path": str(listed_diff.get("rel", "")),
		"perf": _as_dict(body.get("perf", {})),
		"license": str(body.get("license", "")),
		"gaps": gaps,
		"known_gaps": gaps,
		"checkpoint": checkpoint,
		"before": str(body.get("before", "")),
		"after": str(body.get("after", "")),
		"async_review": true,
		"approve_required": false,
		"g2_signoff": false,
		"buttons": {
			"before": {"visible": true, "label": "Before"},
			"after": {"visible": true, "label": "After"},
			"diff": {"visible": true, "label": "Diff"},
			"replay": {"visible": true, "label": "Replay", "mutate": false},
			"revert": {"visible": true, "label": "Revert checkpoint", "action": "git.revert_checkpoint"},
		},
	}


func _diff_snapshot(params: Dictionary) -> Dictionary:
	var card: Dictionary = _card_snapshot(params)
	if card.get("artifact_ok", false) != true:
		card["diff"] = _empty_page(params, 0)
		return card
	var resolved: Dictionary = _resolve_artifact(params)
	var rel_card: String = str(resolved.get("rel", HHAgentConstants.REVIEW_DIR + "/" + HHAgentConstants.REVIEW_FILE))
	var abs_card: String = str(resolved.get("abs", ""))
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(abs_card))
	var body: Dictionary = parsed if parsed is Dictionary else {}
	var listed: Dictionary = _listed_diff_state(body, abs_card)
	var lines: PackedStringArray = _load_diff_lines(body, abs_card)
	var page: Dictionary = _page_lines(lines, params)
	card["diff"] = page
	card["diff_ok"] = listed.get("ok", false) == true and not lines.is_empty()
	card["diff_path"] = str(listed.get("rel", ""))
	card["path"] = rel_card
	if card.get("diff_ok", false) != true:
		card["error"] = {
			"code": HHAgentErrors.E_UNVERIFIED,
			"message": "listed review diff missing",
			"path": str(listed.get("rel", "large.diff")),
		}
	return card


func _fail_card(err: Dictionary) -> Dictionary:
	var code: String = str(err.get("code", HHAgentErrors.E_UNVERIFIED))
	var message: String = str(err.get("message", "review artifact unreadable"))
	var path_s: String = str(err.get("path", HHAgentConstants.REVIEW_DIR + "/" + HHAgentConstants.REVIEW_FILE))
	return {
		"artifact_ok": false,
		"error": {
			"code": code,
			"message": message,
			"path": path_s,
		},
		"path": path_s,
		"goal": "",
		"assumptions": [],
		"files": [],
		"scenes": [],
		"assets": [],
		"tests": [],
		"screenshots": [],
		"screenshots_ok": false,
		"diff_ok": false,
		"perf": {},
		"license": "",
		"gaps": [],
		"known_gaps": [],
		"checkpoint": {},
		"async_review": true,
		"approve_required": false,
		"g2_signoff": false,
		"buttons": {
			"before": {"visible": true, "label": "Before"},
			"after": {"visible": true, "label": "After"},
			"diff": {"visible": true, "label": "Diff"},
			"replay": {"visible": true, "label": "Replay", "mutate": false},
			"revert": {"visible": true, "label": "Revert checkpoint", "action": "git.revert_checkpoint"},
		},
	}


func _resolve_artifact(params: Dictionary) -> Dictionary:
	var raw: String = str(params.get("path", ""))
	if raw.is_empty() and params.has("id"):
		raw = "%s.json" % str(params.get("id"))
	if raw.is_empty():
		raw = HHAgentConstants.REVIEW_FILE
	raw = raw.replace("\\", "/")
	if raw.begins_with("res://"):
		raw = raw.trim_prefix("res://")
	if raw.begins_with(".hh-agent/review/"):
		raw = raw.trim_prefix(".hh-agent/review/")
	if raw.contains("..") or raw.begins_with("/") or raw.contains(":"):
		return {
			"ok": false,
			"code": HHAgentErrors.E_PATH,
			"message": "review path jail",
			"path": raw,
		}
	var root: String = _review_root()
	if root.is_empty():
		return {
			"ok": false,
			"code": HHAgentErrors.E_PATH,
			"message": "project root missing",
			"path": HHAgentConstants.REVIEW_DIR,
		}
	var abs_path: String = root.path_join(raw)
	var abs_norm: String = abs_path.replace("\\", "/")
	var root_norm: String = root.replace("\\", "/")
	if not abs_norm.begins_with(root_norm):
		return {
			"ok": false,
			"code": HHAgentErrors.E_PATH,
			"message": "review path escapes review dir",
			"path": raw,
		}
	return {
		"ok": true,
		"abs": abs_path,
		"rel": "%s/%s" % [HHAgentConstants.REVIEW_DIR, raw],
	}


func _review_root() -> String:
	var root: String = ProjectSettings.globalize_path("res://").rstrip("/\\")
	if root.is_empty():
		return ""
	return root.path_join(".hh-agent").path_join("review")


func _load_diff_lines(body: Dictionary, abs_card: String) -> PackedStringArray:
	var inline: String = str(body.get("diff", body.get("unified_diff", "")))
	if not inline.is_empty() and not inline.begins_with(".") and not inline.ends_with(".diff"):
		return inline.replace("\r\n", "\n").split("\n")
	var rel_diff: String = str(body.get("diff_path", ""))
	if rel_diff.is_empty() and body.get("diff") is Dictionary:
		rel_diff = str((body.get("diff") as Dictionary).get("path", ""))
	if rel_diff.is_empty() and inline.ends_with(".diff"):
		rel_diff = inline
	if rel_diff.is_empty():
		rel_diff = "large.diff"
	rel_diff = rel_diff.replace("\\", "/")
	if rel_diff.begins_with(".hh-agent/review/"):
		rel_diff = rel_diff.trim_prefix(".hh-agent/review/")
	if rel_diff.contains(".."):
		return PackedStringArray()
	var abs_diff: String = abs_card.get_base_dir().path_join(rel_diff.get_file() if rel_diff.contains("/") else rel_diff)
	if rel_diff.contains("/"):
		abs_diff = _review_root().path_join(rel_diff)
	if not FileAccess.file_exists(abs_diff):
		return PackedStringArray()
	var text: String = FileAccess.get_file_as_string(abs_diff)
	return text.replace("\r\n", "\n").split("\n")


func _page_lines(lines: PackedStringArray, params: Dictionary) -> Dictionary:
	var limit: int = HHAgentConstants.DEFAULT_PAGE
	if params.has("limit"):
		limit = int(params.get("limit"))
	if limit < 1:
		limit = 1
	if limit > HHAgentConstants.REVIEW_DIFF_CAP:
		limit = HHAgentConstants.REVIEW_DIFF_CAP
	var offset: int = 0
	if params.has("offset"):
		offset = maxi(0, int(params.get("offset")))
	var total: int = lines.size()
	var end: int = mini(offset + limit, total)
	var items: Array = []
	var i: int = offset
	while i < end:
		items.append(lines[i])
		i += 1
	return {
		"items": items,
		"total": total,
		"offset": offset,
		"limit": limit,
		"has_more": end < total,
		"next_offset": end if end < total else offset,
	}


func _empty_page(params: Dictionary, total: int) -> Dictionary:
	var limit: int = HHAgentConstants.DEFAULT_PAGE
	if params.has("limit"):
		limit = int(params.get("limit"))
	if limit < 1:
		limit = 1
	if limit > HHAgentConstants.REVIEW_DIFF_CAP:
		limit = HHAgentConstants.REVIEW_DIFF_CAP
	var offset: int = 0
	if params.has("offset"):
		offset = maxi(0, int(params.get("offset")))
	return {
		"items": [],
		"total": total,
		"offset": offset,
		"limit": limit,
		"has_more": false,
		"next_offset": offset,
	}


func _screenshot_status(raw: Variant) -> Array:
	var out: Array = []
	var items: Array = []
	if raw is Array:
		items = raw
	elif raw is PackedStringArray:
		for item: String in raw:
			items.append(item)
	for item_v: Variant in items:
		var path_s: String = ""
		if item_v is Dictionary:
			path_s = str((item_v as Dictionary).get("path", ""))
		else:
			path_s = str(item_v)
		if path_s.is_empty():
			continue
		var exists: bool = _screenshot_exists(path_s)
		out.append({
			"path": path_s,
			"ok": exists,
			"status": "ok" if exists else "missing",
			"missing": not exists,
		})
	return out


func _screenshot_exists(path_s: String) -> bool:
	var raw: String = path_s.replace("\\", "/")
	if raw.begins_with("res://"):
		return FileAccess.file_exists(raw)
	if raw.contains(".."):
		return false
	if raw.begins_with(".hh-agent/review/"):
		var leaf: String = raw.trim_prefix(".hh-agent/review/")
		return FileAccess.file_exists(_review_root().path_join(leaf))
	var root: String = ProjectSettings.globalize_path("res://").rstrip("/\\")
	if root.is_empty():
		return false
	return FileAccess.file_exists(root.path_join(raw))


func _screenshots_all_ok(rows: Array) -> bool:
	if rows.is_empty():
		return false
	for item_v: Variant in rows:
		if item_v is Dictionary and (item_v as Dictionary).get("ok", false) != true:
			return false
	return true


func _checkpoint_of(raw: Variant) -> Dictionary:
	if raw is String:
		var id_s: String = str(raw)
		if id_s.is_empty():
			return {}
		return _enrich_checkpoint({"id": id_s})
	if raw is Dictionary:
		return _enrich_checkpoint(raw)
	return {}


func _enrich_checkpoint(raw: Dictionary) -> Dictionary:
	var out: Dictionary = {
		"id": str(raw.get("id", raw.get("checkpoint_id", raw.get("ref", "")))),
		"ref": str(raw.get("ref", raw.get("id", ""))),
		"dest_sha": str(raw.get("dest_sha", "")),
		"files": [],
	}
	var ckpt_id: String = str(out.get("id", ""))
	if ckpt_id.is_empty():
		return out
	var root: String = ProjectSettings.globalize_path("res://").rstrip("/\\")
	if root.is_empty():
		return out
	var man_path: String = root.path_join(".hh-agent").path_join("checkpoints").path_join(ckpt_id).path_join("manifest.json")
	if not FileAccess.file_exists(man_path):
		return out
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(man_path))
	if not (parsed is Dictionary):
		return out
	var man: Dictionary = parsed
	var files_v: Variant = man.get("files", [])
	var files: Array = []
	if files_v is Array:
		for row_v: Variant in files_v:
			if not (row_v is Dictionary):
				continue
			var row: Dictionary = row_v
			files.append({
				"rel": str(row.get("rel", "")),
				"sha256": str(row.get("sha256", "")),
				"missing": row.get("missing", false) == true,
			})
	out["files"] = files
	if str(out.get("dest_sha", "")).is_empty() and not files.is_empty():
		var first: Dictionary = files[0]
		out["dest_sha"] = str(first.get("sha256", ""))
	if str(out.get("ref", "")).is_empty():
		out["ref"] = str(man.get("checkpoint_id", ckpt_id))
	return out


func _as_str_array(raw: Variant) -> Array:
	var out: Array = []
	if raw is PackedStringArray:
		for item: String in raw:
			out.append(item)
		return out
	if raw is Array:
		for item_v: Variant in raw:
			out.append(str(item_v))
	elif typeof(raw) == TYPE_STRING and not str(raw).is_empty():
		out.append(str(raw))
	return out


func _as_dict(raw: Variant) -> Dictionary:
	if raw is Dictionary:
		return raw
	if typeof(raw) == TYPE_STRING:
		return {"notes": str(raw)}
	return {}


func write_card(params: Dictionary) -> Dictionary:
	var body: Dictionary = {
		"schema": HHAgentConstants.REVIEW_SCHEMA,
		"goal": str(params.get("goal", "")),
		"assumptions": _as_str_array(params.get("assumptions", [])),
		"files": _as_str_array(params.get("files", [])),
		"scenes": _as_str_array(params.get("scenes", [])),
		"assets": _as_str_array(params.get("assets", [])),
		"tests": _as_str_array(params.get("tests", [])),
		"screenshots": _as_str_array(params.get("screenshots", [])),
		"perf": _as_dict(params.get("perf", {"notes": "headless; no pixel golden"})),
		"license": str(params.get("license", "MIT")),
		"gaps": _as_str_array(params.get("gaps", [])),
		"before": str(params.get("before", "")),
		"after": str(params.get("after", "")),
	}
	var diff_path_s: String = str(params.get("diff_path", ""))
	if not diff_path_s.is_empty():
		body["diff_path"] = diff_path_s
	var ckpt_id: String = str(params.get("checkpoint_id", ""))
	if params.get("checkpoint") is Dictionary:
		ckpt_id = str((params.get("checkpoint") as Dictionary).get("id", ckpt_id))
	if params.get("auto", false) == true:
		_autofill_card(body)
		if ckpt_id.is_empty():
			ckpt_id = str(body.get("checkpoint_id", ""))
	if not ckpt_id.is_empty():
		body["checkpoint"] = {"id": ckpt_id}
		body.erase("checkpoint_id")
	elif body.has("checkpoint_id"):
		body["checkpoint"] = {"id": str(body.get("checkpoint_id", ""))}
		body.erase("checkpoint_id")
	if not _body_has_required(body):
		return _fail_card({
			"code": HHAgentErrors.E_UNVERIFIED,
			"message": "write_card needs goal and files/scenes/tests",
			"path": HHAgentConstants.REVIEW_DIR + "/" + HHAgentConstants.REVIEW_FILE,
		})
	var wrote: Dictionary = _atomic_write_card(body, str(params.get("path", "")))
	if wrote.get("ok", false) != true:
		return _fail_card({
			"code": str(wrote.get("code", HHAgentErrors.E_UNVERIFIED)),
			"message": str(wrote.get("message", "review card write failed")),
			"path": str(wrote.get("path", "")),
		})
	_cached = _card_snapshot({"path": str(wrote.get("rel", ""))})
	var out: Dictionary = last_card()
	out["written"] = true
	out["writer"] = "godot.review.write_card"
	return out


func revert_checkpoint(ref: String) -> Dictionary:
	var result: Dictionary = _restore_checkpoint(ref)
	result["action"] = "git.revert_checkpoint"
	_last_revert = result.duplicate(true)
	_last_press = "revert"
	return result


func card_checkpoint_ref(card: Dictionary = {}) -> String:
	var snap: Dictionary = card if not card.is_empty() else last_card()
	var ckpt_v: Variant = snap.get("checkpoint", {})
	if ckpt_v is Dictionary:
		var id_s: String = str((ckpt_v as Dictionary).get("id", ""))
		if id_s.is_empty():
			id_s = str((ckpt_v as Dictionary).get("ref", ""))
		return id_s
	return str(ckpt_v)


func _body_has_required(body: Dictionary) -> bool:
	if str(body.get("goal", "")).strip_edges().is_empty():
		return false
	var files: Array = _as_str_array(body.get("files", []))
	var scenes: Array = _as_str_array(body.get("scenes", []))
	var tests: Array = _as_str_array(body.get("tests", []))
	return files.size() + scenes.size() + tests.size() > 0


func _listed_diff_state(body: Dictionary, abs_card: String) -> Dictionary:
	var inline: String = str(body.get("diff", body.get("unified_diff", "")))
	if not inline.is_empty() and not inline.begins_with(".") and not inline.ends_with(".diff"):
		return {"ok": true, "rel": "", "inline": true}
	var rel_diff: String = str(body.get("diff_path", ""))
	if rel_diff.is_empty() and body.get("diff") is Dictionary:
		rel_diff = str((body.get("diff") as Dictionary).get("path", ""))
	if rel_diff.is_empty() and inline.ends_with(".diff"):
		rel_diff = inline
	if rel_diff.is_empty():
		rel_diff = "large.diff"
	rel_diff = rel_diff.replace("\\", "/")
	if rel_diff.begins_with(".hh-agent/review/"):
		rel_diff = rel_diff.trim_prefix(".hh-agent/review/")
	var abs_diff: String = abs_card.get_base_dir().path_join(rel_diff.get_file() if rel_diff.contains("/") else rel_diff)
	if rel_diff.contains("/"):
		abs_diff = _review_root().path_join(rel_diff)
	return {
		"ok": FileAccess.file_exists(abs_diff),
		"rel": rel_diff,
		"abs": abs_diff,
		"inline": false,
	}


func _lines_page(text: String) -> Dictionary:
	var lines: PackedStringArray = text.replace("\r\n", "\n").split("\n")
	return _page_lines(lines, {"offset": 0, "limit": HHAgentConstants.DEFAULT_PAGE})


func _autofill_card(body: Dictionary) -> void:
	var ckpt_id: String = str(body.get("checkpoint_id", ""))
	if body.get("checkpoint") is Dictionary:
		var existing: String = str((body.get("checkpoint") as Dictionary).get("id", ""))
		if not existing.is_empty():
			ckpt_id = existing
	if ckpt_id.is_empty():
		ckpt_id = _latest_checkpoint_id()
	if not ckpt_id.is_empty():
		body["checkpoint_id"] = ckpt_id
		var enriched: Dictionary = _enrich_checkpoint({"id": ckpt_id})
		var files_v: Variant = enriched.get("files", [])
		if (body.get("files") as Array).is_empty() and files_v is Array:
			var files: Array = []
			var scenes: Array = []
			for row_v: Variant in files_v:
				if not (row_v is Dictionary):
					continue
				var rel_s: String = str((row_v as Dictionary).get("rel", ""))
				if rel_s.is_empty():
					continue
				var res_s: String = rel_s if rel_s.begins_with("res://") else "res://%s" % rel_s
				files.append(res_s)
				if res_s.ends_with(".tscn"):
					scenes.append(res_s)
			if (body.get("files") as Array).is_empty() and not files.is_empty():
				body["files"] = files
			if (body.get("scenes") as Array).is_empty() and not scenes.is_empty():
				body["scenes"] = scenes
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store != null:
		var ids: PackedStringArray = store.last_command_ids(8)
		if (body.get("assumptions") as Array).is_empty():
			body["assumptions"] = [
				"Pause stays global A14",
				"observer commands=%d" % ids.size(),
			]
	if (body.get("assumptions") as Array).is_empty():
		body["assumptions"] = ["Pause stays global A14"]
	if (body.get("gaps") as Array).is_empty():
		body["gaps"] = ["G2 stays human"]
	if str(body.get("before", "")).is_empty():
		body["before"] = "checkpoint dest"
	if str(body.get("after", "")).is_empty():
		body["after"] = "working tree"
	if str(body.get("diff_path", "")).is_empty() and FileAccess.file_exists(_review_root().path_join("large.diff")):
		body["diff_path"] = "large.diff"


func _latest_checkpoint_id() -> String:
	var root: String = ProjectSettings.globalize_path("res://").rstrip("/\\")
	if root.is_empty():
		return ""
	var ckpt_root: String = root.path_join(".hh-agent").path_join("checkpoints")
	var dir: DirAccess = DirAccess.open(ckpt_root)
	if dir == null:
		return ""
	var best: String = ""
	var best_mtime: int = -1
	dir.list_dir_begin()
	var name_s: String = dir.get_next()
	while not name_s.is_empty():
		if dir.current_is_dir() and not name_s.begins_with("."):
			var man: String = ckpt_root.path_join(name_s).path_join("manifest.json")
			if FileAccess.file_exists(man):
				var mt: int = int(FileAccess.get_modified_time(man))
				if mt >= best_mtime:
					best_mtime = mt
					best = name_s
		name_s = dir.get_next()
	dir.list_dir_end()
	return best


func _atomic_write_card(body: Dictionary, raw_path: String) -> Dictionary:
	var resolved: Dictionary = _resolve_artifact({"path": raw_path})
	if resolved.get("ok", false) != true:
		return resolved
	var abs_path: String = str(resolved.get("abs", ""))
	var rel_path: String = str(resolved.get("rel", ""))
	var root: String = _review_root()
	if root.is_empty():
		return {"ok": false, "code": HHAgentErrors.E_PATH, "message": "review dir missing", "path": rel_path}
	DirAccess.make_dir_recursive_absolute(root)
	var tmp: String = abs_path + ".tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return {
			"ok": false,
			"code": HHAgentErrors.E_UNVERIFIED,
			"message": "could not open review card tmp",
			"path": rel_path,
		}
	f.store_string(JSON.stringify(body, "\t"))
	f.flush()
	f.close()
	if FileAccess.file_exists(abs_path):
		DirAccess.remove_absolute(abs_path)
	var ren: Error = DirAccess.rename_absolute(tmp, abs_path)
	if ren != OK:
		return {
			"ok": false,
			"code": HHAgentErrors.E_UNVERIFIED,
			"message": "atomic review card rename failed",
			"path": rel_path,
		}
	return {"ok": true, "abs": abs_path, "rel": rel_path}


func _restore_checkpoint(ref: String) -> Dictionary:
	var id_s: String = ref.strip_edges()
	if id_s.is_empty():
		return {
			"ok": false,
			"code": HHAgentErrors.E_CHECKPOINT,
			"message": "checkpoint ref missing",
			"ref": "",
		}
	id_s = id_s.replace("refs/hh-ckpt/", "").replace("hh-ckpt/", "")
	var root: String = ProjectSettings.globalize_path("res://").rstrip("/\\")
	if root.is_empty():
		return {
			"ok": false,
			"code": HHAgentErrors.E_PATH,
			"message": "project root missing",
			"ref": id_s,
		}
	var man_path: String = root.path_join(".hh-agent").path_join("checkpoints").path_join(id_s).path_join("manifest.json")
	if not FileAccess.file_exists(man_path):
		man_path = _find_checkpoint_manifest(root, ref)
	if man_path.is_empty() or not FileAccess.file_exists(man_path):
		return {
			"ok": false,
			"code": HHAgentErrors.E_CHECKPOINT,
			"message": "checkpoint ref not found: %s" % ref,
			"ref": ref,
		}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(man_path))
	if not (parsed is Dictionary):
		return {
			"ok": false,
			"code": HHAgentErrors.E_CHECKPOINT,
			"message": "checkpoint manifest unreadable",
			"ref": id_s,
		}
	var man: Dictionary = parsed
	var files_v: Variant = man.get("files", [])
	if not (files_v is Array):
		return {
			"ok": false,
			"code": HHAgentErrors.E_CHECKPOINT,
			"message": "checkpoint manifest has no files",
			"ref": id_s,
		}
	var files_dir: String = man_path.get_base_dir().path_join("files")
	var restored: Array = []
	var deleted: Array = []
	for row_v: Variant in files_v:
		if not (row_v is Dictionary):
			continue
		var row: Dictionary = row_v
		var rel_s: String = str(row.get("rel", "")).replace("\\", "/")
		if not _dest_allowed(rel_s):
			return {
				"ok": false,
				"code": HHAgentErrors.E_CHECKPOINT,
				"message": "refusing restore outside product files %s" % rel_s,
				"ref": id_s,
			}
		var dest: String = root.path_join(rel_s)
		if row.get("missing", false) == true:
			if FileAccess.file_exists(dest):
				DirAccess.remove_absolute(dest)
				deleted.append(rel_s)
			continue
		var src: String = files_dir.path_join(rel_s.replace("/", "__").replace("\\", "__"))
		if not FileAccess.file_exists(src):
			return {
				"ok": false,
				"code": HHAgentErrors.E_CHECKPOINT,
				"message": "quarantine missing %s" % rel_s,
				"ref": id_s,
			}
		var want_sha: String = str(row.get("sha256", ""))
		if not want_sha.is_empty() and FileAccess.get_sha256(src) != want_sha:
			return {
				"ok": false,
				"code": HHAgentErrors.E_CHECKPOINT,
				"message": "quarantine hash mismatch %s" % rel_s,
				"ref": id_s,
			}
		var copy_err: Dictionary = _atomic_restore_file(src, dest)
		if copy_err.get("ok", false) != true:
			copy_err["ref"] = id_s
			return copy_err
		if not want_sha.is_empty() and FileAccess.get_sha256(dest) != want_sha:
			return {
				"ok": false,
				"code": HHAgentErrors.E_CHECKPOINT,
				"message": "restore hash mismatch %s" % rel_s,
				"ref": id_s,
			}
		restored.append(rel_s)
	return {
		"ok": true,
		"ref": id_s,
		"action": "git.revert_checkpoint",
		"restored": restored,
		"deleted": deleted,
		"source": "plugin_local_restore",
	}


func _find_checkpoint_manifest(root: String, raw: String) -> String:
	var ckpt_root: String = root.path_join(".hh-agent").path_join("checkpoints")
	var dir: DirAccess = DirAccess.open(ckpt_root)
	if dir == null:
		return ""
	dir.list_dir_begin()
	var name_s: String = dir.get_next()
	while not name_s.is_empty():
		if dir.current_is_dir() and not name_s.begins_with("."):
			var man: String = ckpt_root.path_join(name_s).path_join("manifest.json")
			if FileAccess.file_exists(man):
				var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(man))
				if parsed is Dictionary:
					var rec: Dictionary = parsed
					if str(rec.get("checkpoint_id", "")) == raw or str(rec.get("git_ref", "")) == raw:
						dir.list_dir_end()
						return man
		name_s = dir.get_next()
	dir.list_dir_end()
	return ""


func _dest_allowed(rel: String) -> bool:
	var posix: String = rel.replace("\\", "/")
	if posix.is_empty() or posix.contains("..") or posix.begins_with("/"):
		return false
	if posix.begins_with("addons/hh_agent") or posix.begins_with(".hh-agent/"):
		return false
	return true


func _atomic_restore_file(src: String, dest: String) -> Dictionary:
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(src)
	if bytes.is_empty() and FileAccess.get_file_as_bytes(src).is_empty() and not FileAccess.file_exists(src):
		return {
			"ok": false,
			"code": HHAgentErrors.E_CHECKPOINT,
			"message": "restore source missing",
		}
	DirAccess.make_dir_recursive_absolute(dest.get_base_dir())
	var tmp: String = dest + ".hh-restore.tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return {
			"ok": false,
			"code": HHAgentErrors.E_CHECKPOINT,
			"message": "could not open restore tmp",
		}
	f.store_buffer(bytes)
	f.flush()
	f.close()
	if FileAccess.file_exists(dest):
		DirAccess.remove_absolute(dest)
	var ren: Error = DirAccess.rename_absolute(tmp, dest)
	if ren != OK:
		return {
			"ok": false,
			"code": HHAgentErrors.E_CHECKPOINT,
			"message": "restore rename failed",
		}
	return {"ok": true}


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

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


static func current() -> HHAgentReviewStore:
	return _current


func attach() -> void:
	_current = self
	_cached = _card_snapshot({})


func detach() -> void:
	if _current == self:
		_current = null
	_cached = {}


func last_card() -> Dictionary:
	if _cached.is_empty():
		_cached = _card_snapshot({})
	return _cached


func snapshot(params: Dictionary) -> Dictionary:
	_cached = _card_snapshot(params)
	return _redact(_cached.duplicate(true))


func page_diff(params: Dictionary) -> Dictionary:
	return _redact(_diff_snapshot(params))


func open_view(params: Dictionary) -> Dictionary:
	var view_s: String = str(params.get("view", "diff"))
	var card: Dictionary = _card_snapshot(params)
	card["view"] = view_s
	card["opened"] = view_s
	if view_s == "diff":
		var diff_params: Dictionary = params.duplicate(true)
		if not diff_params.has("offset"):
			diff_params["offset"] = 0
		if not diff_params.has("limit"):
			diff_params["limit"] = HHAgentConstants.DEFAULT_PAGE
		var page: Dictionary = _diff_snapshot(diff_params)
		card["diff"] = page.get("diff", {})
		if page.get("artifact_ok", false) != true and card.get("artifact_ok", false) == true:
			card["diff_ok"] = false
			card["error"] = page.get("error", {})
	elif view_s == "before":
		card["opened_text"] = str(card.get("before", ""))
	elif view_s == "after":
		card["opened_text"] = str(card.get("after", ""))
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
	if body.is_empty() and raw.strip_edges() != "{}":
		return _fail_card({
			"code": HHAgentErrors.E_INVALID_TYPE,
			"message": "review artifact corrupt",
			"path": rel_path,
		})
	var screenshots: Array = _screenshot_status(body.get("screenshots", []))
	var gaps: Array = _as_str_array(body.get("gaps", body.get("known_gaps", [])))
	var checkpoint: Dictionary = _checkpoint_of(body.get("checkpoint", {}))
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
	var lines: PackedStringArray = _load_diff_lines(body, abs_card)
	var page: Dictionary = _page_lines(lines, params)
	card["diff"] = page
	card["diff_ok"] = true
	card["path"] = rel_card
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

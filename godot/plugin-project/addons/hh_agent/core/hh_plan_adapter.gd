class_name HHAgentPlanAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _StoreScript: GDScript = preload("res://addons/hh_agent/core/hh_activity_store.gd")
const _ActivityDockScript: GDScript = preload("res://addons/hh_agent/ui/health/hh_activity_dock.gd")

## Compile PROJECT_BRIEF into an acyclic task DAG. Tests first, then produce.
## Vague fields become §6.2 assumptions. E1–E4 are blocker nodes, never silent picks.

const PLAN_SCHEMA: String = "hh-plan/1"
const EXCLUSIVE_RE: String = "(?i)\\b(only|exclusive|must be|must remain|cannot be anything but|strictly)\\b"

static var _current: HHAgentPlanAdapter

var _errors: HHAgentErrors = HHAgentErrors.new()
var _actions: HHAgentActions = HHAgentActions.new()
var _exclusive_re: RegEx = RegEx.new()


func _init() -> void:
	if _exclusive_re.compile(EXCLUSIVE_RE) != OK:
		push_warning("hh_agent: exclusive regex failed")


static func current() -> HHAgentPlanAdapter:
	return _current


func attach() -> void:
	_current = self
	if not _actions.loaded:
		_actions.load_from_res()
	if _exclusive_re.compile(EXCLUSIVE_RE) != OK:
		push_warning("hh_agent: exclusive regex failed")


func detach() -> void:
	if _current == self:
		_current = null


func shutdown() -> void:
	detach()


func handles(action: String) -> bool:
	return action == "plan"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	_precondition: Dictionary,
) -> Dictionary:
	if method != "godot.job" or action != "plan":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a job.plan", "")
	_actions = actions
	var brief_s: String = str(params.get("brief", ""))
	if brief_s.is_empty() and params.has("path"):
		brief_s = _read_brief_path(str(params.get("path", "")))
		if brief_s.begins_with("ERR:"):
			return _errors.fail(command_id, HHAgentErrors.E_PATH, brief_s.substr(4), "path")
	var fields_v: Variant = params.get("fields", {})
	var fields: Dictionary = fields_v if fields_v is Dictionary else {}
	var run_id: String = str(params.get("run_id", ""))
	var inject_cycle: bool = params.get("inject_cycle", false) == true
	var plan: Dictionary = compile_brief(brief_s, fields, run_id, inject_cycle)
	if plan.get("ok", false) != true:
		var err_v: Variant = plan.get("error", {})
		var err: Dictionary = err_v if err_v is Dictionary else {}
		return _errors.fail(
			command_id,
			str(err.get("code", HHAgentErrors.E_UNVERIFIED)),
			str(err.get("message", "plan compile failed")),
			str(err.get("path", "dag")),
		)
	var tasks_v: Variant = plan.get("tasks", [])
	if not (tasks_v is Array) or (tasks_v as Array).is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "empty DAG", "dag")
	var evidence: Dictionary = _write_evidence(plan)
	if evidence.get("ok", false) != true:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "plan evidence write failed", "r7w1/evidence")
	_publish(plan)
	var cards_v: Variant = plan.get("cards", [])
	var cards: Array = cards_v if cards_v is Array else []
	return _errors.ok_read(
		command_id,
		PackedStringArray(["plan_dag_compiled"]),
		{
			"plan": plan,
			"cards": cards,
			"evidence": evidence,
			"dock": {"plan_cards": cards.size(), "task_count": (tasks_v as Array).size()},
		},
	)


func compile_brief(brief: String, fields: Dictionary, run_id: String, inject_cycle: bool = false) -> Dictionary:
	var rid: String = run_id
	if not _run_id_ok(rid):
		rid = _default_run_id(brief)
	if brief.strip_edges().is_empty() and fields.is_empty():
		return _invalid(rid, HHAgentErrors.E_MISSING_REQUIRED, "brief or fields required", "brief")
	var doc: Dictionary = _parse_brief(brief, fields)
	var raw_blockers: Array = _detect_blockers(doc)
	var assumptions: Array = _apply_assumptions(doc)
	var tasks: Array = _build_tasks(doc, rid, raw_blockers)
	if inject_cycle and tasks.size() >= 2:
		var first_v: Variant = tasks[0]
		var last_v: Variant = tasks[tasks.size() - 1]
		if first_v is Dictionary and last_v is Dictionary:
			var first: Dictionary = first_v
			var deps_v: Variant = first.get("deps", [])
			var deps: Array = deps_v if deps_v is Array else []
			deps.append(str((last_v as Dictionary).get("id", "")))
			first["deps"] = deps
	var leftover: PackedStringArray = detect_cycle(tasks)
	if leftover.size() > 0:
		return _invalid(rid, HHAgentErrors.E_CONFLICT, "circular DAG", "dag")
	var ordered: Array = _topo_sort(tasks)
	if ordered.is_empty():
		return _invalid(rid, HHAgentErrors.E_UNVERIFIED, "empty DAG", "dag")
	var original: Dictionary = _parse_brief(brief, fields)
	var acc_items: Array = _acceptance_items(doc, ordered)
	var blockers: Array = []
	var cards: Array = []
	for node_v: Variant in ordered:
		if not (node_v is Dictionary):
			continue
		var node: Dictionary = node_v
		if str(node.get("kind", "")) == "blocker":
			var b_v: Variant = node.get("blocker", {})
			if b_v is Dictionary:
				blockers.append({
					"code": str((b_v as Dictionary).get("code", "")),
					"message": str((b_v as Dictionary).get("message", "")),
					"task_id": str(node.get("id", "")),
				})
		var summary: String = "%s %s ← %s" % [
			str(node.get("kind", "")),
			str(node.get("verify", "")),
			",".join(node.get("acceptance", []) as Array) if node.get("acceptance", []) is Array else "",
		]
		if str(node.get("kind", "")) == "blocker" and node.get("blocker") is Dictionary:
			var bb: Dictionary = node.get("blocker")
			summary = "%s %s" % [str(bb.get("code", "")), str(bb.get("message", ""))]
		cards.append({"id": str(node.get("id", "")), "kind": str(node.get("kind", "")), "summary": summary})
	var traces: Array = []
	for item_v: Variant in acc_items:
		if not (item_v is Dictionary):
			continue
		var item: Dictionary = item_v
		traces.append(_trace_row(item, ordered))
	var status: String = "blocked" if blockers.size() > 0 else "ready"
	return {
		"ok": true,
		"schema": PLAN_SCHEMA,
		"status": status,
		"run_id": rid,
		"complete": _is_complete(original),
		"acyclic": true,
		"tasks": ordered,
		"acceptance": acc_items,
		"assumptions": assumptions,
		"blockers": blockers,
		"traces": traces,
		"cards": cards,
	}


func detect_cycle(tasks: Array) -> PackedStringArray:
	var incoming: Dictionary = {}
	var edges: Dictionary = {}
	var ids: PackedStringArray = PackedStringArray()
	for t_v: Variant in tasks:
		if not (t_v is Dictionary):
			continue
		var tid: String = str((t_v as Dictionary).get("id", ""))
		if tid.is_empty():
			continue
		ids.append(tid)
		incoming[tid] = 0
		edges[tid] = PackedStringArray()
	for t_v2: Variant in tasks:
		if not (t_v2 is Dictionary):
			continue
		var t: Dictionary = t_v2
		var tid2: String = str(t.get("id", ""))
		var deps_v: Variant = t.get("deps", [])
		if not (deps_v is Array):
			continue
		for dep_v: Variant in deps_v:
			var dep: String = str(dep_v)
			if not incoming.has(dep):
				continue
			var nxt: PackedStringArray = edges.get(dep, PackedStringArray())
			nxt.append(tid2)
			edges[dep] = nxt
			incoming[tid2] = int(incoming.get(tid2, 0)) + 1
	var ready: PackedStringArray = PackedStringArray()
	for id_s: String in ids:
		if int(incoming.get(id_s, 0)) == 0:
			ready.append(id_s)
	var seen: PackedStringArray = PackedStringArray()
	while ready.size() > 0:
		var id0: String = ready[0]
		ready.remove_at(0)
		seen.append(id0)
		var outs: PackedStringArray = edges.get(id0, PackedStringArray())
		for nxt_s: String in outs:
			var n: int = int(incoming.get(nxt_s, 1)) - 1
			incoming[nxt_s] = n
			if n == 0:
				ready.append(nxt_s)
	var leftover: PackedStringArray = PackedStringArray()
	for id_s2: String in ids:
		if seen.find(id_s2) < 0:
			leftover.append(id_s2)
	return leftover


func _parse_brief(brief: String, fields: Dictionary) -> Dictionary:
	var sections: Dictionary = _parse_sections(brief)
	var genre_b: Dictionary = _parse_bullets(str(sections.get("genre", "")))
	var camera_b: Dictionary = _parse_bullets(str(sections.get("camera", "")))
	var res_b: Dictionary = _parse_bullets(str(sections.get("resolution", "")))
	var input_b: Dictionary = _parse_bullets(str(sections.get("input", "")))
	var plat_b: Dictionary = _parse_bullets(str(sections.get("platform", "")))
	var art_b: Dictionary = _parse_bullets(str(sections.get("art", "")))
	var audio_b: Dictionary = _parse_bullets(str(sections.get("audio", "")))
	var save_b: Dictionary = _parse_bullets(str(sections.get("save", "")))
	var content_b: Dictionary = _parse_bullets(str(sections.get("content / license", sections.get("content", ""))))
	var audience_b: Dictionary = _parse_bullets(str(sections.get("audience", "")))
	var doc: Dictionary = {
		"genre": str(genre_b.get("value", "")),
		"fantasy": str(genre_b.get("player_fantasy", "")),
		"out_of_scope": str(genre_b.get("out_of_scope", "")),
		"camera": str(camera_b.get("mode", "")),
		"resolution": str(res_b.get("base_design_resolution", res_b.get("base", ""))),
		"stretch": str(res_b.get("stretch_mode", res_b.get("stretch", ""))),
		"aspect": str(res_b.get("aspect", "")),
		"devices": str(input_b.get("devices", "")),
		"actions": str(input_b.get("actions", "")),
		"platform": str(plat_b.get("ship_target", plat_b.get("ship", ""))),
		"art": str(art_b.get("style", "")),
		"audio_bus": str(audio_b.get("bus_layout", audio_b.get("bus", ""))),
		"audio_music": str(audio_b.get("music", "")),
		"audio_license": str(audio_b.get("license_source", audio_b.get("license", ""))),
		"save_needed": str(save_b.get("needed", "")),
		"audience": str(audience_b.get("value", audience_b.get("rating", ""))),
		"content": " ".join(content_b.values()),
		"acceptance": _parse_acceptance(str(sections.get("acceptance", ""))),
		"sections": sections,
	}
	_merge_fields(doc, fields)
	var scan_parts: PackedStringArray = PackedStringArray()
	for key_v: Variant in sections.keys():
		var key: String = str(key_v)
		if key == "assumption policy" or key == "assumption_policy":
			continue
		scan_parts.append(str(sections.get(key, "")))
	scan_parts.append(str(doc.get("genre", "")))
	scan_parts.append(str(doc.get("fantasy", "")))
	scan_parts.append(str(doc.get("out_of_scope", "")))
	scan_parts.append(str(doc.get("camera", "")))
	scan_parts.append(str(doc.get("platform", "")))
	scan_parts.append(str(doc.get("save_needed", "")))
	scan_parts.append(str(doc.get("audio_license", "")))
	scan_parts.append(str(doc.get("audience", "")))
	scan_parts.append(str(doc.get("content", "")))
	var acc_v: Variant = doc.get("acceptance", [])
	if acc_v is Array:
		for a_v: Variant in acc_v:
			scan_parts.append(str(a_v))
	doc["scan_text"] = "\n".join(scan_parts)
	return doc


func _parse_sections(md: String) -> Dictionary:
	var sections: Dictionary = {}
	var current: String = "preamble"
	var buf: PackedStringArray = PackedStringArray()
	var lines: PackedStringArray = md.replace("\r\n", "\n").split("\n")
	for line: String in lines:
		if line.begins_with("## "):
			sections[current] = "\n".join(buf)
			current = line.substr(3).strip_edges().to_lower()
			buf = PackedStringArray()
			continue
		buf.append(line)
	sections[current] = "\n".join(buf)
	return sections


func _parse_bullets(body: String) -> Dictionary:
	var out: Dictionary = {}
	for line: String in body.split("\n"):
		var s: String = line.strip_edges()
		if not s.begins_with("- ") and not s.begins_with("* "):
			continue
		s = s.substr(2).strip_edges()
		if s.begins_with("**"):
			var end: int = s.find("**", 2)
			if end > 2:
				var key: String = _field_key(s.substr(2, end - 2))
				var rest: String = s.substr(end + 2).strip_edges()
				if rest.begins_with(":"):
					rest = rest.substr(1).strip_edges()
				out[key] = rest
				continue
		var colon: int = s.find(":")
		if colon > 0:
			out[_field_key(s.substr(0, colon))] = s.substr(colon + 1).strip_edges()
	return out


func _parse_acceptance(body: String) -> PackedStringArray:
	var items: PackedStringArray = PackedStringArray()
	for line: String in body.split("\n"):
		var s: String = line.strip_edges()
		if s.begins_with("- ") or s.begins_with("* "):
			s = s.substr(2).strip_edges()
		elif s.length() > 2 and s[0].is_valid_int() and s.contains(". "):
			s = s.substr(s.find(". ") + 2).strip_edges()
		else:
			continue
		if s.begins_with("**"):
			var end: int = s.find("**", 2)
			if end > 2:
				var rest: String = s.substr(end + 2).strip_edges()
				if rest.begins_with(":"):
					s = rest.substr(1).strip_edges()
		if _is_placeholder(s) or s.to_lower().begins_with("replace these"):
			continue
		items.append(s)
	return items


func _merge_fields(doc: Dictionary, fields: Dictionary) -> void:
	var genre: Dictionary = fields.get("genre", {}) if fields.get("genre", {}) is Dictionary else {}
	var camera: Dictionary = fields.get("camera", {}) if fields.get("camera", {}) is Dictionary else {}
	var resolution: Dictionary = fields.get("resolution", {}) if fields.get("resolution", {}) is Dictionary else {}
	var input_d: Dictionary = fields.get("input", {}) if fields.get("input", {}) is Dictionary else {}
	var platform: Dictionary = fields.get("platform", {}) if fields.get("platform", {}) is Dictionary else {}
	var art: Dictionary = fields.get("art", {}) if fields.get("art", {}) is Dictionary else {}
	var audio: Dictionary = fields.get("audio", {}) if fields.get("audio", {}) is Dictionary else {}
	var save: Dictionary = fields.get("save", {}) if fields.get("save", {}) is Dictionary else {}
	if not str(genre.get("value", "")).is_empty():
		doc["genre"] = str(genre.get("value", ""))
	if not str(genre.get("player_fantasy", genre.get("fantasy", ""))).is_empty():
		doc["fantasy"] = str(genre.get("player_fantasy", genre.get("fantasy", "")))
	if not str(camera.get("mode", "")).is_empty():
		doc["camera"] = str(camera.get("mode", ""))
	if not str(resolution.get("base", resolution.get("base_design_resolution", ""))).is_empty():
		doc["resolution"] = str(resolution.get("base", resolution.get("base_design_resolution", "")))
	if not str(input_d.get("devices", "")).is_empty():
		doc["devices"] = str(input_d.get("devices", ""))
	if not str(platform.get("ship", platform.get("ship_target", ""))).is_empty():
		doc["platform"] = str(platform.get("ship", platform.get("ship_target", "")))
	if not str(art.get("style", "")).is_empty():
		doc["art"] = str(art.get("style", ""))
	if not str(audio.get("bus", audio.get("bus_layout", ""))).is_empty():
		doc["audio_bus"] = str(audio.get("bus", audio.get("bus_layout", "")))
	if not str(save.get("needed", "")).is_empty():
		doc["save_needed"] = str(save.get("needed", ""))
	if typeof(fields.get("audience", null)) == TYPE_STRING:
		doc["audience"] = str(fields.get("audience", ""))
	if fields.get("acceptance", []) is Array:
		var acc: PackedStringArray = doc.get("acceptance", PackedStringArray())
		for item_v: Variant in fields.get("acceptance", []):
			var item: String = str(item_v).strip_edges()
			if item.is_empty() or _is_placeholder(item):
				continue
			acc.append(item)
		doc["acceptance"] = acc


func _is_placeholder(value: String) -> bool:
	var t: String = value.strip_edges()
	if t.is_empty():
		return true
	if t.begins_with("("):
		return true
	if t == "yes | no" or t == "no | yes":
		return true
	if t.contains(" | ") and t.length() < 64 and _exclusive_re.search(t) == null:
		return true
	return false


func _filled(v: String) -> bool:
	return not _is_placeholder(v)


func _is_complete(doc: Dictionary) -> bool:
	var acc_v: Variant = doc.get("acceptance", [])
	var acc_n: int = acc_v.size() if acc_v is Array or acc_v is PackedStringArray else 0
	return (
		_filled(str(doc.get("genre", "")))
		and _filled(str(doc.get("camera", "")))
		and _filled(str(doc.get("resolution", "")))
		and _filled(str(doc.get("devices", "")))
		and _filled(str(doc.get("platform", "")))
		and _filled(str(doc.get("art", "")))
		and (_filled(str(doc.get("audio_bus", ""))) or _filled(str(doc.get("audio_music", ""))))
		and _filled(str(doc.get("save_needed", "")))
		and acc_n >= 2
	)


func _detect_blockers(doc: Dictionary) -> Array:
	var text: String = str(doc.get("scan_text", ""))
	var out: Array = []
	var seen: Dictionary = {}
	if (
		_re(text, "(?i)\\b(api key|apikey|openai key|anthropic key|steamworks secret|account password|oauth token)\\b")
		or _re(text, "(?i)credentials the machine does not")
		or _re(text, "(?i)must provide (a |an )?(secret|api key|token)")
		or _re(text, "(?i)\\.env file with")
	):
		_add_blocker(out, seen, "E1", "brief requires a secret, account, or API key the machine does not have")
	if (
		_re(text, "(?i)\\b(must buy|purchase a|paid asset|paid license|paid quota|unity asset store)\\b")
		or _re(text, "(?i)costs\\s*\\$")
	):
		_add_blocker(out, seen, "E2", "brief requires spend, paid quota, or buying assets/licenses")
	if (
		_re(text, "(?i)\\b(code sign|signing certificate|upload to steam|publish to the store|public publish|itch\\.io upload)\\b")
		or _re(text, "(?i)send (project |player )?data off")
	):
		_add_blocker(out, seen, "E3", "brief requires signing, store upload, public publish, or sending data off-machine")
	if _re(text, "(?i)\\b(2d[- ]only|must be 2d|2d exclusive|strictly 2d)\\b") and _re(text, "(?i)\\b(3d[- ]only|must be 3d|3d exclusive|strictly 3d)\\b"):
		_add_blocker(out, seen, "E4", "brief requires both exclusive 2D and exclusive 3D")
	var genre_blob: String = "%s %s %s" % [str(doc.get("genre", "")), str(doc.get("fantasy", "")), str(doc.get("out_of_scope", ""))]
	var fams: PackedStringArray = _families_of(genre_blob)
	if fams.size() >= 2 and _exclusive_re.search(genre_blob) != null:
		_add_blocker(out, seen, "E4", "brief names exclusive conflicting genres: %s" % " vs ".join(fams))
	if _re(text, "(?i)\\btop-?down only\\b") and _re(text, "(?i)\\b(side-?scroll|sidescroll) only\\b"):
		_add_blocker(out, seen, "E4", "brief requires exclusive top-down and exclusive side-scroll cameras")
	var save: String = str(doc.get("save_needed", "")).to_lower()
	var acc: String = ""
	var acc_v: Variant = doc.get("acceptance", [])
	if acc_v is PackedStringArray:
		acc = "\n".join(acc_v)
	elif acc_v is Array:
		acc = "\n".join(PackedStringArray(acc_v))
	var no_save: bool = save == "no" or _re(text, "(?i)\\bno save\\b")
	var yes_save: bool = save == "yes" or _re(text, "(?i)\\b(must have save|cloud save required|save/load required)\\b")
	if no_save and yes_save:
		_add_blocker(out, seen, "E4", "brief says no save and also requires save")
	if save == "no" and _re(acc, "(?i)\\b(save|persist|cloud save)\\b") and _re(acc, "(?i)\\b(must|required)\\b"):
		_add_blocker(out, seen, "E4", "acceptance requires save while save.needed is no")
	var aud: String = "%s %s %s" % [str(doc.get("audience", "")), str(doc.get("fantasy", "")), str(doc.get("genre", ""))]
	if _re(aud, "(?i)\\b(kids? only|e-rated only|everyone 10 only|child audience only)\\b") and _re(aud, "(?i)\\b(mature only|18\\+|adults? only)\\b"):
		_add_blocker(out, seen, "E4", "brief requires exclusive kids and exclusive mature audiences")
	if _re(str(doc.get("platform", "")), "(?i)\\b(windows only|desktop only)\\b") and _re(text, "(?i)\\b(mobile only|ios only|android only)\\b"):
		_add_blocker(out, seen, "E4", "brief requires exclusive Windows and exclusive mobile platforms")
	if _re(text, "(?i)\\b(change the genre|pivot the genre|pivot to a different|scrap this genre|wrong target audience)\\b"):
		_add_blocker(out, seen, "E4", "brief asks to change genre, audience, or large scope (product pivot)")
	return out


func _apply_assumptions(doc: Dictionary) -> Array:
	var notes: Array = []
	if not _filled(str(doc.get("genre", ""))):
		doc["genre"] = "top-down 2D"
		_asm(notes, "genre.value", str(doc.get("genre", "")), "1 Godot 4.7.1-stable convention")
	if not _filled(str(doc.get("camera", ""))):
		doc["camera"] = "follow"
		_asm(notes, "camera.mode", str(doc.get("camera", "")), "1 Godot Camera2D follow convention")
	if not _filled(str(doc.get("resolution", ""))):
		doc["resolution"] = "1280x720"
		_asm(notes, "resolution.base", str(doc.get("resolution", "")), "1 pinned 2D template resolution")
	if not _filled(str(doc.get("stretch", ""))):
		doc["stretch"] = "canvas_items"
		_asm(notes, "resolution.stretch", str(doc.get("stretch", "")), "1 Godot 4 stretch convention")
	if not _filled(str(doc.get("aspect", ""))):
		doc["aspect"] = "keep"
		_asm(notes, "resolution.aspect", str(doc.get("aspect", "")), "1 Godot 4 aspect keep")
	if not _filled(str(doc.get("devices", ""))):
		doc["devices"] = "keyboard"
		_asm(notes, "input.devices", str(doc.get("devices", "")), "2 easiest to test and revert")
	if not _filled(str(doc.get("actions", ""))):
		doc["actions"] = "move, interact, pause"
		_asm(notes, "input.actions", str(doc.get("actions", "")), "3 fewest dependencies")
	if not _filled(str(doc.get("platform", ""))):
		doc["platform"] = "Windows desktop"
		_asm(notes, "platform.ship", str(doc.get("platform", "")), "1 repo R9 default")
	if not _filled(str(doc.get("art", ""))):
		doc["art"] = "PLACEHOLDER labeled sprites"
		_asm(notes, "art.style", str(doc.get("art", "")), "2 easiest to test and revert")
	if not _filled(str(doc.get("audio_bus", ""))) and not _filled(str(doc.get("audio_music", ""))):
		doc["audio_bus"] = "Master / Music / SFX"
		_asm(notes, "audio.bus", str(doc.get("audio_bus", "")), "1 Godot bus convention")
	if not _filled(str(doc.get("save_needed", ""))):
		doc["save_needed"] = "no"
		_asm(notes, "save.needed", str(doc.get("save_needed", "")), "3 fewest dependencies")
	var acc_v: Variant = doc.get("acceptance", [])
	var acc_n: int = acc_v.size() if acc_v is Array or acc_v is PackedStringArray else 0
	if acc_n == 0:
		var acc: PackedStringArray = PackedStringArray()
		acc.append("vertical slice: player can move and complete one interaction")
		acc.append("play session: 10 minutes with no blocker")
		acc.append("tests: GUT unit + MCP/E2E evidence on 4.7.1-stable")
		doc["acceptance"] = acc
		_asm(notes, "acceptance", "default measurable slice + play + tests", "2 easiest to test and revert")
	return notes


func _build_tasks(doc: Dictionary, run_id: String, blockers: Array) -> Array:
	var ev: String = "r7w1/evidence/%s" % run_id
	var spec: Dictionary = _produce_spec(doc)
	var acc: PackedStringArray = PackedStringArray()
	var acc_v: Variant = doc.get("acceptance", [])
	if acc_v is PackedStringArray:
		acc = acc_v
	elif acc_v is Array:
		for a_v: Variant in acc_v:
			acc.append(str(a_v))
	var acc_ids: PackedStringArray = PackedStringArray()
	var mapped: PackedStringArray = PackedStringArray()
	var produce_accs: Dictionary = {
		"produce_scene": [],
		"produce_script": [],
		"produce_art": [],
		"produce_audio": [],
	}
	var i: int = 0
	while i < acc.size():
		var aid0: String = "acc%02d" % (i + 1)
		acc_ids.append(aid0)
		var pk: String = _produce_kind_for(acc[i])
		mapped.append(pk)
		var bucket_v: Variant = produce_accs.get(pk, [])
		var bucket: Array = bucket_v if bucket_v is Array else []
		bucket.append(aid0)
		produce_accs[pk] = bucket
		i += 1
	var nodes: Array = []
	var define_ids: PackedStringArray = PackedStringArray()
	i = 0
	while i < acc.size():
		var aid: String = acc_ids[i]
		var did: String = "verify_define_%s" % aid
		define_ids.append(did)
		nodes.append(_task({
			"id": did,
			"kind": "test",
			"acceptance": [aid],
			"criterion": acc[i],
			"outputs": ["%s/tests/%s.hh-test.json" % [ev, aid]],
			"files": ["%s/tests/%s.hh-test.json" % [ev, aid]],
			"scene_leases": [],
			"deps": [],
			"verify": "test.define",
			"commands": ["test.define"],
			"budget": {"commands": 4, "minutes": 5},
			"rollback": "git.revert_checkpoint",
			"checkpoint": "",
		}))
		i += 1
	var blocker_ids: PackedStringArray = PackedStringArray()
	i = 0
	while i < blockers.size():
		var b_v: Variant = blockers[i]
		if b_v is Dictionary:
			var b: Dictionary = b_v
			var bid: String = "blocker_%s_%02d" % [str(b.get("code", "")), i + 1]
			blocker_ids.append(bid)
			var acc_arr: Array = []
			for a2: String in acc_ids:
				acc_arr.append(a2)
			nodes.append(_task({
				"id": bid,
				"kind": "blocker",
				"acceptance": acc_arr,
				"outputs": [],
				"files": [],
				"scene_leases": [],
				"deps": [],
				"verify": "none",
				"commands": [],
				"budget": {"commands": 0, "minutes": 0},
				"rollback": "none",
				"checkpoint": "",
				"blocker": {"code": str(b.get("code", "")), "message": str(b.get("message", ""))},
			}))
		i += 1
	var produce_deps: Array = []
	for d: String in define_ids:
		produce_deps.append(d)
	for b2: String in blocker_ids:
		produce_deps.append(b2)
	var all_acc: Array = []
	for a3: String in acc_ids:
		all_acc.append(a3)
	var scene_path: String = str(spec.get("scene", "res://scenes/overworld/overworld.tscn"))
	nodes.append(_task({
		"id": "produce_scene",
		"kind": "produce",
		"acceptance": (produce_accs.get("produce_scene", []) as Array).duplicate(),
		"outputs": [scene_path],
		"files": [scene_path],
		"scene_leases": [scene_path],
		"deps": produce_deps.duplicate(),
		"verify": "scene.read",
		"commands": ["scene.create", "node.add"],
		"budget": {"commands": 8, "minutes": 10},
		"rollback": "git.revert_checkpoint",
		"checkpoint": "",
	}))
	nodes.append(_task({
		"id": "produce_script",
		"kind": "produce",
		"acceptance": (produce_accs.get("produce_script", []) as Array).duplicate(),
		"outputs": [str(spec.get("script", ""))],
		"files": [str(spec.get("script", ""))],
		"scene_leases": [scene_path],
		"deps": ["produce_scene"],
		"verify": "script.validate",
		"commands": ["script.write", "script.attach"],
		"budget": {"commands": 8, "minutes": 10},
		"rollback": "git.revert_checkpoint",
		"checkpoint": "",
	}))
	nodes.append(_task({
		"id": "produce_art",
		"kind": "produce",
		"acceptance": (produce_accs.get("produce_art", []) as Array).duplicate(),
		"outputs": [str(spec.get("art", ""))],
		"files": [str(spec.get("art", ""))],
		"scene_leases": [],
		"deps": produce_deps.duplicate(),
		"verify": "asset.preview",
		"commands": ["asset.import"],
		"budget": {"commands": 6, "minutes": 15},
		"rollback": "git.revert_checkpoint",
		"checkpoint": "",
	}))
	nodes.append(_task({
		"id": "produce_audio",
		"kind": "produce",
		"acceptance": (produce_accs.get("produce_audio", []) as Array).duplicate(),
		"outputs": [str(spec.get("audio", ""))],
		"files": [str(spec.get("audio", ""))],
		"scene_leases": [],
		"deps": produce_deps.duplicate(),
		"verify": "audio.preview",
		"commands": ["audio.player"],
		"budget": {"commands": 6, "minutes": 15},
		"rollback": "git.revert_checkpoint",
		"checkpoint": "",
	}))
	var run_ids: PackedStringArray = PackedStringArray()
	i = 0
	while i < acc.size():
		var aid2: String = acc_ids[i]
		var rid: String = "verify_run_%s" % aid2
		run_ids.append(rid)
		var deps: Array = []
		if blockers.size() > 0:
			deps.append(define_ids[i])
			for bb: String in blocker_ids:
				deps.append(bb)
		else:
			deps.append(mapped[i] if i < mapped.size() else "produce_scene")
		nodes.append(_task({
			"id": rid,
			"kind": "verify",
			"acceptance": [aid2],
			"outputs": ["%s/reports/%s.json" % [ev, aid2]],
			"files": ["%s/reports/%s.json" % [ev, aid2]],
			"scene_leases": [scene_path],
			"deps": deps,
			"verify": "test.run",
			"commands": ["test.run"],
			"budget": {"commands": 6, "minutes": 8},
			"rollback": "git.revert_checkpoint",
			"checkpoint": "",
		}))
		i += 1
	var ck_deps: Array = []
	for r: String in run_ids:
		ck_deps.append(r)
	nodes.append(_task({
		"id": "checkpoint_slice",
		"kind": "checkpoint",
		"acceptance": all_acc.duplicate(),
		"outputs": ["%s/checkpoint.json" % ev],
		"files": ["%s/checkpoint.json" % ev],
		"scene_leases": [scene_path],
		"deps": ck_deps,
		"verify": "git.checkpoint",
		"commands": ["git.checkpoint"],
		"budget": {"commands": 2, "minutes": 2},
		"rollback": "git.revert_checkpoint",
		"checkpoint": "git.checkpoint",
	}))
	return nodes


func _topo_sort(tasks: Array) -> Array:
	if detect_cycle(tasks).size() > 0:
		return []
	var by_id: Dictionary = {}
	var incoming: Dictionary = {}
	var edges: Dictionary = {}
	for t_v: Variant in tasks:
		if not (t_v is Dictionary):
			continue
		var t: Dictionary = t_v
		var tid: String = str(t.get("id", ""))
		by_id[tid] = t
		incoming[tid] = 0
		edges[tid] = PackedStringArray()
	for t_v2: Variant in tasks:
		if not (t_v2 is Dictionary):
			continue
		var t2: Dictionary = t_v2
		var tid2: String = str(t2.get("id", ""))
		var deps_v: Variant = t2.get("deps", [])
		if not (deps_v is Array):
			continue
		for dep_v: Variant in deps_v:
			var dep: String = str(dep_v)
			if not by_id.has(dep):
				continue
			var nxt: PackedStringArray = edges.get(dep, PackedStringArray())
			nxt.append(tid2)
			edges[dep] = nxt
			incoming[tid2] = int(incoming.get(tid2, 0)) + 1
	var ready: Array = []
	for t_v3: Variant in tasks:
		if t_v3 is Dictionary and int(incoming.get(str((t_v3 as Dictionary).get("id", "")), 0)) == 0:
			ready.append(t_v3)
	_sort_tasks(ready)
	var order: Array = []
	while ready.size() > 0:
		var node: Dictionary = ready[0]
		ready.remove_at(0)
		order.append(node)
		var nid0: String = str(node.get("id", ""))
		var outs: PackedStringArray = edges.get(nid0, PackedStringArray())
		var sorted_next: Array = []
		for s2: String in outs:
			if by_id.has(s2):
				sorted_next.append(by_id[s2])
		_sort_tasks(sorted_next)
		for nxt_d: Variant in sorted_next:
			if not (nxt_d is Dictionary):
				continue
			var nd: Dictionary = nxt_d
			var nid: String = str(nd.get("id", ""))
			var n: int = int(incoming.get(nid, 1)) - 1
			incoming[nid] = n
			if n == 0:
				ready.append(nd)
				_sort_tasks(ready)
	return order


func _sort_tasks(items: Array) -> void:
	var keys: PackedStringArray = PackedStringArray()
	var copy: Array = items.duplicate()
	for item_v: Variant in copy:
		if item_v is Dictionary:
			var item: Dictionary = item_v
			keys.append("%d:%s" % [_kind_order(str(item.get("kind", ""))), str(item.get("id", ""))])
	keys.sort()
	items.clear()
	for key: String in keys:
		var id_s: String = key.substr(key.find(":") + 1)
		for item_v2: Variant in copy:
			if item_v2 is Dictionary and str((item_v2 as Dictionary).get("id", "")) == id_s:
				items.append(item_v2)
				break


func _task_less(a: Dictionary, b: Dictionary) -> bool:
	var ka: int = _kind_order(str(a.get("kind", "")))
	var kb: int = _kind_order(str(b.get("kind", "")))
	if ka != kb:
		return ka < kb
	return str(a.get("id", "")) < str(b.get("id", ""))


func _kind_order(kind: String) -> int:
	if kind == "test":
		return 0
	if kind == "verify":
		return 1
	if kind == "produce":
		return 2
	if kind == "checkpoint":
		return 3
	return 4


func _acceptance_items(doc: Dictionary, ordered: Array) -> Array:
	var out: Array = []
	var acc_v: Variant = doc.get("acceptance", [])
	var acc: PackedStringArray = PackedStringArray()
	if acc_v is PackedStringArray:
		acc = acc_v
	elif acc_v is Array:
		for a_v: Variant in acc_v:
			acc.append(str(a_v))
	var i: int = 0
	while i < acc.size():
		var aid: String = "acc%02d" % (i + 1)
		var tids: Array = []
		for n_v: Variant in ordered:
			if n_v is Dictionary:
				var accs_v: Variant = (n_v as Dictionary).get("acceptance", [])
				if accs_v is Array and (accs_v as Array).has(aid):
					tids.append(str((n_v as Dictionary).get("id", "")))
		out.append({"id": aid, "text": acc[i], "task_ids": tids})
		i += 1
	return out


func _publish(plan: Dictionary) -> void:
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store == null:
		return
	store.set_plan(plan)
	var dock: HHAgentActivityDock = HHAgentActivityDock.current()
	if dock != null:
		dock.set_status({"dock": store.snapshot({}), "plan": plan})
	var cards_v: Variant = plan.get("cards", [])
	if not (cards_v is Array):
		return
	for card_v: Variant in cards_v:
		if not (card_v is Dictionary):
			continue
		var card: Dictionary = card_v
		store.record_planned({
			"command_id": str(plan.get("run_id", "plan")),
			"action": "job.plan",
			"method": "godot.job",
			"scene": "",
			"summary": str(card.get("summary", card.get("id", ""))),
			"status": HHAgentConstants.STATUS_PLANNED,
		})


func _write_evidence(plan: Dictionary) -> Dictionary:
	var run_id: String = str(plan.get("run_id", ""))
	if not _run_id_ok(run_id):
		return {"ok": false, "assumptions": "", "plan": ""}
	var rel_md: String = "r7w1/evidence/%s/assumptions.md" % run_id
	var rel_json: String = "r7w1/evidence/%s/plan.json" % run_id
	var j1: Dictionary = _jail_plan_file(rel_md)
	var j2: Dictionary = _jail_plan_file(rel_json)
	if j1.get("ok", false) != true or j2.get("ok", false) != true:
		return {"ok": false, "assumptions": "", "plan": ""}
	var md: String = _assumptions_md(plan)
	if not _atomic_text(str(j1.get("abs", "")), md):
		return {"ok": false, "assumptions": "", "plan": ""}
	if not _atomic_text(str(j2.get("abs", "")), JSON.stringify(plan, "\t")):
		return {"ok": false, "assumptions": "", "plan": ""}
	return {
		"ok": true,
		"assumptions": rel_md,
		"plan": rel_json,
	}


func _jail_plan_file(rel: String) -> Dictionary:
	var p: String = rel.replace("\\", "/").strip_edges()
	if p.contains("..") or p.contains("addons/") or p.begins_with(".hh-agent"):
		return {"ok": false}
	if not p.begins_with("r7w1/evidence/"):
		return {"ok": false}
	var res_path: String = "res://%s" % p
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	var root: String = ProjectSettings.globalize_path("res://").replace("\\", "/").rstrip("/")
	if not abs_path.replace("\\", "/").begins_with(root):
		return {"ok": false}
	return {"ok": true, "abs": abs_path, "rel": p}


func _assumptions_md(plan: Dictionary) -> String:
	var lines: PackedStringArray = PackedStringArray()
	lines.append("# Assumptions")
	lines.append("")
	lines.append("Run: %s" % str(plan.get("run_id", "")))
	lines.append("Schema: %s" % PLAN_SCHEMA)
	lines.append("Pin: 4.7.1-stable")
	lines.append("Policy: plan §6.2 (convention → test/revert → fewest deps → quality if cost-equal)")
	lines.append("")
	var asm_v: Variant = plan.get("assumptions", [])
	if not (asm_v is Array) or (asm_v as Array).is_empty():
		lines.append("None. Brief specified the small defaults.")
		lines.append("")
		return "\n".join(lines)
	for a_v: Variant in asm_v:
		if a_v is Dictionary:
			var a: Dictionary = a_v
			lines.append("- **%s** `%s` = %s — %s" % [
				str(a.get("id", "")),
				str(a.get("field", "")),
				str(a.get("value", "")),
				str(a.get("rule", "")),
			])
	lines.append("")
	lines.append("E1–E4 are blockers, not assumptions.")
	lines.append("")
	return "\n".join(lines)


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


func _read_brief_path(res_path: String) -> String:
	if not res_path.begins_with("res://"):
		return "ERR:brief path must be res://"
	if res_path.contains(".."):
		return "ERR:brief path escapes"
	if not FileAccess.file_exists(res_path):
		return "ERR:brief file missing"
	return FileAccess.get_file_as_string(res_path)


func _task(body: Dictionary) -> Dictionary:
	return body


func _invalid(run_id: String, code: String, message: String, path_s: String) -> Dictionary:
	return {
		"ok": false,
		"schema": PLAN_SCHEMA,
		"status": "invalid",
		"run_id": run_id,
		"complete": false,
		"acyclic": code != HHAgentErrors.E_CONFLICT,
		"tasks": [],
		"acceptance": [],
		"assumptions": [],
		"blockers": [],
		"traces": [],
		"cards": [],
		"error": {"code": code, "message": message, "path": path_s},
	}


func _run_id_ok(run_id: String) -> bool:
	if run_id.length() != 26:
		return false
	var re: RegEx = RegEx.new()
	if re.compile("^[0-7][0-9A-HJKMNPQRSTVWXYZ]{25}$") != OK:
		return false
	return re.search(run_id) != null


func _default_run_id(brief: String) -> String:
	var hash_i: int = 0
	var i: int = 0
	while i < brief.length():
		hash_i = (hash_i * 33 + brief.unicode_at(i)) & 0x7fffffff
		i += 1
	var tail: String = ("%x" % hash_i).to_upper().replace("I", "X").replace("L", "X").replace("O", "X").replace("U", "X")
	while tail.length() < 8:
		tail = "0" + tail
	var rid: String = ("01R7WP1BRF00000000" + tail)
	if rid.length() > 26:
		rid = rid.substr(0, 26)
	return rid


func _field_key(raw: String) -> String:
	var s: String = raw.strip_edges().to_lower()
	var out: String = ""
	for ch: String in s:
		var code: int = ch.unicode_at(0)
		var is_alnum: bool = (code >= 97 and code <= 122) or (code >= 48 and code <= 57)
		if is_alnum:
			out += ch
		else:
			out += "_"
	while out.begins_with("_"):
		out = out.substr(1)
	while out.ends_with("_"):
		out = out.substr(0, out.length() - 1)
	return out.replace("__", "_")


func _families_of(text: String) -> PackedStringArray:
	var hay: String = " %s " % text.to_lower()
	var found: PackedStringArray = PackedStringArray()
	var groups: Array = [
		["platformer", "platform"],
		["puzzle", "match-3", "match3"],
		["shooter", "twin-stick", "twin stick", "shmup"],
		["rpg", "role-playing", "role playing"],
		["adventure"],
		["farming", "harvest"],
		["novel", "dialogue", "vn"],
		["tower defense", "tower-defense", " td "],
		["racing"],
		["stealth"],
	]
	for g_v: Variant in groups:
		if not (g_v is Array):
			continue
		var g: Array = g_v
		var name_s: String = str(g[0])
		for needle_v: Variant in g:
			if hay.contains(str(needle_v)):
				found.append(name_s)
				break
	return found


func _add_blocker(out: Array, seen: Dictionary, code: String, message: String) -> void:
	var key: String = "%s:%s" % [code, message]
	if seen.has(key):
		return
	seen[key] = true
	out.append({"code": code, "message": message})


func _re(text: String, pattern: String) -> bool:
	var re: RegEx = RegEx.new()
	if re.compile(pattern) != OK:
		return false
	return re.search(text) != null


func _asm(notes: Array, field: String, value: String, rule: String) -> void:
	notes.append({
		"id": "asm%02d" % (notes.size() + 1),
		"field": field,
		"value": value,
		"rule": rule,
	})


func _trace_row(item: Dictionary, ordered: Array) -> Dictionary:
	var aid: String = str(item.get("id", ""))
	var define_cmd: String = "test.define"
	var produce_cmd: String = ""
	var produce_id: String = ""
	var define_id: String = ""
	var test_s: String = ""
	var ck: String = ""
	for node_v: Variant in ordered:
		if not (node_v is Dictionary):
			continue
		var node: Dictionary = node_v
		var accs_v: Variant = node.get("acceptance", [])
		if not (accs_v is Array) or not (accs_v as Array).has(aid):
			continue
		var kind: String = str(node.get("kind", ""))
		var cmds_v: Variant = node.get("commands", [])
		var first_cmd: String = str(node.get("verify", ""))
		if cmds_v is Array and not (cmds_v as Array).is_empty():
			first_cmd = str((cmds_v as Array)[0])
		if kind == "test":
			define_id = str(node.get("id", ""))
			define_cmd = first_cmd
		elif kind == "produce" and produce_id.is_empty():
			produce_id = str(node.get("id", ""))
			produce_cmd = first_cmd
		elif kind == "verify":
			test_s = "test.run:%s" % aid
		elif kind == "checkpoint":
			ck = str(node.get("id", ""))
	var task_id: String = produce_id if not produce_id.is_empty() else define_id
	var command: String = produce_cmd if not produce_cmd.is_empty() else define_cmd
	return {
		"brief": aid,
		"task": task_id,
		"command": command,
		"test": test_s,
		"checkpoint": ck,
	}


func _produce_kind_for(text: String) -> String:
	var t: String = text.to_lower()
	if _re(t, "(?i)\\b(audio|sfx|sound|music|wav)\\b"):
		return "produce_audio"
	if _re(t, "(?i)\\b(art|sprite|tile|portrait|png|palette|pixel|gem art)\\b"):
		return "produce_art"
	if _re(t, "(?i)\\b(script|code|logic|input|move|play|swap|shoot|farm|dialogue|choice|save|key|door|match)\\b"):
		return "produce_script"
	return "produce_scene"


func _produce_spec(doc: Dictionary) -> Dictionary:
	var hay: String = "%s %s %s" % [
		str(doc.get("genre", "")),
		str(doc.get("fantasy", "")),
		str(doc.get("out_of_scope", "")),
	]
	var low: String = hay.to_lower()
	if _re(low, "(?i)\\bmatch[- ]?3\\b"):
		return {
			"slug": "match3",
			"scene": "res://scenes/match3/board.tscn",
			"script": "res://scripts/match3/board.gd",
			"art": "res://art/match3/gem.png",
			"audio": "res://audio/match3/match.wav",
		}
	if _re(low, "(?i)\\btower") or _re(low, "(?i)\\btd\\b"):
		return {
			"slug": "tower",
			"scene": "res://scenes/tower/lane.tscn",
			"script": "res://scripts/tower/tower.gd",
			"art": "res://art/tower/tower.png",
			"audio": "res://audio/tower/shot.wav",
		}
	if _re(low, "(?i)\\b(dialogue|visual novel|vn)\\b"):
		return {
			"slug": "dialogue",
			"scene": "res://scenes/dialogue/conversation.tscn",
			"script": "res://scripts/dialogue/graph.gd",
			"art": "res://art/dialogue/portrait.png",
			"audio": "res://audio/dialogue/talk.wav",
		}
	if _re(low, "(?i)\\b(farm|harvest)\\b"):
		return {
			"slug": "farming",
			"scene": "res://scenes/farm/field.tscn",
			"script": "res://scripts/farm/crop.gd",
			"art": "res://art/farm/crop.png",
			"audio": "res://audio/farm/hoe.wav",
		}
	if _re(low, "(?i)\\b(twin[- ]?stick|shmup|shooter)\\b"):
		return {
			"slug": "twin_stick",
			"scene": "res://scenes/arena/arena.tscn",
			"script": "res://scripts/arena/shooter.gd",
			"art": "res://art/arena/bullet.png",
			"audio": "res://audio/arena/fire.wav",
		}
	if _re(low, "(?i)\\bplatform"):
		return {
			"slug": "platformer",
			"scene": "res://scenes/platformer/level.tscn",
			"script": "res://scripts/platformer/player.gd",
			"art": "res://art/platformer/tiles.png",
			"audio": "res://audio/platformer/jump.wav",
		}
	if _re(low, "(?i)\\bpuzzle\\b"):
		return {
			"slug": "puzzle",
			"scene": "res://scenes/puzzle/board.tscn",
			"script": "res://scripts/puzzle/rules.gd",
			"art": "res://art/puzzle/tile.png",
			"audio": "res://audio/puzzle/click.wav",
		}
	return {
		"slug": "topdown",
		"scene": "res://scenes/overworld/overworld.tscn",
		"script": "res://scripts/overworld/player.gd",
		"art": "res://art/overworld/key.png",
		"audio": "res://audio/overworld/pickup.wav",
	}

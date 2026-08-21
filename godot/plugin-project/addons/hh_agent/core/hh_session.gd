class_name HHAgentSession
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")

## Locate sidecar session.json. project_id is SHA-256(canonical realpath)[:32],
## matching bridge/src/session/project.ts discoverProject.


func project_root_abs() -> String:
	return ProjectSettings.globalize_path("res://")


func canonical_root() -> String:
	## Match Node fs.realpathSync.native as closely as GDScript can:
	## no trailing slash, OS separators, uppercase Windows drive letter.
	var raw: String = project_root_abs().replace("\\", "/")
	while raw.ends_with("/") and raw.length() > 3:
		raw = raw.substr(0, raw.length() - 1)
	if OS.get_name() == "Windows":
		raw = raw.replace("/", "\\")
		if raw.length() >= 2 and raw.substr(1, 1) == ":":
			raw = raw.substr(0, 1).to_upper() + raw.substr(1)
	return raw


func computed_project_id() -> String:
	return _sha256_hex32(canonical_root())


func normalize_for_compare(path: String) -> String:
	var out: String = path.replace("\\", "/").strip_edges()
	while out.ends_with("/") and out.length() > 3:
		out = out.substr(0, out.length() - 1)
	if OS.get_name() == "Windows":
		out = out.to_lower()
	return out


func load_descriptor() -> Dictionary:
	var local: String = OS.get_environment("LOCALAPPDATA")
	if local.is_empty():
		return {}
	var candidate_id: String = computed_project_id()
	var direct: Dictionary = _read_descriptor("%s/%s/%s/%s/%s" % [
		local,
		HHAgentConstants.AGENT_DIR,
		HHAgentConstants.SESSIONS_DIR,
		candidate_id,
		HHAgentConstants.DESCRIPTOR_FILE,
	])
	if _matches_this_project(direct, candidate_id):
		return direct
	return {}


func has_token(desc: Dictionary) -> bool:
	return _token_hex64(str(desc.get("token", "")))


func _matches_this_project(desc: Dictionary, expected_id: String) -> bool:
	if desc.is_empty() or expected_id.is_empty():
		return false
	if str(desc.get("project_id", "")) != expected_id:
		return false
	var root: String = str(desc.get("project_root", ""))
	if root.is_empty():
		return false
	return normalize_for_compare(root) == normalize_for_compare(canonical_root())


func _token_hex64(token: String) -> bool:
	if token.length() != 64:
		return false
	var i: int = 0
	while i < 64:
		var code: int = token.unicode_at(i)
		var hex: bool = (
			(code >= 48 and code <= 57)
			or (code >= 97 and code <= 102)
			or (code >= 65 and code <= 70)
		)
		if not hex:
			return false
		i += 1
	return true


func _read_descriptor(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var text: String = FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	var rec: Dictionary = parsed
	if str(rec.get("protocol", "")) != HHAgentConstants.PROTOCOL:
		return {}
	if str(rec.get("host", "")) != "127.0.0.1":
		return {}
	if int(rec.get("port", 0)) <= 0:
		return {}
	return rec


func _sha256_hex32(text: String) -> String:
	var ctx: HashingContext = HashingContext.new()
	var start_err: Error = ctx.start(HashingContext.HASH_SHA256)
	if start_err != OK:
		return ""
	var upd_err: Error = ctx.update(text.to_utf8_buffer())
	if upd_err != OK:
		return ""
	var digest: PackedByteArray = ctx.finish()
	return digest.hex_encode().substr(0, 32)

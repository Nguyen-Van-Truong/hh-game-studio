class_name WorldPaths
extends RefCounted

## Editor and runtime share this gate (V-A6). Rejects traversal,
## absolute, user://, and any path that leaves the product root.


static func product_root() -> String:
	return _norm(ProjectSettings.globalize_path("res://")).trim_suffix("/")


static func is_res_path(path: String) -> bool:
	return path.begins_with("res://")


static func is_inside_product(path: String) -> bool:
	if path == "" or not is_res_path(path):
		return false
	var rest: String = path.substr(6)
	if rest == "":
		return false
	if rest.contains(".."):
		return false
	if rest.contains(":"):
		return false
	if rest.contains("\\"):
		return false
	if rest.contains("//"):
		return false
	var abs_path: String = _norm(ProjectSettings.globalize_path(path))
	var root: String = product_root()
	if abs_path == root:
		return true
	return abs_path.begins_with(root + "/")


static func visual_ok(path: String) -> bool:
	if not is_inside_product(path):
		return false
	return ResourceLoader.exists(path) or FileAccess.file_exists(path)


static func reject_reason(path: String) -> String:
	if path == "":
		return "empty path"
	if not is_res_path(path):
		return "path must be res:// under product root"
	if not is_inside_product(path):
		return "path escapes product root"
	if not ResourceLoader.exists(path) and not FileAccess.file_exists(path):
		return "visual missing"
	return ""


static func _norm(path: String) -> String:
	return path.replace("\\", "/")

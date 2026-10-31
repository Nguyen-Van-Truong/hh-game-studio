class_name ChibiHeadAtlas
extends RefCounted
## Blender-authored heads, prewarmed before gameplay. Lookup never touches disk.
const ROOT: String = "res://assets/sprites/chibi_brawler/r5_heads/"
const WORLD_RECT: Rect2 = Rect2(-5.0, -5.703125, 10.0, 10.0)
static var _heads: Dictionary = {}
static var _ready: bool = false
static var _issues: Array[String] = []
static var _generation: String = ""


static func prewarm() -> void:
	if _ready:
		return
	_ready = true
	if not FileAccess.file_exists(ROOT + "manifest.json"):
		_issues.append("head_manifest_missing")
		return
	var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string(ROOT + "manifest.json"))
	if not raw is Dictionary:
		_issues.append("head_manifest_missing_or_invalid")
		return
	var manifest: Dictionary = raw as Dictionary
	if manifest.get("schema") != "hh.chibi_blender_head_atlas.v1" or not manifest.get("characters") is Array or not manifest.get("expressions") is Array:
		_issues.append("head_manifest_schema")
		return
	if not ResourceLoader.exists(ROOT + "head_atlas.png"):
		_issues.append("head_texture_missing")
		return
	var texture: Texture2D = load(ROOT + "head_atlas.png") as Texture2D
	var characters: Array = manifest.get("characters", []) as Array
	var expressions: Array = manifest.get("expressions", []) as Array
	var cell: int = int(manifest.get("cell_size", 128))
	if texture == null or cell != 128 or characters.size() < 22 or characters.size() > 64 or expressions.size() < 7 or expressions.size() > 16:
		_issues.append("head_atlas_schema_or_count")
		return
	if texture.get_width() != expressions.size() * cell or texture.get_height() != characters.size() * cell:
		_issues.append("head_atlas_dimensions")
		return
	_generation = str(manifest.get("generation", manifest.get("generation_id", "r5")))
	# In an exported PCK the source PNG may not exist. ResourceLoader remains the
	# runtime authority; the offline manifest verifier checks source hashes.
	if FileAccess.file_exists(ROOT + "head_atlas.png") and manifest.has("atlas_sha256"):
		if FileAccess.get_sha256(ROOT + "head_atlas.png").to_lower() != str(manifest["atlas_sha256"]).to_lower():
			_issues.append("head_atlas_hash_mismatch")
			return
	for row: int in range(characters.size()):
		var cid: String = str(characters[row]).to_lower()
		for col: int in range(expressions.size()):
			var key: String = cid + ":" + str(expressions[col]).to_lower()
			if _heads.has(key):
				_issues.append("duplicate_head:" + key)
				_heads.clear()
				return
			var atlas: AtlasTexture = AtlasTexture.new()
			atlas.atlas = texture
			atlas.region = Rect2(col * cell, row * cell, cell, cell)
			atlas.filter_clip = true
			_heads[key] = atlas


static func get_head(char_id: String, expression: String) -> Texture2D:
	return _heads.get(char_id.to_lower() + ":" + expression.to_lower(), null) as Texture2D


static func validation() -> Dictionary:
	return {"ok": _ready and _issues.is_empty() and _heads.size() >= 154,
		"issues": _issues.duplicate(), "count": _heads.size(), "generation": _generation}

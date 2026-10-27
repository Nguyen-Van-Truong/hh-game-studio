extends RefCounted
## The JSON sidecar is the single source for cropped frames, foot pivots and
## clip cadence. No character-specific geometry or timing belongs in the view.

const REQUIRED_CLIPS: Array[String] = [
	"idle", "aim", "crouch", "run", "jump", "fall", "climb", "punch",
	"jump_kick", "dive", "downed", "shoot", "throw", "power", "hit", "roll",
]

static func read_manifest(path: String, texture: Texture2D) -> Dictionary:
	if texture == null or not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		return {}
	var textures: Array[Texture2D] = [texture]
	var sizes: Array[Vector2] = [texture.get_size()]
	var extra: Variant = Dictionary(parsed).get("extra_atlases", [])
	if not extra is Array:
		return {}
	for entry: Variant in Array(extra):
		if not entry is String or not String(entry).begins_with("res://art/characters/") or ".." in String(entry):
			return {}
		var loaded: Texture2D = load(String(entry)) as Texture2D
		if loaded == null:
			return {}
		textures.append(loaded)
		sizes.append(loaded.get_size())
	var result: Dictionary = validate_manifest(parsed, texture.get_size(), texture.resource_path, sizes)
	if not result.is_empty():
		result[&"textures"] = textures
	return result

static func validate_manifest(parsed: Variant, atlas_size: Vector2, atlas_path: String, atlas_sizes: Array[Vector2] = []) -> Dictionary:
	if not parsed is Dictionary:
		return {}
	var raw: Dictionary = parsed
	var version: int = int(raw.get("schema_version", 0))
	if version not in [1, 2] or raw.get("atlas", "") != atlas_path:
		return {}
	var height: float = float(raw.get("standing_art_height", 0))
	if not is_finite(height) or height <= 0.0:
		return {}
	var rows: Variant = raw.get("frames", null)
	var raw_clips: Variant = raw.get("clips", null)
	var durations: Variant = raw.get("duration_ticks", null)
	if not rows is Array or Array(rows).is_empty() or not raw_clips is Dictionary or not durations is Dictionary:
		return {}
	var frames: Array[Dictionary] = []
	for row: Variant in Array(rows):
		if not row is Dictionary:
			return {}
		var region_values: Variant = Dictionary(row).get("region", null)
		var foot_values: Variant = Dictionary(row).get("foot", null)
		if not _numeric_array(region_values, 4) or not _numeric_array(foot_values, 2):
			return {}
		var r: Array = region_values
		var f: Array = foot_values
		var region := Rect2(float(r[0]), float(r[1]), float(r[2]), float(r[3]))
		var foot := Vector2(float(f[0]), float(f[1]))
		var atlas: int = int(Dictionary(row).get("atlas_index", 0))
		if atlas < 0 or atlas >= maxi(1, atlas_sizes.size()):
			return {}
		var size: Vector2 = atlas_size if atlas_sizes.is_empty() else atlas_sizes[atlas]
		if region.size.x <= 0.0 or region.size.y <= 0.0 or not Rect2(Vector2.ZERO, size).encloses(region):
			return {}
		if foot.x < 0.0 or foot.y < 0.0 or foot.x > region.size.x or foot.y > region.size.y:
			return {}
		var grip_values: Variant = Dictionary(row).get("grip", [foot.x, foot.y - height * 0.55])
		var frame_height: float = float(Dictionary(row).get("standing_art_height", height))
		if not _numeric_array(grip_values, 2) or not is_finite(frame_height) or frame_height <= 0.0:
			return {}
		if version == 2 and not Dictionary(row).has("grip"):
			return {}
		var grip := Vector2(float(grip_values[0]), float(grip_values[1]))
		if not Rect2(Vector2.ZERO, region.size).has_point(grip):
			return {}
		frames.append({&"region": region, &"foot": foot, &"grip": grip, &"atlas_index": atlas, &"standing_height": frame_height})
	var clips: Dictionary = {}
	for key: String in REQUIRED_CLIPS:
		var indices: Variant = Dictionary(raw_clips).get(key, null)
		var duration: Variant = Dictionary(durations).get(key, null)
		if not indices is Array or Array(indices).is_empty() or not _whole_number(duration) or int(duration) <= 0:
			return {}
		for value: Variant in Array(indices):
			if not _whole_number(value) or int(value) < 0 or int(value) >= frames.size():
				return {}
		var loops: Dictionary = raw.get("loop", {})
		clips[StringName(key)] = {&"indices": Array(indices), &"duration": int(duration), &"loop": bool(loops.get(key, true))}
	return {&"frames": frames, &"clips": clips, &"standing_height": height}

static func frame_index(sheet: Dictionary, clip: StringName, elapsed_ticks: int) -> int:
	if sheet.is_empty():
		return 0
	var clips: Dictionary = sheet[&"clips"]
	var selected: Dictionary = clips.get(clip, clips[&"idle"])
	var indices: Array = selected[&"indices"]
	var phase: int = int(maxi(0, elapsed_ticks) / int(selected[&"duration"]))
	return int(indices[phase % indices.size() if bool(selected.get(&"loop", true)) else mini(phase, indices.size() - 1)])

static func _numeric_array(value: Variant, count: int) -> bool:
	if not value is Array or Array(value).size() != count:
		return false
	for component: Variant in Array(value):
		if not (component is float or component is int) or not is_finite(float(component)):
			return false
	return true

static func _whole_number(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == floorf(float(value))

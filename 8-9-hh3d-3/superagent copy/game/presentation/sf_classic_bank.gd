class_name SfClassicBank
extends RefCounted
## Runtime loader for the classic bundle under reference/sf-classic-restored.
## Files stay outside the Godot importer (.gdignore) and are read from disk.

const ROOT_RES := "res://reference/sf-classic-restored"
const PLAYER_SYMBOLS: Array[String] = ["player_johnny", "player_agent"]

## Flash frame labels on player_johnny (Symbol 731). PNG index is label index + 1.
const PLAYER_LABELS: Dictionary = {
	"IDLE": 1, "JUMP": 2, "RUN": 3, "FALL_F": 4, "FALL_B": 5,
	"KNOCKDOWN": 6, "KNEEL": 7, "COVER": 8, "SPRINT": 9, "ROLL": 10,
	"KICK": 11, "DIVE": 12, "PUNCH_01": 13, "PUNCH_02": 14, "PUNCH_03": 15,
	"MACHETE_01": 16, "MACHETE_02": 17, "MACHETE_03": 18,
	"AXE_01": 19, "AXE_02": 20, "AXE_03": 21,
	"SWORD_01": 22, "SWORD_02": 23, "SWORD_03": 24,
	"START_PISTOL": 25, "AIM_PISTOL": 26, "START_MAGNUM": 27, "AIM_MAGNUM": 28,
	"START_RIFLE": 29, "AIM_RIFLE": 30, "START_UZI": 31, "AIM_UZI": 32,
	"START_SHOTGUN": 33, "AIM_SHOTGUN": 34, "START_SNIPER": 35, "AIM_SNIPER": 36,
	"START_BAZOOKA": 37, "AIM_BAZOOKA": 38, "START_FLAMETHROWER": 39, "AIM_FLAMETHROWER": 40,
	"AIM_GRENADE": 41, "AIM_MOLOTOV": 42, "THROW": 43, "CLIMB": 47, "SLIDE": 48,
}

const WEAPON_SYMBOLS: Dictionary = {
	&"pistol": "wpn_pistol",
	&"sidearm": "wpn_pistol",
	&"rifle": "wpn_rifle",
	&"uzi": "wpn_uzi",
	&"shotgun": "wpn_shotgun",
	&"magnum": "wpn_magnum",
	&"sniper": "wpn_sniper",
	&"rocket_launcher": "wpn_bazooka",
	&"bazooka": "wpn_bazooka",
	&"flamethrower": "wpn_flamethrower",
	&"grenade": "wpn_grenades",
	&"grenades": "wpn_grenades",
	&"molotov": "wpn_molotovs",
	&"molotovs": "wpn_molotovs",
	&"knife": "wpn_machete",
	&"machete": "wpn_machete",
	&"pipe": "wpn_axe",
	&"axe": "wpn_axe",
	&"sword": "wpn_sword",
	&"medkit": "wpn_medkit",
	&"pill": "wpn_pills",
	&"bullet_time": "wpn_slowmo_05",
	&"bullet_time_5": "wpn_slowmo_05",
	&"bullet_time_10": "wpn_slowmo_10",
}

const PROP_SYMBOLS: Dictionary = {
	&"crate": "crate_hanging",
	&"barrel": "crate_debris_02",
	&"cover": "comfy_chair",
	&"glass": "glass_shard_1",
	&"chair": "comfy_chair",
	&"window": "window_seg",
	&"lamp": "lamp_1",
}

const SOUND_FILES: Dictionary = {
	&"shot": "2530_gun00.mp3",
	&"shot_pistol": "2530_gun00.mp3",
	&"shot_rifle": "2531_gun01.mp3",
	&"shot_uzi": "2530_gun00.mp3",
	&"shot_shotgun": "2532_gun02.mp3",
	&"shot_magnum": "2532_gun02.mp3",
	&"shot_sniper": "2531_gun01.mp3",
	&"shot_rocket_launcher": "2512_bazooka.mp3",
	&"shot_flamethrower": "2525_fireplosion.mp3",
	&"shot_grenade": "2521_explosion00.mp3",
	&"explosion": "2521_explosion00.mp3",
	&"hit": "2539_punch00.mp3",
	&"hit_punch": "2539_punch00.mp3",
	&"hit_punch_combo": "2539_punch00.mp3",
	&"hit_grab_punch": "2539_punch00.mp3",
	&"hit_kick": "2517_cut00.mp3",
	&"hit_tackle": "2518_cut01.mp3",
	&"hit_grab_throw": "2519_cut02.mp3",
	&"pickup": "2526_getHealth_00.mp3",
	&"jump": "2535_jump_00.mp3",
	&"fire": "2525_fireplosion.mp3",
	&"prop_hit": "2514_bustwood_1.mp3",
	&"prop_destroyed": "2507_comp_explode_01.mp3",
}

const SHEET = preload("res://game/presentation/sf_sheet_data.gd")
const LIBRARY_REL := "/xfl-export/Superfighters/00-original/LIBRARY"

static var _root: String = ""
static var _symbol_dirs: Dictionary = {}
static var _textures: Dictionary = {}
static var _sounds: Dictionary = {}
static var _indexed: bool = false
static var _atlases: Dictionary = {}
static var _sheet_frames: Dictionary = {}
static var _map_texture: Texture2D

static func available() -> bool:
	return DirAccess.dir_exists_absolute(_root_dir())

static func player_symbol(player_id: int) -> String:
	var index: int = clampi(player_id - 1, 0, PLAYER_SYMBOLS.size() - 1)
	return PLAYER_SYMBOLS[index]

static func sheet_frame(player_id: int, clip: String, phase: int) -> Texture2D:
	var frames: PackedInt32Array = _frames_for(clip)
	if frames.is_empty():
		return null
	return _sheet_cell(player_id, frames[posmod(phase, frames.size())])

static func map_texture() -> Texture2D:
	if _map_texture != null:
		return _map_texture
	var image := Image.new()
	var path: String = "%s%s/Bitmap 2219.png" % [_root_dir(), LIBRARY_REL]
	if image.load(path) == OK and image.get_width() > 0:
		_map_texture = ImageTexture.create_from_image(image)
	return _map_texture

static func player_texture(player_id: int, label: String) -> Texture2D:
	var frame: int = int(PLAYER_LABELS.get(label, 1))
	return frame_texture(player_symbol(player_id), frame)

static func weapon_texture(weapon_id: StringName) -> Texture2D:
	var symbol: String = String(WEAPON_SYMBOLS.get(weapon_id, ""))
	if symbol.is_empty() and String(weapon_id).begins_with("bullet_time"):
		symbol = "wpn_slowmo_05"
	if symbol.is_empty():
		return null
	return frame_texture(symbol, 1)

static func prop_texture(kind: StringName) -> Texture2D:
	var symbol: String = String(PROP_SYMBOLS.get(kind, ""))
	if symbol.is_empty():
		return null
	return frame_texture(symbol, 1)

static func frame_texture(symbol: String, frame: int) -> Texture2D:
	var key: String = "%s#%d" % [symbol, frame]
	if _textures.has(key):
		var cached_texture: Variant = _textures[key]
		return cached_texture if cached_texture is Texture2D else null
	var folder: String = _symbol_folder(symbol)
	var texture: Texture2D = null
	if not folder.is_empty():
		var image := Image.new()
		var path: String = "%s/%d.png" % [folder, maxi(1, frame)]
		if image.load(path) == OK and image.get_width() > 0:
			var trimmed := _trim_visible(image)
			if trimmed.get_width() > 1 and trimmed.get_height() > 1:
				texture = ImageTexture.create_from_image(trimmed)
		# A number of Flash clips begin or end with an intentionally empty
		# keyframe.  Returning null for those frames makes a valid classic effect
		# disappear and forces the procedural fallback.  Use the first visible
		# neighbouring frame while preserving the requested cache key.
		if texture == null:
			var candidates: Array[int] = []
			for offset: int in range(1, 16):
				candidates.append(maxi(1, frame - offset))
				candidates.append(frame + offset)
			for candidate: int in candidates:
				var fallback := Image.new()
				if fallback.load("%s/%d.png" % [folder, candidate]) != OK:
					continue
				var visible := _trim_visible(fallback)
				if visible.get_width() > 1 and visible.get_height() > 1:
					texture = ImageTexture.create_from_image(visible)
					break
	_textures[key] = texture
	return texture

static func release_audio() -> void:
	## Drop runtime MP3 references when a short-lived play/test harness exits.
	## Textures remain cached for the next scene; audio playback must not keep
	## AudioStreamMP3/ObjectDB instances alive after shutdown.
	_sounds.clear()

static func sound_for(kind: StringName) -> AudioStream:
	var file_name: String = String(SOUND_FILES.get(kind, ""))
	if file_name.is_empty() and String(kind).begins_with("hit_"):
		file_name = String(SOUND_FILES[&"hit"])
	if file_name.is_empty() and String(kind).begins_with("shot"):
		file_name = String(SOUND_FILES[&"shot"])
	if file_name.is_empty():
		return null
	if _sounds.has(file_name):
		var cached_sound: Variant = _sounds[file_name]
		return cached_sound if cached_sound is AudioStream else null
	var path: String = "%s/03-sounds/%s" % [_root_dir(), file_name]
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(path)
	var stream: AudioStreamMP3 = null
	if not bytes.is_empty():
		stream = AudioStreamMP3.new()
		stream.data = bytes
	_sounds[file_name] = stream
	return stream

static func _frames_for(clip: String) -> PackedInt32Array:
	match clip:
		"run", "sprint":
			return SHEET.RUN
		"jump":
			return SHEET.JUMP
		"fall":
			return SHEET.FALL
		"knockdown":
			return SHEET.KNOCKDOWN
		"roll":
			return SHEET.ROLL
		"climb":
			return SHEET.CLIMB
		"punch":
			return SHEET.PUNCH
		"kick":
			return SHEET.KICK
		"aim_pistol":
			return SHEET.AIM_PISTOL
		"aim_shotgun":
			return SHEET.AIM_SHOTGUN
		"aim_bazooka":
			return SHEET.AIM_BAZOOKA
		"throw":
			return SHEET.THROW
		"idle":
			return SHEET.IDLE
		_:
			# Unknown weapon clips deliberately fall back to the labeled PNG frame
			# instead of silently displaying the idle atlas cell.
			return PackedInt32Array()

static func _sheet_cell(player_id: int, cell_index: int) -> Texture2D:
	var cells: PackedInt32Array = SHEET.CELLS
	if cell_index < 0 or cell_index * 4 + 3 >= cells.size():
		return null
	var key: String = "%d#%d" % [player_id, cell_index]
	if _sheet_frames.has(key):
		var cached: Variant = _sheet_frames[key]
		return cached if cached is Texture2D else null
	var atlas: Texture2D = _player_atlas(player_id)
	var frame: AtlasTexture = null
	if atlas != null:
		frame = AtlasTexture.new()
		frame.atlas = atlas
		var origin: int = cell_index * 4
		frame.region = Rect2(cells[origin], cells[origin + 1], cells[origin + 2], cells[origin + 3])
	_sheet_frames[key] = frame
	return frame

static func _player_atlas(player_id: int) -> Texture2D:
	if _atlases.has(player_id):
		var cached: Variant = _atlases[player_id]
		return cached if cached is Texture2D else null
	var file_name: String = "Bitmap 1456.png" if player_id >= 2 else "Bitmap 1911.png"
	var image := Image.new()
	var texture: Texture2D = null
	if image.load("%s%s/%s" % [_root_dir(), LIBRARY_REL, file_name]) == OK and image.get_width() > 0:
		texture = ImageTexture.create_from_image(image)
	_atlases[player_id] = texture
	return texture

static func _trim_visible(image: Image) -> Image:
	var bounds: Rect2i = image.get_used_rect()
	if bounds.size.x < 2 or bounds.size.y < 2:
		return Image.new()
	if bounds.position == Vector2i.ZERO and bounds.size == image.get_size():
		return image
	return image.get_region(bounds)

static func _root_dir() -> String:
	if _root.is_empty():
		_root = ProjectSettings.globalize_path(ROOT_RES)
	return _root

static func _symbol_folder(symbol: String) -> String:
	_ensure_index()
	return String(_symbol_dirs.get(symbol, ""))

static func _ensure_index() -> void:
	if _indexed:
		return
	_indexed = true
	var csv_path: String = "%s/09-symbolClass/symbols.csv" % _root_dir()
	var sprites_root: String = "%s/02-sprites" % _root_dir()
	if not FileAccess.file_exists(csv_path):
		return
	var text: String = FileAccess.get_file_as_string(csv_path)
	for line: String in text.split("\n"):
		var parts: PackedStringArray = line.strip_edges().split(";")
		if parts.size() < 2:
			continue
		var symbol_id: String = parts[0].strip_edges()
		var symbol_name: String = parts[1].strip_edges()
		if symbol_id.is_empty() or symbol_name.is_empty():
			continue
		var named: String = "%s/DefineSprite_%s_%s" % [sprites_root, symbol_id, symbol_name]
		var plain: String = "%s/DefineSprite_%s" % [sprites_root, symbol_id]
		if DirAccess.dir_exists_absolute(named):
			_symbol_dirs[symbol_name] = named
		elif DirAccess.dir_exists_absolute(plain):
			_symbol_dirs[symbol_name] = plain

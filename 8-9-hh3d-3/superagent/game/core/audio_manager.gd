class_name SFAudioManager
extends Node
## AudioManager singleton loading all 73 original Superfighters sounds and pooling SFX/Music players.

const SOUNDS_DIR: String = "res://assets/sounds"
const SFX_POOL_SIZE: int = 16

var _streams: Dictionary = {}
var _event_groups: Dictionary = {}
var _sfx_pool: Array[AudioStreamPlayer] = []
var _sfx_pool_idx: int = 0
var _music_player: AudioStreamPlayer = null
var _loaded: bool = false


func _ready() -> void:
	ensure_loaded()
	_init_players()


func ensure_loaded() -> void:
	if _loaded:
		return
	_scan_sound_files()
	_build_event_groups()
	_loaded = true


func _init_players() -> void:
	if _music_player == null:
		_music_player = AudioStreamPlayer.new()
		_music_player.name = "MusicPlayer"
		add_child(_music_player)
	if _sfx_pool.is_empty():
		for i: int in range(SFX_POOL_SIZE):
			var p: AudioStreamPlayer = AudioStreamPlayer.new()
			p.name = "SFXPlayer_" + str(i)
			add_child(p)
			_sfx_pool.append(p)


func _scan_sound_files() -> void:
	var dir: DirAccess = DirAccess.open(SOUNDS_DIR)
	if dir == null:
		return
	dir.list_dir_begin()
	var fname: String = dir.get_next()
	while not fname.is_empty():
		if not dir.current_is_dir():
			var lower: String = fname.to_lower()
			if lower.ends_with(".mp3") or lower.ends_with(".wav"):
				var full_path: String = SOUNDS_DIR + "/" + fname
				var stream: AudioStream = _load_audio_stream(full_path)
				if stream != null:
					var stem: String = fname.get_basename()
					_streams[stem] = stream
					_streams[stem.to_lower()] = stream
					_streams[fname] = stream
		fname = dir.get_next()
	dir.list_dir_end()


func _load_audio_stream(res_path: String) -> AudioStream:
	if ResourceLoader.exists(res_path):
		var res: Resource = ResourceLoader.load(res_path)
		if res is AudioStream:
			return res as AudioStream
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	if res_path.to_lower().ends_with(".mp3") and FileAccess.file_exists(abs_path):
		var bytes: PackedByteArray = FileAccess.get_file_as_bytes(abs_path)
		if not bytes.is_empty():
			var mp3: AudioStreamMP3 = AudioStreamMP3.new()
			mp3.data = bytes
			return mp3
	return null


func _build_event_groups() -> void:
	# Exact event mappings from AS3 Sounds.as PlaySoundAt() / PlaySound()
	_event_groups = {
		"pistol": ["gun00", "gun01", "gun02", "gun03"],
		"magnum": ["magnum"],
		"uzi": ["uzi00", "uzi01"],
		"ak47": ["rifle00", "rifle01"],
		"rifle": ["rifle00", "rifle01"],
		"shotgun": ["shotgun00", "shotgun01", "shotgun02"],
		"shotgun_pump": ["shotgun_pump_p1", "shotgun_pump_p2"],
		"sniper": ["sniper00", "sniper01"],
		"sniper_bolt": ["shotgun_pump_p2"],
		"bazooka": ["bazooka"],
		"flamethrower": ["fireplosion"],
		"chainsaw": ["voltage_02"],
		"swing": ["svisch4", "svisch6"],
		"swing_sword": ["katana_01", "svisch4"],
		"swing_machete": ["svisch4", "svisch6"],
		"swing_axe": ["svisch6"],
		"punch": ["punch00", "punch01", "punch02", "punch03"],
		"cut": ["cut00", "cut01", "cut02"],
		"explosion": ["explosion00", "explosion01", "explosion02", "explosion03"],
		"fireplosion": ["fireplosion"],
		"powerup": ["getHealth_00"],
		"grenade_pin": ["grenade_safe"],
		"throw": ["svisch4"],
		"jump": ["jump_00"],
		"roll": ["roll"],
		"dive_catch": ["dive_catch"],
		"gib": ["gib_00"],
		"glass": ["glass_1", "glass_2"],
		"bustwood": ["bustwood_1", "bustwood_2"],
		"wood_impact": ["wood_impact00"],
		"ricochet": ["ric00"],
		"bullet_hit": ["bullet_hit_1", "bullet_hit_2", "bullet_hit_3"],
		"bullet_hitmetal": [
			"bullet_hitmetal_01",
			"bullet_hitmetal_02",
			"bullet_hitmetal_03",
			"bullet_hitmetal_04",
			"bullet_hitmetal_05"
		],
		"shell_bounce": ["shellbounce00", "shellbounce01"],
		"outofammo_light": ["outofammo_light"],
		"outofammo_heavy": ["outofammo_heavy"],
		"aim_small": ["aim_small"],
		"aim_big": ["aim_big"],
		"rifle_draw": ["rifle_draw"],
		"shotgun_aim": ["shotgun_aim"],
		"bazooka_aim": ["bazooka_aim"],
		"accept": ["accept_02"],
		"cancel": ["cancel_02"],
		"wilhelm": ["wilhelm"],
		"groovy": ["groovy00"],
		"theme": ["superfighters_theme"],
		"ambient": ["ambient_loop_1"],
	}


func has_sound(sound_id: String) -> bool:
	ensure_loaded()
	return get_sound_stream(sound_id) != null


func get_sound_stream(sound_id: String) -> AudioStream:
	ensure_loaded()
	if sound_id.is_empty():
		return null
	if _streams.has(sound_id):
		return _streams[sound_id] as AudioStream
	var lower: String = sound_id.to_lower()
	if _streams.has(lower):
		return _streams[lower] as AudioStream
	if _event_groups.has(lower):
		var choices: Array = _event_groups[lower] as Array
		if not choices.is_empty():
			var chosen: String = str(choices[randi() % choices.size()])
			if _streams.has(chosen):
				return _streams[chosen] as AudioStream
	return null


func get_loaded_sound_count() -> int:
	ensure_loaded()
	var count: int = 0
	for k: Variant in _streams.keys():
		var ks: String = str(k)
		if ks.ends_with(".mp3") or ks.ends_with(".wav"):
			count += 1
	return count


var _last_play_usec: Dictionary = {}


func play_sfx(sound_id: String, volume_db: float = 0.0, pitch_scale: float = 1.0) -> void:
	var key_u: String = sound_id.to_lower()
	if key_u == "jump" or key_u == "jump_00":
		return
	if DisplayServer.get_name() == "headless":
		return
	var now_u: int = Time.get_ticks_usec()
	if now_u - int(_last_play_usec.get(key_u, -100000)) < 28000:
		return
	_last_play_usec[key_u] = now_u
	ensure_loaded()
	_init_players()
	var stream: AudioStream = get_sound_stream(sound_id)
	if stream == null or _sfx_pool.is_empty():
		return
	var player: AudioStreamPlayer = _sfx_pool[_sfx_pool_idx]
	_sfx_pool_idx = (_sfx_pool_idx + 1) % _sfx_pool.size()
	player.stream = stream
	player.volume_db = volume_db
	player.pitch_scale = pitch_scale
	player.play()


func play_sfx_at(sound_id: String, _world_pos: Vector2, volume_db: float = 0.0) -> void:
	play_sfx(sound_id, volume_db, randf_range(0.96, 1.04))


func play_bgm(music_id: String = "superfighters_theme", volume_db: float = -4.0) -> void:
	play_music(music_id, volume_db)


func play_music(music_id: String = "superfighters_theme", volume_db: float = -4.0) -> void:
	if DisplayServer.get_name() == "headless":
		return
	ensure_loaded()
	_init_players()
	var stream: AudioStream = get_sound_stream(music_id)
	if stream == null or _music_player == null:
		return
	if _music_player.playing and _music_player.stream == stream:
		return
	_music_player.stream = stream
	_music_player.volume_db = volume_db
	_music_player.play()


func stop_music() -> void:
	if _music_player != null:
		_music_player.stop()
		_music_player.stream = null
	for p: AudioStreamPlayer in _sfx_pool:
		if is_instance_valid(p):
			p.stop()
			p.stream = null


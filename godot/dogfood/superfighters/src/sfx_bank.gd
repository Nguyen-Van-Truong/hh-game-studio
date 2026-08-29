class_name SfxBank
extends Node

const MUSIC_PATH: String = "res://assets/audio/music_fight.wav"
const PATHS: Dictionary = {
	"punch": "res://assets/audio/sfx_punch.wav",
	"shoot": "res://assets/audio/sfx_shoot.wav",
	"shotgun": "res://assets/audio/sfx_shotgun.wav",
	"pickup": "res://assets/audio/sfx_pickup.wav",
	"explode": "res://assets/audio/sfx_explode.wav",
	"jump": "res://assets/audio/sfx_jump.wav",
	"roll": "res://assets/audio/sfx_roll.wav",
	"dive": "res://assets/audio/sfx_jump.wav",
	"kick": "res://assets/audio/sfx_punch.wav",
	"hit": "res://assets/audio/sfx_hit.wav",
	"win": "res://assets/audio/sfx_win.wav",
	"lose": "res://assets/audio/sfx_lose.wav",
}

var last_id: String = ""
var _sfx_a: AudioStreamPlayer
var _sfx_b: AudioStreamPlayer
var _music: AudioStreamPlayer
var _music_db_before_duck: float = 0.0
var _ducked: bool = false
var muted: bool = false
var _shut_down: bool = false


func _ready() -> void:
	name = "SfxBank"
	process_mode = Node.PROCESS_MODE_ALWAYS
	if muted:
		return
	_ensure_players()


func play(sfx_id: String) -> void:
	var path: String = str(PATHS.get(sfx_id, ""))
	if path.is_empty():
		return
	last_id = sfx_id
	if muted or _shut_down:
		return
	_ensure_players()
	var stream: AudioStream = load(path) as AudioStream
	if stream == null:
		return
	var voice: AudioStreamPlayer = _sfx_a
	if _sfx_a.playing:
		voice = _sfx_b
	voice.stream = stream
	voice.play()


func start_music() -> void:
	if muted or _shut_down:
		return
	_ensure_players()
	var stream: AudioStream = load(MUSIC_PATH) as AudioStream
	if stream == null:
		return
	_music.stream = stream
	_music.play()


func duck(active: bool) -> void:
	var idx: int = AudioServer.get_bus_index("Music")
	if idx < 0:
		return
	if active and not _ducked:
		_music_db_before_duck = AudioServer.get_bus_volume_db(idx)
		AudioServer.set_bus_volume_db(idx, _music_db_before_duck - 12.0)
		_ducked = true
	elif not active and _ducked:
		AudioServer.set_bus_volume_db(idx, _music_db_before_duck)
		_ducked = false


func is_music_playing() -> bool:
	if muted or _shut_down:
		return false
	if _music == null or not is_instance_valid(_music):
		return false
	return _music.playing


func has_audio_players() -> bool:
	return _sfx_a != null and is_instance_valid(_sfx_a)


func is_sfx_playing() -> bool:
	if muted or _shut_down:
		return false
	if _sfx_a != null and is_instance_valid(_sfx_a) and _sfx_a.playing:
		return true
	if _sfx_b != null and is_instance_valid(_sfx_b) and _sfx_b.playing:
		return true
	return false


func shutdown() -> void:
	if _shut_down:
		return
	_shut_down = true
	duck(false)
	_release_player(_sfx_a)
	_release_player(_sfx_b)
	_release_player(_music)
	_sfx_a = null
	_sfx_b = null
	_music = null


func _exit_tree() -> void:
	shutdown()


func _ensure_players() -> void:
	if _sfx_a != null:
		return
	_sfx_a = AudioStreamPlayer.new()
	_sfx_a.name = "SfxA"
	_sfx_a.bus = "SFX"
	add_child(_sfx_a)
	_sfx_b = AudioStreamPlayer.new()
	_sfx_b.name = "SfxB"
	_sfx_b.bus = "SFX"
	add_child(_sfx_b)
	_music = AudioStreamPlayer.new()
	_music.name = "Music"
	_music.bus = "Music"
	_music.process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(_music)


func _release_player(player: AudioStreamPlayer) -> void:
	if player == null or not is_instance_valid(player):
		return
	if player.playing:
		player.stop()
	player.stream = null
	var parent: Node = player.get_parent()
	if parent != null:
		parent.remove_child(player)
	player.free()

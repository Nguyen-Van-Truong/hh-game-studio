class_name CombatAudio
extends Node
## Small self-authored procedural SFX bank.
##
## WAV streams are generated once per event kind, so the game has no external
## sound dependency for the Classic prototype.  This presentation node is
## intentionally outside MatchSession and never changes a replay hash.

const SF_BANK = preload("res://game/presentation/sf_classic_bank.gd")
const SAMPLE_RATE: int = 22050
const MAX_VOICES: int = 24

var _streams: Dictionary = {}
var _active_players: Array[AudioStreamPlayer2D] = []

func _ready() -> void:
	if _headless_audio_disabled():
		return
	_ensure_sfx_bus()

func _exit_tree() -> void:
	# A visual harness can end immediately after an action cue. Stop and free
	# every transient player before the node leaves the tree so AudioStreamWAV
	# and AudioStreamPlaybackWAV do not survive as ObjectDB leftovers.
	shutdown()

func shutdown() -> void:
	if not is_inside_tree() and _active_players.is_empty() and _streams.is_empty():
		return
	for player: AudioStreamPlayer2D in _active_players:
		if is_instance_valid(player):
			player.stop()
			player.stream = null
			if player.is_inside_tree():
				player.get_parent().remove_child(player)
			player.free()
	_active_players.clear()
	_streams.clear()
	SF_BANK.release_audio()
	var sfx_bus: int = AudioServer.get_bus_index(&"SFX")
	if sfx_bus >= 0:
		AudioServer.remove_bus(sfx_bus)

func play_event(kind: StringName, position: Vector2, pitch_scale: float = 1.0) -> void:
	if _headless_audio_disabled():
		return
	_prune_voices()
	if _active_players.size() >= MAX_VOICES:
		var oldest: AudioStreamPlayer2D = _active_players.pop_front()
		if is_instance_valid(oldest):
			oldest.queue_free()
	var classic_stream: AudioStream = SF_BANK.sound_for(kind)
	var stream: AudioStream = classic_stream if classic_stream != null else _stream_for(kind)
	var player := AudioStreamPlayer2D.new()
	player.stream = stream
	player.position = position
	player.bus = &"SFX"
	player.max_distance = 1800.0
	player.volume_db = -8.0 if String(kind).begins_with("shot") else -5.0
	player.pitch_scale = clampf(pitch_scale, 0.65, 1.45)
	add_child(player)
	_active_players.append(player)
	player.finished.connect(_on_player_finished.bind(player))
	player.play()

func generated_sample_bytes(kind: StringName) -> int:
	## Read-only diagnostic used by the focused presentation smoke.
	return _stream_for(kind).data.size()

func _on_player_finished(player: AudioStreamPlayer2D) -> void:
	_active_players.erase(player)
	if is_instance_valid(player):
		player.stop()
		player.stream = null
		player.queue_free()

func _prune_voices() -> void:
	for index: int in range(_active_players.size() - 1, -1, -1):
		if not is_instance_valid(_active_players[index]):
			_active_players.remove_at(index)

func _ensure_sfx_bus() -> void:
	var index: int = AudioServer.get_bus_index(&"SFX")
	if index >= 0:
		return
	AudioServer.add_bus()
	AudioServer.set_bus_name(AudioServer.get_bus_count() - 1, &"SFX")

func _headless_audio_disabled() -> bool:
	# Godot's Windows build can keep the "windows" DisplayServer name even
	# with --headless.  Check the actual command line as well so test workers
	# never create MP3 playback objects that outlive the process.
	if OS.has_feature("headless"):
		return true
	if DisplayServer.get_name().to_lower() == "headless":
		return true
	for argument: String in OS.get_cmdline_args():
		if argument == "--headless":
			return true
	return false

func _stream_for(kind: StringName) -> AudioStreamWAV:
	var cached: Variant = _streams.get(kind, null)
	if cached is AudioStreamWAV:
		return cached
	var created: AudioStreamWAV = _build_stream(kind)
	_streams[kind] = created
	return created

func _build_stream(kind: StringName) -> AudioStreamWAV:
	var label: String = String(kind)
	var duration: float = 0.10
	var base_frequency: float = 440.0
	var noise_amount: float = 0.0
	var harmonic_mix: float = 0.20
	var sweep: float = 0.0
	if label == "shot" or label == "shot_pistol":
		# A short dry crack plus a low body and mechanical tail reads as a
		# compact sidearm while staying self-authored and deterministic.
		duration = 0.155
		base_frequency = 118.0
		noise_amount = 0.80
		harmonic_mix = 0.46
		sweep = -0.34
	elif label == "shot_shotgun":
		duration = 0.145
		base_frequency = 105.0
		noise_amount = 0.78
		harmonic_mix = 0.52
		sweep = -0.20
	elif label == "shot_rocket_launcher":
		duration = 0.24
		base_frequency = 72.0
		noise_amount = 0.48
		harmonic_mix = 0.60
		sweep = -0.40
	elif label == "shot_grenade":
		duration = 0.12
		base_frequency = 125.0
		noise_amount = 0.42
		harmonic_mix = 0.45
	elif kind == &"explosion":
		duration = 0.34
		base_frequency = 86.0
		noise_amount = 0.78
		harmonic_mix = 0.48
		sweep = -0.45
	elif kind == &"hit" or label.begins_with("hit_"):
		duration = 0.11
		base_frequency = 130.0 if label in ["hit_punch", "hit_punch_combo", "hit_grab_punch"] else 180.0 if label in ["hit_kick", "hit_tackle", "hit_grab_throw"] else 240.0
		noise_amount = 0.26
		harmonic_mix = 0.35
		sweep = 0.20
	elif kind == &"prop_hit":
		duration = 0.10
		base_frequency = 190.0
		noise_amount = 0.32
		harmonic_mix = 0.30
	elif kind == &"prop_destroyed":
		duration = 0.22
		base_frequency = 120.0
		noise_amount = 0.60
		harmonic_mix = 0.42
	elif kind == &"pickup":
		duration = 0.20
		base_frequency = 620.0
		harmonic_mix = 0.58
		sweep = 0.65
	elif kind == &"disarm":
		duration = 0.16
		base_frequency = 470.0
		noise_amount = 0.12
		harmonic_mix = 0.70
		sweep = 0.45
	elif kind == &"tackle":
		duration = 0.16
		base_frequency = 92.0
		noise_amount = 0.42
		harmonic_mix = 0.48
		sweep = -0.18
	elif kind == &"airdrop":
		duration = 0.21
		base_frequency = 510.0
		harmonic_mix = 0.72
		sweep = -0.52
	elif kind == &"ignite" or kind == &"burn":
		duration = 0.14
		base_frequency = 175.0
		noise_amount = 0.34
	elif kind == &"extinguish":
		duration = 0.17
		base_frequency = 320.0
		noise_amount = 0.18
		sweep = -0.30
	var sample_count: int = maxi(1, int(duration * float(SAMPLE_RATE)))
	var data := PackedByteArray()
	data.resize(sample_count * 2)
	for index: int in range(sample_count):
		var time: float = float(index) / float(SAMPLE_RATE)
		var attack: float = minf(1.0, time * 150.0)
		var release: float = minf(1.0, (duration - time) * (20.0 if noise_amount > 0.45 else 26.0))
		var envelope: float = attack * release
		var ratio: float = time / maxf(0.001, duration)
		var frequency: float = maxf(24.0, base_frequency * (1.0 + sweep * ratio))
		var phase: float = TAU * frequency * time
		var sample: float = sin(phase) * 0.32
		sample += sin(phase * 2.01 + 0.25) * harmonic_mix * 0.30
		sample += sin(phase * 3.07 + 0.80) * harmonic_mix * 0.12
		if noise_amount > 0.0:
			var transient: float = noise_amount * _noise(index) * (1.0 - ratio * 0.72)
			sample += transient
		if label == "shot_pistol" or label == "shot":
			# Three short layers: muzzle crack, low pressure body, then the
			# slide/spring tail.  This is intentionally synthetic and original,
			# but follows the envelope of a compact real sidearm more closely.
			sample += _noise(index) * 0.66 * exp(-time * 300.0)
			sample += sin(TAU * 2800.0 * time) * 0.24 * exp(-time * 175.0)
			sample += sin(TAU * 330.0 * time) * 0.22 * exp(-time * 35.0)
			if time > 0.035:
				sample += sin(TAU * 760.0 * time) * 0.14 * exp(-(time - 0.035) * 58.0)
				sample += _noise(index + 17) * 0.10 * exp(-(time - 0.035) * 90.0)
		if kind == &"pickup" or kind == &"disarm" or kind == &"airdrop":
			sample += sin(TAU * (frequency * 1.5) * time) * 0.20 * clampf(time * 18.0, 0.0, 1.0)
		if kind == &"ignite" or kind == &"burn":
			sample += _noise(index) * 0.14
		var value: int = clampi(int(round(sample * envelope * 32767.0)), -32768, 32767)
		data[index * 2] = value & 0xff
		data[index * 2 + 1] = (value >> 8) & 0xff
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = SAMPLE_RATE
	stream.stereo = false
	stream.data = data
	return stream

func _noise(index: int) -> float:
	var value: float = sin(float(index) * 12.9898) * 43758.5453
	return value - floor(value) - 0.5

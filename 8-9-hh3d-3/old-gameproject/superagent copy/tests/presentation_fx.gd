extends SceneTree
## SA-10 presentation-only smoke: event consumption, deduplication and SFX synthesis.
## It never compares pixels and never treats presentation as gameplay parity.

const FX_SCRIPT = preload("res://game/presentation/arena_fx.gd")
const AUDIO_SCRIPT = preload("res://game/presentation/combat_audio.gd")

var _failures: int = 0
var _assertions: int = 0
var _sound_events: int = 0
var _camera_events: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var fx: Node = FX_SCRIPT.new()
	var audio: Node = AUDIO_SCRIPT.new()
	root.add_child(fx)
	root.add_child(audio)
	fx.connect("sound_requested", Callable(self, "_on_sound"))
	fx.connect("camera_impulse", Callable(self, "_on_camera_impulse"))
	var snapshot: Dictionary = {
		&"tick": 10,
		&"fighters": [
			{&"player": 1, &"x": 100.0, &"y": 740.0, &"health": 100},
			{&"player": 2, &"x": 300.0, &"y": 740.0, &"health": 100}
		],
		&"pickups": [{&"id": &"pistol", &"kind": &"pistol", &"x": 160.0, &"y": 740.0, &"active": true}],
		&"shot_events": [{&"attacker": 1, &"from": Vector2(100.0, 720.0), &"to": Vector2(300.0, 720.0), &"ttl": 5}],
		&"explosions": [],
		&"prop_events": [],
		&"fire_events": [],
		&"weapon_events": []
	}
	fx.call("consume_snapshot", snapshot)
	var effect_rows: Variant = fx.get("_effects")
	_expect(effect_rows is Array and Array(effect_rows).size() >= 2, "shot creates presentation effects")
	_expect(_sound_events == 1, "new shot requests one sound")
	var first_effect_count: int = Array(effect_rows).size() if effect_rows is Array else 0

	var same_event: Dictionary = snapshot.duplicate(true)
	same_event[&"tick"] = 11
	Dictionary(Array(same_event[&"shot_events"])[0])[&"ttl"] = 4
	fx.call("consume_snapshot", same_event)
	effect_rows = fx.get("_effects")
	_expect(Array(effect_rows).size() <= first_effect_count, "ttl decay does not duplicate the same event")
	_expect(_sound_events == 1, "ttl decay does not duplicate the same sound")

	var explosion: Dictionary = same_event.duplicate(true)
	explosion[&"tick"] = 12
	explosion[&"shot_events"] = []
	explosion[&"explosions"] = [{&"x": 240.0, &"y": 740.0, &"radius": 70.0, &"source": &"barrel", &"ttl": 8}]
	fx.call("consume_snapshot", explosion)
	_expect(_sound_events == 2, "new explosion requests one sound")
	_expect(_camera_events == 1, "explosion requests one bounded camera impulse")
	var stream: Variant = audio.call("_stream_for", &"explosion")
	_expect(stream is AudioStreamWAV, "procedural explosion stream is a WAV resource")
	var sample_bytes: int = int(audio.call("generated_sample_bytes", &"explosion"))
	_expect(sample_bytes > 0, "procedural stream contains PCM data")
	_expect(int(snapshot[&"tick"]) == 10, "presentation does not mutate gameplay snapshot")
	var prop_snapshot: Dictionary = explosion.duplicate(true)
	prop_snapshot[&"tick"] = 13
	prop_snapshot[&"explosions"] = []
	prop_snapshot[&"world"] = {&"props": [{&"id": &"crate", &"x": 420.0, &"y": 500.0}]}
	prop_snapshot[&"prop_events"] = [{&"prop_id": &"crate", &"kind": &"prop_hit", &"ttl": 12}]
	fx.call("consume_snapshot", prop_snapshot)
	var location: Vector2 = fx.call("_prop_position", prop_snapshot, &"crate")
	_expect(location == Vector2(420.0, 484.0), "world props resolve impact location instead of origin")
	var paused: Dictionary = prop_snapshot.duplicate(true)
	paused[&"phase"] = &"paused"
	fx.call("consume_snapshot", paused)
	var frozen_effects: String = str(fx.get("_effects"))
	fx.call("_process", 0.1)
	_expect(str(fx.get("_effects")) == frozen_effects, "same-tick pause freezes presentation effects")
	var restart: Dictionary = {&"tick": 0, &"phase": &"playing", &"fighters": [], &"pickups": []}
	fx.call("consume_snapshot", restart)
	_expect(Array(fx.get("_effects")).is_empty(), "new round clears previous effects")
	fx.queue_free()
	audio.queue_free()
	await process_frame
	if _failures == 0:
		print("SA-10 presentation FX PASS: %d assertions; event dedup and procedural SFX" % _assertions)
	else:
		printerr("SA-10 presentation FX FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)

func _on_sound(_kind: StringName, _position: Vector2, _pitch_scale: float) -> void:
	_sound_events += 1

func _on_camera_impulse(_strength: float) -> void:
	_camera_events += 1

func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

extends SceneTree
## Presentation-layer contracts, not gameplay. Same-state flag transitions
## exercise rig cache invalidation as well as palette and immutable sockets.
const Rig = preload("res://game/fighter/fighter_rig_view.gd")
const Painter = preload("res://game/fighter/chibi_brawler_rig_painter.gd")

class Actor:
	extends Node2D
	var awakening_timer: float = 0.0
	var is_summoned_clone: bool = false
	var _hit_flash_timer: float = 0.0
	var is_dead: bool = false
	var burned: bool = false
	var taking_cover: bool = false
	var kneeling: bool = false
	var grabbed_target: Node2D = null
	var air_velocity: Vector2 = Vector2.ZERO
	var on_ground: bool = true
	var burn_state: float = 0.0

var _checks: int = 0
var _failures: int = 0

func _initialize() -> void:
	call_deferred("_run")

func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R7 STYLE] " + label)

func _run() -> void:
	await process_frame
	var actor := Actor.new()
	root.add_child(actor)
	var rig: Node2D = Rig.new()
	actor.add_child(rig)
	rig.set_process(false)
	rig.set("chibi_brawler_enabled", true)
	for character: String in ["goku", "naruto"]:
		for state: String in ["AIM_PISTOL", "AIM_RIFLE"]:
			for facing: int in [-1, 1]:
				for pitch: float in [-45.0, 0.0, 45.0]:
					rig.call("apply_rig_state", character, state, 1, facing, pitch, 1, 100.0, 100.0, 0.0, false, false, 0.0, false, 3.0)
					var muzzle: Vector2 = rig.call("get_muzzle_global_pos")
					for awakened: bool in [false, true, false]:
						for clone: bool in [false, true, false]:
							for charred: bool in [false, true, false]:
								for flash: bool in [false, true, false]:
									actor.awakening_timer = 1.0 if awakened else 0.0
									actor.is_summoned_clone = clone
									actor._hit_flash_timer = 0.1 if flash else 0.0
									actor.is_dead = charred
									actor.burned = charred
									rig.call("apply_rig_state", character, state, 1, facing, pitch, 1, 100.0, 100.0, 0.0, false, false, 0.0, charred, 3.0)
									var weapon: Node2D = rig.get("chibi_weapon_view")
									var actual: Dictionary = weapon.get("_style")
									var expected: Dictionary = Painter.get_character_style(character, awakened)
									_check(weapon.visible and actual.get("character_id") == expected["character_id"], "awakened identity is fresh")
									_check(bool(actual.get("is_charred")) == charred and bool(actual.get("is_hit_flash")) == (flash and not charred), "effect flags invalidate same-state cache")
									for key: String in ["skin_lit", "sleeve", "glove", "hoodie_lit"]:
										_check(actual.get(key) == expected[key], "matching body/arm palette " + key)
										var rendered: Color = weapon.call("_color", key, Color.MAGENTA)
										_check(rendered.is_equal_approx(Painter._tint(expected[key], charred, flash, 1.0)), "matching tint " + key)
									_check(is_equal_approx(weapon.modulate.a, 0.85 if clone else 1.0), "single clone alpha matches body")
									_check(weapon.modulate.r == 1.0 and weapon.modulate.g == 1.0 and weapon.modulate.b == 1.0, "no double tint at node")
									_check(muzzle.distance_to(rig.call("get_muzzle_global_pos")) <= 0.0001, "palette changes preserve muzzle")
									var pose: Dictionary = rig.call("get_chibi_pose_snapshot")
									var pivot: Node2D = rig.get("aim_pivot")
									for side: String in ["front", "back"]:
										var key: String = "shoulder_origin" if side == "front" else "rear_shoulder_origin"
										var local: Vector2 = ((pose["shoulder_" + side] as Vector2) - pivot.position).rotated(-pivot.rotation)
										_check((actual[key] as Vector2).distance_to(local) <= 0.0001, "gun arm uses actual " + side + " shoulder")
	actor.free()
	await process_frame
	var audio: Node = root.get_node_or_null("AudioManager")
	if audio != null and audio.has_method("stop_all_and_drain"):
		_check(bool(await audio.call("stop_all_and_drain")), "audio drained")
	print("[CHIBI R7 STYLE] " + ("PASS" if _failures == 0 else "FAIL") + " checks=" + str(_checks) + " failures=" + str(_failures))
	quit(0 if _failures == 0 else 1)

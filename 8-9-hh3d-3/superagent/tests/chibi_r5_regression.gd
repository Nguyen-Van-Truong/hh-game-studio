extends SceneTree
## Chibi R5 diagnostic regression.
##
## This is deliberately a standalone SceneTree check.  It creates a generic
## Node2D harness rather than a FighterController, so a visual presentation
## change cannot accidentally acquire gameplay state or mutate a live match.
## The script is run by the parent verification flow; it does not launch Godot
## itself.

const RegistryScript: Script = preload("res://game/core/sf_data_registry.gd")
const FighterRigViewScript: Script = preload("res://game/fighter/fighter_rig_view.gd")
const ActionPoseScript: Script = preload("res://game/fighter/chibi_action_pose.gd")
const HudScript: Script = preload("res://game/ui/match_hud_controller.gd")

var _checks: int = 0
var _failures: int = 0
var _did_run: bool = false
var _reg: Node = null


func _process(_delta: float) -> bool:
	if _did_run:
		return true
	# Let autoloads finish _ready before loading the registry and creating the
	# standalone rigs.  No second worker/process is started by this script.
	_did_run = true
	_run()
	if _failures > 0:
		push_error("[CHIBI R5 REGRESSION] FAIL: " + str(_failures) + " of " + str(_checks) + " checks failed")
		quit(1)
	else:
		print("[CHIBI R5 REGRESSION] PASS: " + str(_checks) + " checks")
		quit(0)
	return true


func _run() -> void:
	_reg = _load_registry()
	_check(_reg != null, "SFDataRegistry is available")
	if _reg == null:
		return
	_run_weapon_arm_suite()
	_run_weapon_animation_suite()
	_run_action_pose_suite()
	_run_hud_geometry_suite()


func _load_registry() -> Node:
	var existing: Node = root.get_node_or_null("SFDataRegistry")
	if existing != null:
		if existing.has_method("ensure_loaded"):
			existing.call("ensure_loaded")
		return existing
	var created: Node = RegistryScript.new() as Node
	created.name = "ChibiR5Registry"
	root.add_child(created)
	if created.has_method("ensure_loaded"):
		created.call("ensure_loaded")
	return created


func _new_harness() -> Node2D:
	var harness := Node2D.new()
	harness.name = "ChibiR5GenericHarness"
	root.add_child(harness)
	return harness


func _new_rig(parent: Node, chibi_enabled: bool, label: String) -> Node:
	var rig: Node = FighterRigViewScript.new() as Node
	rig.name = label
	rig.set("registry_override", _reg)
	rig.set("chibi_brawler_enabled", chibi_enabled)
	parent.add_child(rig)
	return rig


func _state_weapon_frames(state_data: Dictionary) -> Array:
	var arm_value: Variant = state_data.get("weapon_arm", state_data.get("start_arm", {}))
	if typeof(arm_value) == TYPE_DICTIONARY:
		var arm: Dictionary = arm_value as Dictionary
		var arm_frames: Variant = arm.get("frames", [])
		if typeof(arm_frames) == TYPE_ARRAY and not (arm_frames as Array).is_empty():
			return arm_frames as Array
	var body_frames: Variant = state_data.get("frames", [])
	return body_frames as Array if typeof(body_frames) == TYPE_ARRAY else []


func _weapon_state_names() -> Array[String]:
	var out: Array[String] = []
	var states: Dictionary = _reg.call("get_states") as Dictionary
	for raw_name: Variant in states.keys():
		var state_name: String = str(raw_name).to_upper()
		if not (state_name.begins_with("AIM_") or state_name.begins_with("START_")):
			continue
		var data_value: Variant = states.get(raw_name)
		if typeof(data_value) != TYPE_DICTIONARY:
			continue
		var data: Dictionary = data_value as Dictionary
		# Only split states own a firearm/arm atlas.  Full-body AIM_FISTS and
		# melee aliases are presentation states and are covered by pose checks.
		if str(data.get("type", "")) not in ["split_rig_aim", "split_rig_start"]:
			continue
		if _state_weapon_frames(data).is_empty():
			continue
		out.append(state_name)
	out.sort()
	return out


func _run_weapon_arm_suite() -> void:
	var state_names: Array[String] = _weapon_state_names()
	_check(state_names.size() >= 10, "compiled split AIM/START state coverage (count=" + str(state_names.size()) + ")")
	if state_names.is_empty():
		return

	var harness: Node2D = _new_harness()
	var chibi_rig: Node = _new_rig(harness, true, "ChibiEnabledRig")
	var plain_rig: Node = _new_rig(harness, false, "ChibiDisabledRig")
	var pitches: Array[float] = [-90.0, -45.0, 0.0, 45.0, 90.0]
	var facings: Array[int] = [1, -1]

	for state_name: String in state_names:
		var state_data: Dictionary = _reg.call("get_state_data", state_name) as Dictionary
		var frames: Array = _state_weapon_frames(state_data)
		_check(not frames.is_empty(), state_name + " has weapon animation frames")
		for weapon_frame: int in range(1, frames.size() + 1):
			for face: int in facings:
				for pitch: float in pitches:
					var args: Array = [
						"johnny", state_name, 1, face, pitch, weapon_frame,
						100.0, 100.0, 0.0, false, false, 0.0, false, float(weapon_frame - 1)
					]
					chibi_rig.callv("apply_rig_state", args)
					plain_rig.callv("apply_rig_state", args)
					_check_weapon_frame(chibi_rig, state_name, weapon_frame, face, pitch)
					_check_socket_parity(chibi_rig, plain_rig, state_name, weapon_frame, face, pitch)

	chibi_rig.queue_free()
	plain_rig.queue_free()
	harness.queue_free()


func _check_weapon_frame(rig: Node, state_name: String, weapon_frame: int, face: int, pitch: float) -> void:
	var arm_sprite: Sprite2D = rig.get("weapon_arm_sprite") as Sprite2D
	_check(arm_sprite != null, state_name + " frame " + str(weapon_frame) + " exposes WeaponArmSprite")
	if arm_sprite == null:
		return
	var atlas: AtlasTexture = arm_sprite.texture as AtlasTexture
	var region_ok: bool = atlas != null and atlas.atlas != null and atlas.region.size.x > 0.0 and atlas.region.size.y > 0.0
	_check(region_ok, state_name + " frame " + str(weapon_frame) + " has a valid AtlasTexture rect")
	var presented: Node2D = rig.get("chibi_weapon_view") as Node2D
	if presented != null and presented.has_weapon(state_name):
		_check(presented.is_visible_in_tree() and presented.modulate.a > 0.0 and not arm_sprite.visible, state_name + " original gun-only art is the visible layer, old head/arm absent")
		var drawn_tip: Vector2 = presented.to_global(presented.get_visual_muzzle_local())
		_check(drawn_tip.distance_to(rig.call("get_muzzle_global_pos")) <= 0.001, state_name + " presented gun muzzle matches source socket")
		var contract: Dictionary = presented.get_draw_contract()
		var kind: String = str(contract.get("render_kind", ""))
		if kind == "procedural_melee":
			_check(state_name.ends_with("CHAINSAW") and str(contract.get("asset", "")) == "procedural://chibi_chainsaw", state_name + " dedicated chainsaw, not flamethrower alias")
		else:
			_check(presented.get("weapon_texture") != null, state_name + " original weapon/prop texture is present")
		var calculated_tip: Vector2 = (contract.get("top_left", Vector2.ZERO) as Vector2) + (contract.get("source_anchor", Vector2.ZERO) as Vector2) * float(contract.get("pixel_scale", 0.0))
		_check(presented.to_global(calculated_tip).distance_to(rig.call("get_muzzle_global_pos")) <= 0.001, state_name + " draw placement derives the aligned anchor")
	else:
		_check(arm_sprite.is_visible_in_tree(), state_name + " fallback arm is visible")
		_check(arm_sprite.self_modulate.a > 0.0, state_name + " fallback arm alpha is nonzero")
	var expected_scale: float = -1.0 if face < 0 else 1.0
	_check(is_equal_approx(float(rig.scale.x), expected_scale), state_name + " facing " + str(face) + " keeps rig facing")
	var direction: Vector2 = rig.call("get_aim_direction_vector")
	_check(is_finite(direction.x) and is_finite(direction.y), state_name + " pitch " + str(pitch) + " has finite aim direction")


func _check_socket_parity(chibi_rig: Node, plain_rig: Node, state_name: String, weapon_frame: int, face: int, pitch: float) -> void:
	var chibi_muzzle: Vector2 = chibi_rig.call("get_muzzle_global_pos")
	var plain_muzzle: Vector2 = plain_rig.call("get_muzzle_global_pos")
	var chibi_shell: Vector2 = chibi_rig.call("get_shell_global_pos")
	var plain_shell: Vector2 = plain_rig.call("get_shell_global_pos")
	var chibi_fire: Vector2 = chibi_rig.call("get_fire_global_pos")
	var plain_fire: Vector2 = plain_rig.call("get_fire_global_pos")
	var tag: String = state_name + " frame " + str(weapon_frame) + " face " + str(face) + " pitch " + str(pitch)
	_check(chibi_muzzle.distance_to(plain_muzzle) <= 0.001, tag + " preserves muzzle socket")
	_check(chibi_shell.distance_to(plain_shell) <= 0.001, tag + " preserves shell socket")
	_check(chibi_fire.distance_to(plain_fire) <= 0.001, tag + " preserves fire socket")


func _run_weapon_animation_suite() -> void:
	var harness: Node2D = _new_harness()
	var rig: Node = _new_rig(harness, true, "WeaponAnimationRig")
	for weapon: String in ["PISTOL", "RIFLE", "SHOTGUN"]:
		rig.call("apply_rig_state", "johnny", "AIM_" + weapon, 1, 1, 0.0, 1)
		var view: Node = rig.get("chibi_weapon_view")
		var idle: Dictionary = view.call("get_draw_contract") as Dictionary
		rig.call("apply_rig_state", "johnny", "AIM_" + weapon, 1, 1, 0.0, 2)
		var fired: Dictionary = view.call("get_draw_contract") as Dictionary
		_check((idle["draw_transform"] as Transform2D) != (fired["draw_transform"] as Transform2D), weapon + " firing frame changes visible recoil transform")
		_check((idle["grip_local"] as Vector2).distance_to(fired["grip_local"] as Vector2) > 0.01, weapon + " hand follows recoiling grip")
		_check((idle["visual_muzzle"] as Vector2).distance_to(fired["visual_muzzle"] as Vector2) <= 0.001, weapon + " recoil keeps barrel tip anchored")
		if weapon == "SHOTGUN":
			rig.call("apply_rig_state", "johnny", "AIM_" + weapon, 1, 1, 0.0, 3)
			var pumped: Dictionary = view.call("get_draw_contract") as Dictionary
			_check((idle["support_local"] as Vector2).distance_to(pumped["support_local"] as Vector2) > 1.0, "shotgun support wrist follows pump frame")
	harness.queue_free()


func _run_action_pose_suite() -> void:
	var registry_states: Dictionary = _reg.call("get_states") as Dictionary
	var registry_known: int = 0
	for raw_state: Variant in registry_states.keys():
		var registry_state: String = str(raw_state).to_upper()
		var registry_pose: Dictionary = ActionPoseScript.sample(registry_state, 1, 0.0, false, 0.0)
		var is_known: bool = bool(registry_pose.get("known_state", false))
		_check(is_known, "registry state " + registry_state + " has a known ChibiActionPose family")
		if is_known:
			registry_known += 1
	_check(registry_known == registry_states.size(), "all compiled registry states have known pose coverage")
	var ledge_pose: Dictionary = ActionPoseScript.sample("LEDGE_GRAB", 2, 0.0, false, 1.0)
	_check(bool(ledge_pose.get("known_state", false)) and str(ledge_pose.get("family", "")) == "ledge", "LEDGE_GRAB uses the authored ledge family")

	var dive_neutral: Dictionary = ActionPoseScript.sample("DIVE", 1, 0.0, false, 0.0, 0.0)
	var dive_rotated: Dictionary = ActionPoseScript.sample("DIVE", 1, 0.0, false, 0.0, 90.0)
	_check(absf(float(dive_neutral.get("body_rotation_deg", 999.0))) <= 0.001, "DIVE neutral body rotation stays zero")
	_check(absf(float(dive_rotated.get("body_rotation_deg", 0.0)) - 90.0) <= 0.001, "DIVE carries authored body rotation")
	_check(absf(float(dive_rotated.get("root_rotation_deg", 0.0)) - float(dive_neutral.get("root_rotation_deg", 0.0))) > 45.0, "DIVE presentation root rotates with gameplay rotation")
	_check((dive_rotated.get("root_origin", Vector2.ZERO) as Vector2).distance_to(dive_neutral.get("root_origin", Vector2.ZERO) as Vector2) > 0.1, "DIVE root origin rotates around the source body pivot")

	var hit_frames: Array[float] = [3.0, 3.5, 4.0]
	var punch_families: Array[String] = []
	var contact_signatures: Array[Vector2] = []
	for i: int in range(3):
		var state_name: String = "PUNCH_0" + str(i + 1)
		var hit: float = hit_frames[i]
		var windup: Dictionary = ActionPoseScript.sample(state_name, 1, 0.0, false, hit - 1.0)
		var contact: Dictionary = ActionPoseScript.sample(state_name, 1, 0.0, false, hit)
		var recovery: Dictionary = ActionPoseScript.sample(state_name, 1, 0.0, false, hit + 2.0)
		var family: String = str(contact.get("family", ""))
		punch_families.append(family)
		contact_signatures.append((contact.get("hand_front", Vector2.ZERO) as Vector2) + (contact.get("hand_back", Vector2.ZERO) as Vector2))
		_check(str(windup.get("phase", "")) == "windup" and not bool(windup.get("contact", false)), state_name + " has a windup phase")
		_check(str(contact.get("phase", "")) == "contact" and bool(contact.get("contact", false)), state_name + " contact phase is asserted")
		_check(absf(float(contact.get("source_frame", -1.0)) - hit) <= 0.001, state_name + " contact uses authored source frame " + str(hit))
		_check(str(recovery.get("phase", "")) == "recovery" and not bool(recovery.get("contact", false)), state_name + " has a recovery phase")
	_check(punch_families.size() == 3 and punch_families[0] != punch_families[1] and punch_families[1] != punch_families[2] and punch_families[0] != punch_families[2], "PUNCH_01/02/03 families are distinct")
	_check(contact_signatures[0].distance_to(contact_signatures[1]) > 0.25 and contact_signatures[1].distance_to(contact_signatures[2]) > 0.25, "PUNCH_01/02/03 contact hand coordinates are distinct")

	var category_states: Array[String] = ["CROUCH", "COVER", "ROLL", "KICK", "CLIMB"]
	var category_families: Dictionary = {}
	for state_name: String in category_states:
		var pose: Dictionary = ActionPoseScript.sample(state_name, 2, 0.0, false, 1.0)
		var family: String = str(pose.get("family", ""))
		category_families[state_name] = family
		_check(not family.is_empty() and family != "idle", state_name + " has an authored action family")
	_check(category_families.get("CROUCH", "") != category_families.get("ROLL", ""), "crouch and roll families are distinct")
	_check(category_families.get("COVER", "") != category_families.get("ROLL", ""), "cover and roll families are distinct")
	_check(category_families.get("KICK", "") != category_families.get("ROLL", ""), "kick and roll families are distinct")
	_check(category_families.get("CLIMB", "") != category_families.get("ROLL", ""), "climb and roll families are distinct")
	_check(category_families.get("KICK", "") != category_families.get("CLIMB", ""), "kick and climb families are distinct")
	for pitch: float in [-90.0, -45.0, 0.0, 45.0, 90.0]:
		for stance: String in ["", "COVER"]:
			var aim_pose: Dictionary = ActionPoseScript.sample("AIM_PISTOL", 1, pitch, false, 0.0, 0.0, stance)
			_check(str(aim_pose.get("family", "")) == "aim" and bool(aim_pose.get("split_arms", false)), "AIM_PISTOL pitch/stance coverage remains split-rig " + str(pitch) + "/" + stance)
			_check(is_finite(float(aim_pose.get("head_tilt_deg", NAN))) and is_finite((aim_pose.get("head", Vector2.ZERO) as Vector2).y), "AIM_PISTOL pitch/stance has finite head pose " + str(pitch) + "/" + stance)

	var nan_pose: Dictionary = ActionPoseScript.sample("PUNCH_01", 1, NAN, false, NAN)
	var inf_pose: Dictionary = ActionPoseScript.sample("PUNCH_02", 1, INF, false, INF)
	_check(is_finite(float(nan_pose.get("source_frame", NAN))) and is_finite(float(inf_pose.get("source_frame", NAN))), "NaN/Inf inputs resolve to finite source frames")
	_check(is_equal_approx(float(nan_pose.get("weapon_angle_deg", 0.0)), -60.0), "NaN aim falls back to neutral aim")
	var unknown_pose: Dictionary = ActionPoseScript.sample("NOT_A_RUNTIME_STATE", 0, 999.0, false, -INF)
	_check(str(unknown_pose.get("family", "")) == "safe_fallback" and not bool(unknown_pose.get("known_state", true)) and str(unknown_pose.get("fallback_reason", "")) == "unknown_state" and is_finite(float(unknown_pose.get("source_frame", NAN))), "unknown state and invalid source frame use explicit safe fallback metadata")


func _run_hud_geometry_suite() -> void:
	var hud: Node = HudScript.new()
	for vp: Vector2 in [Vector2(960.0, 540.0), Vector2(1280.0, 720.0)]:
		for count: int in [1, 2, 4, 8]:
			var cards: Array = hud.call("compute_adaptive_card_rects", vp, count, mini(count, 2)) as Array
			for index: int in range(cards.size()):
				var card: Rect2 = cards[index] as Rect2
				_check(Rect2(Vector2.ZERO, vp).encloses(card), "HUD card fits full viewport " + str(vp) + "/" + str(count))
				if index >= mini(count, 2):
					continue
				var layout: Dictionary = hud.call("get_local_card_layout", card) as Dictionary
				_check((layout["portrait"] as Rect2).size == Vector2(48.0, 48.0), "local portrait stays48px")
				var inventory: Array = layout["inventory_slots"] as Array
				var skills: Array = layout["skills"] as Array
				_check(inventory.size() == 4 and skills.size() == 4, "local inventory and skill rows retain four slots")
				for r: Rect2 in inventory:
					_check(card.encloses(r) and not r.intersects(layout["portrait"] as Rect2), "inventory avoids portrait and fits card")
				for r: Rect2 in skills:
					_check(card.encloses(r) and r.size.x >= 24.0 and r.size.y >= 24.0, "skill button remains24px and inside card")
					_check(not r.intersects(layout["resource"] as Rect2) and not r.intersects(layout["portrait"] as Rect2), "skill row avoids portrait/status")
				for key: String in ["name", "hp", "stamina", "resource"]:
					_check(card.encloses(layout[key] as Rect2), "local status field fits " + key)
	hud.free()


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R5 REGRESSION] FAIL: " + message)

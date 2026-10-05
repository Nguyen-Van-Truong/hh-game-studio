@tool
extends RefCounted
## Proposal-driven animation diagnostic. No public command or acceptance.

var _rows: Array[Dictionary] = []
var _failures: Array[String] = []


func run(root: Node, undo: EditorUndoRedoManager, history: UndoRedo, proposals: Array) -> Dictionary:
	_check("animation_proposal_count", proposals.size() == 2)
	var actor2d := Node2D.new()
	actor2d.name = "Actor2D"
	var actor3d := Node3D.new()
	actor3d.name = "Actor3D"
	var player := AnimationPlayer.new()
	player.name = "Player"
	var targets := {"actor2d": actor2d, "actor3d": actor3d}
	for node: Node in [actor2d, actor3d, player]:
		node.set_meta("hh_o2_temporary", true)
		root.add_child(node)
		node.owner = root
	player.root_node = player.get_path_to(root)
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var history_id := undo.get_object_history_id(root)
	undo.clear_history(history_id, false)
	for proposal: Dictionary in proposals:
		var animation_id := str(proposal.get("animation_id", ""))
		var prefix := "animation_" + animation_id
		var bound: bool = proposal.get("operation") == "scene.animation.create" \
			and proposal.get("runtime_authorized") == false and proposal.get("changes_applied") == false \
			and proposal.get("profile") == "hh-godot-animation-library-1" and proposal.get("authority") == 0 \
			and proposal.get("expected_generation") == 7 and proposal.get("target_stable_id") == "player" \
			and proposal.get("expected_revision") == "sha256:" + "1".repeat(64) \
			and proposal.get("project_revision") == "sha256:" + "2".repeat(64) \
			and proposal.get("animation_root_stable_id") == "root" \
			and animation_id in ["motion2d", "motion3d"]
		_check(prefix + "_binding", bound, {"command_id": proposal.get("command_id"),
			"request_digest": proposal.get("request_digest")})
		if not bound:
			continue
		var tracks: Array = proposal.get("tracks", [])
		var native_bound := tracks.size() == 3 and root.get_class() == "Node3D" and root.name == &"Fixture"
		for spec: Dictionary in tracks:
			var target: Node = targets.get(str(spec.get("node_stable_id", "")))
			native_bound = native_bound and target != null
			if target != null:
				native_bound = native_bound and target.get_class() == spec.get("node_type") \
					and str(root.get_path_to(target)) == spec.get("node_path") \
					and spec.get("property") in ["position", "rotation_degrees", "scale"]
		_check(prefix + "_native_binding", native_bound)
		if not native_bound:
			continue
		var animation := Animation.new()
		animation.length = float(proposal["length"])
		animation.loop_mode = Animation.LOOP_LINEAR if int(proposal["loop_mode"]) == 1 else Animation.LOOP_NONE
		for spec: Dictionary in tracks:
			var index := animation.add_track(Animation.TYPE_VALUE)
			animation.track_set_path(index, NodePath(str(spec["node_path"]) + ":" + str(spec["property"])))
			animation.track_set_interpolation_type(index, Animation.INTERPOLATION_LINEAR)
			for key: Array in spec["keys"]:
				animation.track_insert_key(index, float(key[0]), _native_value(key[1]))
		var library := AnimationLibrary.new()
		_check(prefix + "_resource_created", library.add_animation(StringName(animation_id), animation) == OK)
		_check(prefix + "_before", player.get_animation_library_list().is_empty())
		undo.create_action("O2 animation " + animation_id, UndoRedo.MERGE_DISABLE, player)
		undo.add_do_method(player, &"add_animation_library", &"", library)
		undo.add_undo_method(player, &"remove_animation_library", &"")
		undo.commit_action()
		_check(prefix + "_do_transition", history.has_undo())
		_resource_readback(prefix + "_do_readback", player, animation_id)
		_playback(prefix + "_playback", player, proposal, targets)
		_check(prefix + "_undo_transition", history.undo())
		_check(prefix + "_undo_readback", player.get_animation_library_list().is_empty() and not player.is_playing())
		_check(prefix + "_redo_transition", history.redo())
		_resource_readback(prefix + "_redo_readback", player, animation_id)
		_playback(prefix + "_redo_playback", player, proposal, targets)
		_check(prefix + "_cleanup_transition", history.undo())
		_check(prefix + "_cleanup_readback", player.get_animation_library_list().is_empty() and not player.is_playing())
		undo.clear_history(history_id, false)
	undo.clear_history(history_id, false)
	for node: Node in [player, actor3d, actor2d]:
		root.remove_child(node)
		node.free()
	return {"checks": _rows, "failures": _failures}


func _resource_readback(label: String, player: AnimationPlayer, animation_id: String) -> void:
	var animation: Animation = player.get_animation(StringName(animation_id))
	if animation == null:
		_check(label, false)
		return
	var tracks: Array[Dictionary] = []
	for index in animation.get_track_count():
		var keys: Array = []
		for key in animation.track_get_key_count(index):
			keys.append([animation.track_get_key_time(index, key), _json_value(animation.track_get_key_value(index, key))])
		tracks.append({"path": str(animation.track_get_path(index)), "type": animation.track_get_type(index),
			"interpolation": animation.track_get_interpolation_type(index), "keys": keys})
	_check(label, true, {"animation_id": animation_id, "length": animation.length,
		"loop_mode": animation.loop_mode, "tracks": tracks})


func _playback(label: String, player: AnimationPlayer, proposal: Dictionary, targets: Dictionary) -> void:
	# Reset to a deliberately unrelated pose so cached/pre-existing values cannot pass.
	for spec: Dictionary in proposal["tracks"]:
		var target: Node = targets[str(spec["node_stable_id"])]
		var sentinel: Variant = 17.0 if not spec["keys"][0][1] is Array else \
			(Vector2(17, 19) if str(spec["node_type"]) == "Node2D" else Vector3(17, 19, 23))
		target.set(str(spec["property"]), sentinel)
	player.play(StringName(str(proposal["animation_id"])))
	player.advance(0.0)
	var length_seconds := float(proposal["length"])
	var samples: Array[Dictionary] = [_sample(player, proposal, targets)]
	player.advance(length_seconds * 0.5)
	samples.append(_sample(player, proposal, targets))
	player.advance(length_seconds * (0.75 if int(proposal["loop_mode"]) == 1 else 0.5))
	samples.append(_sample(player, proposal, targets))
	player.stop()
	_check(label, samples.size() == 3 and not player.is_playing(),
		{"command_id": proposal["command_id"], "request_digest": proposal["request_digest"], "samples": samples})


func _sample(player: AnimationPlayer, proposal: Dictionary, targets: Dictionary) -> Dictionary:
	var values: Dictionary = {}
	for spec: Dictionary in proposal["tracks"]:
		var target: Node = targets[str(spec["node_stable_id"])]
		values[str(spec["node_stable_id"]) + ":" + str(spec["property"])] = _json_value(target.get(str(spec["property"])))
	return {"position_seconds": player.current_animation_position, "values": values}


func _native_value(value: Variant) -> Variant:
	if value is Array:
		return Vector2(float(value[0]), float(value[1])) if value.size() == 2 else \
			Vector3(float(value[0]), float(value[1]), float(value[2]))
	return float(value)


func _json_value(value: Variant) -> Variant:
	if value is Vector2:
		return [value.x, value.y]
	if value is Vector3:
		return [value.x, value.y, value.z]
	return value


func _check(label: String, passed: bool, details: Dictionary = {}) -> void:
	_rows.append({"label": label, "passed": passed, "details": details})
	if not passed:
		_failures.append(label)

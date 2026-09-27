@tool
extends RefCounted
## Disposable native interpreter diagnostic for validated declarative behavior.
## It never loads or executes caller GDScript and never emits a public ACK.

var _rows: Array[Dictionary] = []
var _failures: Array[String] = []


func run(root: Node, undo: EditorUndoRedoManager, history: UndoRedo, proposals: Array) -> Dictionary:
	_check("behavior_proposal_count", proposals.size() == 1)
	var actor := CharacterBody2D.new()
	actor.name = "BehaviorActor"
	actor.set_meta("hh_o2_temporary", true)
	root.add_child(actor)
	actor.owner = root
	var history_id := undo.get_object_history_id(root)
	undo.clear_history(history_id, false)
	for proposal: Dictionary in proposals:
		var bound: bool = proposal.get("operation") == "scene.behavior.create" \
			and proposal.get("profile") == "hh-godot-declarative-gameplay-1" \
			and proposal.get("authority") == 0 and proposal.get("runtime_authorized") == false \
			and proposal.get("changes_applied") == false and proposal.get("expected_generation") == 8 \
			and proposal.get("target_stable_id") == "actor" \
			and proposal.get("expected_revision") == "sha256:" + "1".repeat(64) \
			and proposal.get("project_revision") == "sha256:" + "2".repeat(64)
		_check("behavior_binding", bound, {"command_id": proposal.get("command_id"),
			"request_digest": proposal.get("request_digest")})
		var transitions: Array = proposal.get("transitions", [])
		var native_bound: bool = bound and proposal.get("states", []).size() == 3 and transitions.size() == 3
		for transition: Dictionary in transitions:
			native_bound = native_bound and transition.get("from_state", "") != "" \
				and transition.get("to_state", "") != "" and transition.get("effects", []) is Array
		_check("behavior_native_binding", native_bound)
		if not native_bound:
			continue
		var actions := ["move_right", "jump", "land"]
		var machine := {"state": str(proposal["initial_state"]), "signals": [], "animation": ""}
		_reset(actor, machine)
		var sequence: Array[Dictionary] = []
		for action: String in actions:
			_dispatch(actor, machine, proposal, action)
			sequence.append(_snapshot(actor, machine))
		var repeat_machine := {"state": str(proposal["initial_state"]), "signals": [], "animation": ""}
		_reset(actor, repeat_machine)
		var repeat_sequence: Array[Dictionary] = []
		for action: String in actions:
			_dispatch(actor, repeat_machine, proposal, action)
			repeat_sequence.append(_snapshot(actor, repeat_machine))
		_check("behavior_dispatch", sequence.size() == 3 and repeat_sequence.size() == 3,
			{"command_id": proposal["command_id"], "request_digest": proposal["request_digest"],
			"sequence": sequence})
		_check("behavior_deterministic", sequence == repeat_sequence,
			{"command_id": proposal["command_id"], "request_digest": proposal["request_digest"],
			"sequence": sequence, "repeat_sequence": repeat_sequence})
		_reset(actor, machine)
		var before := _snapshot(actor, machine)
		undo.create_action("O2 declarative behavior", UndoRedo.MERGE_DISABLE, actor)
		undo.add_do_method(self, &"_dispatch", actor, machine, proposal, "move_right")
		undo.add_undo_method(self, &"_restore", actor, machine, before)
		undo.commit_action()
		var after_do := _snapshot(actor, machine)
		_check("behavior_undo_transition", history.has_undo())
		_check("behavior_undo_readback", history.undo() and _snapshot(actor, machine) == before,
			{"before": before, "after_do": after_do, "after_undo": _snapshot(actor, machine)})
		var redo_ok := history.redo()
		_check("behavior_redo_transition", redo_ok)
		var after_redo := _snapshot(actor, machine)
		_check("behavior_redo_readback", after_redo == after_do,
			{"after_do": after_do, "after_redo": after_redo})
		_check("behavior_cleanup_readback", history.undo() and _snapshot(actor, machine) == before)
		undo.clear_history(history_id, false)
	if is_instance_valid(actor):
		root.remove_child(actor)
		actor.free()
	return {"checks": _rows, "failures": _failures}


func _dispatch(actor: CharacterBody2D, machine: Dictionary, proposal: Dictionary, action: String) -> void:
	var selected: Dictionary = {}
	for transition: Dictionary in proposal["transitions"]:
		if transition["from_state"] == machine["state"] and transition["action"] == action:
			selected = transition
			break
	if selected.is_empty():
		return
	machine["state"] = selected["to_state"]
	for effect: Dictionary in selected["effects"]:
		var params: Dictionary = effect["params"]
		match effect["kind"]:
			"move":
				actor.velocity.x = float(params["speed"])
				actor.position.x += float(params["speed"])
			"jump":
				actor.velocity.y = float(params["velocity_y"])
			"set_velocity":
				actor.velocity = Vector2(float(params["velocity_x"]), float(params["velocity_y"]))
			"face":
				actor.rotation_degrees = float(params["angle"])
			"emit_signal":
				(machine["signals"] as Array).append(str(params["signal"]))
			"play_animation":
				machine["animation"] = str(params["animation"])


func _restore(actor: CharacterBody2D, machine: Dictionary, snapshot: Dictionary) -> void:
	actor.position = Vector2(float(snapshot["position"][0]), float(snapshot["position"][1]))
	actor.velocity = Vector2(float(snapshot["velocity"][0]), float(snapshot["velocity"][1]))
	actor.rotation_degrees = float(snapshot["rotation_degrees"])
	machine["state"] = snapshot["state"]
	machine["signals"] = (snapshot["signals"] as Array).duplicate()
	machine["animation"] = snapshot["animation"]


func _reset(actor: CharacterBody2D, machine: Dictionary) -> void:
	_restore(actor, machine, {"state": "idle", "position": [0.0, 0.0], "velocity": [0.0, 0.0],
		"rotation_degrees": 0.0, "signals": [], "animation": ""})


func _snapshot(actor: CharacterBody2D, machine: Dictionary) -> Dictionary:
	return {"state": str(machine["state"]), "position": [actor.position.x, actor.position.y],
		"velocity": [actor.velocity.x, actor.velocity.y], "rotation_degrees": actor.rotation_degrees,
		"signals": (machine["signals"] as Array).duplicate(), "animation": str(machine["animation"])}


func _check(label: String, passed: bool, details: Dictionary = {}) -> void:
	_rows.append({"label": label, "passed": passed, "details": details})
	if not passed:
		_failures.append(label)

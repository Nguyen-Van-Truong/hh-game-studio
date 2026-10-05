@tool
extends RefCounted
## Private diagnostic consumer of host-validated candidate projections.
## No public dispatch, persistence, script execution, or acceptance authority.

var rows: Array[Dictionary] = []
var failures: Array[String] = []
var _actor: Button
var _target: Button


func run(root: Node, undo: EditorUndoRedoManager, history: UndoRedo, proposals: Array) -> Dictionary:
	_actor = Button.new()
	_target = Button.new()
	_actor.name = "EdgeActor"
	_target.name = "EdgeTarget"
	root.add_child(_actor)
	root.add_child(_target)
	_actor.owner = root
	_target.owner = root
	_check("edge_proposal_count", proposals.size() == 3)
	var names: Array[String] = []
	for proposal: Dictionary in proposals:
		var operation := str(proposal.get("operation", ""))
		var prefix := "edge_" + operation.replace(".", "_")
		var effect: Dictionary = proposal.get("after", {})
		_check(prefix + "_binding", proposal.get("profile") == "hh-godot-gameplay-edges-1"
			and proposal.get("runtime_authorized") == false and proposal.get("changes_applied") == false
			and proposal.get("native_verified") == false)
		if operation not in ["scene.signal.connect", "scene.group.assign", "input.action.define"]:
			_check(prefix + "_allowed", false)
			continue
		# This diagnostic binds only fixed fixture identities and a built-in method.
		# Production signal signature/owner authorization remains a separate gate.
		var supported := true
		if operation == "scene.signal.connect":
			supported = effect == {"source_id": "actor", "signal_name": "pressed", "target_id": "bot", "method": "hide"}
		elif operation == "scene.group.assign":
			supported = effect.get("node_id") == "actor" and effect.get("group_name") == "o2_probe_group"
		else:
			supported = effect.get("action_name") == "o2_probe_jump" and not InputMap.has_action("o2_probe_jump")
		_check(prefix + "_fixture_target", supported)
		if not supported:
			continue
		_check(prefix + "_before", not _present(operation, effect))
		undo.create_action("O2 edge " + operation, UndoRedo.MERGE_DISABLE, root)
		undo.add_do_method(self, &"_apply", operation, effect)
		undo.add_undo_method(self, &"_remove", operation, effect)
		undo.commit_action()
		_check(prefix + "_do_readback", _present(operation, effect))
		_check(prefix + "_effect", _effect_observed(operation, effect))
		_check(prefix + "_undo_transition", history.undo())
		_check(prefix + "_undo_readback", not _present(operation, effect))
		_check(prefix + "_redo_transition", history.redo())
		_check(prefix + "_redo_readback", _present(operation, effect))
		_check(prefix + "_redo_effect", _effect_observed(operation, effect))
		_check(prefix + "_cleanup_transition", history.undo())
		_check(prefix + "_cleanup_readback", not _present(operation, effect))
		names.append(str(proposal.get("request_digest", "")))
	# Drop methods referring to this helper before freeing its fixture nodes.
	undo.clear_history(undo.get_object_history_id(root), false)
	root.remove_child(_actor)
	root.remove_child(_target)
	_actor.free()
	_target.free()
	return {"checks": rows, "failures": failures, "request_digests": names}


func _apply(operation: String, effect: Dictionary) -> void:
	match operation:
		"scene.signal.connect":
			_actor.connect(&"pressed", Callable(_target, &"hide"), Object.CONNECT_PERSIST)
		"scene.group.assign":
			_actor.add_to_group(StringName(effect.group_name), true)
		"input.action.define":
			var event := InputEventKey.new()
			event.physical_keycode = int(effect.physical_key)
			InputMap.add_action(StringName(effect.action_name), float(effect.deadzone))
			InputMap.action_add_event(StringName(effect.action_name), event)


func _remove(operation: String, effect: Dictionary) -> void:
	match operation:
		"scene.signal.connect":
			_actor.disconnect(&"pressed", Callable(_target, &"hide"))
		"scene.group.assign":
			_actor.remove_from_group(StringName(effect.group_name))
		"input.action.define":
			InputMap.erase_action(StringName(effect.action_name))


func _present(operation: String, effect: Dictionary) -> bool:
	match operation:
		"scene.signal.connect":
			return _actor.is_connected(&"pressed", Callable(_target, &"hide"))
		"scene.group.assign":
			return _actor.is_in_group(StringName(effect.group_name))
		"input.action.define":
			if not InputMap.has_action(StringName(effect.action_name)):
				return false
			var events := InputMap.action_get_events(StringName(effect.action_name))
			return (events.size() == 1 and events[0] is InputEventKey
				and events[0].physical_keycode == int(effect.physical_key)
				and is_equal_approx(InputMap.action_get_deadzone(StringName(effect.action_name)), float(effect.deadzone)))
	return false


func _effect_observed(operation: String, effect: Dictionary) -> bool:
	match operation:
		"scene.signal.connect":
			_target.show()
			_actor.emit_signal(&"pressed")
			return not _target.visible
		"scene.group.assign":
			return _actor.get_tree().get_nodes_in_group(StringName(effect.group_name)).has(_actor)
		"input.action.define":
			var event := InputEventKey.new()
			event.physical_keycode = int(effect.physical_key)
			event.pressed = true
			return InputMap.event_is_action(event, StringName(effect.action_name), true)
	return false


func _check(label: String, passed: bool) -> void:
	rows.append({"label": label, "passed": passed})
	if not passed:
		failures.append(label)

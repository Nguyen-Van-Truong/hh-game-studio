class_name HHAgentIdentity
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")

## Composite node identity. Godot 4.7.1 does not expose unique_id to GDScript.
## Persistable meta is hh_agent_uid (underscore meta is not serialized).

var _seq: int = 0


func mint() -> String:
	_seq += 1
	return "hhuid_%d_%d" % [Time.get_ticks_usec(), _seq]


func read_uid(node: Node) -> String:
	if node == null:
		return ""
	if node.has_meta(HHAgentConstants.NODE_UID_META):
		return str(node.get_meta(HHAgentConstants.NODE_UID_META))
	if node.has_meta(HHAgentConstants.NODE_UID_META_HIDDEN):
		return str(node.get_meta(HHAgentConstants.NODE_UID_META_HIDDEN))
	return godot_unique_id(node)


func godot_unique_id(node: Node) -> String:
	if node == null:
		return ""
	for item_v: Variant in node.get_property_list():
		if not (item_v is Dictionary):
			continue
		var item: Dictionary = item_v
		var pname: String = str(item.get("name", ""))
		if pname == "unique_id" or pname == "scene_unique_id":
			return str(node.get(pname))
	return ""


func stamp(node: Node, uid: String) -> void:
	if node == null or uid.is_empty():
		return
	node.set_meta(HHAgentConstants.NODE_UID_META, uid)
	node.set_meta(HHAgentConstants.NODE_UID_META_HIDDEN, uid)


func remint_owned(node: Node, owner: Node) -> void:
	if node == null:
		return
	stamp(node, mint())
	var packed_root: bool = (
		owner != null
		and not node.scene_file_path.is_empty()
		and node.scene_file_path != owner.scene_file_path
	)
	var i: int = 0
	while i < node.get_child_count():
		var child: Node = node.get_child(i)
		if packed_root and is_packed_internal(child, owner):
			i += 1
			continue
		remint_owned(child, owner)
		i += 1


func tree_path(node: Node, root: Node) -> String:
	if node == null or root == null:
		return ""
	if node == root:
		return "."
	return str(root.get_path_to(node))


func owner_path(node: Node, root: Node) -> String:
	if node == null or root == null:
		return ""
	if node.owner == null:
		return ""
	return tree_path(node.owner, root)


func pick_owner(parent: Node, edited: Node) -> Node:
	if edited == null:
		return parent
	if parent == null or parent == edited:
		return edited
	var inst: Node = instance_root(parent, edited)
	if inst != null and inst != edited:
		return edited
	if parent.owner != null:
		return parent.owner
	return edited


func owner_after_reparent(node: Node, new_parent: Node, edited: Node) -> Node:
	if node == null:
		return pick_owner(new_parent, edited)
	var old_inst: Node = instance_root(node, edited)
	var new_inst: Node = instance_root(new_parent, edited)
	if old_inst != null and old_inst != node and old_inst == new_inst:
		if node.owner == edited:
			return edited
		return old_inst
	if new_inst != null and new_inst != edited:
		return edited
	return pick_owner(new_parent, edited)


func is_packed_internal(node: Node, edited: Node) -> bool:
	if node == null or node == edited:
		return false
	var inst: Node = instance_root(node, edited)
	if inst == null or inst == node:
		return false
	return node.owner == inst or node.owner == null


func instance_root(node: Node, edited: Node) -> Node:
	var cur: Node = node
	while cur != null and cur != edited:
		if not cur.scene_file_path.is_empty() and cur.scene_file_path != edited.scene_file_path:
			return cur
		cur = cur.get_parent()
	return null


func set_owned_tree(node: Node, owner: Node) -> void:
	if node == null or owner == null:
		return
	if node != owner:
		node.owner = owner
	var i: int = 0
	while i < node.get_child_count():
		var child: Node = node.get_child(i)
		if not child.scene_file_path.is_empty() and child.scene_file_path != owner.scene_file_path:
			child.owner = owner
		elif child.owner == null or child.owner == node or child.owner == owner:
			set_owned_tree(child, owner)
		i += 1


func supports_global_transform(node: Node) -> bool:
	return node is Node2D or node is Control or node is Node3D


func plan_collision_repairs(root: Node) -> Array:
	var seen: Dictionary = {}
	var repairs: Array = []
	_walk_collisions(root, root, seen, repairs)
	return repairs


func _walk_collisions(node: Node, edited: Node, seen: Dictionary, repairs: Array) -> void:
	if node == null:
		return
	var uid: String = read_uid(node)
	if not uid.is_empty():
		if seen.has(uid):
			repairs.append({"node": node, "old": uid, "new": mint()})
		else:
			seen[uid] = true
	var i: int = 0
	while i < node.get_child_count():
		_walk_collisions(node.get_child(i), edited, seen, repairs)
		i += 1

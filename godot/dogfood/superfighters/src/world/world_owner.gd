class_name WorldOwner
extends RefCounted

## Sole spawn/despawn writer for world props (VF4-WP1).
## Presentation cannot mutate. ledger:RL-WORLD-OWN (assumption).

const ROOT_NAME: String = "WorldProps"
const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")
const _Paths: GDScript = preload("res://src/world/world_paths.gd")
const _Body: GDScript = preload("res://src/world/prop_body.gd")
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")

var session: GameSession
var root: Node2D
var bodies: Array = []
var seq: int = 0
var last_errors: PackedStringArray = PackedStringArray()


func bind(p_session: GameSession) -> void:
	session = p_session


func attach(parent: Node2D) -> void:
	clear()
	if parent == null:
		return
	root = Node2D.new()
	root.name = ROOT_NAME
	parent.add_child(root)


func spawn_map(map_id: String) -> PackedStringArray:
	last_errors = PackedStringArray()
	var catalog_errs: PackedStringArray = _Catalog.validate()
	if not catalog_errs.is_empty():
		last_errors = catalog_errs
		return last_errors
	var rows: Array = _Catalog.placements_for(map_id)
	var i: int = 0
	while i < rows.size():
		var place: Dictionary = rows[i] as Dictionary
		_append(last_errors, _spawn_placement(place))
		i += 1
	return last_errors


func clear() -> void:
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		if body != null and is_instance_valid(body):
			body.queue_free()
		i += 1
	bodies.clear()
	seq = 0
	if root != null and is_instance_valid(root):
		root.queue_free()
	root = null


func count_valid() -> int:
	var n: int = 0
	var i: int = 0
	while i < bodies.size():
		var live: Node2D = bodies[i] as Node2D
		if live != null and is_instance_valid(live) and bool(live.get("alive")):
			n += 1
		i += 1
	return n


func instance_ids() -> PackedInt64Array:
	var out: PackedInt64Array = PackedInt64Array()
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		if body != null and is_instance_valid(body):
			out.append(body.get_instance_id())
		i += 1
	return out


func snapshot() -> Array:
	var rows: Array = []
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		if body != null and is_instance_valid(body) and body.has_method("snapshot_row"):
			rows.append(body.call("snapshot_row"))
		i += 1
	rows.sort_custom(_row_less)
	return rows


func stable_hash() -> String:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(SimSnapshot.canonical(snapshot()).to_utf8_buffer())
	return ctx.finish().hex_encode()


func try_mutate_from_view(view: Sprite2D, op: String, value: float = 0.0) -> PackedStringArray:
	if view == null:
		return PackedStringArray(["missing view"])
	var raw: Variant = null
	if op == "despawn" and view.has_method("request_despawn"):
		raw = view.call("request_despawn")
	elif op == "health" and view.has_method("request_set_health"):
		raw = view.call("request_set_health", value)
	elif op == "move" and view.has_method("request_move"):
		raw = view.call("request_move", Vector2(value, value))
	if raw is PackedStringArray:
		return raw as PackedStringArray
	return PackedStringArray(["presentation cannot mutate"])


func kinds_present() -> PackedStringArray:
	var seen: Dictionary = {}
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		if body != null and is_instance_valid(body):
			seen[str(body.get("kind"))] = true
		i += 1
	var keys: Array = seen.keys()
	keys.sort()
	var out: PackedStringArray = PackedStringArray()
	var k: int = 0
	while k < keys.size():
		out.append(str(keys[k]))
		k += 1
	return out


func _spawn_placement(place: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if root == null or not is_instance_valid(root):
		errors.append("world owner has no root")
		return errors
	var spec_id: String = str(place.get("spec", ""))
	var spec: Dictionary = _Catalog.spec(spec_id)
	if spec.is_empty():
		errors.append("unknown spec %s" % spec_id)
		return errors
	var vpath: String = str(_Spec.visual_path(spec))
	if not _Paths.visual_ok(vpath):
		errors.append("spawn rejected path %s" % _Paths.reject_reason(vpath))
		return errors
	seq += 1
	var body: Node2D = _Body.new() as Node2D
	root.add_child(body)
	var setup_v: Variant = body.call("setup", place, spec, seq, _Catalog.layers())
	if setup_v is PackedStringArray:
		_append(errors, setup_v as PackedStringArray)
	if not errors.is_empty():
		body.queue_free()
		return errors
	bodies.append(body)
	if session != null and session.ledger != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "prop_own", "prop_spawn", {
			"id": str(place.get("id", "")),
			"spec": spec_id,
			"kind": str(spec.get("kind", "")),
			"uid": seq,
			"x": SimConstants.quantize(body.global_position.x),
			"y": SimConstants.quantize(body.global_position.y),
		})
	return errors


static func _row_less(a: Variant, b: Variant) -> bool:
	var da: Dictionary = a as Dictionary
	var db: Dictionary = b as Dictionary
	var ax: int = int(da.get("x", 0))
	var bx: int = int(db.get("x", 0))
	if ax != bx:
		return ax < bx
	var ay: int = int(da.get("y", 0))
	var by: int = int(db.get("y", 0))
	if ay != by:
		return ay < by
	return str(da.get("id", "")) < str(db.get("id", ""))


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1

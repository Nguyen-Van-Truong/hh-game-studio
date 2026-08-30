class_name WorldOwner
extends RefCounted

## Sole spawn/despawn/break/throw writer for world props (VF4-WP2).
## Presentation cannot mutate. ledger:RL-WORLD-OWN (assumption).

const ROOT_NAME: String = "WorldProps"
const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")
const _Paths: GDScript = preload("res://src/world/world_paths.gd")
const _Body: GDScript = preload("res://src/world/prop_body.gd")
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")
const _Break: GDScript = preload("res://src/world/prop_break.gd")

var session: GameSession
var root: Node2D
var bodies: Array = []
var seq: int = 0
var last_errors: PackedStringArray = PackedStringArray()
var break_events: int = 0
var last_debris_count: int = 0
var last_break_id: String = ""


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
			if body.has_method("_clear_debris"):
				body.call("_clear_debris")
			body.queue_free()
		i += 1
	bodies.clear()
	seq = 0
	break_events = 0
	last_debris_count = 0
	last_break_id = ""
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


func body_from_node(node: Object) -> Node2D:
	var cur: Node = node as Node
	while cur != null:
		if cur.is_in_group(str(_Body.GROUP)):
			return cur as Node2D
		cur = cur.get_parent()
	return null


func find_by_id(placement_id: String) -> Node2D:
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		if body != null and is_instance_valid(body) and str(body.get("placement_id")) == placement_id:
			return body
		i += 1
	return null


func apply_damage(body: Node2D, raw: float, source: String, attacker: int = -1, seq: int = -1) -> bool:
	if body == null or not is_instance_valid(body):
		return false
	if not bool(body.get("alive")):
		return false
	if str(body.get("kind")) != "breakable":
		return false
	if seq >= 0 and bool(body.call("already_hit", attacker, seq)):
		return false
	if seq >= 0:
		body.call("mark_hit", attacker, seq)
	var spec: Dictionary = body.get("spec_cache") as Dictionary
	var scaled: float = float(_Break.scale_damage(raw, spec, source))
	var hp0: float = float(body.get("health"))
	body.set("health", hp0 - scaled)
	if session != null and session.ledger != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "prop_break", "prop_hit", {
			"id": str(body.get("placement_id")),
			"source": source,
			"attacker": attacker,
			"raw": SimConstants.quantize(raw),
			"scaled": SimConstants.quantize(scaled),
			"health": SimConstants.quantize(float(body.get("health"))),
		})
	if float(body.get("health")) > 0.0:
		return false
	_break_body(body, source)
	return true


func apply_melee(box: Rect2, raw: float, facing: float, attacker: int, seq: int) -> int:
	var hits: int = 0
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		i += 1
		if body == null or not is_instance_valid(body) or not bool(body.get("alive")):
			continue
		if int(body.get("carried_by")) >= 0:
			continue
		var rect: Rect2 = body.call("aabb") as Rect2
		if not box.intersects(rect, false):
			continue
		if str(body.get("kind")) == "breakable":
			if apply_damage(body, raw, "melee", attacker, seq):
				hits += 1
			else:
				hits += 1
		elif bool(body.get("movable")):
			if apply_shove(body, facing, attacker, seq):
				hits += 1
	return hits


func apply_shove(body: Node2D, facing: float, attacker: int, seq: int) -> bool:
	if body == null or not is_instance_valid(body):
		return false
	if not bool(body.get("alive")) or not bool(body.get("movable")):
		return false
	if int(body.get("carried_by")) >= 0:
		return false
	if seq >= 0 and bool(body.call("already_hit", attacker, seq)):
		return false
	if seq >= 0:
		body.call("mark_hit", attacker, seq)
	var side: float = 1.0 if facing >= 0.0 else -1.0
	body.set("velocity", Vector2(side * float(_Break.shove_speed()), 0.0))
	if session != null and session.ledger != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "prop_motion", "prop_shove", {
			"id": str(body.get("placement_id")),
			"attacker": attacker,
			"vx": SimConstants.quantize(float((body.get("velocity") as Vector2).x)),
		})
	return true


func try_carry(fighter: Fighter) -> bool:
	if fighter == null or fighter.dead:
		return false
	if carrier_of(fighter.slot) != null:
		return false
	var best: Node2D = null
	var best_d: float = float(_Break.carry_radius())
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		i += 1
		if body == null or not is_instance_valid(body) or not bool(body.get("alive")):
			continue
		if not bool(body.get("movable")):
			continue
		if int(body.get("carried_by")) >= 0:
			continue
		var d: float = body.global_position.distance_to(fighter.global_position)
		if d <= best_d:
			best_d = d
			best = body
	if best == null:
		return false
	best.set("carried_by", fighter.slot)
	best.set("velocity", Vector2.ZERO)
	best.call("set_solid_enabled", false)
	_follow_carrier(best, fighter)
	if session != null and session.ledger != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "prop_motion", "prop_carry", {
			"id": str(best.get("placement_id")),
			"carrier": fighter.slot,
		})
	return true


func try_throw(fighter: Fighter, dir: Vector2) -> bool:
	var body: Node2D = carrier_of(fighter.slot if fighter != null else -1)
	if body == null or fighter == null:
		return false
	var aim: Vector2 = dir
	if aim == Vector2.ZERO:
		aim = Vector2(fighter.facing, 0.0)
	aim = aim.normalized()
	var origin: Vector2 = fighter.global_position + Vector2(aim.x * 16.0, -6.0)
	body.global_position = origin
	body.set("carried_by", -1)
	body.set("velocity", Vector2(aim.x * float(_Break.throw_speed()), float(_Break.throw_lift())))
	body.call("set_solid_enabled", true)
	if session != null and session.ledger != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "prop_motion", "prop_throw", {
			"id": str(body.get("placement_id")),
			"carrier": fighter.slot,
			"vx": SimConstants.quantize(float((body.get("velocity") as Vector2).x)),
			"vy": SimConstants.quantize(float((body.get("velocity") as Vector2).y)),
		})
	return true


func carrier_of(slot: int) -> Node2D:
	if slot < 0:
		return null
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		if body != null and is_instance_valid(body) and int(body.get("carried_by")) == slot:
			return body
		i += 1
	return null


func step(dt: float) -> void:
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		i += 1
		if body == null or not is_instance_valid(body):
			continue
		body.call("tick_debris")
		var carrier: int = int(body.get("carried_by"))
		if carrier >= 0 and session != null:
			var f: Fighter = _fighter(carrier)
			if f != null and not f.dead:
				_follow_carrier(body, f)
				continue
			body.set("carried_by", -1)
			body.call("set_solid_enabled", true)
		if not bool(body.get("alive")):
			continue
		if not bool(body.get("movable")):
			continue
		_step_motion(body, dt)


func has_cover_at(at: Vector2) -> bool:
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		i += 1
		if body == null or not is_instance_valid(body) or not bool(body.get("alive")):
			continue
		if str(body.get("kind")) != "breakable" and str(body.get("kind")) != "static":
			continue
		if (body.call("aabb") as Rect2).has_point(at):
			return true
	return false


func _break_body(body: Node2D, source: String) -> void:
	if body == null or not is_instance_valid(body):
		return
	if not bool(body.get("alive")):
		return
	body.call("disable_cover")
	var debris_n: int = int(body.call("spawn_debris"))
	break_events += 1
	last_debris_count = debris_n
	last_break_id = str(body.get("placement_id"))
	if session != null and session.ledger != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "prop_break", "break", {
			"id": last_break_id,
			"spec": str(body.get("spec_id")),
			"material": str(body.get("mat_id")),
			"source": source,
			"debris": debris_n,
			"uid": int(body.get("uid")),
		})


func _follow_carrier(body: Node2D, fighter: Fighter) -> void:
	var side: float = 1.0 if fighter.facing >= 0.0 else -1.0
	body.global_position = fighter.global_position + Vector2(side * 12.0, -4.0)


func _step_motion(body: Node2D, dt: float) -> void:
	var vel: Vector2 = body.get("velocity") as Vector2
	if vel == Vector2.ZERO:
		return
	vel.y += float(_Break.gravity()) * dt
	var from: Vector2 = body.global_position
	var to: Vector2 = from + vel * dt
	var map_id: String = session.map_id if session != null else ""
	if Maps.solid_at(map_id, to + Vector2(0.0, 7.0)) and vel.y > 0.0:
		to.y = from.y
		vel.y = 0.0
		vel.x = move_toward(vel.x, 0.0, float(_Break.friction()) * dt)
	if Maps.solid_at(map_id, to + Vector2(signf(vel.x) * 8.0, 0.0)):
		to.x = from.x
		vel.x = 0.0
	body.global_position = to
	if absf(vel.x) < 4.0 and absf(vel.y) < 4.0:
		vel = Vector2.ZERO
	body.set("velocity", vel)


func _fighter(slot: int) -> Fighter:
	if session == null:
		return null
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and f.slot == slot:
			return f
		i += 1
	return null


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

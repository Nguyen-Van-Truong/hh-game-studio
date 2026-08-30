class_name WorldOwner
extends RefCounted

## Sole spawn/despawn/break/throw/explode writer for world props.
## Presentation cannot mutate. ledger:RL-WORLD-OWN (assumption).

const ROOT_NAME: String = "WorldProps"
const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")
const _Paths: GDScript = preload("res://src/world/world_paths.gd")
const _Body: GDScript = preload("res://src/world/prop_body.gd")
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")
const _Break: GDScript = preload("res://src/world/prop_break.gd")
const _Hazard: GDScript = preload("res://src/world/prop_hazard.gd")
const _View: GDScript = preload("res://src/world/prop_view.gd")
const _Moving: GDScript = preload("res://src/world/moving_spec.gd")
const _Mover: GDScript = preload("res://src/world/moving_body.gd")

var session: GameSession
var root: Node2D
var bodies: Array = []
var movers: Array = []
var seq: int = 0
var mover_seq: int = 0
var door_open_events: int = 0
var board_events: int = 0
var unboard_events: int = 0
var trigger_events: int = 0
var call_events: int = 0
var tunnel_events: int = 0
var max_board_dy: float = 0.0
var _unboard_tick: Dictionary = {}
var _unboard_y: Dictionary = {}
var last_errors: PackedStringArray = PackedStringArray()
var break_events: int = 0
var last_debris_count: int = 0
var last_break_id: String = ""
var explode_events: int = 0
var last_explode_id: String = ""
var max_chain_seen: int = 0
var vfx_spawned: int = 0
var vfx_rejected: int = 0
var drop_events: int = 0
var _vfx: Array = []
var _vfx_life: Array = []
var _fire_views: Dictionary = {}


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
	_append(last_errors, _Moving.validate())
	var movers_rows: Array = _Moving.placements_for(map_id)
	i = 0
	while i < movers_rows.size():
		var mplace: Dictionary = movers_rows[i] as Dictionary
		_append(last_errors, _spawn_mover(mplace))
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
	_clear_movers()
	seq = 0
	mover_seq = 0
	door_open_events = 0
	board_events = 0
	unboard_events = 0
	trigger_events = 0
	call_events = 0
	tunnel_events = 0
	max_board_dy = 0.0
	_unboard_tick.clear()
	_unboard_y.clear()
	break_events = 0
	last_debris_count = 0
	last_break_id = ""
	explode_events = 0
	last_explode_id = ""
	max_chain_seen = 0
	vfx_spawned = 0
	vfx_rejected = 0
	drop_events = 0
	_clear_vfx()
	_fire_views.clear()
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
	i = 0
	while i < movers.size():
		var mover: Node2D = movers[i] as Node2D
		if mover != null and is_instance_valid(mover) and mover.has_method("snapshot_row"):
			rows.append(mover.call("snapshot_row"))
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
	i = 0
	while i < movers.size():
		var mover: Node2D = movers[i] as Node2D
		if mover != null and is_instance_valid(mover) and str(mover.get("placement_id")) == placement_id:
			return mover
		i += 1
	return null


func apply_damage(body: Node2D, raw: float, source: String, attacker: int = -1, seq: int = -1, depth: int = 0) -> bool:
	if body == null or not is_instance_valid(body):
		return false
	if not bool(body.get("alive")):
		return false
	if bool(body.get("hanging")):
		return release_hang(body, source)
	var kind: String = str(body.get("kind"))
	if kind != "breakable" and kind != "explosive":
		return false
	if kind == "explosive" and bool(body.get("exploded")):
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
	if kind == "explosive":
		_explode_body(body, source, depth)
		return true
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
		if bool(body.get("hanging")):
			if apply_damage(body, raw, "melee", attacker, seq):
				hits += 1
		elif str(body.get("kind")) == "explosive":
			if apply_damage(body, raw, "melee", attacker, seq):
				hits += 1
			else:
				hits += 1
		elif str(body.get("kind")) == "breakable":
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


func apply_blast(origin: Vector2, radius: float, raw: float, source: String, depth: int = 0) -> int:
	var hits: int = 0
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		i += 1
		if body == null or not is_instance_valid(body) or not bool(body.get("alive")):
			continue
		var d: float = body.global_position.distance_to(origin)
		if d > radius:
			continue
		if bool(body.get("hanging")):
			if release_hang(body, source):
				hits += 1
			continue
		var kind: String = str(body.get("kind"))
		if kind == "explosive":
			if depth + 1 > int(_Hazard.chain_max_depth()):
				continue
			if apply_damage(body, raw, source, -1, -1, depth + 1):
				hits += 1
		elif bool(body.get("flammable")) and kind == "breakable":
			body.set("burning", true)
			body.set("burn_left", int(_Hazard.burn_ticks()))
	return hits


func release_hang(body: Node2D, source: String) -> bool:
	if body == null or not is_instance_valid(body):
		return false
	if not bool(body.get("hanging")):
		return false
	body.set("hanging", false)
	body.set("movable", true)
	body.set("velocity", Vector2(0.0, float(_Hazard.drop_impulse())))
	drop_events += 1
	if session != null and session.ledger != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "prop_motion", "prop_drop", {
			"id": str(body.get("placement_id")),
			"source": source,
			"vy": SimConstants.quantize(float(_Hazard.drop_impulse())),
		})
	return true


func has_fire_view(slot: int) -> bool:
	if not _fire_views.has(slot):
		return false
	var view: Node = _fire_views[slot] as Node
	return view != null and is_instance_valid(view)


func vfx_live_count() -> int:
	var n: int = 0
	var i: int = 0
	while i < _vfx.size():
		var spr: Node = _vfx[i] as Node
		if spr != null and is_instance_valid(spr):
			n += 1
		i += 1
	var keys: Array = _fire_views.keys()
	var k: int = 0
	while k < keys.size():
		var view: Node = _fire_views[keys[k]] as Node
		if view != null and is_instance_valid(view):
			n += 1
		k += 1
	return n


func step(dt: float) -> void:
	_tick_vfx()
	_sync_fighter_fire()
	_step_movers()
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
		if bool(body.get("hanging")):
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


func _explode_body(body: Node2D, source: String, depth: int) -> void:
	if body == null or not is_instance_valid(body):
		return
	if not bool(body.get("alive")) or bool(body.get("exploded")):
		return
	if depth > int(_Hazard.chain_max_depth()):
		return
	body.set("exploded", true)
	body.call("disable_cover")
	explode_events += 1
	last_explode_id = str(body.get("placement_id"))
	if depth > max_chain_seen:
		max_chain_seen = depth
	var sparks: int = _spawn_explode_vfx(body.global_position)
	if session != null and session.ledger != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "prop_expl", "prop_explode", {
			"id": last_explode_id,
			"spec": str(body.get("spec_id")),
			"source": source,
			"depth": depth,
			"vfx": sparks,
			"uid": int(body.get("uid")),
		})
	if session != null and session.sfx != null:
		session.sfx.play("explode")
	var origin: Vector2 = body.global_position
	_ignite_fighters(origin)
	apply_blast(origin, float(_Hazard.chain_radius()), float(_Hazard.explode_damage()), "explosion", depth)


func _ignite_fighters(origin: Vector2) -> void:
	if session == null:
		return
	var rad: float = float(_Hazard.fire_radius())
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or f.dead:
			continue
		if f.global_position.distance_to(origin) > rad:
			continue
		f.ignite_fire(int(_Hazard.burn_ticks()))


func _spawn_explode_vfx(at: Vector2) -> int:
	var spawned: int = 0
	var want: int = int(_Hazard.vfx_per_explode())
	var i: int = 0
	while i < want:
		if _try_spawn_vfx(str(_Hazard.explode_visual()), at + Vector2(float((i * 5) % 7) - 3.0, float((i * 3) % 5) - 2.0)):
			spawned += 1
		i += 1
	return spawned


func _try_spawn_vfx(tex_path: String, at: Vector2) -> bool:
	if vfx_live_count() >= int(_Hazard.vfx_cap()):
		vfx_rejected += 1
		return false
	if root == null or not is_instance_valid(root):
		vfx_rejected += 1
		return false
	var tex: Texture2D = _View.load_texture(tex_path)
	if tex == null:
		vfx_rejected += 1
		return false
	var spr: Sprite2D = Sprite2D.new()
	spr.name = "HazardVfx_%d" % vfx_spawned
	spr.centered = true
	spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	spr.texture = tex
	spr.global_position = at
	root.add_child(spr)
	_vfx.append(spr)
	_vfx_life.append(int(_Hazard.vfx_life()))
	vfx_spawned += 1
	return true


func _tick_vfx() -> void:
	var i: int = 0
	while i < _vfx.size():
		_vfx_life[i] = int(_vfx_life[i]) - 1
		if int(_vfx_life[i]) > 0:
			i += 1
			continue
		var spr: Node = _vfx[i] as Node
		if spr != null and is_instance_valid(spr):
			spr.queue_free()
		_vfx.remove_at(i)
		_vfx_life.remove_at(i)


func _clear_vfx() -> void:
	var i: int = 0
	while i < _vfx.size():
		var spr: Node = _vfx[i] as Node
		if spr != null and is_instance_valid(spr):
			spr.queue_free()
		i += 1
	_vfx.clear()
	_vfx_life.clear()
	var keys: Array = _fire_views.keys()
	var k: int = 0
	while k < keys.size():
		var view: Node = _fire_views[keys[k]] as Node
		if view != null and is_instance_valid(view):
			view.queue_free()
		k += 1
	_fire_views.clear()


func _sync_fighter_fire() -> void:
	if session == null:
		return
	var seen: Dictionary = {}
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or f.dead or not f.burning:
			continue
		seen[f.slot] = true
		if _fire_views.has(f.slot):
			var live: Node2D = _fire_views[f.slot] as Node2D
			if live != null and is_instance_valid(live):
				live.global_position = f.global_position + Vector2(0.0, -10.0)
				continue
		if vfx_live_count() >= int(_Hazard.vfx_cap()):
			vfx_rejected += 1
			continue
		if root == null or not is_instance_valid(root):
			continue
		var tex: Texture2D = _View.load_texture(str(_Hazard.fire_visual()))
		if tex == null:
			continue
		var spr: Sprite2D = Sprite2D.new()
		spr.name = "FireView_%d" % f.slot
		spr.centered = true
		spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		spr.texture = tex
		spr.global_position = f.global_position + Vector2(0.0, -10.0)
		root.add_child(spr)
		_fire_views[f.slot] = spr
		vfx_spawned += 1
	var keys: Array = _fire_views.keys()
	var k: int = 0
	while k < keys.size():
		var slot: int = int(keys[k])
		if seen.has(slot):
			k += 1
			continue
		var view: Node = _fire_views[slot] as Node
		if view != null and is_instance_valid(view):
			view.queue_free()
		_fire_views.erase(slot)
		k += 1


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


func _spawn_mover(place: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if root == null or not is_instance_valid(root):
		errors.append("world owner has no root")
		return errors
	var spec_id: String = str(place.get("spec", ""))
	var spec: Dictionary = _Moving.spec(spec_id)
	if spec.is_empty():
		errors.append("unknown mover spec %s" % spec_id)
		return errors
	var vpath: String = str(_Spec.visual_path(spec))
	if not _Paths.visual_ok(vpath):
		errors.append("mover rejected path %s" % _Paths.reject_reason(vpath))
		return errors
	mover_seq += 1
	var body: Node2D = _Mover.new() as Node2D
	root.add_child(body)
	var setup_v: Variant = body.call("setup", place, spec, mover_seq, _Catalog.layers())
	if setup_v is PackedStringArray:
		_append(errors, setup_v as PackedStringArray)
	if not errors.is_empty():
		body.queue_free()
		return errors
	movers.append(body)
	if session != null and session.ledger != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "world_move", "mover_spawn", {
			"id": str(place.get("id", "")),
			"spec": spec_id,
			"kind": str(spec.get("kind", "")),
			"uid": mover_seq,
			"x": SimConstants.quantize(body.global_position.x),
			"y": SimConstants.quantize(body.global_position.y),
		})
	return errors


func _clear_movers() -> void:
	var i: int = 0
	while i < movers.size():
		var mover: Node2D = movers[i] as Node2D
		if mover != null and is_instance_valid(mover):
			mover.queue_free()
		i += 1
	movers.clear()


func _step_movers() -> void:
	_tick_triggers()
	_clear_riding()
	var i: int = 0
	while i < movers.size():
		var mover: Node2D = movers[i] as Node2D
		i += 1
		if mover == null or not is_instance_valid(mover):
			continue
		if str(mover.get("kind")) != "platform":
			continue
		_maybe_auto_call(mover)
		var old_aabb: Rect2 = mover.call("aabb") as Rect2
		var delta: Vector2 = mover.call("advance_path") as Vector2
		_carry_riders(mover, old_aabb, delta)


func _tick_triggers() -> void:
	var i: int = 0
	while i < movers.size():
		var mover: Node2D = movers[i] as Node2D
		i += 1
		if mover == null or not is_instance_valid(mover):
			continue
		if str(mover.get("kind")) != "trigger":
			continue
		var held: bool = _any_fighter_overlaps(mover)
		if held:
			mover.set("hold_ticks", int(mover.get("hold_ticks")) + 1)
		else:
			mover.set("hold_ticks", 0)
		if held and int(mover.get("hold_ticks")) == int(_Moving.arm_ticks()):
			var tid: String = str(mover.get("target_id"))
			if _call_id(tid):
				trigger_events += 1
				if session != null and session.ledger != null:
					session.ledger.push(session.clock.tick if session.clock != null else 0, "world_move", "trigger_fire", {
						"id": str(mover.get("placement_id")),
						"target": tid,
					})


func _maybe_auto_call(mover: Node2D) -> void:
	if not bool(mover.call("auto_call_on_board")):
		return
	if str(mover.get("phase")) != "idle":
		return
	if not _any_standing_rider(mover, mover.call("aabb") as Rect2):
		return
	mover.set("hold_ticks", int(mover.get("hold_ticks")) + 1)
	if int(mover.get("hold_ticks")) < int(_Moving.arm_ticks()):
		return
	if bool(mover.call("call_now")):
		call_events += 1
		_log_call(mover)


func _call_id(placement_id: String) -> bool:
	if placement_id == "":
		return false
	var mover: Node2D = find_by_id(placement_id)
	if mover == null or not mover.has_method("call_now"):
		return false
	if not bool(mover.call("call_now")):
		return false
	if str(mover.get("kind")) == "door":
		door_open_events += 1
		if session != null and session.ledger != null:
			session.ledger.push(session.clock.tick if session.clock != null else 0, "world_move", "door_open", {
				"id": placement_id,
			})
	else:
		call_events += 1
		_log_call(mover)
	return true


func _log_call(mover: Node2D) -> void:
	if session == null or session.ledger == null or mover == null:
		return
	session.ledger.push(session.clock.tick if session.clock != null else 0, "world_move", "platform_call", {
		"id": str(mover.get("placement_id")),
		"phase": str(mover.get("phase")),
	})


func _carry_riders(mover: Node2D, old_aabb: Rect2, delta: Vector2) -> void:
	if session == null:
		return
	var next_boarded: PackedInt32Array = PackedInt32Array()
	var prev: PackedInt32Array = mover.get("boarded") as PackedInt32Array
	var now_box: Rect2 = mover.call("aabb") as Rect2
	var tick: int = session.clock.tick if session.clock != null else 0
	var warp: float = float(_Moving.warp_px())
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or f.dead:
			continue
		var was: bool = _slot_in(prev, f.slot)
		var now: bool = _can_ride(f, mover, old_aabb, was) or (was and _can_ride(f, mover, now_box, true))
		if now and f.velocity.y < -40.0:
			now = false
		if now:
			var y0: float = f.global_position.y
			if delta != Vector2.ZERO:
				f.global_position += delta
			var would: float = _snap_would_dy(f, mover)
			if absf(would) > max_board_dy:
				max_board_dy = absf(would)
			if absf(would) + 0.0001 >= warp:
				tunnel_events += 1
				if session.ledger != null:
					session.ledger.push(tick, "world_move", "ride_warp", {
						"id": str(mover.get("placement_id")),
						"slot": f.slot,
						"dy": would,
					})
			else:
				_snap_rider(f, mover)
			if f.velocity.y > 0.0:
				f.velocity.y = 0.0
			var extra: float = absf((f.global_position.y - y0) - delta.y)
			if extra > max_board_dy:
				max_board_dy = extra
			if extra + 0.0001 >= warp:
				tunnel_events += 1
				if session.ledger != null:
					session.ledger.push(tick, "world_move", "ride_warp", {
						"id": str(mover.get("placement_id")),
						"slot": f.slot,
						"dy": extra,
					})
			if _fighter_tunneled(f):
				tunnel_events += 1
				f.global_position -= delta
				if session.ledger != null:
					session.ledger.push(tick, "world_move", "ride_tunnel", {
						"id": str(mover.get("placement_id")),
						"slot": f.slot,
					})
			if not was:
				_note_reboard_warp(f, tick)
				board_events += 1
				if session.ledger != null:
					session.ledger.push(tick, "world_move", "board", {
						"id": str(mover.get("placement_id")),
						"slot": f.slot,
					})
			f.platform_riding = true
			next_boarded.append(f.slot)
		elif was:
			unboard_events += 1
			_unboard_tick[f.slot] = tick
			_unboard_y[f.slot] = f.global_position.y
			f.ledge_lock_left = maxf(f.ledge_lock_left, 0.12)
			if session.ledger != null:
				session.ledger.push(tick, "world_move", "unboard", {
					"id": str(mover.get("placement_id")),
					"slot": f.slot,
				})
	mover.set("boarded", next_boarded)


func _any_rider(mover: Node2D, box: Rect2) -> bool:
	if session == null:
		return false
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if _is_rider(f, mover, box):
			return true
	return false


func _any_standing_rider(mover: Node2D, box: Rect2) -> bool:
	if session == null:
		return false
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or f.dead:
			continue
		if absf(f.velocity.x) > 48.0:
			continue
		if _is_rider(f, mover, box):
			return true
	return false


func _snap_rider(fighter: Fighter, mover: Node2D) -> void:
	if fighter == null or mover == null:
		return
	var would: float = _snap_would_dy(fighter, mover)
	if absf(would) <= float(_Moving.snap_eps()):
		fighter.global_position.y += would


func _snap_would_dy(fighter: Fighter, mover: Node2D) -> float:
	if fighter == null or mover == null:
		return 0.0
	var box: Rect2 = mover.call("aabb") as Rect2
	return box.position.y - _feet_half(fighter) - fighter.global_position.y


func _feet_half(fighter: Fighter) -> float:
	var feet: float = 12.0
	if fighter != null and fighter.stand_shape != null:
		feet = fighter.stand_shape.size.y * 0.5 + fighter.stand_offset.y
	return feet


func _clear_riding() -> void:
	if session == null:
		return
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f != null:
			f.platform_riding = false


func _note_reboard_warp(fighter: Fighter, tick: int) -> void:
	if fighter == null:
		return
	if not _unboard_tick.has(fighter.slot):
		return
	var prev_tick: int = int(_unboard_tick[fighter.slot])
	if tick - prev_tick > 8:
		return
	var prev_y: float = float(_unboard_y.get(fighter.slot, fighter.global_position.y))
	var dy: float = absf(fighter.global_position.y - prev_y)
	if dy > max_board_dy:
		max_board_dy = dy
	if dy + 0.0001 < float(_Moving.warp_px()):
		return
	tunnel_events += 1
	if session != null and session.ledger != null:
		session.ledger.push(tick, "world_move", "ride_warp", {
			"slot": fighter.slot,
			"dy": dy,
			"reboard": 1,
		})


func _any_fighter_overlaps(mover: Node2D) -> bool:
	if session == null or mover == null:
		return false
	var box: Rect2 = mover.call("aabb") as Rect2
	box = box.grow(2.0)
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or f.dead:
			continue
		# Walk-across must not arm: stand on the plate (low vx) for arm_ticks.
		if absf(f.velocity.x) > 48.0:
			continue
		if box.intersects(_Moving.fighter_aabb(f), false):
			return true
	return false


func _is_rider(fighter: Fighter, mover: Node2D, box: Rect2) -> bool:
	return _can_ride(fighter, mover, box, true)


func _can_ride(fighter: Fighter, mover: Node2D, box: Rect2, was: bool) -> bool:
	if fighter == null or fighter.dead or mover == null:
		return false
	if fighter.hanging or fighter.recover_left > 0.0:
		return false
	var fa: Rect2 = _Moving.fighter_aabb(fighter)
	var pad: Rect2 = Rect2(
		box.position + Vector2(-3.0, -float(_Moving.board_eps())),
		box.size + Vector2(6.0, float(_Moving.board_eps()))
	)
	if not fa.intersects(pad, false):
		return false
	var feet_y: float = fighter.global_position.y + _feet_half(fighter)
	if absf(feet_y - box.position.y) > float(_Moving.board_eps()):
		return false
	if was:
		return true
	return fighter.is_on_floor() or fighter.platform_riding


func _fighter_tunneled(fighter: Fighter) -> bool:
	if fighter == null or session == null:
		return false
	var map_id: String = session.map_id
	if Maps.solid_at(map_id, fighter.global_position):
		return true
	return Maps.solid_at(map_id, fighter.global_position + Vector2(0.0, 10.0))


func _slot_in(slots: PackedInt32Array, slot: int) -> bool:
	var i: int = 0
	while i < slots.size():
		if int(slots[i]) == slot:
			return true
		i += 1
	return false


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

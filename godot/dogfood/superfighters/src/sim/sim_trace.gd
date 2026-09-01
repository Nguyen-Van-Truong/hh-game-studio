class_name SimTrace
extends RefCounted

## Golden InputFrame traces. Official traces are typed frames only.
## Fixture traces may teleport / force_kill. 60 Hz is
## ledger:RL-SIM-FIXED-60 (assumption), not an observed Y8 clock.

static var FORBIDDEN_OFFICIAL: PackedStringArray = PackedStringArray([
	"teleport", "force_kill"
])


static func load_path(path: String) -> Dictionary:
	var parsed: Dictionary = SimConstants.load_json(path)
	if parsed.is_empty():
		return {}
	return parsed


static func list_dir(dir_path: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return out
	dir.list_dir_begin()
	var name: String = dir.get_next()
	while name != "":
		if not dir.current_is_dir() and name.ends_with(".json"):
			out.append("%s/%s" % [dir_path, name])
		name = dir.get_next()
	dir.list_dir_end()
	out.sort()
	return out


static func validate(trace: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if str(trace.get("schema", "")) != SimConstants.TRACE_ID:
		errors.append("trace schema must be %s" % SimConstants.TRACE_ID)
	if int(trace.get("schema_version", 0)) != SimConstants.SCHEMA_VERSION:
		errors.append("trace schema_version mismatch")
	if str(trace.get("title", "")) != "Vault Fighters":
		errors.append("trace title must be Vault Fighters")
	if int(trace.get("tick_hz", 0)) != SimConstants.TICK_HZ:
		errors.append("trace tick_hz must be 60")
	if bool(trace.get("y8_tick_rate_claimed", true)):
		errors.append("trace must not claim a Y8 tick rate")
	if bool(trace.get("y8_parity_claimed", true)):
		errors.append("trace must not claim Y8 parity")
	if str(trace.get("ledger_clock", "")) != "RL-SIM-FIXED-60":
		errors.append("trace must cite ledger:RL-SIM-FIXED-60")
	var kind: String = str(trace.get("kind", ""))
	if kind != "official" and kind != "fixture":
		errors.append("trace kind must be official or fixture")
	if kind == "official":
		_append(errors, official_forbidden(trace))
	if not trace.has("segments") and not trace.has("frames"):
		errors.append("trace missing segments and frames")
	if trace.has("frames"):
		errors.append_array(validate_frame_ticks(trace.get("frames", []) as Array))
	if trace.has("segments"):
		var segs: Array = trace.get("segments", []) as Array
		var si: int = 0
		while si < segs.size():
			if not (segs[si] is Dictionary):
				errors.append("segment %d must be object" % si)
			else:
				var seg: Dictionary = segs[si] as Dictionary
				if int(seg.get("ticks", 1)) < 1 and not seg.has("repeat"):
					errors.append("segment %d ticks must be positive" % si)
			si += 1
	var ops: Array = trace.get("match_ops", []) as Array
	var seen_ticks: Dictionary = {}
	var quit_seen: bool = false
	var previous_op_tick: int = -1
	var oi: int = 0
	while oi < ops.size():
		if not (ops[oi] is Dictionary):
			errors.append("match_ops[%d] must be object" % oi)
		else:
			var op: Dictionary = ops[oi] as Dictionary
			var name: String = str(op.get("op", ""))
			var tick: int = int(op.get("tick", -1))
			if not ["pause", "resume", "quit"].has(name):
				errors.append("illegal match op %s" % name)
			if tick < 0:
				errors.append("match op tick must be non-negative")
			elif tick < previous_op_tick:
				errors.append("match op ticks must be non-decreasing")
			previous_op_tick = maxi(previous_op_tick, tick)
			if seen_ticks.has(tick):
				errors.append("duplicate same-tick match op at %d" % tick)
			seen_ticks[tick] = true
			if quit_seen:
				errors.append("match op %s occurs after terminal quit" % name)
			if name == "quit":
				quit_seen = true
			oi += 1
	return errors


static func validate_frame_ticks(raw: Array) -> PackedStringArray:
	## Validate authored tick continuity before _normalize_frames can synthesize
	## missing slots or overwrite malformed indices.
	var errors: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < raw.size():
		var row: Variant = raw[i]
		if row is Dictionary:
			var d: Dictionary = row as Dictionary
			if not d.has("tick"):
				errors.append("frame row %d missing tick" % i)
			elif int(d.get("tick", -1)) != i:
				errors.append("frame row %d tick discontinuity expected=%d got=%d" % [i, i, int(d.get("tick", -1))])
		elif row is Array:
			var slots: Array = row as Array
			var s: int = 0
			while s < slots.size():
				var frame: Variant = slots[s]
				var tick: int = -1
				if frame is InputFrame:
					tick = (frame as InputFrame).tick
				elif frame is Dictionary:
					tick = int((frame as Dictionary).get("tick", -1))
				if tick != i:
					errors.append("frame row %d slot %d tick discontinuity expected=%d got=%d" % [i, s, i, tick])
				s += 1
		i += 1
	return errors


static func official_forbidden(trace: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var ops: Array = trace.get("fixture_ops", []) as Array
	if not ops.is_empty():
		errors.append("official trace must not contain fixture_ops")
	var i: int = 0
	while i < ops.size():
		var op: Dictionary = ops[i] as Dictionary
		var name: String = str(op.get("op", ""))
		if FORBIDDEN_OFFICIAL.has(name):
			errors.append("official trace contains %s" % name)
		i += 1
	var dumped: String = JSON.stringify(trace)
	if dumped.contains("teleport") or dumped.contains("force_kill"):
		errors.append("official trace text contains teleport or force_kill")
	return errors


static func is_official(trace: Dictionary) -> bool:
	return str(trace.get("kind", "")) == "official"


static func snapshot_every(trace: Dictionary) -> int:
	var n: int = int(trace.get("snapshot_every", SimConstants.DEFAULT_SNAPSHOT_EVERY))
	if n < 1:
		return SimConstants.DEFAULT_SNAPSHOT_EVERY
	return n


static func fighter_count(trace: Dictionary) -> int:
	var n: int = int(trace.get("fighter_count", 0))
	if n > 0:
		return n
	var mode: String = str(trace.get("mode", "vs2"))
	if mode == "vs2":
		return 2
	return 3


static func expand_tick_bundles(trace: Dictionary) -> Array:
	if trace.has("frames"):
		return _normalize_frames(trace.get("frames", []) as Array, fighter_count(trace))
	var flat: Array = _flatten_segments(trace.get("segments", []) as Array)
	var count: int = fighter_count(trace)
	var bundles: Array = []
	var prev_held: Array = []
	var s: int = 0
	while s < count:
		prev_held.append(PackedStringArray())
		s += 1
	var tick: int = 0
	var i: int = 0
	while i < flat.size():
		var seg: Dictionary = flat[i] as Dictionary
		var ticks: int = int(seg.get("ticks", 1))
		if ticks < 1:
			ticks = 1
		var t: int = 0
		while t < ticks:
			var slots: Array = []
			var si: int = 0
			while si < count:
				var spec: Dictionary = _slot_spec(seg, si)
				var held: PackedStringArray = InputFrame._to_packed(spec.get("held", []))
				var pressed: PackedStringArray = PackedStringArray()
				var released: PackedStringArray = InputFrame._to_packed(spec.get("released", []))
				var prev: PackedStringArray = prev_held[si] as PackedStringArray
				var h: int = 0
				while h < held.size():
					var action: String = String(held[h])
					if not prev.has(action):
						pressed.append(action)
					h += 1
				h = 0
				while h < prev.size():
					var was: String = String(prev[h])
					if not held.has(was) and not released.has(was):
						released.append(was)
					h += 1
				if spec.has("pressed"):
					pressed = InputFrame._to_packed(spec.get("pressed", []))
				var frame: Dictionary = InputActions.empty_frame(tick, si)
				frame["held"] = Array(held)
				frame["pressed"] = Array(pressed)
				frame["released"] = Array(released)
				frame["move_x"] = float(spec.get("move_x", _axis_from_held(held, "left", "right")))
				frame["move_y"] = float(spec.get("move_y", _axis_from_held(held, "up", "down")))
				slots.append(frame)
				prev_held[si] = held
				si += 1
			bundles.append(slots)
			tick += 1
			t += 1
		i += 1
	return bundles


static func to_input_frames(bundle: Array) -> Array:
	var frames: Array = []
	var i: int = 0
	while i < bundle.size():
		var raw: Variant = bundle[i]
		if raw is InputFrame:
			frames.append(raw)
		elif raw is Dictionary:
			frames.append(InputFrame.from_dict(raw as Dictionary))
		i += 1
	return frames


static func mutate_one_key(trace: Dictionary) -> Dictionary:
	var copy: Dictionary = trace.duplicate(true)
	var bundles: Array = expand_tick_bundles(copy)
	if bundles.is_empty():
		return copy
	var found: bool = false
	var i: int = 0
	while i < bundles.size() and not found:
		var slots: Array = bundles[i] as Array
		if slots.is_empty():
			i += 1
			continue
		var frame: Dictionary = slots[0] as Dictionary
		var held: Array = frame.get("held", []) as Array
		if held.has("right") or float(frame.get("move_x", 0.0)) > 0.0:
			frame["held"] = []
			frame["pressed"] = []
			frame["move_x"] = 0.0
			slots[0] = frame
			bundles[i] = slots
			found = true
		i += 1
	if not found and not bundles.is_empty():
		var first_slots: Array = bundles[0] as Array
		var first: Dictionary = first_slots[0] as Dictionary
		first["held"] = ["crouch"]
		first["pressed"] = ["crouch"]
		first["move_x"] = 0.0
		first_slots[0] = first
		bundles[0] = first_slots
	copy.erase("segments")
	copy["frames"] = _bundles_to_frames(bundles)
	return copy


static func _bundles_to_frames(bundles: Array) -> Array:
	var frames: Array = []
	var i: int = 0
	while i < bundles.size():
		frames.append({
			"tick": i,
			"slots": bundles[i],
		})
		i += 1
	return frames


static func _normalize_frames(raw: Array, count: int) -> Array:
	var bundles: Array = []
	var i: int = 0
	while i < raw.size():
		var row: Variant = raw[i]
		if row is Array:
			bundles.append(row)
		elif row is Dictionary:
			var d: Dictionary = row as Dictionary
			if d.has("slots"):
				bundles.append(d.get("slots", []) as Array)
			else:
				var one: Array = []
				one.append(d)
				var s: int = 1
				while s < count:
					one.append(InputActions.empty_frame(int(d.get("tick", i)), s))
					s += 1
				bundles.append(one)
		i += 1
	return bundles


static func _flatten_segments(raw: Array) -> Array:
	var out: Array = []
	var i: int = 0
	while i < raw.size():
		var item: Dictionary = raw[i] as Dictionary
		if item.has("repeat"):
			var n: int = int(item.get("repeat", 1))
			var inner: Array = _flatten_segments(item.get("segments", []) as Array)
			var r: int = 0
			while r < n:
				var j: int = 0
				while j < inner.size():
					out.append(inner[j])
					j += 1
				r += 1
		else:
			out.append(item)
		i += 1
	return out


static func _slot_spec(seg: Dictionary, slot: int) -> Dictionary:
	if slot == 0 and seg.has("p1"):
		return seg.get("p1", {}) as Dictionary
	if slot == 1 and seg.has("p2"):
		return seg.get("p2", {}) as Dictionary
	var slots: Dictionary = seg.get("slots", {}) as Dictionary
	var key: String = str(slot)
	if slots.has(key):
		return slots[key] as Dictionary
	if slots.has(slot):
		return slots[slot] as Dictionary
	return {}


static func _axis_from_held(held: PackedStringArray, neg: String, pos: String) -> float:
	var v: float = 0.0
	if held.has(pos):
		v += 1.0
	if held.has(neg):
		v -= 1.0
	return v


static func _append(into: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		into.append(String(extra[i]))
		i += 1

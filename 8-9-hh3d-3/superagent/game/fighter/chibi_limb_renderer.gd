extends RefCounted
## Shared cel arms for body and gun view: one skin/clothing silhouette, not
## individually outlined bones. Coordinates are presentation-only.

const Geometry = preload("res://game/fighter/chibi_limb_geometry.gd")

static var _arm_geom_cache: Dictionary = {}
static var _leg_geom_cache: Dictionary = {}


static func _q_vec(v: Vector2) -> Vector2i:
	return Vector2i(int(roundf(v.x * 20.0)), int(roundf(v.y * 20.0)))


static func get_cached_leg_geometry(hip: Vector2, knee: Vector2, ankle: Vector2) -> Dictionary:
	var key: Array = [_q_vec(hip), _q_vec(knee), _q_vec(ankle)]
	if _leg_geom_cache.has(key):
		return _leg_geom_cache[key] as Dictionary
	if _leg_geom_cache.size() >= 1024:
		_leg_geom_cache.clear()
	var contours: Array[PackedVector2Array] = Geometry.chain_contours(hip, knee, ankle, 1.25, 1.03, 0.81)
	var outlines: Array[PackedVector2Array] = []
	for contour: PackedVector2Array in contours:
		var closed: PackedVector2Array = contour.duplicate()
		closed.append(contour[0])
		outlines.append(closed)
	var entry: Dictionary = {
		"contours": contours,
		"outlines": outlines,
	}
	_leg_geom_cache[key] = entry
	return entry


static func get_cached_arm_geometry(
	shoulder: Vector2,
	elbow: Vector2,
	hand: Vector2,
	direction: Vector2,
	shape: String,
	handwear: String,
	strike: bool,
	coverage: String
) -> Dictionary:
	var key: Array = [_q_vec(shoulder), _q_vec(elbow), _q_vec(hand), shape, handwear, strike, coverage]
	if _arm_geom_cache.has(key):
		return _arm_geom_cache[key] as Dictionary
	if _arm_geom_cache.size() >= 1024:
		_arm_geom_cache.clear()
	var palm: PackedVector2Array = hand_polygon(hand, direction, shape, handwear, strike)
	var contours: Array[PackedVector2Array] = Geometry.chain_contours(shoulder, elbow, hand, 0.92, 0.73, 0.48)
	if not contours.is_empty():
		var merged: Array[PackedVector2Array] = Geometry2D.merge_polygons(contours[0], palm)
		if merged.size() == 1:
			contours = merged
	var short_patches: Array[PackedVector2Array] = []
	if coverage == "short" and not contours.is_empty():
		for patch: PackedVector2Array in Geometry.chain_contours(shoulder, shoulder.lerp(elbow, 0.28), shoulder.lerp(elbow, 0.52), 0.92, 0.84, 0.76):
			for clipped: PackedVector2Array in Geometry2D.intersect_polygons(contours[0], patch):
				short_patches.append(clipped)
	var strokes: Array[PackedVector2Array] = []
	var upper: Vector2 = (elbow - shoulder).normalized()
	for contour: PackedVector2Array in contours:
		var first_open_edge: int = -1
		for index: int in range(contour.size()):
			var a: Vector2 = contour[index]
			var b: Vector2 = contour[(index + 1) % contour.size()]
			var offset: Vector2 = (a + b) * 0.5 - shoulder
			if offset.length_squared() < 1.2 and offset.dot(upper) < 0.15:
				first_open_edge = index
				break
		var stroke: PackedVector2Array = PackedVector2Array()
		for step: int in range(contour.size()):
			var index: int = (first_open_edge + 1 + step) % contour.size()
			var a: Vector2 = contour[index]
			var b: Vector2 = contour[(index + 1) % contour.size()]
			var offset: Vector2 = (a + b) * 0.5 - shoulder
			if offset.length_squared() < 1.2 and offset.dot(upper) < 0.15:
				if stroke.size() > 1:
					strokes.append(stroke.duplicate())
				stroke.clear()
				continue
			if stroke.is_empty():
				stroke.append(a)
			stroke.append(b)
		if stroke.size() > 1:
			strokes.append(stroke.duplicate())
	var entry: Dictionary = {
		"contours": contours,
		"palm": palm,
		"short_patches": short_patches,
		"strokes": strokes,
	}
	_arm_geom_cache[key] = entry
	return entry


static func tint_color(color: Color, charred: bool, hit_flash: bool, alpha: float = 1.0) -> Color:
	if charred:
		return Color(0.05, 0.04, 0.04, color.a * alpha)
	if hit_flash:
		return Color(lerpf(color.r, 1.0, 0.8), lerpf(color.g, 1.0, 0.8), lerpf(color.b, 1.0, 0.8), color.a * alpha)
	return Color(color.r, color.g, color.b, color.a * alpha)


static func draw_arm(canvas: CanvasItem, shoulder: Vector2, elbow: Vector2, hand: Vector2, sleeve: Color, skin: Color, glove: Color, trim: Color, outline: Color, strike: bool = false, shape: String = "relaxed", handwear: String = "bare", wristband: bool = false, coverage: String = "long") -> void:
	var direction: Vector2 = (hand - elbow).normalized()
	if direction.length_squared() < 0.01:
		direction = Vector2.DOWN
	var normal: Vector2 = direction.orthogonal()
	var geom: Dictionary = get_cached_arm_geometry(shoulder, elbow, hand, direction, shape, handwear, strike, coverage)
	var contours: Array = geom["contours"] as Array
	if contours.is_empty():
		return
	var palm: PackedVector2Array = geom["palm"] as PackedVector2Array
	var base: Color = sleeve if coverage == "long" else skin
	for contour: PackedVector2Array in contours:
		canvas.draw_colored_polygon(contour, base)
	# Volumetric 2-tone cel highlight & shadow along the arm cylinder
	var upper_dir: Vector2 = (elbow - shoulder).normalized()
	var upper_norm: Vector2 = upper_dir.orthogonal()
	canvas.draw_line(shoulder.lerp(elbow, 0.25) - upper_norm * 0.28, elbow.lerp(hand, 0.65) - normal * 0.22, base.lightened(0.15), 0.36, true)
	canvas.draw_line(shoulder.lerp(elbow, 0.25) + upper_norm * 0.32, elbow.lerp(hand, 0.65) + normal * 0.25, base.darkened(0.18), 0.34, true)
	# Sleeve/skin are material changes, never black rings around each bone.
	if coverage == "short":
		for clipped: PackedVector2Array in geom["short_patches"] as Array:
			canvas.draw_colored_polygon(clipped, sleeve)
	var palm_color: Color = skin if handwear == "bare" else glove
	canvas.draw_colored_polygon(palm, palm_color)
	for stroke: PackedVector2Array in geom["strokes"] as Array:
		canvas.draw_polyline(stroke, outline, 0.43, true)
	# Small fabric crease, not a full outline across the elbow.
	if coverage == "long":
		canvas.draw_line(elbow - normal * 0.3, elbow + direction * 0.4, sleeve.darkened(0.18), 0.23, true)
	if wristband or handwear in ["glove", "gauntlet"]:
		var wrist: Vector2 = hand - direction * 0.45
		canvas.draw_line(wrist - normal * 0.5, wrist + normal * 0.5, glove, 0.64, true)
		if wristband:
			canvas.draw_line(wrist - direction * 0.26 - normal * 0.45, wrist - direction * 0.26 + normal * 0.45, glove.lightened(0.15), 0.2, true)
	_draw_hand_detail(canvas, hand, direction, shape, handwear, skin, palm_color)
	if strike:
		# Dynamic 2-layer crescent action smear arc & impact flash
		var arc_back: Vector2 = shoulder.lerp(elbow, 0.5) - normal * 1.4
		var arc_mid: Vector2 = elbow + direction * 1.1 - normal * 1.1
		var arc_tip: Vector2 = hand + direction * 2.8
		canvas.draw_polyline(PackedVector2Array([arc_back, arc_mid, arc_tip]), Color(trim.r, trim.g, trim.b, 0.55), 1.15, true)
		canvas.draw_line(hand + direction * 1.4, arc_tip, Color(1.0, 0.98, 0.88, 0.92), 0.68, true)


static func hand_polygon(hand: Vector2, direction: Vector2, shape: String, handwear: String, strike: bool = false) -> PackedVector2Array:
	var normal: Vector2 = direction.orthogonal()
	var closed: bool = shape in ["fist", "loose_fist", "grip"]
	var length: float = 0.85 if closed else 1.12
	var width: float = 0.67 if closed else 0.59
	if handwear in ["glove", "gauntlet"]:
		length += 0.10
		width += 0.10
	if strike:
		length += 0.12
		width += 0.08
	return PackedVector2Array([
		hand - direction * 0.72 - normal * 0.45,
		hand + direction * 0.12 - normal * width,
		hand + direction * length - normal * width * 0.64,
		hand + direction * (length + 0.1) + normal * width * 0.35,
		hand + direction * 0.25 + normal * width,
		hand - direction * 0.72 + normal * 0.45,
	])


static func draw_grip_overlay(canvas: CanvasItem, hand: Vector2, elbow: Vector2, skin: Color, glove: Color, outline: Color, handwear: String) -> void:
	var direction: Vector2 = (hand - elbow).normalized()
	if direction.length_squared() < 0.01:
		direction = Vector2.DOWN
	var palm: PackedVector2Array = hand_polygon(hand, direction, "grip", handwear)
	var color: Color = skin if handwear == "bare" else glove
	canvas.draw_colored_polygon(palm, color)
	# Open wrist edge: the arm silhouette is already underneath the gun.
	canvas.draw_polyline(palm, outline, 0.43, true)
	_draw_hand_detail(canvas, hand, direction, "grip", handwear, skin, color)


static func _draw_hand_detail(canvas: CanvasItem, hand: Vector2, direction: Vector2, shape: String, handwear: String, skin: Color, palm_color: Color) -> void:
	var normal: Vector2 = direction.orthogonal()
	if handwear == "fingerless":
		canvas.draw_line(hand + direction * 0.65 - normal * 0.3, hand + direction * 0.65 + normal * 0.3, skin, 0.45, true)
	if shape in ["fist", "loose_fist", "grip"]:
		canvas.draw_line(hand + direction * 0.48 - normal * 0.25, hand + direction * 0.48 + normal * 0.22, palm_color.darkened(0.24), 0.22, true)
	elif shape == "splayed":
		canvas.draw_line(hand + direction * 0.45, hand + direction * 1.05, palm_color.darkened(0.24), 0.19, true)

extends RefCounted
## Pure, bounded presentation geometry. Returned contours are unclosed: fill
## each polygon, then append its first point once to draw its exterior outline.
## No nodes, resources, pose mutation, persistent cache, or interior joint rings.

const MIN_RADIUS: float = 0.03125
const MAX_RADIUS: float = 4096.0
const MAX_COORDINATE: float = 32768.0
const MAX_VERTICES: int = 48
const _EPSILON_SQUARED: float = 0.00000001
const _RING: Array[Vector2] = [
	Vector2(1.0, 0.0), Vector2(0.8660254, 0.5),
	Vector2(0.5, 0.8660254), Vector2(0.0, 1.0),
	Vector2(-0.5, 0.8660254), Vector2(-0.8660254, 0.5),
	Vector2(-1.0, 0.0), Vector2(-0.8660254, -0.5),
	Vector2(-0.5, -0.8660254), Vector2(0.0, -1.0),
	Vector2(0.5, -0.8660254), Vector2(0.8660254, -0.5),
]


static func chain_contours(
	start: Vector2, joint: Vector2, finish: Vector2,
	start_radius: float, joint_radius: float, end_radius: float
) -> Array[PackedVector2Array]:
	# Invalid/oversized inputs fail safely with no geometry. Finite nonpositive
	# widths become a tiny positive width, so zero-width/collapsed chains still
	# have a triangulatable silhouette. Valid endpoints are never moved.
	var result: Array[PackedVector2Array] = []
	if not _valid_point(start) or not _valid_point(joint) or not _valid_point(finish):
		return result
	if not is_finite(start_radius) or not is_finite(joint_radius) or not is_finite(end_radius):
		return result
	if maxf(maxf(start_radius, joint_radius), end_radius) > MAX_RADIUS:
		return result
	var r0: float = maxf(MIN_RADIUS, start_radius)
	var r1: float = maxf(MIN_RADIUS, joint_radius)
	var r2: float = maxf(MIN_RADIUS, end_radius)
	# Work relative to the joint to preserve clipping precision after translation.
	var upper: PackedVector2Array = _segment(start - joint, Vector2.ZERO, r0, r1)
	var lower: PackedVector2Array = _segment(Vector2.ZERO, finish - joint, r1, r2)
	var merged: Array[PackedVector2Array] = Geometry2D.merge_polygons(upper, lower)
	var contour: PackedVector2Array
	if merged.size() == 1:
		contour = _unclosed(merged[0])
	# Both convex segments contain the same nonzero joint disk. Their union is
	# star-shaped about the joint, and therefore has one boundary and no holes,
	# including 180-degree folds. A numeric clipping failure gets a conservative
	# convex exterior rather than disjoint outlines or invalid draw geometry.
	if contour.size() < 3 or contour.size() > MAX_VERTICES:
		var all_points: PackedVector2Array = upper.duplicate()
		all_points.append_array(lower)
		contour = _unclosed(Geometry2D.convex_hull(all_points))
	for index: int in range(contour.size()):
		contour[index] += joint
	# Godot's float32 ear clipper sums absolute-coordinate cross products. At
	# distant coordinates its winding estimate can disagree with the local
	# geometry even though every edge is valid. Only that exceptional path pays
	# for triangulation checks; ordinary fighter-local drawing stays unchanged.
	if maxf(maxf(absf(joint.x), absf(joint.y)), maxf(maxf(absf(start.x), absf(start.y)), maxf(absf(finish.x), absf(finish.y)))) > 1024.0:
		contour = _precision_safe(contour, start, joint, finish, r1)
	result.append(contour)
	return result


static func _precision_safe(contour: PackedVector2Array, start: Vector2, joint: Vector2, finish: Vector2, joint_radius: float) -> PackedVector2Array:
	if _triangulatable(contour):
		return contour
	# Try alternate summation starts without changing winding or geometry.
	for offset: int in range(1, contour.size()):
		var rotated: PackedVector2Array = PackedVector2Array()
		for index: int in range(contour.size()):
			rotated.append(contour[(index + offset) % contour.size()])
		if _triangulatable(rotated):
			return rotated
	# A distant numeric failure may conservatively fill the inner bend. Remove
	# the least significant convex corners only while both centerlines and the
	# inner joint disk remain covered. Each pass removes one vertex: bounded48.
	var outer: PackedVector2Array = _unclosed(Geometry2D.convex_hull(contour))
	while outer.size() >= 3:
		if _triangulatable(outer):
			return outer
		if outer.size() == 3:
			break
		var best_index: int = -1
		var best_area: float = INF
		for index: int in range(outer.size()):
			var previous: Vector2 = outer[(index + outer.size() - 1) % outer.size()]
			var next: Vector2 = outer[(index + 1) % outer.size()]
			var area: float = absf((outer[index] - previous).cross(next - outer[index]))
			if area >= best_area:
				continue
			var candidate: PackedVector2Array = outer.duplicate()
			candidate.remove_at(index)
			if _covers_chain(candidate, start, joint, finish, joint_radius):
				best_area = area
				best_index = index
		if best_index < 0:
			break
		outer.remove_at(best_index)
	# Last-resort numerical envelope. It is only reached beyond the local-space
	# use case, preserves coverage, and never emits an undrawable polygon.
	var bounds: Rect2 = Rect2(contour[0], Vector2.ZERO)
	for point: Vector2 in contour:
		bounds = bounds.expand(point)
	var padding: float = MIN_RADIUS
	for attempt: int in range(16):
		var safe: Rect2 = bounds.grow(padding)
		var box: PackedVector2Array = PackedVector2Array([safe.position, Vector2(safe.end.x, safe.position.y), safe.end, Vector2(safe.position.x, safe.end.y)])
		if _triangulatable(box):
			return box
		padding *= 2.0
	return outer


static func _triangulatable(contour: PackedVector2Array) -> bool:
	return Geometry2D.triangulate_polygon(contour).size() == (contour.size() - 2) * 3


static func _covers_chain(contour: PackedVector2Array, start: Vector2, joint: Vector2, finish: Vector2, joint_radius: float) -> bool:
	if not Geometry2D.is_point_in_polygon(start, contour) or not Geometry2D.is_point_in_polygon(joint, contour) or not Geometry2D.is_point_in_polygon(finish, contour):
		return false
	for direction: Vector2 in _RING:
		if not Geometry2D.is_point_in_polygon(joint + direction * joint_radius * 0.5, contour):
			return false
	return true


static func _valid_point(point: Vector2) -> bool:
	return is_finite(point.x) and is_finite(point.y) and absf(point.x) <= MAX_COORDINATE and absf(point.y) <= MAX_COORDINATE


static func _segment(start: Vector2, finish: Vector2, start_radius: float, end_radius: float) -> PackedVector2Array:
	var points: PackedVector2Array = PackedVector2Array()
	points.resize(_RING.size() * 2)
	for index: int in range(_RING.size()):
		points[index] = start + _RING[index] * start_radius
		points[index + _RING.size()] = finish + _RING[index] * end_radius
	return _unclosed(Geometry2D.convex_hull(points))


static func _unclosed(points: PackedVector2Array) -> PackedVector2Array:
	var clean: PackedVector2Array = PackedVector2Array()
	for point: Vector2 in points:
		if clean.is_empty() or clean[clean.size() - 1].distance_squared_to(point) > _EPSILON_SQUARED:
			clean.append(point)
	if clean.size() > 1 and clean[0].distance_squared_to(clean[clean.size() - 1]) <= _EPSILON_SQUARED:
		clean.resize(clean.size() - 1)
	return clean

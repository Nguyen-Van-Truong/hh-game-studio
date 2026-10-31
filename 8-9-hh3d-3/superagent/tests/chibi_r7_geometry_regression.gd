extends SceneTree
## Pure geometry fixtures. Coordinator runs this in its serial engine sequence.
## Benchmarks report helper wall time, never an inferred gameplay FPS claim.

const Limb = preload("res://game/fighter/chibi_limb_geometry.gd")
const Pose = preload("res://game/fighter/chibi_action_pose.gd")
const Renderer = preload("res://game/fighter/chibi_limb_renderer.gd")
const BENCHMARK_CHAINS: int = 4000

var _checks: int = 0
var _failures: int = 0
var _chains: int = 0
var _largest_contour: int = 0


func _initialize() -> void:
	_authored_poses()
	_extreme_chains()
	_malformed_inputs()
	_benchmark()
	print("[CHIBI R7 GEOMETRY] " + ("PASS" if _failures == 0 else "FAIL") + " checks=" + str(_checks) + " failures=" + str(_failures) + " chains=" + str(_chains) + " max_vertices=" + str(_largest_contour))
	quit(0 if _failures == 0 else 1)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R7 GEOMETRY] " + label)


func _authored_poses() -> void:
	var states: Array = Pose.STATE_LENGTHS.keys()
	states.append_array(["WIN", "AIM_FISTS", "AIM_PISTOL", "AIM_SHOTGUN", "START_PISTOL", "GRAB_PUNCH", "JUMP_PUNCH_01"])
	for state_value: Variant in states:
		var state: String = str(state_value)
		var length: int = int(ceil(float(Pose.STATE_LENGTHS.get(state, 8.0))))
		# Every authored frame and its halfway interpolation sample.
		for half_frame: int in range(length * 2 + 1):
			var source: float = float(half_frame) * 0.5
			var pose: Dictionary = Pose.sample(state, 1, 0.0, false, source)
			_check_pose(pose, state + "/" + str(source))
	# Optional context changes the actual authored endpoint configurations.
	for state: String in ["IDLE", "RUN", "SPRINT", "JUMP", "FALL", "CROUCH", "COVER", "AIM_PISTOL", "THROW", "FALL_B", "ROLL"]:
		for source: float in [0.0, 1.75, 3.5, 5.25, 7.5]:
			for velocity_y: float in [-5.0, 0.0, 3.0, 10.0]:
				for carrying: bool in [false, true]:
					var pose: Dictionary = Pose.sample(state, 1, -65.0, carrying, source, 137.0, "COVER", {"velocity": Vector2(2.0, velocity_y), "grounded": false, "burning": true})
					_check_pose(pose, "context/" + state)


func _check_pose(pose: Dictionary, label: String) -> void:
	var before: Dictionary = pose.duplicate(true)
	var angle: float = deg_to_rad(float(pose["root_rotation_deg"]))
	var origin: Vector2 = pose["root_origin"]
	for side: String in ["front", "back"]:
		var shoulder: Vector2 = origin + (pose["shoulder_" + side] as Vector2).rotated(angle)
		var elbow: Vector2 = origin + (pose["elbow_" + side] as Vector2).rotated(angle)
		var hand: Vector2 = origin + (pose["hand_" + side] as Vector2).rotated(angle)
		_inspect(shoulder, elbow, hand, Vector3(0.92, 0.73, 0.48), label + "/arm/" + side)
		_inspect_hand_union(shoulder, elbow, hand, str(pose["hand_" + side + "_shape"]), bool(pose["contact"]), label + "/palm/" + side)
		var hip: Vector2 = origin + (pose["hip_" + side] as Vector2).rotated(angle)
		var knee: Vector2 = origin + (pose["knee_" + side] as Vector2).rotated(angle)
		var ankle: Vector2 = origin + (pose["ankle_" + side] as Vector2).rotated(angle)
		_inspect(hip, knee, ankle, Vector3(1.25, 1.03, 0.81), label + "/leg/" + side)
	_check(pose == before, label + " preserves all sampled pose endpoints and socket context")


func _inspect_hand_union(shoulder: Vector2, elbow: Vector2, hand: Vector2, shape: String, strike: bool, label: String) -> void:
	var direction: Vector2 = (hand - elbow).normalized()
	if direction.length_squared() < 0.01:
		direction = Vector2.DOWN
	var arm: Array[PackedVector2Array] = Limb.chain_contours(shoulder, elbow, hand, 0.92, 0.73, 0.48)
	if arm.size() != 1:
		return # The matching arm inspection already records the invalid contour.
	for handwear: String in ["bare", "fingerless", "glove", "gauntlet"]:
		var palm: PackedVector2Array = Renderer.hand_polygon(hand, direction, shape, handwear, strike)
		var merged: Array[PackedVector2Array] = Geometry2D.merge_polygons(arm[0], palm)
		var tag: String = label + "/" + handwear
		_check(merged.size() == 1, tag + " arm/palm union has one contour and no holes")
		if merged.size() != 1:
			continue
		var polygon: PackedVector2Array = merged[0]
		var triangles: PackedInt32Array = Geometry2D.triangulate_polygon(polygon)
		_check(triangles.size() == (polygon.size() - 2) * 3, tag + " arm/palm union triangulates")
		_check(not _self_intersects(polygon), tag + " arm/palm union has a simple exterior")
		_check(Geometry2D.is_point_in_polygon(hand, polygon), tag + " wrist attachment remains solid")


func _extreme_chains() -> void:
	for degrees: float in [-180.0, -179.99, -175.0, -135.0, -90.0, -45.0, -0.01, 0.0, 0.01, 45.0, 90.0, 135.0, 175.0, 179.99, 180.0]:
		for radii: Vector3 in [Vector3(0.92, 0.73, 0.48), Vector3(1.25, 1.03, 0.81), Vector3(0.03, 3.0, 0.03), Vector3(3.0, 0.03, 3.0), Vector3.ZERO]:
			for length: float in [0.0, 0.000001, 0.05, 1.0, 12.0]:
				var start: Vector2 = Vector2(-length, 0.0)
				var finish: Vector2 = Vector2(length, 0.0).rotated(deg_to_rad(degrees))
				_inspect(start, Vector2.ZERO, finish, radii, "bend/" + str(degrees) + "/" + str(length))
	_inspect(Vector2.ONE, Vector2.ONE, Vector2.ONE, Vector3(0.92, 0.73, 0.48), "all collapsed")
	_inspect(Vector2(-10.0, 2.0), Vector2(4.0, 2.0), Vector2(-10.0, 2.0), Vector3(0.92, 0.73, 0.48), "exact reversed overlap")
	_inspect(Vector2(-3.0, -4.0), Vector2.ZERO, Vector2(0.0, 9.0), Vector3(-10.0, -1.0, 0.0), "finite nonpositive radii")
	_inspect(Vector2(32000.0, 32000.0), Vector2(32002.0, 32003.0), Vector2(32000.0, 32004.0), Vector3(0.92, 0.73, 0.48), "large finite translated chain")


func _inspect(start: Vector2, joint: Vector2, finish: Vector2, radii: Vector3, label: String) -> void:
	_chains += 1
	var contours: Array[PackedVector2Array] = Limb.chain_contours(start, joint, finish, radii.x, radii.y, radii.z)
	_check(contours.size() == 1, label + " has one outer boundary and no hole contours")
	if contours.size() != 1:
		return
	var polygon: PackedVector2Array = contours[0]
	_largest_contour = maxi(_largest_contour, polygon.size())
	_check(polygon.size() >= 3 and polygon.size() <= Limb.MAX_VERTICES, label + " bounded vertex count")
	var finite: bool = true
	for point: Vector2 in polygon:
		finite = finite and is_finite(point.x) and is_finite(point.y)
	_check(finite, label + " finite contour")
	_check(polygon[0] != polygon[polygon.size() - 1], label + " contour is unclosed")
	var triangles: PackedInt32Array = Geometry2D.triangulate_polygon(polygon)
	_check(triangles.size() == (polygon.size() - 2) * 3, label + " triangulates as a simple solid polygon")
	_check(not _self_intersects(polygon), label + " no nonadjacent boundary intersections")
	var centerline_covered: bool = true
	for index: int in range(9):
		var weight: float = float(index) / 8.0
		centerline_covered = centerline_covered and Geometry2D.is_point_in_polygon(start.lerp(joint, weight), polygon) and Geometry2D.is_point_in_polygon(joint.lerp(finish, weight), polygon)
	_check(centerline_covered, label + " both centerlines and joint remain covered")
	# The whole inner joint disk must be solid, not an outlined ring or hole.
	var joint_solid: bool = true
	for index: int in range(8):
		var inner: Vector2 = joint + Vector2.RIGHT.rotated(TAU * float(index) / 8.0) * maxf(Limb.MIN_RADIUS, radii.y) * 0.5
		joint_solid = joint_solid and Geometry2D.is_point_in_polygon(inner, polygon)
	_check(joint_solid, label + " joint interior is solid")


func _self_intersects(polygon: PackedVector2Array) -> bool:
	for first: int in range(polygon.size()):
		var first_next: int = (first + 1) % polygon.size()
		for second: int in range(first + 1, polygon.size()):
			var second_next: int = (second + 1) % polygon.size()
			if first_next == second or second_next == first:
				continue
			if Geometry2D.segment_intersects_segment(polygon[first], polygon[first_next], polygon[second], polygon[second_next]) != null:
				return true
	return false


func _malformed_inputs() -> void:
	for bad_point: Vector2 in [Vector2(NAN, 0.0), Vector2(0.0, INF), Vector2(-INF, NAN), Vector2(1e30, 0.0)]:
		_check(Limb.chain_contours(bad_point, Vector2.ZERO, Vector2.ONE, 1.0, 1.0, 1.0).is_empty(), "bad start rejected")
		_check(Limb.chain_contours(Vector2.ZERO, bad_point, Vector2.ONE, 1.0, 1.0, 1.0).is_empty(), "bad joint rejected")
		_check(Limb.chain_contours(Vector2.ZERO, Vector2.ONE, bad_point, 1.0, 1.0, 1.0).is_empty(), "bad finish rejected")
	for bad_radius: float in [NAN, INF, -INF, 1e30]:
		_check(Limb.chain_contours(Vector2.ZERO, Vector2.ONE, Vector2(2.0, 0.0), bad_radius, 1.0, 1.0).is_empty(), "bad start radius rejected")
		_check(Limb.chain_contours(Vector2.ZERO, Vector2.ONE, Vector2(2.0, 0.0), 1.0, bad_radius, 1.0).is_empty(), "bad joint radius rejected")
		_check(Limb.chain_contours(Vector2.ZERO, Vector2.ONE, Vector2(2.0, 0.0), 1.0, 1.0, bad_radius).is_empty(), "bad end radius rejected")
	var first: Array[PackedVector2Array] = Limb.chain_contours(Vector2.ZERO, Vector2(2.0, 1.0), Vector2(3.0, 4.0), 0.92, 0.73, 0.48)
	var original: PackedVector2Array = first[0].duplicate()
	first[0][0] = Vector2(999.0, 999.0)
	_check(Limb.chain_contours(Vector2.ZERO, Vector2(2.0, 1.0), Vector2(3.0, 4.0), 0.92, 0.73, 0.48)[0] == original, "caller mutation never pollutes later results")


func _benchmark() -> void:
	var vertex_total: int = 0
	var started: int = Time.get_ticks_usec()
	for index: int in range(BENCHMARK_CHAINS):
		var angle: float = float(index % 360) * PI / 180.0
		var contours: Array[PackedVector2Array] = Limb.chain_contours(Vector2(-3.0, 0.0), Vector2.ZERO, Vector2(3.0, 0.0).rotated(angle), 0.92, 0.73, 0.48)
		vertex_total += contours[0].size()
	var elapsed: int = Time.get_ticks_usec() - started
	_check(vertex_total > 0 and elapsed >= 0, "benchmark completed bounded nonempty work")
	print("[CHIBI R7 GEOMETRY] BENCHMARK chains=" + str(BENCHMARK_CHAINS) + " total_usec=" + str(elapsed) + " usec_per_chain=" + str(float(elapsed) / float(BENCHMARK_CHAINS)) + " vertices=" + str(vertex_total) + " fps_claim=none")

extends SceneTree
## Render-driver fixture for the CPU time spent inside the actual Chibi painter.
## Eight CanvasItem draw callbacks are sampled per tick after head prewarming.
## This excludes ChibiWeaponView, controllers/world, GPU work, frame latency and
## FPS.  No performance budget is asserted: PASS means a valid measurement only.

const Painter = preload("res://game/fighter/chibi_brawler_rig_painter.gd")
const HeadAtlas = preload("res://game/fighter/chibi_head_atlas.gd")
const ACTOR_COUNT: int = 8
const WARMUP_COUNT: int = 30
const SAMPLE_COUNT: int = 120
const TARGET_SIZE: Vector2i = Vector2i(960, 480)


class PainterProbe:
	extends Node2D
	var identity: String = "agent"
	var state_name: String = "IDLE"
	var source_frame: float = 0.0
	var pitch: float = 0.0
	var body_angle: float = 0.0
	var motion: Dictionary = {}
	var callbacks_this_tick: int = 0
	var elapsed_usec: int = 0
	var armed: bool = false
	var painter_script: Script = Painter

	func prepare(tick: int) -> void:
		source_frame = float(tick) * 0.5
		if state_name.begins_with("PUNCH"):
			source_frame = fposmod(source_frame, 8.0)
		elif state_name == "ROLL":
			source_frame = fposmod(source_frame, 6.0)
		callbacks_this_tick = 0
		elapsed_usec = 0
		armed = true
		queue_redraw()

	func _draw() -> void:
		var started_usec: int = Time.get_ticks_usec()
		painter_script.draw_chibi_brawler_rig(
			self, identity, state_name, 1, pitch, "CHEEKY_SMIRK", 0.0,
			false, false, false, false, false, false, 0.0, Vector2.ZERO,
			"", 3.4, source_frame, body_angle, Transform2D.IDENTITY, "", motion
		)
		var duration_usec: int = Time.get_ticks_usec() - started_usec
		if armed:
			callbacks_this_tick += 1
			elapsed_usec += duration_usec


var _page: Node2D = null
var _probes: Array[PainterProbe] = []
var _samples_ms: Array[float] = []
var _failed: bool = false
var _painter_script: Script = Painter
var _variant_label: String = "current"


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	if "--baseline" in OS.get_cmdline_user_args():
		var baseline_path: String = "res://.local/checkpoints/chibi-r7-20261028/chibi_brawler_rig_painter.gd"
		var source: String = FileAccess.get_file_as_string(baseline_path).replace("\r", "")
		if not source.begins_with("class_name ChibiBrawlerRigPainter\n"):
			_fail("missing/invalid checkpoint painter")
			await _finish(false)
			return
		var baseline := GDScript.new()
		# Avoid registering a duplicate global class; no renderer code changes.
		baseline.source_code = source.trim_prefix("class_name ChibiBrawlerRigPainter\n")
		if baseline.reload() != OK:
			_fail("checkpoint painter cannot compile")
			await _finish(false)
			return
		_painter_script = baseline
		_variant_label = "checkpoint_before_r7"
		print("[CHIBI R7 RENDER PERF] baseline_sha256=" + FileAccess.get_sha256(baseline_path))
	HeadAtlas.prewarm()
	if not bool(HeadAtlas.validation().get("ok", false)):
		_fail("head atlas prewarm validation failed")
		await _finish(false)
		return
	root.size = TARGET_SIZE
	root.content_scale_size = TARGET_SIZE
	RenderingServer.viewport_set_update_mode(root.get_viewport_rid(), RenderingServer.VIEWPORT_UPDATE_ALWAYS)
	_build_probes()
	# Settle the initial automatic CanvasItem draw outside every measured tick.
	await process_frame
	await RenderingServer.frame_post_draw
	for tick: int in range(WARMUP_COUNT + SAMPLE_COUNT):
		for probe: PainterProbe in _probes:
			probe.prepare(tick)
		await process_frame
		await RenderingServer.frame_post_draw
		var callbacks: int = 0
		var total_usec: int = 0
		for probe: PainterProbe in _probes:
			probe.armed = false
			callbacks += probe.callbacks_this_tick
			total_usec += probe.elapsed_usec
			if probe.callbacks_this_tick != 1 or probe.elapsed_usec <= 0:
				_fail("expected one positive-duration callback for " + probe.identity + "/" + probe.state_name + " tick=" + str(tick))
		if callbacks != ACTOR_COUNT:
			_fail("callback count=" + str(callbacks) + " expected=8 tick=" + str(tick))
		var elapsed_ms: float = float(total_usec) / 1000.0
		if not is_finite(elapsed_ms) or elapsed_ms <= 0.0:
			_fail("non-finite or nonpositive sample tick=" + str(tick))
		if _failed:
			await _finish(false)
			return
		if tick >= WARMUP_COUNT:
			_samples_ms.append(elapsed_ms)
	if _samples_ms.size() != SAMPLE_COUNT:
		_fail("sample count mismatch")
		await _finish(false)
		return
	await _finish(true)


func _build_probes() -> void:
	_page = Node2D.new()
	_page.name = "ChibiR7PainterCpuFixture"
	root.add_child(_page)
	var identities: Array[String] = ["agent", "goku", "naruto", "luffy", "saitama", "agent", "goku", "naruto"]
	var states: Array[String] = ["IDLE", "RUN", "JUMP", "PUNCH_01", "PUNCH_02", "PUNCH_03", "CROUCH", "ROLL"]
	for index: int in range(ACTOR_COUNT):
		var probe := PainterProbe.new()
		probe.name = "PainterProbe" + str(index)
		probe.identity = identities[index]
		probe.painter_script = _painter_script
		probe.state_name = states[index]
		var row: int = floori(float(index) / 4.0)
		probe.position = Vector2(120.0 + float(index % 4) * 240.0, 180.0 + float(row) * 230.0)
		probe.scale = Vector2.ONE * 3.4
		probe.motion = {"velocity": Vector2(2.0, -5.0) if index == 2 else Vector2(2.0 if index == 1 else 0.0, 0.0), "grounded": index != 2, "burning": false}
		_page.add_child(probe)
		_probes.append(probe)


func _fail(message: String) -> void:
	_failed = true
	push_error("[CHIBI R7 RENDER PERF] " + message)


func _finish(success: bool) -> void:
	_probes.clear()
	if is_instance_valid(_page):
		_page.free()
		_page = null
	await process_frame
	var drained: bool = true
	var audio: Node = root.get_node_or_null("AudioManager")
	if audio != null and audio.has_method("stop_all_and_drain"):
		drained = bool(await audio.call("stop_all_and_drain"))
	if success and drained:
		var ordered: Array[float] = _samples_ms.duplicate()
		ordered.sort()
		var p50: float = ordered[ceili(float(SAMPLE_COUNT) * 0.50) - 1]
		var p95: float = ordered[ceili(float(SAMPLE_COUNT) * 0.95) - 1]
		var maximum: float = ordered[SAMPLE_COUNT - 1]
		print("[CHIBI R7 RENDER PERF] PASS samples=120 actors=8 callbacks=960 warmup=30 p50=%.4f p95=%.4f max=%.4f units=ms scope=painter_cpu_only fps_claim=none weapon_renderer=excluded gpu=excluded world=excluded variant=%s" % [p50, p95, maximum, _variant_label])
	quit(0 if success and drained else 1)

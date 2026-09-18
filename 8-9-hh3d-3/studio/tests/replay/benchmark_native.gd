@tool
extends EditorPlugin
## Disposable native fixture only: direct accepted semantic adapter operations.
## Fixed benchmark fixture; native diagnostics do not imply full acceptance.
## This is not the public/API command benchmark and grants no publication ACK.
## Copy with benchmark_plugin.cfg to res://addons/hh_benchmark/; enable beside
## unchanged hh_studio. Import with HH_BENCHMARK_MODE unset. Activate using
## HH_BENCHMARK_MODE=full (35x100) or diagnostic (1x1, never benchmark evidence).
## The isolated owned runner instead passes exactly one user argument after --:
## --hh-benchmark-mode=diagnostic (or full). Never activate import. Environment
## plus argument, duplicate argument or unknown --hh-benchmark* flag is rejected.
## Fixed input: res://benchmark/input.json; new empty res://benchmark/out/.
## Input schema 1.2.0 has exactly schema_id, schema_version, run_id, mode,
## source_closure_sha256, profile_sha256, batch_barrier, batch_start. Full requires
## batch_barrier="host_ack_v1" and an initially empty res://benchmark/input/;
## batch_start="host_permit_v1". Diagnostic uses batch_barrier="diagnostic_none"
## and batch_start="diagnostic_immediate", and never claims host integration.
## Sequential full batch: ready -> host1000 commands -> start permit -> native100
## cycles -> quiescent batch -> joint host sample -> ACK -> next ready.
## Ready artifact benchmark/out/ready-XX.json has native issued/deadline (+600s),
## root/generation/baseline and fixed input binding. HH_GT06_BENCHMARK_READY emits
## its exact SHA. Start permit is atomically published at benchmark/input/start-XX.json
## with exactly schema_id="hh-studio.native-cycle-batch-start", schema_version=
## "1.0.0", run_id, batch_index, source_closure_sha256, profile_sha256,
## command_batch_sha256, ready_sha256, deadline_mono_us. Echo native deadline;
## command_batch_sha256 binds completed host command bytes for external assembly.
## This receipt does not independently verify the host commands' correctness.
## Full mode publishes batch-XX.json, then waits without starting another cycle.
## The host samples that batch and atomically publishes benchmark/input/ack-XX.json
## (temporary file plus rename). The ACK has exactly schema_id=
## "hh-studio.native-cycle-batch-ack", schema_version="1.0.0", run_id,
## batch_index, native_batch_sha256, source_closure_sha256, profile_sha256,
## deadline_mono_us. Hashes are lowercase bare SHA256. The batch hash covers exact
## batch file bytes. Echo the batch barrier's native-clock deadline unchanged;
## never compare it with a host monotonic clock or extend it. No arbitrary path
## is accepted. Wrong, stale, late, oversized or altered ACKs fail closed.
## Completion requires the final ACK. Retained ACK receipts attest only this
## synchronization barrier, not correctness of the separately measured host work.
## Pinned save_scene() can return OK before durable save proof, so require the
## actual scene_saved signal plus disk hash and later semantic reload readback.
## https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_interface.cpp
## https://docs.godotengine.org/en/stable/classes/class_editorplugin.html#signals
## Object/resource monitors are direct ObjectDB/ResourceCache counts in this pin:
## https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/main/performance.cpp

const Adapter = preload("res://addons/hh_studio/plugin.gd")
const SCENE: String = "res://scenes/fixture.tscn"
const INPUT: String = "res://benchmark/input.json"
const EVIDENCE_IGNORE: String = "res://benchmark/.gdignore"
const ACK_DIRECTORY: String = "res://benchmark/input"
const OUTPUT: String = "res://benchmark/out"
const FULL_BATCHES: int = 35
const FULL_CYCLES: int = 100
const WARMUP_BATCHES: int = 5
const PHASE_TIMEOUT_US: int = 15000000
const BATCH_TIMEOUT_US: int = 180000000
const HOST_BARRIER_TIMEOUT_US: int = 30000000
const HOST_START_TIMEOUT_US: int = 600000000
## Aggregate hard limit stays unchanged. It can expire before all worst-case
## per-phase waits: 35*(600+180+30)=28350s does not fit within 7410s.
const RUN_TIMEOUT_US: int = 7410000000
const SETTLE_FRAMES: int = 4
const SETTLE_US: int = 1100000
const HEARTBEAT_US: int = 500000
const MAX_BATCH_BYTES: int = 1048576
const SOURCE_PATHS: Array[String] = ["res://addons/hh_studio/plugin.gd",
    "res://addons/hh_studio/scene_commands.gd", "res://addons/hh_studio/jcs_godot.gd",
    "res://addons/hh_studio/plugin.cfg", "res://scripts/fixture_actor.gd",
    "res://addons/hh_benchmark/benchmark_native.gd", "res://addons/hh_benchmark/plugin.cfg",
    "res://project.godot", INPUT, EVIDENCE_IGNORE]

enum Phase { INACTIVE, INITIALIZE, HOST_START, CYCLE_BEGIN, CREATE, UNDO, SAVE, SAVE_WAIT,
    RELOAD, RELOAD_WAIT, CYCLE_SETTLE, BATCH_SETTLE, BATCH_WRITE, HOST_BARRIER, FINISHED }

var _phase: Phase = Phase.INACTIVE
var _phase_started_us: int = 0
var _run_started_us: int = 0
var _run_started_unix: float = 0.0
var _batch_started_us: int = 0
var _batch: int = 0
var _cycle: int = 0
var _batch_limit: int = FULL_BATCHES
var _cycle_limit: int = FULL_CYCLES
var _mode: String = ""
var _activation_invalid: bool = false
var _input: Dictionary = {}
var _source_hashes: Dictionary = {}
var _adapter: Adapter
var _baseline_revision: String = ""
var _last_root_id: int = 0
var _before: Dictionary = {}
var _row: Dictionary = {}
var _timing: Dictionary = {}
var _cycles: Array[Dictionary] = []
var _raw_timings: Array[Dictionary] = []
var _batches: Array[Dictionary] = []
var _barrier: Dictionary = {}
var _pending_batch_sha256: String = ""
var _barrier_receipts: Array[Dictionary] = []
var _start_offer: Dictionary = {}
var _start_offer_sha256: String = ""
var _start_receipt: Dictionary = {}
var _start_receipts: Array[Dictionary] = []
var _adapter_ready_count: int = 0
var _reload_ready_before: int = 0
var _save_signal_count: int = 0
var _save_signal_before: int = 0
var _save_signal_us: int = 0
var _settle_start_us: int = 0
var _settle_start_frame: int = 0
var _last_heartbeat_us: int = 0
var _max_status_gap_us: int = 0
var _batch_status_gap_us: int = 0
var _startup_settle_frame: int = -1
var _startup_settle_us: int = 0
var _startup_owners: Dictionary = {}
var _startup_readiness: Dictionary = {}
var _startup_dispatching: bool = false
var _startup_dispatch_count: int = 0
var _startup_notification_count: int = 0
var _failed: bool = false


func _notification(what: int) -> void:
    if _startup_dispatching and what == NOTIFICATION_APPLICATION_FOCUS_IN:
        _startup_notification_count += 1


func _enter_tree() -> void:
    _mode = OS.get_environment("HH_BENCHMARK_MODE")
    OS.unset_environment("HH_BENCHMARK_MODE")
    for argument: String in OS.get_cmdline_user_args():
        if not argument.begins_with("--hh-benchmark"):
            continue
        if not argument.begins_with("--hh-benchmark-mode=") or not _mode.is_empty():
            _activation_invalid = true
        else:
            _mode = argument.trim_prefix("--hh-benchmark-mode=")
            if _mode not in ["full", "diagnostic"]:
                _activation_invalid = true
    if _mode.is_empty() and not _activation_invalid:
        set_process(false)
        return
    _run_started_us = Time.get_ticks_usec()
    _run_started_unix = Time.get_unix_time_from_system()
    scene_saved.connect(_on_scene_saved)
    call_deferred("_boot")


func _exit_tree() -> void:
    if scene_saved.is_connected(_on_scene_saved):
        scene_saved.disconnect(_on_scene_saved)
    if is_instance_valid(_adapter) and _adapter.adapter_ready.is_connected(_on_adapter_ready):
        _adapter.adapter_ready.disconnect(_on_adapter_ready)
    _adapter = null


func _boot() -> void:
    if _activation_invalid:
        _fail("BENCHMARK_ACTIVATION_ARGUMENTS")
        return
    if not Engine.is_editor_hint() or not _main_thread() or _mode not in ["full", "diagnostic"]:
        _fail("BENCHMARK_CONTEXT")
        return
    # get_setting() resolves the frozen project override; Object.get() does not.
    # This bounds displayed paragraphs only; raw ObjectDB/RSS checks stay intact.
    var editor_settings: EditorSettings = EditorInterface.get_editor_settings()
    if editor_settings == null:
        _fail("BENCHMARK_OUTPUT_LOG_LIMIT")
        return
    var output_limit: Variant = editor_settings.get_setting("run/output/max_lines")
    if not output_limit is int or output_limit != 100:
        _fail("BENCHMARK_OUTPUT_LOG_LIMIT")
        return
    # Require explicit frozen project keys as well as effective values. Defaults
    # alone would let a missing focused key pass because its stock value is 6900.
    var expected_editor_settings: Dictionary = {
        "interface/editor/display/update_continuously": false,
        "interface/editor/timers/low_processor_mode_sleep_usec": 6900,
        "interface/editor/timers/unfocused_low_processor_mode_sleep_usec": 6900,
        "run/output/max_lines": 100}
    var project_config := ConfigFile.new()
    if project_config.load("res://project.godot") != OK or not project_config.has_section("editor_overrides"):
        _fail("BENCHMARK_EDITOR_CADENCE")
        return
    if project_config.get_section_keys("editor_overrides").size() != expected_editor_settings.size():
        _fail("BENCHMARK_EDITOR_CADENCE")
        return
    var editor_readback: Dictionary = {}
    for setting: String in expected_editor_settings:
        if not project_config.has_section_key("editor_overrides", setting):
            _fail("BENCHMARK_EDITOR_CADENCE")
            return
        var expected_value: Variant = expected_editor_settings[setting]
        var configured_value: Variant = project_config.get_value("editor_overrides", setting)
        var effective_value: Variant = editor_settings.get_setting(setting)
        if typeof(configured_value) != typeof(expected_value) or configured_value != expected_value or typeof(effective_value) != typeof(expected_value) or effective_value != expected_value:
            _fail("BENCHMARK_EDITOR_CADENCE")
            return
        editor_readback[setting] = effective_value
    if not FileAccess.file_exists(EVIDENCE_IGNORE) or FileAccess.get_file_as_bytes(EVIDENCE_IGNORE) != "# HH Studio benchmark evidence is not a Godot asset.\n".to_utf8_buffer():
        _fail("BENCHMARK_EVIDENCE_IGNORE")
        return
    var input_file: FileAccess = FileAccess.open(INPUT, FileAccess.READ)
    if input_file == null:
        _fail("BENCHMARK_INPUT_MISSING")
        return
    var size: int = input_file.get_length()
    if size < 1 or size > 8192:
        input_file.close()
        _fail("BENCHMARK_INPUT_SIZE")
        return
    var decoded: Variant = JSON.parse_string(input_file.get_as_text())
    input_file.close()
    if not decoded is Dictionary:
        _fail("BENCHMARK_INPUT_JSON")
        return
    _input = decoded
    var fields: Array[String] = ["schema_id", "schema_version", "run_id", "mode", "source_closure_sha256", "profile_sha256", "batch_barrier", "batch_start"]
    if _input.size() != fields.size() or not _input.has_all(fields):
        _fail("BENCHMARK_INPUT_FIELDS")
        return
    if _input.schema_id != "hh-studio.native-cycle-benchmark-run" or _input.schema_version != "1.2.0" or _input.mode != _mode:
        _fail("BENCHMARK_INPUT_BINDING")
        return
    if not _identifier(_input.run_id) or not _hex(_input.source_closure_sha256) or not _hex(_input.profile_sha256):
        _fail("BENCHMARK_INPUT_VALUE")
        return
    var expected_barrier: String = "host_ack_v1" if _mode == "full" else "diagnostic_none"
    if _input.batch_barrier != expected_barrier:
        _fail("BENCHMARK_INPUT_BARRIER")
        return
    var expected_start: String = "host_permit_v1" if _mode == "full" else "diagnostic_immediate"
    if _input.batch_start != expected_start:
        _fail("BENCHMARK_INPUT_START")
        return
    if _mode == "full":
        var ack_directory: DirAccess = DirAccess.open(ACK_DIRECTORY)
        if ack_directory == null or not ack_directory.get_files().is_empty() or not ack_directory.get_directories().is_empty():
            _fail("BENCHMARK_ACK_DIRECTORY_NOT_EMPTY")
            return
    var output_dir: DirAccess = DirAccess.open(OUTPUT)
    if output_dir == null or not output_dir.get_files().is_empty() or not output_dir.get_directories().is_empty():
        _fail("BENCHMARK_OUTPUT_NOT_EMPTY")
        return
    for path: String in SOURCE_PATHS:
        var digest: String = FileAccess.get_sha256(path)
        if not _hex(digest):
            _fail("BENCHMARK_SOURCE_MISSING")
            return
        _source_hashes[path] = digest
    # Supplemental native readback, bound to this already-validated input. This
    # adds no file or source path and does not change batch/index/profile schemas.
    print("HH_GT06_BENCHMARK_CADENCE " + JSON.stringify({"run_id": _input.run_id,
        "pid": OS.get_process_id(), "source_closure_sha256": _input.source_closure_sha256,
        "profile_sha256": _input.profile_sha256, "settings": editor_readback,
        "os_low_processor_usage_mode": OS.low_processor_usage_mode,
        "os_low_processor_usage_mode_sleep_usec": OS.low_processor_usage_mode_sleep_usec}))
    if _mode == "diagnostic":
        _batch_limit = 1
        _cycle_limit = 1
    _set_phase(Phase.INITIALIZE)
    _heartbeat(true)
    set_process(true)


func _process(_delta: float) -> void:
    if _phase in [Phase.INACTIVE, Phase.FINISHED] or _failed:
        return
    if not _main_thread():
        _fail("BENCHMARK_MAIN_THREAD")
        return
    var now: int = Time.get_ticks_usec()
    _heartbeat()
    if now - _run_started_us > RUN_TIMEOUT_US:
        _fail("BENCHMARK_RUN_TIMEOUT")
        return
    if _phase not in [Phase.HOST_START, Phase.HOST_BARRIER] and now - _phase_started_us > PHASE_TIMEOUT_US:
        _fail("BENCHMARK_PHASE_TIMEOUT")
        return
    if _phase not in [Phase.HOST_START, Phase.HOST_BARRIER] and _batch_started_us > 0 and now - _batch_started_us > BATCH_TIMEOUT_US:
        _fail("BENCHMARK_BATCH_TIMEOUT")
        return
    match _phase:
        Phase.INITIALIZE:
            _initialize()
        Phase.HOST_START:
            _wait_host_start()
        Phase.CYCLE_BEGIN:
            _begin_cycle()
        Phase.CREATE:
            _create()
        Phase.UNDO:
            _undo()
        Phase.SAVE:
            _save()
        Phase.SAVE_WAIT:
            _wait_save()
        Phase.RELOAD:
            _reload()
        Phase.RELOAD_WAIT:
            _wait_reload()
        Phase.CYCLE_SETTLE:
            _settle_cycle()
        Phase.BATCH_SETTLE:
            _settle_batch()
        Phase.BATCH_WRITE:
            _write_batch()
        Phase.HOST_BARRIER:
            _wait_host_ack()


func _initialize() -> void:
    if _adapter == null:
        _adapter = _find_adapter()
        if _adapter == null:
            return
        if _adapter.get("_ipc") != null:
            _fail("BENCHMARK_ACTIVE_IPC_FORBIDDEN")
            return
        _adapter.adapter_ready.connect(_on_adapter_ready)
    var snapshot: Dictionary = _adapter.inspect_scene()
    if not snapshot.get("ok", false):
        return
    var root: Node = EditorInterface.get_edited_scene_root()
    if root == null or root.scene_file_path != SCENE or snapshot.get("held", true):
        _fail("BENCHMARK_APPROVED_ROOT")
        return
    if _startup_settle_frame < 0:
        _baseline_revision = str(snapshot.revision)
        if not _startup_begin(snapshot, root):
            return
        _startup_settle_frame = Engine.get_process_frames()
        _startup_settle_us = Time.get_ticks_usec()
        return
    if Engine.get_process_frames() < _startup_settle_frame + SETTLE_FRAMES or Time.get_ticks_usec() - _startup_settle_us < SETTLE_US:
        return
    if str(snapshot.revision) != _baseline_revision or not _revision(_baseline_revision):
        _fail("BENCHMARK_INITIAL_STATE_CHANGED")
        return
    var settled: Dictionary = _startup_snapshot(snapshot, root, true)
    if _failed:
        return
    if settled.roots != _startup_readiness.immediate.roots:
        _fail("BENCHMARK_STARTUP_ROOTS_UNSETTLED")
        return
    _startup_readiness["settled"] = settled
    _last_root_id = root.get_instance_id()
    _begin_batch()


func _startup_callback(dialog: ConfirmationDialog) -> Dictionary:
    var found: Dictionary = {}
    var connections: Array[Dictionary] = dialog.get_signal_connection_list("confirmed")
    if connections.size() > 16:
        _fail("BENCHMARK_STARTUP_CALLBACK_CAP")
        return {}
    for connection: Dictionary in connections:
        var callback: Callable = connection["callable"]
        var target: Object = callback.get_object()
        if not is_instance_valid(target):
            continue
        var method: String = str(callback.get_method())
        method = method.get_slice("::", method.get_slice_count("::") - 1)
        var role: String = ""
        if target.get_class() == "EditorNode" and method == "_reload_modified_scenes":
            role = "editor_disk_changes"
        elif target.get_class() == "ScriptEditor" and method == "reload_scripts":
            role = "script_disk_changes"
        if role.is_empty():
            continue
        if not found.is_empty():
            _fail("BENCHMARK_STARTUP_CALLBACK_AMBIGUOUS")
            return {}
        found = {"role": role, "callback_target_id": str(callback.get_object_id()),
            "callback_target_class": target.get_class(), "callback_method": method}
    return found


func _startup_discover() -> void:
    var pending: Array[Node] = [get_tree().root]
    var visited: int = 0
    while not pending.is_empty() and not _failed:
        var node: Node = pending.pop_back()
        visited += 1
        if visited > 50000:
            _fail("BENCHMARK_STARTUP_NODE_CAP")
            return
        if node is ConfirmationDialog:
            var owner: Dictionary = _startup_callback(node as ConfirmationDialog)
            if not owner.is_empty():
                var role: String = str(owner.role)
                if _startup_owners.has(role):
                    _fail("BENCHMARK_STARTUP_OWNER_AMBIGUOUS")
                    return
                var descendants: Array[Node] = node.get_children(true)
                var tree_id: String = ""
                while not descendants.is_empty():
                    var child: Node = descendants.pop_back()
                    visited += 1
                    if visited > 50000:
                        _fail("BENCHMARK_STARTUP_NODE_CAP")
                        return
                    if child is Tree:
                        if not tree_id.is_empty():
                            _fail("BENCHMARK_STARTUP_TREE_AMBIGUOUS")
                            return
                        tree_id = str(child.get_instance_id())
                    descendants.append_array(child.get_children(true))
                if tree_id.is_empty():
                    _fail("BENCHMARK_STARTUP_TREE_MISSING")
                    return
                owner.erase("role")
                owner["dialog_id"] = str(node.get_instance_id())
                owner["tree_id"] = tree_id
                _startup_owners[role] = owner
        pending.append_array(node.get_children(true))
    if _startup_owners.size() != 2 or not _startup_owners.has_all(["editor_disk_changes", "script_disk_changes"]):
        _fail("BENCHMARK_STARTUP_OWNERS_MISSING")


func _startup_snapshot(snapshot: Dictionary, root: Node, require_roots: bool) -> Dictionary:
    if not _good_snapshot(snapshot) or root == null or root.scene_file_path != SCENE or snapshot.revision != _baseline_revision:
        _fail("BENCHMARK_STARTUP_SCENE_DRIFT")
        return {}
    var point: Dictionary = {"mono_us": Time.get_ticks_usec(), "frame": Engine.get_process_frames(),
        "scene_root_id": str(root.get_instance_id()), "scene_revision": str(snapshot.revision),
        "scene_file_sha256": FileAccess.get_sha256(SCENE), "source_files": {}, "roots": {}}
    if not _hex(point.scene_file_sha256):
        _fail("BENCHMARK_STARTUP_SCENE_HASH")
        return {}
    if _startup_readiness.has("before"):
        for key: String in ["scene_root_id", "scene_revision", "scene_file_sha256"]:
            if point[key] != _startup_readiness.before[key]:
                _fail("BENCHMARK_STARTUP_SCENE_DRIFT")
                return {}
    for path: String in SOURCE_PATHS:
        var digest: String = FileAccess.get_sha256(path)
        if digest != _source_hashes[path]:
            _fail("BENCHMARK_STARTUP_SOURCE_DRIFT")
            return {}
        point.source_files[path] = digest
    for role: String in ["editor_disk_changes", "script_disk_changes"]:
        var owner: Dictionary = _startup_owners[role]
        var dialog: ConfirmationDialog = instance_from_id(int(owner.dialog_id)) as ConfirmationDialog
        var tree: Tree = instance_from_id(int(owner.tree_id)) as Tree
        if not is_instance_valid(dialog) or not is_instance_valid(tree) or not dialog.is_ancestor_of(tree):
            _fail("BENCHMARK_STARTUP_OWNER_LOST")
            return {}
        var callback: Dictionary = _startup_callback(dialog)
        var expected: Dictionary = owner.duplicate()
        expected.erase("dialog_id")
        expected.erase("tree_id")
        expected["role"] = role
        if _failed or callback != expected:
            _fail("BENCHMARK_STARTUP_CALLBACK_DRIFT")
            return {}
        var item: TreeItem = tree.get_root()
        if dialog.visible or tree.columns != 1 or (require_roots and item == null):
            _fail("BENCHMARK_STARTUP_BLANK_ROOT_REQUIRED")
            return {}
        if item != null and (item.get_parent() != null or item.get_first_child() != null or not item.get_text(0).is_empty()):
            _fail("BENCHMARK_STARTUP_BLANK_ROOT_REQUIRED")
            return {}
        point.roots[role] = {"root_id": str(item.get_instance_id()) if item != null else "",
            "columns": tree.columns, "child_count": 0, "text": "", "dialog_visible": dialog.visible}
    return point


func _startup_begin(snapshot: Dictionary, root: Node) -> bool:
    if _startup_dispatch_count != 0 or not _startup_readiness.is_empty():
        _fail("BENCHMARK_STARTUP_DUPLICATE_DISPATCH")
        return false
    _startup_discover()
    if _failed:
        return false
    var before: Dictionary = _startup_snapshot(snapshot, root, false)
    if _failed:
        return false
    _startup_readiness = {"schema_id": "hh-studio.native-startup-readiness", "schema_version": "1.0.0",
        "run_id": _input.run_id, "pid": OS.get_process_id(), "source_closure_sha256": _input.source_closure_sha256,
        "synthetic": true, "notification": NOTIFICATION_APPLICATION_FOCUS_IN,
        "operation": "SceneTree.root.propagate_notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)",
        "minimum_settle_frames": SETTLE_FRAMES, "minimum_settle_us": SETTLE_US,
        "owners": _startup_owners.duplicate(true), "before": before}
    # Explicit synthetic startup stimulus; never OS focus manipulation or private Tree mutation.
    _startup_dispatch_count += 1
    _startup_dispatching = true
    get_tree().root.propagate_notification(NOTIFICATION_APPLICATION_FOCUS_IN)
    _startup_dispatching = false
    if _startup_notification_count != 1:
        _fail("BENCHMARK_STARTUP_NOTIFICATION_READBACK")
        return false
    _startup_readiness["dispatch_count"] = _startup_dispatch_count
    _startup_readiness["observed_dispatch_count"] = _startup_notification_count
    _startup_readiness["immediate"] = _startup_snapshot(_adapter.inspect_scene(), EditorInterface.get_edited_scene_root(), true)
    return not _failed


func _find_adapter() -> Adapter:
    var pending: Array[Node] = [get_tree().root]
    var visited: int = 0
    while not pending.is_empty() and visited < 20000:
        var node: Node = pending.pop_back()
        visited += 1
        if node.get_script() == Adapter:
            return node as Adapter
        for child: Node in node.get_children(true):
            pending.append(child)
    return null


func _begin_batch() -> void:
    _cycle = 0
    _cycles = []
    _raw_timings = []
    _batch_status_gap_us = 0
    _batch_started_us = 0
    _start_offer = {}
    _start_offer_sha256 = ""
    _start_receipt = {}
    if _mode != "full":
        _start_native_batch()
        return
    var snapshot: Dictionary = _adapter.inspect_scene()
    var root: Node = EditorInterface.get_edited_scene_root()
    var scene_hash: String = FileAccess.get_sha256(SCENE)
    if not _good_snapshot(snapshot) or snapshot.revision != _baseline_revision or root == null or root.get_instance_id() != _last_root_id or not _hex(scene_hash):
        _fail("BENCHMARK_READY_DRIFT")
        return
    var issued: int = Time.get_ticks_usec()
    _start_offer = {"schema_id": "hh-studio.native-cycle-batch-ready", "schema_version": "1.0.0",
        "run_id": _input.run_id, "pid": OS.get_process_id(), "batch_index": _batch,
        "source_closure_sha256": _input.source_closure_sha256, "profile_sha256": _input.profile_sha256,
        "start_file": "benchmark/input/start-%02d.json" % _batch,
        "issued_mono_us": issued, "deadline_mono_us": issued + HOST_START_TIMEOUT_US,
        "root_instance_id": root.get_instance_id(), "generation": int(snapshot.generation),
        "baseline_sha256": _bare(_baseline_revision), "scene_file_sha256": scene_hash,
        "process_frame": Engine.get_process_frames()}
    var written: Dictionary = _write_new("ready-%02d.json" % _batch, _start_offer)
    if written.is_empty():
        _fail("BENCHMARK_READY_WRITE")
        return
    _start_offer_sha256 = str(written.sha256)
    _set_phase(Phase.HOST_START)
    _heartbeat(true)
    print("HH_GT06_BENCHMARK_READY " + JSON.stringify({"run_id": _input.run_id, "pid": OS.get_process_id(),
        "index": _batch, "sha256": written.sha256, "size_bytes": written.size_bytes,
        "deadline_mono_us": _start_offer.deadline_mono_us}))


func _wait_host_start() -> void:
    if Time.get_ticks_usec() > int(_start_offer.deadline_mono_us):
        _fail("BENCHMARK_HOST_START_TIMEOUT")
        return
    var root: Node = EditorInterface.get_edited_scene_root()
    if root == null or root.get_instance_id() != int(_start_offer.root_instance_id) or int(_adapter.get("_generation")) != int(_start_offer.generation):
        _fail("BENCHMARK_HOST_START_DRIFT")
        return
    var path: String = ACK_DIRECTORY.path_join("start-%02d.json" % _batch)
    if not FileAccess.file_exists(path):
        return
    var file: FileAccess = FileAccess.open(path, FileAccess.READ)
    if file == null:
        _fail("BENCHMARK_HOST_START_READ")
        return
    var size: int = file.get_length()
    if size < 1 or size > 8192:
        file.close()
        _fail("BENCHMARK_HOST_START_SIZE")
        return
    var raw: PackedByteArray = file.get_buffer(size)
    file.close()
    if raw.size() != size:
        _fail("BENCHMARK_HOST_START_READ")
        return
    var decoded: Variant = JSON.parse_string(raw.get_string_from_utf8())
    if not decoded is Dictionary:
        _fail("BENCHMARK_HOST_START_JSON")
        return
    var permit: Dictionary = decoded
    var fields: Array[String] = ["schema_id", "schema_version", "run_id", "batch_index",
        "source_closure_sha256", "profile_sha256", "command_batch_sha256", "ready_sha256", "deadline_mono_us"]
    if permit.size() != fields.size() or not permit.has_all(fields):
        _fail("BENCHMARK_HOST_START_FIELDS")
        return
    if permit.schema_id != "hh-studio.native-cycle-batch-start" or permit.schema_version != "1.0.0" or permit.run_id != _input.run_id:
        _fail("BENCHMARK_HOST_START_BINDING")
        return
    if not _json_integer(permit.batch_index) or int(permit.batch_index) != _batch or not _json_integer(permit.deadline_mono_us) or int(permit.deadline_mono_us) != int(_start_offer.deadline_mono_us):
        _fail("BENCHMARK_HOST_START_POSITION")
        return
    if permit.ready_sha256 != _start_offer_sha256 or permit.source_closure_sha256 != _input.source_closure_sha256 or permit.profile_sha256 != _input.profile_sha256 or not _hex(permit.command_batch_sha256):
        _fail("BENCHMARK_HOST_START_HASH")
        return
    var snapshot: Dictionary = _adapter.inspect_scene()
    if not _good_snapshot(snapshot) or snapshot.revision != _baseline_revision or int(snapshot.generation) != int(_start_offer.generation) or FileAccess.get_sha256(SCENE) != _start_offer.scene_file_sha256:
        _fail("BENCHMARK_HOST_START_POSTCONDITION")
        return
    var digest: String = _bytes_sha256(raw)
    if FileAccess.get_sha256(path) != digest or FileAccess.get_sha256(OUTPUT.path_join("ready-%02d.json" % _batch)) != _start_offer_sha256:
        _fail("BENCHMARK_HOST_START_CHANGED")
        return
    var observed: int = Time.get_ticks_usec()
    if observed > int(_start_offer.deadline_mono_us):
        _fail("BENCHMARK_HOST_START_TIMEOUT")
        return
    _heartbeat(true)
    _start_receipt = {"batch_index": _batch, "start_file": _start_offer.start_file,
        "start_sha256": digest, "start_size_bytes": size,
        "ready_file": "benchmark/out/ready-%02d.json" % _batch, "ready_sha256": _start_offer_sha256,
        "command_batch_sha256": permit.command_batch_sha256,
        "issued_mono_us": _start_offer.issued_mono_us, "deadline_mono_us": _start_offer.deadline_mono_us,
        "start_observed_mono_us": observed, "process_frame": Engine.get_process_frames(),
        "root_instance_id": root.get_instance_id(), "generation": int(snapshot.generation),
        "semantic_sha256": _bare(str(snapshot.revision)), "max_status_gap_ms": float(_batch_status_gap_us) / 1000.0}
    _start_receipts.append(_start_receipt)
    print("HH_GT06_BENCHMARK_START " + JSON.stringify(_start_receipt))
    _start_native_batch()


func _start_native_batch() -> void:
    _batch_started_us = Time.get_ticks_usec()
    _set_phase(Phase.CYCLE_BEGIN)
    _heartbeat(true)


func _begin_cycle() -> void:
    _before = _adapter.inspect_scene()
    var root: Node = EditorInterface.get_edited_scene_root()
    if not _good_snapshot(_before) or root == null or root.get_instance_id() != _last_root_id or str(_before.revision) != _baseline_revision:
        _fail("BENCHMARK_CYCLE_BASELINE")
        return
    _row = {"index": _cycle, "root_before": _last_root_id, "root_after": 0,
        "before_sha256": _bare(str(_before.revision)), "created_sha256": "", "undone_sha256": "",
        "saved_file_sha256": "", "reloaded_sha256": "", "latency_ms": {},
        "effects": {"create": 1, "undo": 1, "save": 1, "reload": 1}, "main_thread": true}
    _timing = {"index": _cycle, "generation_before": int(_before.generation), "generation_after": 0}
    _set_phase(Phase.CREATE)


func _projection(operation: String, snapshot: Dictionary, payload: Dictionary) -> Dictionary:
    return {"operation": operation,
        "command_id": "benchmark." + str(_input.run_id).sha256_text().substr(0, 12) + ".b" + str(_batch) + ".c" + str(_cycle) + "." + operation.get_slice(".", operation.get_slice_count(".") - 1),
        "expected_generation": int(snapshot.generation), "expected_revision": str(snapshot.revision),
        "target_stable_id": "root", "payload": payload}


func _create() -> void:
    var start: int = Time.get_ticks_usec()
    var projection: Dictionary = _projection("scene.node.create", _before,
        {"expected_generation": int(_before.generation), "stable_id": "benchmark.native-node",
        "node_type": "MeshInstance3D", "name": "BenchmarkNativeNode", "position": [1.0, 0.0, 0.0],
        "rotation_degrees": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0], "box_size": [1.0, 1.0, 1.0]})
    var result: Dictionary = _adapter.apply_projection(projection)
    var after: Dictionary = _adapter.inspect_scene()
    if not result.get("ok", false) or not _good_snapshot(after) or str(after.revision) == str(_before.revision) or int(after.total) != int(_before.total) + 1 or after.revision != result.get("revision"):
        _fail("BENCHMARK_CREATE_READBACK")
        return
    _row.created_sha256 = _bare(str(after.revision))
    _record_time("create", start, Time.get_ticks_usec())
    _set_phase(Phase.UNDO)


func _undo() -> void:
    var before: Dictionary = _adapter.inspect_scene()
    if not _good_snapshot(before) or _bare(str(before.revision)) != _row.created_sha256:
        _fail("BENCHMARK_UNDO_PRECONDITION")
        return
    var start: int = Time.get_ticks_usec()
    var result: Dictionary = _adapter.apply_projection(_projection("scene.undo", before,
        {"expected_generation": int(before.generation), "steps": 1}))
    var after: Dictionary = _adapter.inspect_scene()
    if not result.get("ok", false) or not _good_snapshot(after) or str(after.revision) != _baseline_revision or int(after.total) != int(_before.total) or after.revision != result.get("revision"):
        _fail("BENCHMARK_UNDO_READBACK")
        return
    _row.undone_sha256 = _bare(str(after.revision))
    _record_time("undo", start, Time.get_ticks_usec())
    _set_phase(Phase.SAVE)


func _save() -> void:
    _save_signal_before = _save_signal_count
    _save_signal_us = 0
    _timing["save"] = {"start_us": Time.get_ticks_usec(), "end_us": 0}
    _set_phase(Phase.SAVE_WAIT)
    var result: Error = EditorInterface.save_scene()
    if result != OK:
        _fail("BENCHMARK_SAVE_CALL")


func _on_scene_saved(path: String) -> void:
    if _phase == Phase.INACTIVE or _phase == Phase.FINISHED:
        return
    if path != SCENE or _phase != Phase.SAVE_WAIT:
        _fail("BENCHMARK_UNEXPECTED_SAVE")
        return
    _save_signal_count += 1
    _save_signal_us = Time.get_ticks_usec()


func _wait_save() -> void:
    if _save_signal_count == _save_signal_before:
        return
    var snapshot: Dictionary = _adapter.inspect_scene()
    var digest: String = FileAccess.get_sha256(SCENE)
    if _save_signal_count != _save_signal_before + 1 or not _good_snapshot(snapshot) or snapshot.revision != _baseline_revision or not _hex(digest):
        _fail("BENCHMARK_SAVE_READBACK")
        return
    _row.saved_file_sha256 = digest
    _timing.save_signal_mono_us = _save_signal_us
    _record_time("save", int(_timing.save.start_us), Time.get_ticks_usec())
    _set_phase(Phase.RELOAD)


func _reload() -> void:
    _reload_ready_before = _adapter_ready_count
    _timing["reload"] = {"start_us": Time.get_ticks_usec(), "end_us": 0}
    _set_phase(Phase.RELOAD_WAIT)
    EditorInterface.reload_scene_from_path(SCENE)


func _on_adapter_ready(_snapshot: Dictionary) -> void:
    _adapter_ready_count += 1


func _wait_reload() -> void:
    var root: Node = EditorInterface.get_edited_scene_root()
    if root == null or root.get_instance_id() == int(_row.root_before) or _adapter_ready_count <= _reload_ready_before:
        return
    var after: Dictionary = _adapter.inspect_scene()
    if not _good_snapshot(after):
        return
    if int(after.generation) != int(_before.generation) + 1 or after.revision != _baseline_revision or FileAccess.get_sha256(SCENE) != _row.saved_file_sha256:
        _fail("BENCHMARK_RELOAD_READBACK")
        return
    _row.root_after = root.get_instance_id()
    _row.reloaded_sha256 = _bare(str(after.revision))
    _timing.generation_after = int(after.generation)
    _timing.reload_observed_process_frame = Engine.get_process_frames()
    _record_time("reload", int(_timing.reload.start_us), Time.get_ticks_usec())
    _last_root_id = int(_row.root_after)
    _settle_start_frame = Engine.get_process_frames()
    _set_phase(Phase.CYCLE_SETTLE)


func _settle_cycle() -> void:
    if Engine.get_process_frames() < _settle_start_frame + 1:
        return
    var snapshot: Dictionary = _adapter.inspect_scene()
    if not _good_snapshot(snapshot) or snapshot.revision != _baseline_revision:
        _fail("BENCHMARK_POST_RELOAD_DRIFT")
        return
    _cycles.append(_row)
    _raw_timings.append(_timing)
    _row = {}
    _timing = {}
    _before = {}
    _cycle += 1
    if _cycle < _cycle_limit:
        _set_phase(Phase.CYCLE_BEGIN)
    else:
        _settle_start_us = Time.get_ticks_usec()
        _settle_start_frame = Engine.get_process_frames()
        _set_phase(Phase.BATCH_SETTLE)


func _settle_batch() -> void:
    if Engine.get_process_frames() < _settle_start_frame + SETTLE_FRAMES or Time.get_ticks_usec() - _settle_start_us < SETTLE_US:
        return
    var snapshot: Dictionary = _adapter.inspect_scene()
    if not _good_snapshot(snapshot) or snapshot.revision != _baseline_revision:
        _fail("BENCHMARK_QUIESCENT_DRIFT")
        return
    _set_phase(Phase.BATCH_WRITE)


func _write_batch() -> void:
    var ended: int = Time.get_ticks_usec()
    _heartbeat(true)
    var snapshot: Dictionary = _adapter.inspect_scene()
    var root: Node = EditorInterface.get_edited_scene_root()
    if not _good_snapshot(snapshot) or snapshot.revision != _baseline_revision or root == null or root.get_instance_id() != _last_root_id:
        _fail("BENCHMARK_BATCH_WRITE_DRIFT")
        return
    _barrier = {"mode": _input.batch_barrier, "required": _mode == "full"}
    if _mode == "full":
        _barrier.merge({"ack_file": "benchmark/input/ack-%02d.json" % _batch,
            "issued_mono_us": ended, "deadline_mono_us": ended + HOST_BARRIER_TIMEOUT_US,
            "root_instance_id": _last_root_id, "generation": int(snapshot.generation),
            "baseline_sha256": _bare(_baseline_revision)})
    var objects: float = Performance.get_monitor(Performance.OBJECT_COUNT)
    var resources: float = Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)
    if not is_finite(objects) or not is_finite(resources) or objects < 1.0 or resources < 0.0 or objects != floor(objects) or resources != floor(resources):
        _fail("BENCHMARK_COUNTER_READBACK")
        return
    var memory: Dictionary = {"phase": "post_batch_quiescent", "monotonic_us": ended,
        "process_frame": Engine.get_process_frames(), "settle_frames": Engine.get_process_frames() - _settle_start_frame,
        "settle_us": ended - _settle_start_us, "editor": {
        "rss_bytes": {"value": null, "unavailable_reason": "Requires retained host process sampler"},
        "objects": {"value": int(objects), "unavailable_reason": null},
        "resources": {"value": int(resources), "unavailable_reason": null},
        "held_handles": {"value": null, "unavailable_reason": "Requires retained host process sampler"}}}
    var batch_data: Dictionary = {"schema_id": "hh-studio.native-cycle-batch", "schema_version": "1.2.0",
        "run_id": _input.run_id, "mode": _mode, "pid": OS.get_process_id(), "index": _batch,
        "warmup": _mode == "full" and _batch < WARMUP_BATCHES, "started_mono_us": _batch_started_us,
        "ended_mono_us": ended, "cycles": _cycles, "raw_timings": _raw_timings, "memory": memory,
        "barrier": _barrier, "start_permit": _start_receipt if _mode == "full" else null,
        "max_status_gap_ms": float(_batch_status_gap_us) / 1000.0, "dropped_commands": 0, "dropped_telemetry": 0}
    var name: String = "batch-%02d.json" % _batch
    var written: Dictionary = _write_new(name, batch_data)
    if written.is_empty():
        _fail("BENCHMARK_BATCH_WRITE")
        return
    _batches.append({"index": _batch, "file": name, "sha256": written.sha256, "size_bytes": written.size_bytes})
    _pending_batch_sha256 = str(written.sha256)
    if _mode == "full":
        _set_phase(Phase.HOST_BARRIER)
    print("HH_GT06_BENCHMARK_BATCH " + JSON.stringify({"run_id": _input.run_id, "pid": OS.get_process_id(),
        "index": _batch, "sha256": written.sha256, "memory_mono_us": ended, "barrier": _barrier}))
    if _mode != "full":
        _advance_batch()


func _wait_host_ack() -> void:
    if Time.get_ticks_usec() > int(_barrier.deadline_mono_us):
        _fail("BENCHMARK_HOST_ACK_TIMEOUT")
        return
    var root: Node = EditorInterface.get_edited_scene_root()
    if root == null or root.get_instance_id() != int(_barrier.root_instance_id) or int(_adapter.get("_generation")) != int(_barrier.generation):
        _fail("BENCHMARK_HOST_BARRIER_DRIFT")
        return
    var path: String = ACK_DIRECTORY.path_join("ack-%02d.json" % _batch)
    if not FileAccess.file_exists(path):
        return
    var file: FileAccess = FileAccess.open(path, FileAccess.READ)
    if file == null:
        _fail("BENCHMARK_HOST_ACK_READ")
        return
    var size: int = file.get_length()
    if size < 1 or size > 8192:
        file.close()
        _fail("BENCHMARK_HOST_ACK_SIZE")
        return
    var raw: PackedByteArray = file.get_buffer(size)
    file.close()
    if raw.size() != size:
        _fail("BENCHMARK_HOST_ACK_READ")
        return
    var decoded: Variant = JSON.parse_string(raw.get_string_from_utf8())
    if not decoded is Dictionary:
        _fail("BENCHMARK_HOST_ACK_JSON")
        return
    var ack: Dictionary = decoded
    var fields: Array[String] = ["schema_id", "schema_version", "run_id", "batch_index",
        "native_batch_sha256", "source_closure_sha256", "profile_sha256", "deadline_mono_us"]
    if ack.size() != fields.size() or not ack.has_all(fields):
        _fail("BENCHMARK_HOST_ACK_FIELDS")
        return
    if ack.schema_id != "hh-studio.native-cycle-batch-ack" or ack.schema_version != "1.0.0" or ack.run_id != _input.run_id:
        _fail("BENCHMARK_HOST_ACK_BINDING")
        return
    if not _json_integer(ack.batch_index) or int(ack.batch_index) != _batch or not _json_integer(ack.deadline_mono_us) or int(ack.deadline_mono_us) != int(_barrier.deadline_mono_us):
        _fail("BENCHMARK_HOST_ACK_POSITION")
        return
    if ack.native_batch_sha256 != _pending_batch_sha256 or ack.source_closure_sha256 != _input.source_closure_sha256 or ack.profile_sha256 != _input.profile_sha256:
        _fail("BENCHMARK_HOST_ACK_HASH")
        return
    var snapshot: Dictionary = _adapter.inspect_scene()
    if not _good_snapshot(snapshot) or snapshot.revision != _baseline_revision or int(snapshot.generation) != int(_barrier.generation) or FileAccess.get_sha256(SCENE) != _cycles[-1].saved_file_sha256:
        _fail("BENCHMARK_HOST_ACK_POSTCONDITION")
        return
    var digest: String = _bytes_sha256(raw)
    if FileAccess.get_sha256(path) != digest:
        _fail("BENCHMARK_HOST_ACK_CHANGED")
        return
    # Fresh counters after host joint sampling and validated ACK. Never reuse
    # the earlier batch publication observation as the joint native sample.
    var objects: float = Performance.get_monitor(Performance.OBJECT_COUNT)
    var resources: float = Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)
    var process_frame: int = Engine.get_process_frames()
    if not is_finite(objects) or not is_finite(resources) or objects < 1.0 or resources < 0.0 or objects != floor(objects) or resources != floor(resources) or process_frame < 1:
        _fail("BENCHMARK_ACK_COUNTER_READBACK")
        return
    var observed: int = Time.get_ticks_usec()
    if observed > int(_barrier.deadline_mono_us):
        _fail("BENCHMARK_HOST_ACK_TIMEOUT")
        return
    _heartbeat(true)
    _barrier_receipts.append({"batch_index": _batch, "ack_file": _barrier.ack_file,
        "ack_sha256": digest, "ack_size_bytes": size, "native_batch_sha256": _pending_batch_sha256,
        "issued_mono_us": _barrier.issued_mono_us, "deadline_mono_us": _barrier.deadline_mono_us,
        "ack_observed_mono_us": observed, "root_instance_id": root.get_instance_id(),
        "generation": int(snapshot.generation), "semantic_sha256": _bare(str(snapshot.revision)),
        "process_frame": process_frame, "objects": {"value": int(objects), "unavailable_reason": null},
        "resources": {"value": int(resources), "unavailable_reason": null},
        "max_status_gap_ms": float(_batch_status_gap_us) / 1000.0})
    print("HH_GT06_BENCHMARK_ACK " + JSON.stringify(_barrier_receipts[-1]))
    _advance_batch()


func _advance_batch() -> void:
    _barrier = {}
    _pending_batch_sha256 = ""
    _batch += 1
    if _batch < _batch_limit:
        _begin_batch()
    else:
        _finish()


func _finish() -> void:
    if _mode == "full" and (_barrier_receipts.size() != FULL_BATCHES or _start_receipts.size() != FULL_BATCHES):
        _fail("BENCHMARK_HOST_ACK_INCOMPLETE")
        return
    for receipt: Dictionary in _start_receipts:
        if FileAccess.get_sha256("res://" + str(receipt.start_file)) != receipt.start_sha256 or FileAccess.get_sha256("res://" + str(receipt.ready_file)) != receipt.ready_sha256:
            _fail("BENCHMARK_HOST_START_CHANGED")
            return
    for receipt: Dictionary in _barrier_receipts:
        if FileAccess.get_sha256("res://" + str(receipt.ack_file)) != receipt.ack_sha256:
            _fail("BENCHMARK_HOST_ACK_CHANGED")
            return
    for path: String in SOURCE_PATHS:
        if FileAccess.get_sha256(path) != _source_hashes[path]:
            _fail("BENCHMARK_SOURCE_CHANGED")
            return
    var report: Dictionary = {"schema_id": "hh-studio.native-cycle-benchmark", "schema_version": "1.3.0",
        "input": _input, "pid": OS.get_process_id(), "engine": Engine.get_version_info(),
        "display_server": DisplayServer.get_name(), "editor_hint": Engine.is_editor_hint(), "main_thread": _main_thread(),
        "started_mono_us": _run_started_us, "ended_mono_us": Time.get_ticks_usec(),
        "started_unix": _run_started_unix,
        "startup_readiness": _startup_readiness,
        "source_files": _source_hashes, "batches": _batches, "batches_completed": _batch,
        "host_barriers": _barrier_receipts, "host_integrated": _mode == "full",
        "start_permits": _start_receipts, "host_start_timeout_us": HOST_START_TIMEOUT_US,
        "batch_order": "host_commands_then_native_cycles_then_joint_ack" if _mode == "full" else "diagnostic_native_cycle_only",
        "cycles_per_batch": _cycle_limit, "baseline_revision": _baseline_revision,
        "max_status_gap_ms": float(_max_status_gap_us) / 1000.0, "heartbeat_target_met": _max_status_gap_us <= 2000000,
        "quiescence": {"minimum_frames": SETTLE_FRAMES, "minimum_us": SETTLE_US},
        "host_barrier_timeout_us": HOST_BARRIER_TIMEOUT_US,
        "counter_definitions": {"objects": "Performance.OBJECT_COUNT -> ObjectDB::get_object_count",
            "resources": "Performance.OBJECT_RESOURCE_COUNT -> ResourceCache::get_cached_resource_count"},
        "scope": "direct-semantic test fixture; excludes public/API command mix and Stop latency",
        "benchmark_complete": _mode == "full", "completed": true, "formal_acceptance": false}
    var written: Dictionary = _write_new("index.json", report)
    if written.is_empty():
        _fail("BENCHMARK_INDEX_WRITE")
        return
    _set_phase(Phase.FINISHED)
    print("HH_GT06_BENCHMARK_COMPLETE " + JSON.stringify({"run_id": _input.run_id, "pid": OS.get_process_id(),
        "mode": _mode, "batches": _batch, "index_sha256": written.sha256, "benchmark_complete": _mode == "full",
        "host_integrated": _mode == "full"}))
    get_tree().quit(0)


func _record_time(step: String, start: int, end: int) -> void:
    if end <= start:
        _fail("BENCHMARK_CLOCK_RESOLUTION")
        return
    _timing[step] = {"start_us": start, "end_us": end}
    _row.latency_ms[step] = float(end - start) / 1000.0


func _good_snapshot(value: Dictionary) -> bool:
    return value.get("ok", false) and not value.get("held", true) and _revision(value.get("revision")) and int(value.get("generation", 0)) > 0


func _set_phase(value: Phase) -> void:
    _phase = value
    _phase_started_us = Time.get_ticks_usec()


func _heartbeat(force: bool = false) -> void:
    var now: int = Time.get_ticks_usec()
    if not force and now - _last_heartbeat_us < HEARTBEAT_US:
        return
    if _last_heartbeat_us > 0:
        var gap: int = now - _last_heartbeat_us
        _max_status_gap_us = maxi(_max_status_gap_us, gap)
        if _batch_started_us > 0 or not _start_offer.is_empty():
            _batch_status_gap_us = maxi(_batch_status_gap_us, gap)
    _last_heartbeat_us = now
    print("HH_GT06_BENCHMARK_HEARTBEAT " + JSON.stringify({"run_id": _input.get("run_id", "unbound"),
        "pid": OS.get_process_id(), "batch": _batch, "cycle": _cycle, "phase": Phase.keys()[_phase],
        "monotonic_us": now, "main_thread": _main_thread()}))


func _write_new(name: String, value: Dictionary) -> Dictionary:
    var target: String = OUTPUT.path_join(name)
    var temporary: String = target + ".tmp"
    if FileAccess.file_exists(target) or FileAccess.file_exists(temporary):
        return {}
    var raw: PackedByteArray = (JSON.stringify(value, "", true, true) + "\n").to_utf8_buffer()
    if raw.is_empty() or raw.size() > MAX_BATCH_BYTES:
        return {}
    var file: FileAccess = FileAccess.open(temporary, FileAccess.WRITE)
    if file == null:
        return {}
    file.store_buffer(raw)
    file.flush()
    var error: Error = file.get_error()
    file.close()
    if error != OK or DirAccess.rename_absolute(temporary, target) != OK:
        return {}
    var digest: String = _bytes_sha256(raw)
    if FileAccess.get_sha256(target) != digest:
        return {}
    return {"sha256": digest, "size_bytes": raw.size()}


func _fail(code: String) -> void:
    if _failed:
        return
    _failed = true
    var failure: Dictionary = {"schema_id": "hh-studio.native-cycle-failure", "schema_version": "1.2.0",
        "code": code, "input": _input, "pid": OS.get_process_id(), "phase": Phase.keys()[_phase],
        "batch": _batch, "cycle": _cycle, "monotonic_us": Time.get_ticks_usec(),
        "host_barrier": _barrier, "pending_batch_sha256": _pending_batch_sha256,
        "start_offer": _start_offer, "start_permit": _start_receipt,
        "partial_cycle": _row, "partial_timing": _timing, "completed": false, "formal_acceptance": false}
    _write_new("failure.json", failure)
    print("HH_GT06_BENCHMARK_FAILED " + JSON.stringify({"code": code, "pid": OS.get_process_id(),
        "batch": _batch, "cycle": _cycle, "completed": false}))
    _phase = Phase.FINISHED
    get_tree().quit(86)


func _main_thread() -> bool:
    return OS.get_thread_caller_id() == OS.get_main_thread_id()


func _bytes_sha256(raw: PackedByteArray) -> String:
    var hash_context := HashingContext.new()
    hash_context.start(HashingContext.HASH_SHA256)
    hash_context.update(raw)
    return hash_context.finish().hex_encode()


func _json_integer(value: Variant) -> bool:
    if typeof(value) not in [TYPE_INT, TYPE_FLOAT]:
        return false
    return is_finite(float(value)) and float(value) >= 0.0 and float(value) <= 9007199254740991.0 and float(value) == floor(float(value))


func _hex(value: Variant) -> bool:
    if not value is String or value.length() != 64:
        return false
    for character: String in value:
        if character not in "0123456789abcdef":
            return false
    return true


func _revision(value: Variant) -> bool:
    return value is String and value.begins_with("sha256:") and _hex(value.trim_prefix("sha256:"))


func _bare(value: String) -> String:
    return value.trim_prefix("sha256:")


func _identifier(value: Variant) -> bool:
    if not value is String or value.length() < 1 or value.length() > 64 or value[0] not in "abcdefghijklmnopqrstuvwxyz":
        return false
    for character: String in value:
        if character not in "abcdefghijklmnopqrstuvwxyz0123456789._-":
            return false
    return true

# Disposable diagnostic instrumentation appended before import; never runtime source.
# No await/timer, private-tree mutation, native source patch, or performance claim.
const FOCUS_SETTLE_US: int = 1500000
const FOCUS_SETTLE_FRAMES: int = 8
const FOCUS_MAX_WALL_US: int = 30000000
var _focus_probe_stage: int = 0
var _focus_probe_started_us: int = 0
var _focus_probe_due_us: int = 0
var _focus_probe_due_frame: int = 0
var _focus_probe_dispatch: int = 0
var _focus_probe_overflow: bool = false
var _focus_probe_visited: int = 0
var _focus_probe_tree_visited: int = 0
var _focus_probe_owners: Dictionary = {}
var _focus_probe_previous_roots: Dictionary = {}
var _focus_probe_events: Array[Dictionary] = []
var _focus_probe_stimuli: Array[Dictionary] = []
var _focus_probe_points: Array[Dictionary] = []
var _focus_probe_total_bytes: int = 0


func _notification(what: int) -> void:
    if what not in [NOTIFICATION_APPLICATION_FOCUS_IN, NOTIFICATION_APPLICATION_FOCUS_OUT]:
        return
    if not Engine.is_editor_hint() or _mode != "diagnostic":
        return
    if _focus_probe_events.size() >= 64:
        _focus_probe_overflow = true
        return
    _focus_probe_events.append({"ordinal": _focus_probe_events.size(),
        "notification": what, "mono_us": Time.get_ticks_usec(),
        "frame": Engine.get_process_frames(), "pid": OS.get_process_id(),
        "probe_synthetic_dispatch": _focus_probe_dispatch,
        "origin": "probe_synthetic" if _focus_probe_dispatch > 0 else "received_outside_probe_dispatch"})


func _focus_probe_counters() -> Dictionary:
    var filesystem: EditorFileSystem = EditorInterface.get_resource_filesystem()
    var result: Dictionary = {"filesystem_scanning_before": filesystem.is_scanning(),
        "objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
        "cached_resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
        "tree_nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
        "orphan_nodes": int(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT))}
    result["filesystem_scanning_after"] = filesystem.is_scanning()
    return result


func _focus_probe_text(value: String) -> Dictionary:
    return {"text": value.left(512), "length": value.length(),
        "sha256": value.sha256_text(), "truncated": value.length() > 512}


func _focus_probe_callbacks(dialog: ConfirmationDialog) -> Array[Dictionary]:
    var rows: Array[Dictionary] = []
    for connection: Dictionary in dialog.get_signal_connection_list("confirmed"):
        var callback: Callable = connection["callable"]
        var target: Object = callback.get_object()
        if not is_instance_valid(target):
            _fail("FOCUS_CALLBACK_TARGET_INVALID")
            return []
        rows.append({"target_id": str(callback.get_object_id()), "method": str(callback.get_method()),
            "target_class": target.get_class(),
            "target_path": str((target as Node).get_path()) if target is Node else ""})
    if rows.size() > 16:
        _fail("FOCUS_CALLBACK_CAP")
    return rows


func _focus_probe_role(callbacks: Array[Dictionary]) -> String:
    var role: String = ""
    for row: Dictionary in callbacks:
        var method: String = str(row["method"])
        var plain: String = method.get_slice("::", method.get_slice_count("::") - 1)
        var found: String = ""
        if plain == "_reload_modified_scenes" and row.target_class == "EditorNode":
            found = "editor_disk_changes"
        elif plain == "reload_scripts" and row.target_class == "ScriptEditor":
            found = "script_disk_changes"
        if not found.is_empty():
            if not role.is_empty() and role != found:
                _fail("FOCUS_AMBIGUOUS_CALLBACK_ROLE")
                return ""
            role = found
    return role


func _focus_probe_find_trees(node: Node, ids: Array[String], depth: int = 0) -> void:
    _focus_probe_tree_visited += 1
    if _failed or depth > 128 or _focus_probe_tree_visited > 50000:
        _fail("FOCUS_TREE_SCAN_CAP")
        return
    if node is Tree:
        ids.append(str(node.get_instance_id()))
        return
    for child: Node in node.get_children(true):
        _focus_probe_find_trees(child, ids, depth + 1)


func _focus_probe_discover(node: Node, depth: int = 0) -> void:
    if _failed:
        return
    _focus_probe_visited += 1
    if depth > 128 or _focus_probe_visited > 50000:
        _fail("FOCUS_NODE_SCAN_CAP")
        return
    if node is ConfirmationDialog:
        var dialog: ConfirmationDialog = node as ConfirmationDialog
        var callbacks: Array[Dictionary] = _focus_probe_callbacks(dialog)
        var role: String = _focus_probe_role(callbacks)
        if not role.is_empty():
            var trees: Array[String] = []
            _focus_probe_find_trees(dialog, trees)
            if trees.size() != 1 or _focus_probe_owners.has(role):
                _fail("FOCUS_OWNER_AMBIGUOUS")
                return
            _focus_probe_owners[role] = {"dialog_id": str(dialog.get_instance_id()),
                "tree_id": trees[0], "confirmed_callbacks": callbacks}
    for child: Node in node.get_children(true):
        _focus_probe_discover(child, depth + 1)


func _focus_probe_items(item: TreeItem, tree: Tree, rows: Array[Dictionary]) -> void:
    if item == null or _failed:
        return
    if rows.size() >= 64:
        _fail("FOCUS_TREE_ITEM_CAP")
        return
    var cells: Array[Dictionary] = []
    for column: int in range(mini(tree.columns, 8)):
        var cell: Dictionary = _focus_probe_text(item.get_text(column))
        cell["column"] = column
        cells.append(cell)
    rows.append({"id": str(item.get_instance_id()), "class": item.get_class(),
        "owner_tree_id": str(item.get_tree().get_instance_id()),
        "parent_item_id": str(item.get_parent().get_instance_id()) if item.get_parent() != null else "",
        "queued_for_deletion": item.is_queued_for_deletion(), "columns": tree.columns,
        "cell_texts": cells})
    var child: TreeItem = item.get_first_child()
    while child != null and not _failed:
        _focus_probe_items(child, tree, rows)
        child = child.get_next()


func _focus_probe_owner_snapshot() -> Dictionary:
    var result: Dictionary = {}
    for role: String in ["editor_disk_changes", "script_disk_changes"]:
        var identity: Dictionary = _focus_probe_owners[role]
        var dialog: ConfirmationDialog = instance_from_id(int(identity.dialog_id)) as ConfirmationDialog
        var tree: Tree = instance_from_id(int(identity.tree_id)) as Tree
        if not is_instance_valid(dialog) or not is_instance_valid(tree) or not dialog.is_ancestor_of(tree):
            _fail("FOCUS_OWNER_IDENTITY_LOST")
            return {}
        var callbacks: Array[Dictionary] = _focus_probe_callbacks(dialog)
        if _focus_probe_role(callbacks) != role or callbacks != identity.confirmed_callbacks:
            _fail("FOCUS_OWNER_CALLBACK_DRIFT")
            return {}
        var root_item: TreeItem = tree.get_root()
        var previous_id: String = str(_focus_probe_previous_roots.get(role, ""))
        var items: Array[Dictionary] = []
        _focus_probe_items(root_item, tree, items)
        result[role] = {"dialog_id": identity.dialog_id, "dialog_path": str(dialog.get_path()),
            "dialog_parent_class": dialog.get_parent().get_class(),
            "dialog_title": _focus_probe_text(dialog.title), "dialog_visible": dialog.visible,
            "confirmed_callbacks": callbacks, "tree_id": identity.tree_id,
            "tree_path": str(tree.get_path()), "tree_visible": tree.is_visible_in_tree(),
            "columns": tree.columns, "hide_root": tree.hide_root,
            "previous_root_item_id": previous_id,
            "previous_root_still_valid": is_instance_id_valid(int(previous_id)) if not previous_id.is_empty() else null,
            "root_item_id": str(root_item.get_instance_id()) if root_item != null else "",
            "root_present": root_item != null, "item_count": items.size(), "items": items}
        _focus_probe_previous_roots[role] = result[role].root_item_id
    return result


func _focus_probe_files() -> Dictionary:
    var result: Dictionary = {}
    var paths: Array[String] = SOURCE_PATHS.duplicate()
    paths.append(SCENE)
    var total_bytes: int = 0
    for path: String in paths:
        var file: FileAccess = FileAccess.open(path, FileAccess.READ)
        if file == null:
            _fail("FOCUS_FILE_READ")
            return {}
        var size: int = file.get_length()
        file.close()
        file = null
        total_bytes += size
        if size < 1 or size > 1048576 or total_bytes > 2097152:
            _fail("FOCUS_FILE_CAP")
            return {}
        var digest: String = FileAccess.get_sha256(path)
        if not _hex(digest):
            _fail("FOCUS_FILE_HASH")
            return {}
        result[path] = {"sha256": digest, "size_bytes": size,
            "modified_time": FileAccess.get_modified_time(path)}
    return result


func _focus_probe_snapshot(label: String) -> void:
    if _failed or _focus_probe_points.size() >= 6:
        _fail("FOCUS_POINT_CAP_OR_PRIOR_FAILURE")
        return
    var before: Dictionary = _focus_probe_counters()
    var started: int = Time.get_ticks_usec()
    var owners: Dictionary = _focus_probe_owner_snapshot()
    var files: Dictionary = _focus_probe_files()
    var after: Dictionary = _focus_probe_counters()
    if _failed:
        return
    var point: Dictionary = {"schema_id": "hh-studio.focus-causal-diagnostic-point", "schema_version": "1.0.0",
        "run_id": _input.run_id, "pid": OS.get_process_id(), "sequence": _focus_probe_points.size(),
        "formal_acceptance": false, "full_benchmark": false, "full_objectdb_attribution": false,
        "label": label, "mono_us": started, "collection_end_us": Time.get_ticks_usec(),
        "frame": Engine.get_process_frames(), "phase": Phase.keys()[_phase],
        "batch": _batch, "cycle": _cycle, "focus_probe_stage": _focus_probe_stage,
        "main_window_title": _focus_probe_text(get_window().title),
        "main_window_focused": get_window().has_focus(), "event_count": _focus_probe_events.size(),
        "counters_before": before, "counters_after": after,
        "counters_equal_across_collection": before == after, "owners": owners, "files": files}
    var size: int = JSON.stringify(point, "", true, true).to_utf8_buffer().size()
    _focus_probe_total_bytes += size
    if size > 262144 or _focus_probe_total_bytes > 1572864:
        _fail("FOCUS_POINT_BYTE_CAP")
        return
    var name: String = "focus-%02d.json" % _focus_probe_points.size()
    var written: Dictionary = _write_new(name, point)
    if written.is_empty():
        _fail("FOCUS_POINT_WRITE")
        return
    _focus_probe_points.append({"file": name, "sha256": written.sha256,
        "size_bytes": written.size_bytes, "sequence": point.sequence, "label": label})


func _focus_probe_settle(stage: int) -> void:
    _focus_probe_stage = stage
    _focus_probe_due_us = Time.get_ticks_usec() + FOCUS_SETTLE_US
    _focus_probe_due_frame = Engine.get_process_frames() + FOCUS_SETTLE_FRAMES


func _focus_probe_stimulus(number: int) -> void:
    var event_start: int = _focus_probe_events.size()
    var before: int = Time.get_ticks_usec()
    var before_frame: int = Engine.get_process_frames()
    _focus_probe_dispatch = number
    get_tree().root.propagate_notification(NOTIFICATION_APPLICATION_FOCUS_IN)
    _focus_probe_dispatch = 0
    _focus_probe_stimuli.append({"ordinal": number, "synthetic": true,
        "operation": "SceneTree.root.propagate_notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)",
        "notification": NOTIFICATION_APPLICATION_FOCUS_IN, "begin_mono_us": before,
        "end_mono_us": Time.get_ticks_usec(), "begin_frame": before_frame,
        "end_frame": Engine.get_process_frames(), "before_point_sequence": _focus_probe_points.size() - 1,
        "event_start_index": event_start, "event_end_index": _focus_probe_events.size()})
    if _focus_probe_events.size() != event_start + 1 or _focus_probe_events[-1].probe_synthetic_dispatch != number:
        _fail("FOCUS_STIMULUS_NOTIFICATION_READBACK")


func _focus_probe_after_batch() -> void:
    if _batch != 0 or _cycle != 1 or _focus_probe_stage != 0:
        _fail("FOCUS_SINGLE_CYCLE_REQUIRED")
        return
    _focus_probe_started_us = Time.get_ticks_usec()
    _focus_probe_discover(get_tree().root)
    if _failed:
        return
    if _focus_probe_owners.size() != 2 or not _focus_probe_owners.has("editor_disk_changes") or not _focus_probe_owners.has("script_disk_changes"):
        _fail("FOCUS_OWNER_NOT_FOUND")
        return
    _focus_probe_snapshot("natural_after_cycle")
    _focus_probe_settle(1)


func _focus_probe_tick() -> bool:
    if _focus_probe_stage == 0:
        return false
    if _focus_probe_overflow or Time.get_ticks_usec() - _focus_probe_started_us > FOCUS_MAX_WALL_US:
        _fail("FOCUS_EVENT_CAP_OR_DEADLINE")
        return true
    if Time.get_ticks_usec() < _focus_probe_due_us or Engine.get_process_frames() < _focus_probe_due_frame:
        return true
    if _focus_probe_stage == 1:
        _focus_probe_snapshot("before_first_stimulus")
        if not _failed:
            _focus_probe_stimulus(1)
        if not _failed:
            _focus_probe_snapshot("after_first_return")
            _focus_probe_settle(2)
    elif _focus_probe_stage == 2:
        _focus_probe_snapshot("after_first_settle_before_second")
        if not _failed:
            _focus_probe_stimulus(2)
        if not _failed:
            _focus_probe_snapshot("after_second_return")
            _focus_probe_settle(3)
    elif _focus_probe_stage == 3:
        _focus_probe_snapshot("after_second_settle")
        if not _failed:
            var report: Dictionary = {"schema_id": "hh-studio.focus-causal-diagnostic", "schema_version": "1.0.0",
                "run_id": _input.run_id, "pid": OS.get_process_id(), "formal_acceptance": false,
                "full_benchmark": false, "root_cause_proven": false, "completed_diagnostic": true,
                "stimulus_is_synthetic_not_os_focus": true, "private_tree_mutation": false,
                "settle_minimum_us": FOCUS_SETTLE_US, "settle_minimum_frames": FOCUS_SETTLE_FRAMES,
                "events": _focus_probe_events, "stimuli": _focus_probe_stimuli, "points": _focus_probe_points}
            if _write_new("focus-index.json", report).is_empty():
                _fail("FOCUS_INDEX_WRITE")
            else:
                _focus_probe_stage = 4
                _advance_batch()
    return true

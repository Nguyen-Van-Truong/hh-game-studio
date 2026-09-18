# Appended only to the disposable diagnostic benchmark plugin. Not runtime source.
# No await, timers, retained Object/RefCounted references, or arbitrary property getters.
var _object_probe_previous: Dictionary = {}
var _object_probe_signature: Array = []
var _object_probe_sequence: int = 0
var _object_probe_next_us: int = 0
var _object_probe_idle_until_us: int = 0
var _object_probe_bytes: int = 0
var _object_probe_last_write_us: int = 0


func _object_probe_counters() -> Dictionary:
    var filesystem: EditorFileSystem = EditorInterface.get_resource_filesystem()
    var scanning_before: bool = filesystem.is_scanning()
    var counters: Dictionary = {"objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
        "cached_resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
        "tree_nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
        "orphan_nodes": int(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT))}
    counters["filesystem_scanning_before"] = scanning_before
    counters["filesystem_scanning_after"] = filesystem.is_scanning()
    return counters


func _object_probe_describe(object: Object, rows: Dictionary, relation: String) -> void:
    if not is_instance_valid(object):
        return
    var key: String = str(object.get_instance_id())
    if rows.has(key):
        return
    var row: Dictionary = {"id": key, "class": object.get_class(), "relation": relation,
        "queued_for_deletion": object.is_queued_for_deletion()}
    if object is Node:
        var node: Node = object as Node
        row["name"] = str(node.name)
        row["inside_tree"] = node.is_inside_tree()
        row["path"] = str(node.get_path()) if node.is_inside_tree() else ""
        row["scene_file_path"] = node.scene_file_path
        row["parent_id"] = str(node.get_parent().get_instance_id()) if node.get_parent() != null else ""
        if node is CanvasItem:
            row["visible"] = (node as CanvasItem).is_visible_in_tree()
        if node is RichTextLabel:
            row["paragraph_count"] = (node as RichTextLabel).get_paragraph_count()
            row["character_count"] = (node as RichTextLabel).get_total_character_count()
        if node is Timer:
            row["wait_time"] = (node as Timer).wait_time
            row["stopped"] = (node as Timer).is_stopped()
            var callbacks: Array[Dictionary] = []
            for connection: Dictionary in node.get_signal_connection_list("timeout"):
                var callback: Callable = connection["callable"]
                callbacks.append({"target_id": str(callback.get_object_id()),
                    "method": str(callback.get_method())})
            row["timeout_callbacks"] = callbacks
    elif object is Resource:
        row["resource_path"] = (object as Resource).resource_path
    rows[key] = row


func _object_probe_tree_item(item: TreeItem, rows: Dictionary, tree_id: String) -> void:
    if item == null:
        return
    _object_probe_describe(item, rows, "tree_item:" + tree_id)
    var child: TreeItem = item.get_first_child()
    while child != null:
        _object_probe_tree_item(child, rows, tree_id)
        child = child.get_next()


func _object_probe_node(node: Node, rows: Dictionary) -> void:
    _object_probe_describe(node, rows, "node")
    if node is Tree:
        _object_probe_tree_item((node as Tree).get_root(), rows, str(node.get_instance_id()))
    # Signal sources expose existing timers/resources connected to editor nodes.
    # Keep only primitive descriptors, never the connections or source objects.
    for connection: Dictionary in node.get_incoming_connections():
        var source_signal: Signal = connection["signal"]
        _object_probe_describe(source_signal.get_object(), rows,
            "incoming_signal_to:" + str(node.get_instance_id()))
    for child: Node in node.get_children(true):
        _object_probe_node(child, rows)


func _object_probe_collect() -> Dictionary:
    var rows: Dictionary = {}
    _object_probe_node(get_tree().root, rows)
    for orphan_id: int in Node.get_orphan_node_ids():
        _object_probe_describe(instance_from_id(orphan_id), rows, "orphan")
    for tween: Tween in get_tree().get_processed_tweens():
        _object_probe_describe(tween, rows, "processed_tween")
    return rows


func _object_probe_sample(label: String, force: bool = false) -> void:
    var before: Dictionary = _object_probe_counters()
    var signature: Array = [before.objects, before.cached_resources,
        before.tree_nodes, before.orphan_nodes, _batch,
        before.filesystem_scanning_before, before.filesystem_scanning_after]
    var now: int = Time.get_ticks_usec()
    if not force and signature == _object_probe_signature and now < _object_probe_next_us:
        return
    if _object_probe_sequence >= 512:
        _fail("OBJECT_PROBE_SNAPSHOT_CAP")
        return
    var rows: Dictionary = _object_probe_collect()
    var after: Dictionary = _object_probe_counters()
    var collection_us: int = Time.get_ticks_usec() - now
    var added: Array[Dictionary] = []
    var changed: Array[Dictionary] = []
    var removed: Array[Dictionary] = []
    var class_counts: Dictionary = {}
    for key: String in rows:
        var row: Dictionary = rows[key]
        var class_name_value: String = str(row["class"])
        class_counts[class_name_value] = int(class_counts.get(class_name_value, 0)) + 1
        if not _object_probe_previous.has(key):
            # Initial reachable inventory is large. Keep its count/class summary;
            # emit full identities for subsequent changes and removals only.
            if _object_probe_sequence > 0:
                added.append(row)
        elif row != _object_probe_previous[key]:
            changed.append(row)
    for key: String in _object_probe_previous:
        if not rows.has(key):
            var removed_row: Dictionary = _object_probe_previous[key].duplicate()
            removed_row["still_valid"] = is_instance_id_valid(int(key))
            removed.append(removed_row)
    var point: Dictionary = {"schema_id": "hh-studio.object-attribution-diagnostic",
        "schema_version": "1.0.0", "formal_acceptance": false, "full_benchmark": false,
        "run_id": _input.run_id, "pid": OS.get_process_id(), "sequence": _object_probe_sequence,
        "label": label, "batch": _batch, "cycle": _cycle, "phase": Phase.keys()[_phase],
        "frame": Engine.get_process_frames(), "mono_us": now,
        "last_heartbeat_us": _last_heartbeat_us, "focused": get_window().has_focus(),
        "filesystem_scanning": EditorInterface.get_resource_filesystem().is_scanning(),
        "counters_before": before, "counters_after": after,
        "counters_equal_across_collection": before == after,
        "inventory_duration_us": collection_us,
        "previous_snapshot_write_us": _object_probe_last_write_us,
        "inventory_count": rows.size(), "class_counts": class_counts,
        "unattributed_object_count": int(before.objects) - rows.size(),
        "inventory_complete_objectdb": false,
        "initial_inventory_ids_omitted": _object_probe_sequence == 0,
        "added": added, "changed": changed, "removed": removed}
    _object_probe_previous = rows
    _object_probe_signature = signature
    # Enumerating the large editor tree costs ~1.1-1.6s on this host. Keep
    # count-change samples immediate but reduce unchanged full censuses.
    _object_probe_next_us = now + 10000000
    var write_started_us: int = Time.get_ticks_usec()
    var raw: PackedByteArray = (JSON.stringify(point, "", true, true) + "\n").to_utf8_buffer()
    _object_probe_bytes += raw.size()
    if raw.size() > 8388608 or _object_probe_bytes > 134217728:
        _fail("OBJECT_PROBE_BYTE_CAP")
        return
    var target: String = OUTPUT.path_join("object-%04d.json" % _object_probe_sequence)
    var temporary: String = target + ".pending"
    if FileAccess.file_exists(target) or FileAccess.file_exists(temporary):
        _fail("OBJECT_PROBE_EXISTS")
        return
    var file: FileAccess = FileAccess.open(temporary, FileAccess.WRITE)
    if file == null:
        _fail("OBJECT_PROBE_OPEN")
        return
    file.store_buffer(raw)
    file.flush()
    var error: Error = file.get_error()
    file.close()
    if error != OK or DirAccess.rename_absolute(temporary, target) != OK:
        _fail("OBJECT_PROBE_PUBLISH")
        return
    if FileAccess.get_sha256(target) != _bytes_sha256(raw):
        _fail("OBJECT_PROBE_READBACK")
        return
    _object_probe_last_write_us = Time.get_ticks_usec() - write_started_us
    _object_probe_sequence += 1


func _object_probe_after_batch() -> void:
    _object_probe_sample("after_batch", true)
    if _failed:
        return
    if _batch == _batch_limit - 1:
        _object_probe_idle_until_us = Time.get_ticks_usec() + 60000000
    else:
        _advance_batch()


func _object_probe_tick() -> bool:
    if _object_probe_idle_until_us > 0:
        _object_probe_sample("idle")
        if not _failed and Time.get_ticks_usec() >= _object_probe_idle_until_us:
            _object_probe_sample("idle_end", true)
            if not _failed:
                _object_probe_idle_until_us = 0
                _advance_batch()
        return true
    if _phase == Phase.BATCH_SETTLE:
        _object_probe_sample("settle")
    return _failed

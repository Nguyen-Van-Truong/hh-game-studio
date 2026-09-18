# Disposable diagnostic overlay only; never part of runtime source or acceptance.
# Derived from S82. Ordinary baseline descriptors are neither built nor retained.
# Persist only primitive ID/class membership and Tree/RichTextLabel summaries.
var _object_probe_previous: Dictionary = {}
var _object_probe_previous_summaries: Dictionary = {}
var _object_probe_signature: Array = []
var _object_probe_sequence: int = 0
var _object_probe_next_us: int = 0
var _object_probe_idle_until_us: int = 0
var _object_probe_bytes: int = 0
var _object_probe_last_write_us: int = 0
var _object_probe_retained_cleared: bool = false


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


func _object_probe_describe(object: Object, relation: String) -> Dictionary:
    # Called only for summaries or newly appeared IDs, never ordinary baseline IDs.
    var row: Dictionary = {"id": str(object.get_instance_id()), "class": object.get_class(),
        "relation": relation, "queued_for_deletion": object.is_queued_for_deletion()}
    if object is Node:
        var node: Node = object as Node
        row["name"] = str(node.name)
        row["inside_tree"] = node.is_inside_tree()
        row["path"] = str(node.get_path()) if node.is_inside_tree() else ""
        row["scene_file_path"] = node.scene_file_path
        row["parent_id"] = str(node.get_parent().get_instance_id()) if node.get_parent() != null else ""
        if node is CanvasItem:
            row["visible"] = (node as CanvasItem).is_visible_in_tree()
        if node is Tree:
            row["columns"] = (node as Tree).columns
            row["hide_root"] = (node as Tree).hide_root
        if node is RichTextLabel:
            row["paragraph_count"] = (node as RichTextLabel).get_paragraph_count()
            row["character_count"] = (node as RichTextLabel).get_total_character_count()
        if node is Timer:
            row["wait_time"] = (node as Timer).wait_time
            row["stopped"] = (node as Timer).is_stopped()
            var callbacks: Array[Dictionary] = []
            for connection: Dictionary in node.get_signal_connection_list("timeout"):
                var callback: Callable = connection["callable"]
                callbacks.append({"target_id": str(callback.get_object_id()), "method": str(callback.get_method())})
            row["timeout_callbacks"] = callbacks
    elif object is Resource:
        row["resource_path"] = (object as Resource).resource_path
    return row


func _object_probe_visit(object: Object, census: Dictionary, relation: String) -> void:
    if not is_instance_valid(object):
        return
    # Signed decimal IDs are kept exactly; no positivity test or lossy float path.
    var key: String = str(object.get_instance_id())
    var classes: Dictionary = census["classes"]
    if classes.has(key):
        return
    var class_name_value: String = object.get_class()
    classes[key] = class_name_value
    var class_counts: Dictionary = census["class_counts"]
    class_counts[class_name_value] = int(class_counts.get(class_name_value, 0)) + 1
    # Exact-class summary scope preserves the S82 baseline emission contract.
    var summary: bool = class_name_value in ["Tree", "RichTextLabel"]
    var appeared: bool = _object_probe_sequence > 0 and not _object_probe_previous.has(key)
    if summary or appeared:
        var row: Dictionary = _object_probe_describe(object, relation)
        var details: Dictionary = census["details"]
        details[key] = row
        if summary:
            var summaries: Dictionary = census["summaries"]
            summaries[key] = row
        if appeared:
            var added: Array[Dictionary] = census["added"]
            added.append(row)


func _object_probe_tree_item(item: TreeItem, census: Dictionary, tree_id: String) -> void:
    if item == null:
        return
    var key: String = str(item.get_instance_id())
    _object_probe_visit(item, census, "tree_item:" + tree_id)
    # Each owner Tree is visited once in the node traversal. Count every item,
    # but do not build its cell text/path descriptor unless this ID is new.
    var owners: Dictionary = census["owner_tree_item_counts"]
    owners[tree_id] = int(owners.get(tree_id, 0)) + 1
    var details: Dictionary = census["details"]
    if details.has(key):
        var row: Dictionary = details[key]
        var tree: Tree = item.get_tree()
        row["owner_tree_id"] = tree_id
        row["owner_tree_path"] = str(tree.get_path()) if tree.is_inside_tree() else ""
        row["owner_tree_visible"] = tree.is_visible_in_tree()
        row["parent_item_id"] = str(item.get_parent().get_instance_id()) if item.get_parent() != null else ""
        row["columns"] = tree.columns
        var texts: Array[Dictionary] = []
        for column: int in range(mini(tree.columns, 8)):
            var text: String = item.get_text(column)
            texts.append({"column": column, "text": text.left(512), "length": text.length(),
                "sha256": text.sha256_text(), "truncated": text.length() > 512})
        row["cell_texts"] = texts
    var child: TreeItem = item.get_first_child()
    while child != null:
        _object_probe_tree_item(child, census, tree_id)
        child = child.get_next()


func _object_probe_node(node: Node, census: Dictionary) -> void:
    _object_probe_visit(node, census, "node")
    if node is Tree:
        _object_probe_tree_item((node as Tree).get_root(), census, str(node.get_instance_id()))
    for connection: Dictionary in node.get_incoming_connections():
        var source_signal: Signal = connection["signal"]
        _object_probe_visit(source_signal.get_object(), census, "incoming_signal_to:" + str(node.get_instance_id()))
    for child: Node in node.get_children(true):
        _object_probe_node(child, census)


func _object_probe_collect() -> Dictionary:
    var added: Array[Dictionary] = []
    var census: Dictionary = {"classes": {}, "class_counts": {}, "summaries": {},
        "details": {}, "owner_tree_item_counts": {}, "added": added}
    _object_probe_node(get_tree().root, census)
    for orphan_id: int in Node.get_orphan_node_ids():
        _object_probe_visit(instance_from_id(orphan_id), census, "orphan")
    for tween: Tween in get_tree().get_processed_tweens():
        _object_probe_visit(tween, census, "processed_tween")
    return census


func _object_probe_sample(label: String, force: bool = false) -> void:
    if _object_probe_retained_cleared:
        _fail("OBJECT_PROBE_CLEARED")
        return
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
    var census: Dictionary = _object_probe_collect()
    var after: Dictionary = _object_probe_counters()
    var collection_us: int = Time.get_ticks_usec() - now
    var classes: Dictionary = census["classes"]
    var summaries: Dictionary = census["summaries"]
    var added: Array[Dictionary] = census["added"]
    var changed: Array[Dictionary] = []
    var removed: Array[Dictionary] = []
    var initial_id_classes: Dictionary = {}
    if _object_probe_sequence == 0:
        initial_id_classes = classes
        for key: String in summaries:
            added.append(summaries[key])
    else:
        for key: String in summaries:
            if _object_probe_previous_summaries.has(key) and summaries[key] != _object_probe_previous_summaries[key]:
                changed.append(summaries[key])
        for key: String in _object_probe_previous:
            if not classes.has(key):
                var removed_row: Dictionary
                if _object_probe_previous_summaries.has(key):
                    removed_row = _object_probe_previous_summaries[key].duplicate()
                else:
                    removed_row = {"id": key, "class": _object_probe_previous[key],
                        "old_metadata_available": false, "old_metadata_scope": "not_retained"}
                removed_row["still_valid"] = is_instance_id_valid(int(key))
                removed.append(removed_row)
    var details: Dictionary = census["details"]
    var point: Dictionary = {"schema_id": "hh-studio.object-attribution-diagnostic",
        "schema_version": "1.0.0", "collector_variant": "compact_ids_summaries_v1",
        "formal_acceptance": false, "full_benchmark": false,
        "run_id": _input.run_id, "pid": OS.get_process_id(), "sequence": _object_probe_sequence,
        "label": label, "batch": _batch, "cycle": _cycle, "phase": Phase.keys()[_phase],
        "frame": Engine.get_process_frames(), "mono_us": now,
        "last_heartbeat_us": _last_heartbeat_us, "focused": get_window().has_focus(),
        "filesystem_scanning": EditorInterface.get_resource_filesystem().is_scanning(),
        "counters_before": before, "counters_after": after,
        "counters_equal_across_collection": before == after,
        "inventory_duration_us": collection_us, "previous_snapshot_write_us": _object_probe_last_write_us,
        "inventory_count": classes.size(), "class_counts": census["class_counts"],
        "unattributed_object_count": int(before.objects) - classes.size(),
        "inventory_complete_objectdb": false, "initial_inventory_ids_omitted": false,
        "initial_id_classes": initial_id_classes, "owner_tree_item_counts": census["owner_tree_item_counts"],
        "initial_tree_and_richtext_ids_included": true,
        "retained_identity_count": classes.size(), "retained_summary_count": summaries.size(),
        "descriptors_collected_this_sample": details.size(), "retained_ordinary_descriptors": 0,
        "content_change_coverage": "exact_class_Tree_and_RichTextLabel_summaries_only",
        "ordinary_baseline_content_changes_observed": false,
        "prior_metadata_for_ordinary_removals": "unknown_not_retained_even_if_emitted_when_added",
        "per_tree_count_coverage": "all_reachable_TreeItems; old_per_item_owner_not_retained",
        "added": added, "changed": changed, "removed": removed}
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
    # FileAccess is RefCounted: closing its OS handle does not release the Object.
    # Drop the local before the in-function ObjectDB self-drift readback.
    file = null
    if error != OK or DirAccess.rename_absolute(temporary, target) != OK:
        _fail("OBJECT_PROBE_PUBLISH")
        return
    if FileAccess.get_sha256(target) != _bytes_sha256(raw):
        _fail("OBJECT_PROBE_READBACK")
        return
    # Commit primitive retained state only after verified publication. New ordinary
    # descriptors belong to this sample's JSON and are not retained across calls.
    _object_probe_previous = classes
    _object_probe_previous_summaries = summaries
    _object_probe_signature = signature
    _object_probe_next_us = now + 10000000
    _object_probe_last_write_us = Time.get_ticks_usec() - write_started_us
    _object_probe_sequence += 1
    if before != after:
        _fail("OBJECT_PROBE_COUNTER_DRIFT")
        return
    if int(Performance.get_monitor(Performance.OBJECT_COUNT)) != int(before.objects):
        _fail("ATTRIBUTION_SELF_DRIFT")


func _object_probe_clear_retained() -> void:
    # A/B cost phase only. No Object/RefCounted references are stored here.
    _object_probe_previous.clear()
    _object_probe_previous_summaries.clear()
    _object_probe_signature.clear()
    # Do not reset sequence/byte cap and silently overwrite/rebase an output series.
    _object_probe_retained_cleared = true


func _object_probe_after_batch() -> void:
    _object_probe_sample("after_batch", true)
    if _failed:
        return
    if _batch == _batch_limit - 1:
        _object_probe_idle_until_us = Time.get_ticks_usec() + 120000000
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

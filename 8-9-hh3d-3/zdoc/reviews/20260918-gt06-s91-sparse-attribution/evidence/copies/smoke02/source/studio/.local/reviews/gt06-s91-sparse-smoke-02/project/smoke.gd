extends SceneTree

class SparseProbe:
    extends Node
    var _mode: String = "full"
    var _batch: int = 4
    var _input: Dictionary = {"run_id": "gt06-s91-sparse-smoke-02"}
    var _failed: bool = false
    var failures: PackedStringArray = PackedStringArray()
    var records: Dictionary = {}
    var output_directory: String = ""

    func _fail(code: String) -> void:
        _failed = true
        failures.append(code)

    func _write_new(name: String, value: Dictionary) -> Dictionary:
        if name not in ["sparse-00.json", "sparse-post-00.json", "sparse-01.json", "sparse-post-01.json", "serialization.json", "smoke-status.json"]:
            _fail("SMOKE_OUTPUT_NAME")
            return {}
        if output_directory not in ["res://out/tree_item_and_node", "res://out/tree_item_only"]:
            _fail("SMOKE_OUTPUT_DIRECTORY")
            return {}
        var target: String = output_directory + "/" + name
        var temporary: String = target + ".pending"
        if records.has(name) or FileAccess.file_exists(target) or FileAccess.file_exists(temporary):
            _fail("SMOKE_OUTPUT_EXISTS")
            return {}
        # Atomic per-name claim in this fresh private project; never overwrite.
        if DirAccess.make_dir_absolute(target + ".claim") != OK:
            _fail("SMOKE_OUTPUT_CLAIM")
            return {}
        var raw: PackedByteArray = (JSON.stringify(value, "", true, true) + "\n").to_utf8_buffer()
        if raw.size() > 1048576:
            _fail("SMOKE_OUTPUT_CAP")
            return {}
        var file: FileAccess = FileAccess.open(temporary, FileAccess.WRITE)
        if file == null:
            _fail("SMOKE_OUTPUT_OPEN")
            return {}
        file.store_buffer(raw)
        file.flush()
        var error: Error = file.get_error()
        file.close()
        file = null
        if error != OK or DirAccess.rename_absolute(temporary, target) != OK:
            _fail("SMOKE_OUTPUT_PUBLISH")
            return {}
        var digest: String = raw.get_string_from_utf8().sha256_text()
        if FileAccess.get_sha256(target) != digest:
            _fail("SMOKE_OUTPUT_READBACK")
            return {}
        records[name] = value
        return {"sha256": digest, "size_bytes": raw.size()}

    # S91_SPARSE_HELPER_BOUNDARY
    # Disposable diagnostic only. Census retains primitive IDs, never Objects or content.
    const S91_ID_CAP: int = 32768
    const S91_SNAPSHOT_CAP: int = 2
    
    var _s91_baseline: Dictionary = {}
    var _s91_baseline_objects: int = -1
    var _s91_snapshot_count: int = 0
    
    
    func _s91_counters() -> Dictionary:
        return {
            "objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
            "resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
            "nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
            "orphan_nodes": int(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT))
        }
    
    
    func _s91_tree_items(tree: Tree, remaining: int) -> Dictionary:
        var ids: PackedInt64Array = PackedInt64Array()
        var item: TreeItem = tree.get_root()
        while item != null:
            if ids.size() >= remaining:
                return {"complete": false, "ids": ids}
            ids.append(item.get_instance_id())
            var child: TreeItem = item.get_first_child()
            if child != null:
                item = child
                continue
            while item != null and item.get_next() == null:
                item = item.get_parent()
            if item != null:
                item = item.get_next()
        ids.sort()
        return {"complete": true, "ids": ids}
    
    
    func _s91_collect() -> Dictionary:
        var trees: Dictionary = {}
        var nodes: PackedInt64Array = PackedInt64Array()
        var total: int = 0
        var items_total: int = 0
        # Native filtering includes internal nodes; owned=false includes editor internals.
        # The only Node/TreeItem variables live in these synchronous helper frames.
        var found_trees: Array[Node] = get_tree().root.find_children("*", "Tree", true, false)
        for candidate: Node in found_trees:
            if total >= S91_ID_CAP:
                return {"complete": false, "trees": trees, "node3d_ids": nodes, "id_count": total, "tree_item_count": items_total}
            total += 1
            var tree: Tree = candidate as Tree
            var row: Dictionary = _s91_tree_items(tree, S91_ID_CAP - total)
            var item_ids: PackedInt64Array = row.ids
            trees[tree.get_instance_id()] = item_ids
            total += item_ids.size()
            items_total += item_ids.size()
            if not row.complete:
                return {"complete": false, "trees": trees, "node3d_ids": nodes, "id_count": total, "tree_item_count": items_total}
        found_trees.clear()
        var found_nodes: Array[Node] = get_tree().root.find_children("*", "Node3D", true, false)
        for node: Node in found_nodes:
            if total >= S91_ID_CAP:
                return {"complete": false, "trees": trees, "node3d_ids": nodes, "id_count": total, "tree_item_count": items_total}
            nodes.append(node.get_instance_id())
            total += 1
        found_nodes.clear()
        nodes.sort()
        return {"complete": true, "trees": trees, "node3d_ids": nodes, "id_count": total, "tree_item_count": items_total}
    
    
    func _s91_difference(old_ids: PackedInt64Array, new_ids: PackedInt64Array) -> Dictionary:
        var added: PackedInt64Array = PackedInt64Array()
        var removed: PackedInt64Array = PackedInt64Array()
        var removed_valid: PackedInt64Array = PackedInt64Array()
        var old_pos: int = 0
        var new_pos: int = 0
        while old_pos < old_ids.size() or new_pos < new_ids.size():
            if old_pos >= old_ids.size():
                added.append(new_ids[new_pos])
                new_pos += 1
            elif new_pos >= new_ids.size() or old_ids[old_pos] < new_ids[new_pos]:
                var removed_id: int = old_ids[old_pos]
                removed.append(removed_id)
                if is_instance_id_valid(removed_id):
                    removed_valid.append(removed_id)
                old_pos += 1
            elif new_ids[new_pos] < old_ids[old_pos]:
                added.append(new_ids[new_pos])
                new_pos += 1
            else:
                old_pos += 1
                new_pos += 1
        return {"added": added, "removed": removed, "removed_still_valid": removed_valid,
            "net_count": new_ids.size() - old_ids.size()}
    
    
    func _s91_delta(current: Dictionary) -> Dictionary:
        var old_trees: Dictionary = _s91_baseline.trees
        var new_trees: Dictionary = current.trees
        var tree_ids: PackedInt64Array = PackedInt64Array()
        for tree_id: int in old_trees:
            tree_ids.append(tree_id)
        for tree_id: int in new_trees:
            if not old_trees.has(tree_id):
                tree_ids.append(tree_id)
        tree_ids.sort()
        var trees: Dictionary = {}
        for tree_id: int in tree_ids:
            var old_ids: PackedInt64Array = old_trees.get(tree_id, PackedInt64Array())
            var new_ids: PackedInt64Array = new_trees.get(tree_id, PackedInt64Array())
            var delta: Dictionary = _s91_difference(old_ids, new_ids)
            if not delta.added.is_empty() or not delta.removed.is_empty() or old_trees.has(tree_id) != new_trees.has(tree_id):
                delta["tree_existed_before"] = old_trees.has(tree_id)
                delta["tree_exists_now"] = new_trees.has(tree_id)
                delta["tree_still_valid"] = is_instance_id_valid(tree_id)
                trees[tree_id] = delta
        return {"trees": trees, "node3d_ids": _s91_difference(_s91_baseline.node3d_ids, current.node3d_ids),
            "target_net_count": int(current.id_count) - int(_s91_baseline.id_count)}
    
    
    func _s91_before_batch() -> void:
        if _mode != "full" or _s91_snapshot_count >= S91_SNAPSHOT_CAP:
            return
        var before: Dictionary = _s91_counters()
        var baseline: bool = _batch == 4 and _s91_snapshot_count == 0
        var growth: bool = _batch > 4 and _s91_baseline_objects >= 0 and int(before.objects) > _s91_baseline_objects
        if not baseline and not growth:
            return
        var started: int = Time.get_ticks_usec()
        var frame: int = Engine.get_process_frames()
        var static_before: int = int(Performance.get_monitor(Performance.MEMORY_STATIC))
        var current: Dictionary = _s91_collect()
        # _s91_collect returned; all Node arrays and local Object variables are gone.
        var after: Dictionary = _s91_counters()
        var collected: int = Time.get_ticks_usec()
        var static_after: int = int(Performance.get_monitor(Performance.MEMORY_STATIC))
        var complete: bool = bool(current.complete)
        var delta: Dictionary = _s91_delta(current) if growth and complete else {}
        var point: Dictionary = {
            "schema_id": "hh-studio.gt06.s91-sparse-attribution", "schema_version": "1.0.0",
            "run_id": _input.run_id, "pid": OS.get_process_id(), "batch": _batch,
            "sequence": _s91_snapshot_count, "phase": "before_batch_counter_readback",
            "trigger": "baseline_batch4" if baseline else "first_prepublication_object_growth",
            "partial_inventory": true, "complete_within_target_scope": complete,
            "target_scope": "reachable_Tree_owned_TreeItems_and_reachable_Node3D_family",
            "formal_acceptance": false, "eligible_for_dataset": false,
            "id_cap": S91_ID_CAP, "snapshot_cap": S91_SNAPSHOT_CAP,
            "object_references_retained": false, "user_content_collected": false,
            "before": before, "after_collection": after, "counter_self_drift": before != after,
            "started_mono_us": started, "collected_mono_us": collected,
            "collection_elapsed_us": collected - started, "process_frame": frame,
            "static_before_bytes": static_before, "static_after_collection_bytes": static_after,
            "baseline_objects": int(before.objects) if baseline else _s91_baseline_objects,
            "object_delta_from_baseline": 0 if baseline else int(before.objects) - _s91_baseline_objects,
            "target_id_count": current.id_count, "tree_count": current.trees.size(),
            "tree_item_count": current.tree_item_count, "node3d_count": current.node3d_ids.size(),
            "baseline_primitive_inventory": current if baseline else {}, "delta": delta
        }
        var receipt: Dictionary = _write_new("sparse-%02d.json" % _s91_snapshot_count, point)
        if receipt.is_empty():
            _fail("S91_SPARSE_WRITE")
            return
        var after_publication: Dictionary = _s91_counters()
        var post: Dictionary = _write_new("sparse-post-%02d.json" % _s91_snapshot_count, {
            "schema_id": "hh-studio.gt06.s91-sparse-post", "schema_version": "1.0.0",
            "run_id": _input.run_id, "batch": _batch, "sequence": _s91_snapshot_count,
            "snapshot_sha256": receipt.sha256, "before": before, "after_publication": after_publication,
            "counter_self_drift": before != after_publication,
            "through_snapshot_publication_elapsed_us": Time.get_ticks_usec() - started,
            "static_after_publication_bytes": int(Performance.get_monitor(Performance.MEMORY_STATIC)),
            "formal_acceptance": false, "eligible_for_dataset": false
        })
        if post.is_empty():
            _fail("S91_SPARSE_POST_WRITE")
            return
        if not complete:
            _fail("S91_ID_CAP")
            return
        if before != after or before != after_publication or before != _s91_counters():
            _fail("S91_COUNTER_SELF_DRIFT")
            return
        if baseline:
            _s91_baseline = current
            _s91_baseline_objects = int(before.objects)
        _s91_snapshot_count += 1

# END_EXACT_INDENTED_S91_HELPER

var checks: Dictionary = {}

func _initialize() -> void:
    _run.call_deferred()

func _check(name: String, passed: bool) -> void:
    checks[name] = passed

func _run_arm(arm: String, include_node: bool) -> bool:
    checks.clear()
    var probe: SparseProbe = SparseProbe.new()
    probe.output_directory = "res://out/" + arm
    root.add_child(probe)
    var tree: Tree = Tree.new()
    probe.add_child(tree)
    var root_item: TreeItem = tree.create_item()
    var child_item: TreeItem = tree.create_item(root_item)
    var original_node: Node3D = Node3D.new()
    probe.add_child(original_node)
    var expected: Dictionary = {"tree_id": str(tree.get_instance_id()),
        "root_item_id": str(root_item.get_instance_id()), "child_item_id": str(child_item.get_instance_id()),
        "original_node_id": str(original_node.get_instance_id())}
    probe._batch = 4
    probe._s91_before_batch()
    _check("baseline_helper_not_failed", not probe._failed)
    _check("baseline_one_snapshot", probe._s91_snapshot_count == 1)
    if probe.records.has("sparse-00.json"):
        var baseline: Dictionary = probe.records["sparse-00.json"]
        _check("baseline_self_drift_false", baseline.counter_self_drift == false)
        _check("baseline_original_counter_delta_zero", baseline.before == baseline.after_collection)
        _check("baseline_target_counts", baseline.tree_count == 1 and baseline.tree_item_count == 2 and baseline.node3d_count == 1 and baseline.target_id_count == 4)
        _check("baseline_partial_inventory", baseline.partial_inventory == true and baseline.complete_within_target_scope == true)
    else:
        _check("baseline_record_exists", false)
    # Godot 4.7.2 TreeItem::Cell instantiates one TextParagraph per column.
    # https://github.com/godotengine/godot/blob/4.7.2-stable/scene/gui/tree.h#L124
    var before_creation: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    var added_item: TreeItem = tree.create_item(root_item)
    var after_item_creation: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    expected["added_item_id"] = str(added_item.get_instance_id())
    if include_node:
        var added_node: Node3D = Node3D.new()
        probe.add_child(added_node)
        expected["added_node_id"] = str(added_node.get_instance_id())
    var after_node_creation: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    var expected_object_delta: int = 3 if include_node else 2
    var expected_target_delta: int = 2 if include_node else 1
    _check("one_column_tree", tree.columns == 1)
    _check("tree_item_creation_adds_two_objects", after_item_creation - before_creation == 2)
    _check("node_creation_delta_expected", after_node_creation - after_item_creation == (1 if include_node else 0))
    _check("no_drift_before_controlled_creation", before_creation == probe._s91_baseline_objects)
    probe._batch = 5
    probe._s91_before_batch()
    _check("growth_helper_not_failed", not probe._failed)
    _check("growth_two_snapshots", probe._s91_snapshot_count == 2)
    if probe.records.has("sparse-01.json"):
        var growth: Dictionary = probe.records["sparse-01.json"]
        _check("growth_self_drift_false", growth.counter_self_drift == false)
        _check("growth_original_counter_delta_expected", growth.object_delta_from_baseline == expected_object_delta)
        _check("growth_target_net_count_expected", growth.delta.target_net_count == expected_target_delta)
        _check("growth_node_delta_expected", growth.delta.node3d_ids.net_count == (1 if include_node else 0))
        _check("growth_tree_delta_one", growth.delta.trees[tree.get_instance_id()].net_count == 1)
    else:
        _check("growth_record_exists", false)
    var writes_before_third: int = probe.records.size()
    probe._batch = 6
    probe._s91_before_batch()
    _check("third_snapshot_capped", probe._s91_snapshot_count == 2 and probe.records.size() == writes_before_third)
    _check("no_third_snapshot_file", not FileAccess.file_exists(probe.output_directory + "/sparse-02.json"))
    for name: String in ["sparse-post-00.json", "sparse-post-01.json"]:
        _check(name + "_self_drift_false", probe.records.has(name) and probe.records[name].counter_self_drift == false)
    var packed_ids: PackedInt64Array = PackedInt64Array([9007199254740993, 9223372036854775807, -9007199254740993, -9223372036854775807])
    var keyed_ids: Dictionary = {}
    for value: int in packed_ids:
        keyed_ids[value] = str(value)
    var serial_receipt: Dictionary = probe._write_new("serialization.json", {"packed_ids": packed_ids, "id_keys": keyed_ids})
    _check("serialization_written", not serial_receipt.is_empty())
    var passed: bool = not probe._failed
    for value: bool in checks.values():
        passed = passed and value
    var status: Dictionary = {"schema_id": "hh-studio.gt06.s91-controlled-smoke", "schema_version": "1.0.0",
        "run_id": "gt06-s91-sparse-smoke-02", "helper_sha256": "0837a4a6d21715c3706ce376750dc2f28ebae7f4f214f2988b4ea90a71a25281", "passed": passed, "arm": arm,
        "checks": checks, "expected_ids": expected, "helper_failures": probe.failures,
        "expected_growth": {"objects": expected_object_delta, "target_ids": expected_target_delta,
            "TreeItem": 1, "TextParagraph": 1, "Node3D": 1 if include_node else 0},
        "controlled_creation": {"before": before_creation, "after_tree_item": after_item_creation, "after_node3d": after_node_creation},
        "ownership_source": "Godot4.7.2 TreeItem::Cell owns one TextParagraph per column; this fixture has one column",
        "s86_root_cause_claim": false,
        "formal_acceptance": false, "eligible_for_dataset": false}
    var status_receipt: Dictionary = probe._write_new("smoke-status.json", status)
    passed = passed and not status_receipt.is_empty() and not probe._failed
    print("HH_S91_CONTROLLED_SMOKE " + JSON.stringify(status, "", true, true))
    probe.free()
    return passed

func _run() -> void:
    var pair_passed: bool = _run_arm("tree_item_and_node", true)
    var item_passed: bool = _run_arm("tree_item_only", false)
    quit(0 if pair_passed and item_passed else 1)

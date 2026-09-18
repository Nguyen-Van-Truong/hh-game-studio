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

"""Read-only compact census arithmetic; not Godot/process/campaign verification."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def valid_id(value):
    return type(value) is str and re.fullmatch(r"-?[1-9][0-9]*", value) is not None \
        and -(2**63) <= int(value) < 2**63


def row_map(rows):
    result = {}
    for row in rows:
        require(valid_id(row.get("id")) and type(row.get("class")) is str, "row ID/class")
        require(row["id"] not in result, "duplicate row ID")
        result[row["id"]] = row
    return result


def diff(before, after):
    return {key: after.get(key, 0) - before.get(key, 0)
            for key in sorted(before.keys() | after.keys()) if before.get(key, 0) != after.get(key, 0)}


def reconstruct(points):
    require(bool(points), "no snapshots")
    membership, reports, previous = {}, [], None
    baseline = points[0]
    for sequence, point in enumerate(points):
        require(point["collector_variant"] == "compact_ids_summaries_v1" and point["sequence"] == sequence,
                "compact variant/contiguous sequence")
        require(point["run_id"] == baseline["run_id"] and point["pid"] == baseline["pid"], "run/PID changed")
        require(point["retained_ordinary_descriptors"] == 0
                and point["ordinary_baseline_content_changes_observed"] is False,
                "compact content coverage changed")
        require(point["counters_before"] == point["counters_after"]
                and point["counters_equal_across_collection"] is True, "collection counter drift")
        for number in (point["inventory_count"], point["counters_before"]["objects"],
                       *point["class_counts"].values(), *point["owner_tree_item_counts"].values()):
            require(type(number) is int and number >= 0, "invalid integer counter")
        added, removed, changed = (row_map(point[k]) for k in ("added", "removed", "changed"))
        require(not (added.keys() & removed.keys() or added.keys() & changed.keys()
                     or changed.keys() & removed.keys()), "overlapping delta sets")
        unknown = []
        if sequence == 0:
            require(not removed and not changed, "baseline contains changes/removals")
            membership = dict(point["initial_id_classes"])
            require(all(valid_id(k) and type(v) is str for k, v in membership.items()), "baseline ID/classes")
            require(all(membership.get(k) == row["class"] and row["class"] in ("Tree", "RichTextLabel")
                        for k, row in added.items()), "baseline descriptors are not selected summaries")
        else:
            require(not point["initial_id_classes"], "repeated baseline map")
            for key, row in removed.items():
                require(membership.get(key) == row["class"], "removed ID/class absent from prior census")
                require(type(row.get("still_valid")) is bool, "removed validity not observed")
                if row["class"] not in ("Tree", "RichTextLabel"):
                    require(row.get("old_metadata_available") is False
                            and row.get("old_metadata_scope") == "not_retained", "ordinary old metadata scope")
                    unknown.append(key)
                membership.pop(key)
            for key, row in added.items():
                require(key not in membership, "added ID already present")
                membership[key] = row["class"]
            for key, row in changed.items():
                require(membership.get(key) == row["class"] and row["class"] in ("Tree", "RichTextLabel"),
                        "changed row outside summary coverage")
        require(len(membership) == point["inventory_count"]
                and dict(Counter(membership.values())) == point["class_counts"], "reconstructed census mismatch")
        owners = point["owner_tree_item_counts"]
        require(sum(owners.values()) == point["class_counts"].get("TreeItem", 0)
                and all(owner in membership and membership[owner] != "TreeItem" for owner in owners),
                "owner TreeItem count mismatch")
        objects, reachable = point["counters_before"]["objects"], point["inventory_count"]
        require(objects - reachable == point["unattributed_object_count"] >= 0, "residual arithmetic")
        require(point["retained_identity_count"] == reachable, "retained identity count")
        summary_count = sum(value in ("Tree", "RichTextLabel") for value in membership.values())
        require(point["retained_summary_count"] == summary_count, "retained summary count")
        delta = None
        if previous is not None:
            delta_objects = objects - previous["counters_before"]["objects"]
            delta_reachable = reachable - previous["inventory_count"]
            require(delta_reachable == len(added) - len(removed), "delta arithmetic")
            delta = {"added_count": len(added), "removed_count": len(removed), "changed_summary_count": len(changed),
                "objectdb_net": delta_objects, "reachable_net": delta_reachable,
                "unattributed_net": delta_objects - delta_reachable,
                "class_net": diff(previous["class_counts"], point["class_counts"]),
                "owner_tree_count_net": diff(previous["owner_tree_item_counts"], owners),
                "removed_ids_with_unknown_prior_metadata": unknown,
                "removed_still_valid": [key for key, row in removed.items() if row["still_valid"]],
                "added_rows": list(added.values()), "changed_summaries": list(changed.values()),
                "objectdb_since_baseline": objects - baseline["counters_before"]["objects"],
                "reachable_since_baseline": reachable - baseline["inventory_count"]}
        reports.append({"sequence": sequence, "objects": objects, "reachable": reachable,
                        "unattributed": objects - reachable, "delta": delta})
        previous = point
    return {"authority": 0, "formal_acceptance": False, "scope": "published compact census arithmetic only",
            "ordinary_content_changes_observed": False, "initial_ids_are_not_growth": True,
            "godot_execution_verified": False, "publication_receipts_verified": False, "snapshots": reports}


def main():
    require(len(sys.argv) > 1, "supply published object-NNNN.json paths in sequence order")
    raw = [(Path(name), Path(name).read_bytes()) for name in sys.argv[1:]]
    result = reconstruct([json.loads(data) for _, data in raw])
    result["inputs"] = [{"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
                        for path, data in raw]
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

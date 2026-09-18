# S90_LIFECYCLE_HELPER_BOUNDARY

var _s90_batch_objects: int = -1
var _s90_batch_resources: int = -1
var _s90_batch_mono_us: int = -1

func _s90_write_lifecycle(batch: int, ack_preopen: int, after_close: int, after_release: int, batch_objects: int, batch_resources: int, ack_objects: int, ack_resources: int, batch_mono_us: int, process_frame: int) -> void:
    var receipt: Dictionary = _write_new("lifecycle-%02d.json" % batch, {
        "schema_id": "hh-studio.gt06.s90-lifecycle",
        "schema_version": "1.0.0",
        "run_id": _input.run_id,
        "batch": batch,
        "object_count_at_batch_publish": batch_objects,
        "resource_count_at_batch_publish": batch_resources,
        "batch_publish_mono_us": batch_mono_us,
        "object_count_at_ack_preopen": ack_preopen,
        "object_count_after_file_close": after_close,
        "object_count_after_file_release": after_release,
        "object_delta_close_to_release": after_release - after_close,
        "object_count_after_fresh_ack": ack_objects,
        "resource_count_after_fresh_ack": ack_resources,
        "object_delta_batch_to_fresh_ack": ack_objects - batch_objects,
        "object_delta_ack_preopen_to_fresh_ack": ack_objects - ack_preopen,
        "process_frame": process_frame,
        "formal_acceptance": false,
        "eligible_for_dataset": false
    })
    if receipt.is_empty():
        _fail("S90_LIFECYCLE_WRITE")

extends SceneTree
func _init() -> void:
    print("S171_START pid=%d" % OS.get_process_id())
    print("S171_READY")
    await create_timer(6.0).timeout
    var fh := FileAccess.open("user://s171-held.bin", FileAccess.WRITE)
    if fh == null:
        print("S171_OPEN_FAILED")
        quit(2)
        return
    print("S171_OPEN")
    await create_timer(5.0).timeout
    fh.close()
    print("S171_CLOSE")
    await create_timer(0.5).timeout
    print("S171_EXIT")
    quit(0)

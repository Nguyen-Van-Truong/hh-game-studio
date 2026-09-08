extends CanvasLayer

@onready var score_label: Label = $Root/TopBar/Score
@onready var time_label: Label = $Root/TopBar/Time
@onready var hint_label: Label = $Root/Hint
@onready var overlay: ColorRect = $Root/Overlay
@onready var overlay_title: Label = $Root/Overlay/Title
@onready var overlay_body: Label = $Root/Overlay/Body
@onready var hit_marker: ColorRect = $Root/HitMarker


func _ready() -> void:
	hit_marker.modulate.a = 0.0
	show_overlay(
		"NIGHT ROOM FPS",
		"Click to start\nWASD move  •  Mouse look  •  Left click shoot\nSpace jump  •  Shift sprint  •  Esc pause  •  R restart"
	)


func set_score(value: int) -> void:
	score_label.text = "SCORE  %d" % value


func set_time(seconds: float) -> void:
	var t: int = maxi(int(ceil(seconds)), 0)
	time_label.text = "TIME  %02d" % t


func set_hint(text: String) -> void:
	hint_label.text = text


func show_overlay(title: String, body: String) -> void:
	overlay.visible = true
	overlay_title.text = title
	overlay_body.text = body


func hide_overlay() -> void:
	overlay.visible = false


func flash_hit() -> void:
	hit_marker.modulate.a = 0.9
	var tw := create_tween()
	tw.tween_property(hit_marker, "modulate:a", 0.0, 0.12)

class_name ArenaSkin
extends RefCounted
## Original Relay Yard architecture. These background panels, utility pipes and
## foundation faces never create colliders. Gameplay surfaces remain in the map.
## Keep quiet back-wall values below the bright collision edges and fighter art.

static func draw_foundation(c: CanvasItem, size: Vector2, floor_y: float) -> void:
	# Foundation has depth and service markings. The service pit stays black.
	c.draw_rect(Rect2(112.0, floor_y + 12.0, size.x - 112.0, 100.0), Color("#142234"))
	for x: int in range(120, int(size.x), 96):
		c.draw_rect(Rect2(x, floor_y + 24.0, 85.0, 56.0), Color("#0b1424"))
		c.draw_line(Vector2(x, floor_y + 24.0), Vector2(x + 85.0, floor_y + 24.0), Color("#30445e"), 2.0)
		c.draw_line(Vector2(x + 7.0, floor_y + 74.0), Vector2(x + 78.0, floor_y + 30.0), Color("#20334c"), 3.0)

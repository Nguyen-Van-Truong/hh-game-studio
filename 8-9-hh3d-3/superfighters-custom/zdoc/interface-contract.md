# HỢP ĐỒNG GIAO DIỆN KỸ THUẬT (INTERFACE CONTRACT) — `superfighters-y8`

Tài liệu này quy định chính xác tên class, hàm, thuộc tính và cấu trúc dữ liệu giữa các module để đảm bảo tích hợp 100% không lệch pha.

---

## 1. QUY ƯỚC HỆ TỌA ĐỘ TRONG `data/sf_compiled_*.json`

1. **`sf_compiled_maps.json`**:
   - **`bg_layers` & `fg_layers`**:
     * Mỗi layer có `path` (`res://assets/maps/...`), `tx`, `ty`, `sx`, `sy`.
     * Tạo `Sprite2D` với `centered = false`, `position = Vector2(tx, ty)`, `scale = Vector2(sx, sy)`.
     * `bg_layers` có `z_index = -10`; `fg_layers` (lớp che hố thang máy/cửa `levels_front`) có `z_index = 20` (vẽ đè lên trước nhân vật khi đi vào hố thang máy/cổng).
   - **`ground_boxes`**:
     * **CỰC KỲ QUAN TRỌNG**: Trong `ground_boxes`, `(x, y)` là **tâm Box2D (`center_x, center_y`)**, còn `(w, h)` là **chiều rộng và chiều cao toàn phần**.
     * Hình chữ nhật thế giới là: `Rect2(x - w * 0.5, y - h * 0.5, w, h)` (mặt sàn trên cùng ở `top_y = y - h * 0.5`).
     * Phân loại theo mảng `tags`:
       - Nếu `"LADDER" in tags`: Đây là **vùng thang leo (`Ladder`)**, KHÔNG tạo va chạm rắn chặn người chơi; đăng ký vào mảng `map_loader.ladder_rects: Array[Rect2]`.
       - Nếu `"CLOUD" in tags`: Đây là **sàn một chiều (`One-Way Cloud Platform`)**, chỉ đỡ người chơi/vật thể khi rơi từ trên xuống (`vel.y >= 0`) và không bật trạng thái `drop_through`; đăng ký vào `map_loader.cloud_rects: Array[Rect2]` (và tạo `StaticBody2D` với `one_way_collision = true`).
       - Ngược lại (`"NONE" in tags` hoặc mặc định): Đây là **tường/sàn đặc (`Solid Ground`)**, đăng ký vào `map_loader.solid_rects: Array[Rect2]` (và tạo `StaticBody2D`).
   - **`ground_polygons` (Cầu thang nghiêng / Slopes)**:
     * Đặt tại tâm `(x, y)`, danh sách đỉnh `vertices` là tọa độ local so với `(x, y)`, có `tilt_value`. Đăng ký vào `map_loader.slope_polygons: Array[Dictionary]`.
   - **`elevators`**:
     * `{var_name, type, direction, x, y, distance, speed}`: Sàn nâng một chiều (`DrawCloudBox = true`), dao động hình sin quanh tâm hành trình với tổng quãng đường `distance` và tốc độ góc `speed` rad/s.
   - **`portals`**:
     * `{entry_rect: [x, y, w, h], exit_rect: [x, y, w, h], dir: [dx, dy], door_open, ignore_vel}`.
   - **`glasses`**:
     * `{x1, y1, x2, y2}`: Tấm kính nối từ `(x1, y1)` đến `(x2, y2)`, dày `3 px`, `hp = 5.0`.

2. **`sf_compiled_rigs.json`**:
   - Với state có `type == "full_body"`:
     * Lấy frame hiện tại từ `frames` (mảng đã trải phẳng từng frame 24Hz) hoặc `keyframes`.
     * Mỗi frame có `rect: [u, v, w, h]` trên tấm sheet `600x400` và `pivot: [tx, ty]` tính từ điểm đáy chân `(0, 0)`.
     * `BodySprite` (`centered = false`) đặt `position = Vector2(pivot[0], pivot[1])`.
   - Với state có `type == "split_rig"` (`START_*` và `AIM_*`):
     * `torso.frames[0]`: vẽ thân không tay trên `BodySprite` tại `Vector2(torso_frame.pivot[0], torso_frame.pivot[1])`.
     * `weapon_arm`:
       - Đặt `AimPivot.position = Vector2(shoulder_pivot[0], shoulder_pivot[1])` (`Vector2(-3.0, -12.0)`).
       - Xoay `AimPivot.rotation = deg_to_rad(current_aim_pitch)`.
       - Chọn frame trong `weapon_arm.frames` theo `weapon_anim_frame_nr` (mặc định `1`, khi bắn chuyển theo `FireSequence[step].frame_nr`).
       - Trên `WeaponArmSprite` (`centered = false`, con của `AimPivot`), đặt `position = Vector2(arm_frame.pivot[0], arm_frame.pivot[1])`.
       - Đặt `MuzzleSocket.position = Vector2(arm_frame.muzzle_center[0], arm_frame.muzzle_center[1])`, `ShellSocket.position = Vector2(arm_frame.shell_center[0], arm_frame.shell_center[1])`.

---

## 2. GIAO DIỆN CÁC CLASS CỐT LÕI (`class_name` & Public API)

### 2.1. `FighterController` (`game/fighter/fighter_controller.gd`, `class_name FighterController extends CharacterBody2D`)
- **Thuộc tính chính**:
  - `var slot_index: int = 0` (`0` = P1, `1` = P2, `2..7` = Bots)
  - `var team_id: int = 0` (`0` = Free-for-all, `1..4` = Team)
  - `var character_id: String = "johnny"`
  - `var display_name: String = "Johnny"`
  - `var is_bot: bool = false`
  - `var bot_difficulty: int = 2` (`1` = Easy, `2` = Medium, `3` = Hard)
  - `var hp: float = 100.0`, `var max_hp: float = 100.0`
  - `var sprint_energy: float = 100.0`, `var max_sprint_energy: float = 100.0`
  - `var is_dead: bool = false`, `var is_gibbed: bool = false`
  - `var facing: int = 1` (`1` = Phải, `-1` = Trái)
  - `var current_state: String = "IDLE"`
  - `var on_ground: bool = false`, `var sprinting: bool = false`, `var kneeling: bool = false`, `var taking_cover: bool = false`
  - `var rolling: bool = false`, `var diving: bool = false`, `var climbing: bool = false`, `var falling: bool = false`, `var knockdowned: bool = false`
  - `var aiming: bool = false`, `var aim_mode: int = 0` (`0` = Gun, `1` = Throwable)
  - `var current_aim_pitch: float = 0.0` (độ, `-90..+90`)
  - `var burn_state: float = 0.0`, `var burned: bool = false`
  - `var cover_object_id: int = -1`
  - `var air_velocity: Vector2 = Vector2.ZERO` (đơn vị px/frame 24Hz)
  - `var inventory: Dictionary = {1: "FISTS", 2: "", 3: "", 4: "", 5: ""}` + `var inventory_ammo: Dictionary = {1: -1, 2: 0, 3: 0, 4: 0, 5: 0}`
  - `var active_gun_slot: int = 2` (`2` = Sidearm, `3` = Primary)
  - `var rig_view: Node2D = null` (`FighterRigView`)
  - `var match_world: Node2D = null` (tham chiếu tới `MatchController`)
- **Hàm Public bắt buộc**:
  - `func setup_fighter(p_slot: int, p_char_id: String, p_pos: Vector2, p_is_bot: bool = false, p_team: int = 0, p_diff: int = 2) -> void`
  - `func step_fighter(step_24hz: float, input_state: Dictionary) -> void`
    *(Nếu `input_state` rỗng và `!is_bot`, tự đọc từ `Input` theo `p1_*` hoặc `p2_*`; nếu `is_bot`, đọc từ `bot_brain_input`).*
  - `func get_mid_pos() -> Vector2` (`Vector2(global_position.x, global_position.y - 8.0)` khi đứng, `-6.0` khi cúi, `-3.0` khi nằm)
  - `func get_hit_rect() -> Rect2` (trả về hình chữ nhật thế giới `Rect2(global_position.x - 6.0, global_position.y - height, 12.0, height)`)
  - `func apply_bullet_hit(damage: float, pushback: float, dir_x: int, is_crit: bool, hit_pos: Vector2, is_rocket: bool = false) -> bool` (trả về `false` nếu né được nhờ Roll/Dive 90%/50%)
  - `func apply_melee_hit(damage: float, dir_x: int, is_finisher: bool, is_kick: bool, is_jump_kick: bool, attacker: Node2D = null) -> void`
  - `func apply_explosion_hit(angle_rad: float, power: float, damage: float) -> void`
  - `func add_burn(amount: float, set_full: bool = false) -> void`
  - `func force_fall(vx: float, vy: float, knockdown: bool = false) -> void`
  - `func equip_weapon(weapon_id: String, ammo_override: int = -999) -> void`
  - `func get_active_weapon_id() -> String`
  - `func get_active_weapon_ammo() -> int`

### 2.2. `ProjectileManager` (`game/world/projectile_manager.gd`, `class_name ProjectileManager extends Node2D`)
- `var match_world: Node2D = null`
- `func step_projectiles(step_24hz: float) -> void`
- `func spawn_bullet(owner_fighter: Node2D, weapon_id: String, start_pos: Vector2, angle_deg: float, ignore_cover_id: int = -1) -> void`
- `func spawn_throwable(owner_fighter: Node2D, weapon_id: String, start_pos: Vector2, angle_deg: float, remaining_fuse_frames: float = 72.0) -> void`
- `func deflect_bullets_in_box(deflector: Node2D, rect: Rect2, facing_dir: int) -> int`
- `func clear_all() -> void`

### 2.3. `FireHazardSystem` (`game/world/fire_hazard_system.gd`, `class_name FireHazardSystem extends Node2D`)
- `var match_world: Node2D = null`
- `func step_hazards(step_24hz: float) -> void`
- `func trigger_explosion(world_pos: Vector2, base_radius: float = 33.0, player_damage: float = 20.0, player_power: float = 5.0, source_fighter: Node2D = null) -> void`
- `func trigger_fire_burst(source_type: String, world_pos: Vector2, count: int = 18) -> void`
- `func spawn_flamethrower_particle(world_pos: Vector2, angle_deg: float, source_fighter: Node2D = null) -> void`
- `func spawn_muzzle_flash(world_pos: Vector2, angle_deg: float) -> void`
- `func spawn_shell_casing(world_pos: Vector2, eject_dir: int) -> void`
- `func spawn_hit_sparks(world_pos: Vector2, is_blood: bool = false) -> void`
- `func spawn_glass_shards(p1: Vector2, p2: Vector2, impact_vel: Vector2) -> void`
- `func spawn_gibs(world_pos: Vector2, impulse: Vector2) -> void`
- `func clear_all() -> void`

### 2.4. `MapLoader` (`game/world/map_loader.gd`, `class_name MapLoader extends Node2D`)
- `var match_world: Node2D = null`
- `var current_map_id: String = "rooftops"`
- `var map_bounds: Rect2 = Rect2(-12, -110, 583, 510)`
- `var solid_rects: Array[Rect2] = []`
- `var cloud_rects: Array[Rect2] = []`
- `var ladder_rects: Array[Rect2] = []`
- `var slope_polygons: Array[Dictionary] = []`
- `var portals: Array[Dictionary] = []`
- `var elevators: Array[Dictionary] = []`
- `var glasses: Array[Dictionary] = []`
- `var player_spawns: Array[Vector2] = []`
- `var weapon_spawns: Array[Dictionary] = []`
- `var ai_nodes: Array[Dictionary] = []`
- `var ai_binds: Array[Dictionary] = []`
- `func load_map(map_id: String) -> void`
- `func step_map(step_24hz: float) -> void` (cập nhật vị trí mây trôi, thang máy `elevators`, kiểm tra `portals`)
- `func is_point_solid(pt: Vector2, include_clouds: bool = false) -> bool`
- `func raycast_solid(from_pt: Vector2, to_pt: Vector2, ignore_cover_id: int = -1) -> Dictionary` (trả về `{hit: bool, pos: Vector2, normal: Vector2, prop: Node2D, glass_idx: int}`)
- `func check_and_break_glass_segment(from_pt: Vector2, to_pt: Vector2, impact_vel: Vector2) -> bool`
- `func get_ladder_at(pt: Vector2) -> Rect2`
- `func find_cover_prop_near(pt: Vector2, dir_x: int) -> int`

### 2.5. `MatchController` (`game/core/match_controller.gd`, `class_name MatchController extends Node2D`)
- Quản lý toàn bộ `map_loader`, `projectile_manager`, `fire_hazard_system`, `dynamic_camera`, `fighters: Array[Node2D]`, `props: Array[Node2D]`, `pickups: Array[Dictionary]`.
- `func start_match(config: Dictionary) -> void`
  * `config` hỗ trợ: `mode` (`"vs"`, `"stage"`, `"survival"`), `map_id` (mặc định `"rooftops"`), `two_player` (`true`/`false`), `p1_char` (`"johnny"`), `p2_char` (`"agent"`), `bot_count` (`0..6`), `bot_difficulty` (`1..3`), `stage_level` (`1..12`).
- `func spawn_weapon_pickup(weapon_id: String, pos: Vector2, ammo: int = -999, from_sky_crate: bool = false) -> void`
- `func try_pickup_near(fighter: Node2D) -> bool`

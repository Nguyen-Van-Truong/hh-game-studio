# ĐẶC TẢ CHÍNH XÁC 100% CÔNG THỨC & HẰNG SỐ AS3 GỐC (SUPERFIGHTERS Y8)

Tài liệu này được trích xuất trực tiếp từ mã nguồn ActionScript 3 gốc tại:
`8-9-hh3d-3/asset-superfighter/reference/src-superfighter/restored-project/01-actionscript/Code/`
(`Data/Players/Player.as`, `PlayerState.as`, `PlayerAnimation.as`, `BotState.as`, `Handler/Weapons.as`, `Projectiles.as`, `ProjectilesUpdater.as`, `Fires.as`, `Explosions.as`, `Maps.as`, `MapPremadeItems.as`, `Cam.as`, `PlayersKeeper.as`, `Portals.as`).

---

## 0. HỆ QUY CHIẾU VẬT LÝ CHUNG
- **Tick rate gốc**: **24 FPS** (`1000 / 24 ≈ 41.67 ms/frame`), `game_speed = 1.0` (bình thường), `< 1.0` khi Slow-mo.
  - Khi chạy trong `_physics_process(delta)` ở **60 Hz** của Godot: `step_24hz = delta * 24.0 * game_speed` (`= 0.4` mỗi tick 60Hz).
- **Tỷ lệ Box2D**: `30 px = 1 meter`. Trọng lực Box2D thế giới (`Maps.as:2581`): `b2Vec2(0, 10)`.
- **Tọa độ & Kích thước Player (`Player.as`, `PlayerState.as:696`)**:
  - `PosX() = _this_x` (tâm chân X), `PosY() = _this_y` (đáy bàn chân Y). `MidPosX() = _this_x`.
  - `MidPosY()`: `Diving` = `_this_y`; `Knockdowned` = `_this_y - 3`; `Kneeling || Falling` = `_this_y - 6`; đứng thường = `_this_y - 8`.
  - `PlayerHeight`: `Diving = 8`, `Knockdowned = 10`, `Falling = 12`, `Rolling = 14`, `Kneeling/TakingCover = 12`, `MaxPlayerHeight = 18`.
  - `PlayerEdgeDistance = 4`, `PlayerFeetSize = 4`, `Mass = 0.7`, `UpdateYAxisDistance = 3`.
  - Hitbox đạn `_player_area_mc`: X `[-6, +6]` (rộng `12 px`), Y `[-18, +2]` (cao `20 px`).
- **Máu & Tự hồi máu (`PlayerState.as:68, 725, 1138`)**:
  - `HP = 100`. Khi nhận sát thương: `_hp_damage_timer = 72` frames (3.0s).
  - Khi `HP < 100 && _hp_damage_timer <= 0`: hồi `HP += 0.1 * step_24hz` mỗi tick (`2.4 HP/s`).

---

## 1. DI CHUYỂN & VẬT LÝ NHÂN VẬT (`Player.as`, `PlayerState.as`, `PlayerAnimation.as`)

### 1.1. Run, Sprint & Năng lượng (`SprintEnergy`)
- **Tốc độ chạy (`PlayerState.as:60, 777`)**:
  - `_runSpeed = 1.7` px/frame (`40.8 px/s`).
  - Khi `_sprinting == true`: `RunSpeed = _runSpeed * 2 = 3.4` px/frame (`81.6 px/s`).
  - Không có quán tính trơn trượt trên mặt đất; bám dốc cầu thang mượt theo `tiltValue`.
- **Kích hoạt Sprint**:
  - Giữ phím `Sprint` HOẶC **Double-tap Left/Right** (cửa sổ nhấp đúp `3` frames 24Hz = `125 ms`, để dễ bấm trên bàn phím hiện đại dùng `200 ms`).
- **Tiêu hao & Hồi `SprintEnergy` (`Max = 100`)**:
  - Đang chạy nước rút trên đất: `-1.2 * step_24hz`. Chạm `0` thì tắt `_sprinting = false`.
  - Đang chạy thường hoặc leo thang: hồi `+1.0 * step_24hz`.
  - Đứng yên trên đất: hồi `+2.0 * step_24hz`.
  - Tiêu hao tức thời (`DrainEnergy`): `JUMP = -5`, `ROLL = -5`, `SPRINT_JUMP = -12`, `SPRINT_DIVE = -12`.

### 1.2. Jump, WallJump & Drop-through Cloud Platform
- **Nhảy thường (`BeginJump`)**:
  - `PlayerJumpPower = -5.0` (`AirVelocityY = -5.0`). Nếu đang `Sprinting`, giữ vận tốc ngang `±3.4`.
- **Nhảy tường (`Walljump`)**:
  - Khi trên không gần tường (`±5 px`), `|AirVelocityY| <= 3`: đảo hướng `LastDirX *= -1`, `AirVelocityY = -5.0`, vận tốc ngang bật ra `LastDirX * 1.7`.
- **Tụt xuống sàn một chiều (Cloud Platform)**:
  - Bấm đúp phím `Down` (trong `250 ms`) hoặc `Down + Jump` khi đang đứng trên sàn một chiều: bỏ qua va chạm sàn một chiều cho tới khi rơi qua `_this_y + 10`.

### 1.3. Gravity, Falling & Fall Damage
- `PlayerGravity = 0.6` px/frame².
- `FallTriggerSpeed = 8.5` px/frame: khi `AirVelocityY >= 8.5` (và không `Climbing`/`Diving`), tự chuyển sang `Falling = true` (`FALL_F` / `FALL_B`).
- **Sát thương rơi cao (`PlayerLands`)**:
  - Khi chạm đất trong trạng thái `Falling`: `dmg = (|AirVelocityY| - 3.0) * 1.5`. Nếu `dmg >= 3.0` thì trừ `HP -= dmg` và chuyển sang `KNOCKDOWN`.

### 1.4. Roll (Lăn) & Dive (Nhào lộn cá heo)
- **Roll (`Player.as:3566`)**:
  - Khi `OnGround`, giữ `Down + Left/Right` (không Sprint): tốc độ `RollSpeed = 2.0` px/frame.
  - **Né đạn khi `Rolling || Diving`**: 90% cơ hội đạn thường xuyên qua (`BulletWillHit`), 50% cơ hội tên lửa Bazooka xuyên qua (`RocketWillHit`).
  - **Dập lửa khi Roll (`DecreaseBurnState`)**: Nếu `BurnState < 100 && !Burned`, dập tắt hoàn toàn `BurnState = 0`; nếu đang cháy to (`BurnState == 100 || Burned`), giảm `BurnState = 50` (lăn 2 lần tắt hẳn).
- **Dive (`Player.as:3608`)**:
  - Khi `OnGround && Sprinting`, nhấn `Down` (hoặc phím Dive):
    - `Diving = true`, `Jumping = true`, `AirVelocityX += LastDirX * 3.5` (hoặc gán `LastDirX * 4.8`), `AirVelocityY = -3.0`, `_this_y -= 6`.
    - Trong pha bay: xoay `HELPMC.rotation += 1.5 * step_24hz` độ/frame (nếu `FALL_F` xoay `+10..+36` độ/frame, `FALL_B` xoay `-10..-36` độ/frame).
    - Nếu chạm cửa kính: phá vỡ kính bay tiếp! Khi chạm đất: tự động chuyển sang `Roll()` và không bị sát thương rơi.

### 1.5. Leo thang (`Climbing`) & Nấp (`TakingCover`)
- **Leo thang**: `ClimbSpeed = 1.5` px/frame (lên/ngang). Giữ `Down` trượt nhanh với `SlideSpeed = 3.0` px/frame và đá văng người bên dưới cùng thang (`LadderSliding`).
- **Nấp (`TakingCover`)**: Khi ngồi (`Kneel`) cạnh vật chắn/tường thấp phía trước (`8 px`): chuyển sang `COVER`, đạn của bản thân bắn xuyên qua vật chắn đang nấp (`IgnoreCoverID`), đạn đối phương bắn vào vật chắn bị chặn lại.

---

## 2. CẬN CHIẾN (MELEE), DISARM & DIVE-GRAB (`Player.as`, `Weapons.as`)

### 2.1. Vũ khí Cận chiến & Combo 3 Đòn
- **Bảng thông số cận chiến (`Weapons.as:51-71`)**:
  - `FISTS` (Tay không): Damage = `[6, 7, 8]`, Range X = `[10, 11, 13]` (+4px = `14, 15, 17 px`), Độ bền = Vô hạn (`-1`), Anim = `PUNCH_01..03`.
  - `BATON` / `PIPE`: Damage = `[7, 8, 9]`, Range X = `[12, 12, 16]`, Độ bền = `20`, Anim = `BATON_01..03`.
  - `MACHETE` / `KNIFE`: Damage = `[8, 9, 10]`, Range X = `[13, 13, 19]`, Độ bền = `20`, Anim = `MACHETE_01..03`.
  - `AXE`: Damage = `[11, 12, 13]`, Range X = `[18, 18, 20]`, Độ bền = `20`, Anim = `AXE_01..03`.
  - `SWORD` (Katana): Damage = `[13, 14, 15]`, Range X = `[18, 18, 23]`, Độ bền = `20`, Anim = `SWORD_01..03`.
  - `CHAINSAW`: Damage liên tục `2.5`/frame cận chiến, Range X = `16`, Độ bền = `100`, Anim = `CHAINSAW_01..02`.
- **Hitbox & Hiệu ứng Combo**:
  - Frame gây sát thương: Đòn 1 = frame `4`, Đòn 2 = frame `5`, Đòn 3 = frame `6`.
  - Đòn thứ 3 có lướt tới (`PunchGlideSpeed = 2.0` px/frame) và **hất tung đối thủ ngã** (`AirVelocityX = LastDirX * 3.0`, `AirVelocityY = -2.5`, `Fall()`).
  - **Chém bật đạn (`DeflectBullets`)**: Khi vung vũ khí cận chiến (`Machete`, `Axe`, `Sword`, `Baton`) đúng frame ra đòn, đạn trước mặt trong tầm `Range` bị chém bật ngược lại!

### 2.2. Kick & Jump Kick
- `KickDamage = 4`, `JumpKickDamage = 4`, `KickPower = 1.6`, `KickingTimer = 8` frames.
- Hitbox X: `<= 16 px` phía trước.
- Trúng đòn đá: đẩy `AirVelocityX = dirX * 4.0`, `AirVelocityY = -2.0`, làm rơi súng nếu đang ngắm (`CheckAimDrop`), đánh ngã (`Fall()`) hoặc loạng choạng (`Stagger`).
- Đá vào thùng/bàn ghế: truyền xung lực đẩy vật thể bay về phía trước đập vào kẻ địch!

### 2.3. Disarm (Tước súng) & Dive-Grab / Tackle-Throw
- **Disarm**: Đấm hoặc đá trúng đối phương đang giữ ngắm súng (`Aiming == true`) làm súng văng khỏi tay (`vel = (-2 * dir, -3)`).
- **Dive-Grab & Tackle-Throw**:
  - Khi `Dive` (hoặc `Sprint + Crouch` tackle) chạm đối phương (`|dx| <= 10, |dy| <= 12`): tóm gọn đối phương (`GRAB` / `GRABBED`).
  - Có thể mang đối phương bay theo cú Dive đập xuống đất (`KNOCKDOWN`), hoặc khi đang giữ đối phương thì bấm Attack để đấm bồi / bấm Hướng + Attack để **quăng đối phương (`THROW`)** bay với `AirVelocityX = LastDirX * 5.0, AirVelocityY = -3.0`!

---

## 3. SÚNG, GÓC NGẮM, ĐẠN ĐẠO, NỔ & LỬA (`Weapons.as`, `Projectiles.as`, `Explosions.as`, `Fires.as`)

### 3.1. Góc ngắm `CurrentAimPitch`
- Phạm vi: `[-90°, +90°]` (`0°` là bắn ngang, âm là chếch lên, dương là chúc xuống).
- Khi giữ phím Up/Down lúc đang ngắm: tốc độ góc ngắm tăng dần (`0.5° -> 2.5° -> 4.5°` mỗi frame 24Hz) giúp vừa chỉnh tâm chính xác khi nhấp nhẹ, vừa lia nòng nhanh khi giữ phím.

### 3.2. Bảng Thông Số Vũ Khí Tầm Xa (`Weapons.as` & `Projectiles.as`)
| Vũ khí | Slot | Ammo | Cooldown (24Hz) | Độ lệch (`Spread`) | Range (px) | Speed (px/24Hz) | Damage | Crit (% -> Dmg) | Pushback | Chuỗi bắn (`FireSequence`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **PISTOL** | Sidearm | 12 | 6 | `1.0°` | 300 | 30 | 10 | `5% -> 15` | 15 | Frame 1: bắn 1 viên (`ammo -1`) |
| **SILENCED PISTOL**| Sidearm | 12 | 5 | `0.8°` | 300 | 32 | 9 | `10% -> 14` | 12 | Frame 1: bắn 1 viên |
| **MAGNUM** | Sidearm | 6 | 8 | `0.5°` | 350 | 40 | 25 | `40% -> 35` | 50 | Frame 1: bắn 1 viên xuyên mạnh |
| **UZI** | Sidearm | 25 | 6 | `6.0°` | 200 | 30 | 7 | `4% -> 10` | 10 | Frame 1, 3, 5, 7, 9: **loạt 5 viên liên thanh** |
| **FLARE GUN** | Sidearm | 4 | 10 | `1.5°` | 260 | 22 | 8 + Cháy| `0%` | 20 | Frame 1: bắn đạn pháo sáng gây cháy `BurnState = 100` |
| **SHOTGUN** | Primary | 32 (8x4)| 3 | `4.3°` | 200 | 30 | 6 x 4 | `0%` | 33/viên | Frame 1: bắn chùm **4 viên** (`ammo -4`); Frame 6, 11: bơm đạn |
| **SAWED-OFF** | Primary | 24 (6x4)| 4 | `7.5°` | 170 | 28 | 6 x 4 | `0%` | 35/viên | Frame 1: bắn chùm 4 viên góc rộng |
| **RIFLE** | Primary | 25 | 6 | `3.0°` | 300 | 35 | 8 | `6% -> 10` | 20 | Frame 1, 3, 5, 7, 9: **loạt 5 viên liên thanh** |
| **SMG / TOMMY** | Primary | 30 | 6 | `4.5°` | 240 | 32 | 7.5 | `5% -> 11` | 15 | Frame 1, 3, 5, 7, 9: loạt 5 viên liên thanh |
| **M60** | Primary | 40 | 7 | `4.0°` | 300 | 34 | 9 | `8% -> 13` | 25 | Frame 1, 3, 5, 7, 9: loạt 5 viên hạng nặng |
| **SNIPER** | Primary | 5 | 18 | `0.0°` (có tia Laser)| 900 | 40 | 30 | `75% -> 60` | 50 | Frame 1: bắn 1 viên chí mạng (có tia laser đỏ khi ngắm) |
| **BAZOOKA** | Primary | 3 | 10 | `2.0°` | 400 | 18 | Nổ (20+) | `0%` | Nổ | Frame 1: bắn tên lửa lắc nhẹ `±4°/f`, hỗ trợ **Rocket Riding** |
| **FLAMETHROWER**| Primary | 60 | 10 | `6.0°` | 140 | 9.5 | Lửa | `0%` | 0 | Frame 1..10: phun luồng hạt lửa có trọng lực bám cháy |

- **Pushback tích lũy**: Khi `CurrentPushbackPower >= 100` hoặc trúng đạn **Crit**: đẩy lùi `AirVelocityX += dir * 2, AirVelocityY = -2` và làm mục tiêu ngã (`Fall`) hoặc loạng choạng (`Stagger`).

### 3.3. Lựu đạn (`GRENADE`), Bom xăng (`MOLOTOV`), C4 & Mìn (`MINE`)
- **Quỹ đạo ném**: `vx = cos(angle) * 5.5`, `vy = sin(angle) * 5.5 - 2.0` (trong hệ Box2D m/s, tương đương `vx ≈ 6.8 px/frame`, `vy ≈ -2.5 px/frame` ở 24Hz).
- **Lựu đạn**: `Ammo = 3`, đếm ngược `72` frames (`3.0s`) ngay khi rút chốt giữ ngắm (phát tiếng `tick` mỗi 12 frames). Nổ 36 tia bán kính `33..49.5 px`, sát thương cơ sở `20` (cộng dồn theo tia trúng), hất văng nhân vật và vật thể.
- **Bom xăng (`Molotov`)**: `Ammo = 3`, vỡ tung ngay khi chạm sàn/tường hoặc chạm người chơi, bung ra **22 hạt lửa** bán kính bốc cháy tức thời `20 px` (`BurnState = 100`).
- **Lửa & Thiêu đốt (`BurnState`)**:
  - `BurnState >= 15` (Cháy cấp 1): trừ `0.2 HP/frame` (`4.8 HP/s`).
  - `BurnState >= 100` (Cháy cấp 2 / `Burned`): trừ `0.4 HP/frame` (`9.6 HP/s`), không tự tắt theo thời gian — phải bấm **Lăn (`Roll`)** để dập lửa!

---

## 4. CAMERA ĐỘNG & CÁC VẬT THỂ TƯƠNG TÁC (`Cam.as`, `Maps.as`, `MapPremadeItems.as`, `Portals.as`)

### 4.1. Camera Động (`Cam.as` & `PlayersKeeper.as`)
- Tính hộp bao `(minX, maxX, minY, maxY)` của tất cả nhân vật còn sống (hoặc vừa gục `< 48` frames) với lề đệm: Trái/Phải `±15 px`, Trên `-30 px`, Dưới `0 px`, cộng đệm vùng nhìn `+40 px` mỗi chiều.
- Nội suy mượt vị trí tâm Camera và hệ số `zoom` để giữ mọi người chơi trong khung hình (giới hạn trong `camera_bounds` của từng map, ví dụ `Rect2(0, 0, 920, 460)` trên Rooftops).

### 4.2. Thang Máy (`Elevator` / `Lift`)
- `LIFT_SMALL_01` (`26x7 px`), `LIFT_01` (`36x8 px`).
- Dao động điều hòa hình sin dọc hoặc ngang theo cơ cấu tay biên:
  - Map `Rooftops`: `LIFT_SMALL_01` tại `x = 878, y_center = 204`, hành trình `92 px` (từ `y = 158` đến `y = 250`), tốc độ góc `1.0 rad/s`.

### 4.3. Cổng Dịch Chuyển (`Portals.as`)
- Khi nhân vật, đạn hoặc vật thể đi vào hình chữ nhật `portal` cùng hướng với `trigger_dir`: dịch chuyển tức thời sang `target_portal.x + target_portal.width * 0.5`, giữ nguyên độ lệch `dy = pos.y - portal.y`; nếu `inverse_x == true` thì đảo hướng vận tốc ngang `vx *= -1` và hướng mặt `facing *= -1`.

### 4.4. Kính Vỡ (`SOLID_GLASS_01`)
- `HP = 5`, vỡ ngay lập tức khi đạn bắn xuyên qua (đạn không bị giảm tốc), khi nổ, khi vật thể đập vào hoặc khi người chơi `Dive` / `Kick` / `Fall` xuyên qua!
- Khi vỡ: phát âm thanh kính vỡ và sinh chuỗi mảnh kính `GLASS_SHARD_1` dọc theo chiều dài tấm kính (cứ mỗi `6 px` 1 mảnh) bay theo hướng lực tác động.

### 4.5. Thùng Gỗ Treo (`CRATE_HANGING` + `CRATE_HANGING_HOLDER`)
- Móc treo phía trên (`9x6 px`, `HP = 6`): khi trúng 1 viên đạn hoặc mảnh nổ sẽ đứt dây, làm khối thùng gỗ nặng (`27x14 px`, `CanGibb = true`) rơi tự do xuống đè bẹp mục tiêu bên dưới!

### 4.6. Thùng Phuy Nổ 2 Pha (`BARREL_EXPLOSIVE`) & Bình Xăng (`GASCAN`)
- `BARREL_EXPLOSIVE` (`9x13 px`) & `GASCAN` (`7x9 px`):
  - Trúng bất kỳ viên đạn hoặc vụ nổ nào là kích nổ ngay (sau độ trễ `1 frame` để tạo hiệu ứng nổ dây chuyền).
  - Nếu bị lửa đốt: cháy trong ~`70` frames rồi nổ.
  - `GASCAN` khi nổ: bung cầu lửa **18 hạt lửa** bán kính `16 px`.
  - `BARREL_EXPLOSIVE` khi nổ (Pha 1): tạo vụ nổ lớn (bán kính `33..49.5 px`, sát thương `20`) + bung 18 hạt lửa + hất tung xác thùng cháy `BARREL_WRECK` (`HP = 50`) bay lên không trung; khi `BARREL_WRECK` cháy hết máu hoặc bị bắn bồi sẽ **nổ lần thứ 2 (Pha 2)**!

---

## 5. BOT AI (`BotState.as` & `Player.as`)
- **3 mức độ khó (`Easy`, `Medium`, `Hard`)**:
  - `Easy`: `_updateDelay = 8`, `_aimDelay = 12`, không Sprint/Roll/Dive.
  - `Medium`: `_updateDelay = 6`, `_aimDelay = 9`, có Sprint & Melee.
  - `Hard`: `_updateDelay = 1`, `_aimDelay = 5`, đầy đủ Sprint, Roll dập lửa, Dive-Grab, né lựu đạn/thùng nổ (`_Diff_Avoid`), nấp bắn (`TakingCover`) và bắn tỉa thùng nổ cạnh kẻ địch!

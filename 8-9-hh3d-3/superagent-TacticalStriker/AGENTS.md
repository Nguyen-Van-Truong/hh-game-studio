# AGENTS.md — Superfighters Y8 Remake (`8-9-hh3d-3/superfighters-y8`)

## 1. NGUỒN KẾ HOẠCH VÀ THẨM QUYỀN DUY NHẤT
- Kế hoạch chuẩn duy nhất cho thư mục này:
  `8-9-hh3d-3/superfighters-y8/zdoc/23-10-superfighters-y8-remake-master-plan.txt`
- **Owner Waiver (Bỏ toàn bộ rào cản bản quyền/clean-room và thủ tục cũ)**:
  - Được phép và bắt buộc sử dụng trực tiếp 100% tài nguyên gốc (spritesheets, bitmaps, XFL XML timelines/matrices, âm thanh `.mp3`, mã nguồn `.as`, hằng số vật lý/vũ khí/map) từ:
    `8-9-hh3d-3/asset-superfighter/reference/src-superfighter/restored-project`
  - **KHÔNG** áp dụng các quy tắc cũ của `Vault Fighters` (`zdocs/29-8-*`), `SA-02` (`18-9-superagent-2d-y8-plan.txt`), hay `run_guarded.py` (không dùng `measure-window.lock`, không freeze SHA-256, không chặn tên gọi `Superfighters`).

## 2. CÔNG CỤ & GODOT ENGINE
- Sử dụng Godot 4.7.2-stable tại:
  `D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\8-9-hh3d-3\superagent copy\.local\tooling\godot-4.7.2-stable\Godot_v4.7.2-stable_win64_console.exe`
  (và bản GUI `Godot_v4.7.2-stable_win64.exe` cho file `.bat` mở game).

## 3. TIÊU CHUẨN KỸ THUẬT BẮT BUỘC
1. **Không cắt ảnh thủ công bằng `_trim_visible()` hay scale cứng chiều cao `108px`**:
   - Mọi nhân vật phải dùng dữ liệu `rect` + `pivot (tx, ty)` + `2-layer split rig` (`BodySprite` + `AimPivot/WeaponArmSprite` tại khớp vai `(-3, -12)`) được biên dịch tự động từ `xfl-export/Superfighters/LIBRARY/Symbol *.xml` qua `tools/compile_xfl_assets.py`.
2. **Hệ tọa độ gốc & Nhịp 24Hz trên nền 60Hz**:
   - Giữ đúng kích thước gốc của Flash (nhân vật đứng cao `18px`, rộng `12px`, map `Rooftops` `920x460px` đặt tại `(0, 0)`), dùng `Camera2D` động (`TEXTURE_FILTER_NEAREST`) để phóng to sắc nét.
   - Quy đổi chuẩn các hằng số 24 FPS của `Player.as` / `PlayerState.as` sang `_physics_process(delta)` 60Hz bằng hệ số `step_24hz = delta * 24.0 * time_scale`.
3. **Kiến trúc dễ bảo trì & mở rộng**:
   - Tách bạch rõ ràng dữ liệu (`data/*.json`), hiển thị (`FighterRigView`), điều khiển vật lý/chiến đấu (`FighterController`), bản đồ/vật thể (`MapLoader`, `InteractiveProp`), AI (`BotController`) và cổng mở rộng nhân vật mới / MUGEN (`MugenFighterAdapter`).
4. **Cập nhật tiến độ**:
   - Khi hoàn thành mỗi Milestone (`SF-M1` -> `SF-M7`), cập nhật bảng tổng quan ở đầu file `zdoc/23-10-superfighters-y8-remake-master-plan.txt` và ghi vào mục `3. NHẬT KÝ TIẾN ĐỘ`.

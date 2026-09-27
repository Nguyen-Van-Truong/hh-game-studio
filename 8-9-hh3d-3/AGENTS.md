# HH3D-3 — routing hiện hành

Owner steering mới nhất 27-09-2026 và O4 đã thay chế độ solo tuyệt đối:
coordinator giữ một writer/file; có thể nhờ subagent làm việc độc lập khi cần
(owner ưu tiên GPT-6 Astra extra-high). Không dispatch lại khi thiếu credit.
Riêng critic nghiệm thu theo O4.3: coordinator chuẩn bị CRITIC_PACKAGE để
owner chuyển phiên review độc lập chạy hai critic khác model cùng hash.
Không tự gọi critic nghiệm thu, không ký thay hoặc tái dùng chữ ký hash cũ.

Resume đúng checkpoint; không làm lại phần đã chứng minh. Tuần tự hóa engine
runs; không chạy Godot/Blender khác hay test nặng cạnh GT-06 formal. Giữ actual
exits, source/evidence hash và raw lỗi. Không rerun test/commit metadata khi
source và điều kiện không đổi. Preflight/watchdog dùng O4.1; app người dùng
là inventory, không tự đóng. Không thay counter/status-gap/timeout của O1.

Governance chỉ sửa trên nhánh chính. Nhánh O2 ghi chi tiết vào
studio/AUTHORING_STATUS.md, làm theo gap của hai fixture; giữ DSL sáu effect.
Không mở GT-07 trước GT-06 ACCEPTED. Đọc CURRENT_VALID_WP và bảng trạng thái
trong tools plan, không lấy số test/diagnostic làm nguồn tick.

Ba plan TXT có scope riêng theo lệnh owner 18-09-2026:

1. [8-9-godot-blender-agent-studio-plan.txt](zdoc/8-9-godot-blender-agent-studio-plan.txt) — bộ công cụ Godot + Blender + agent, làm trước.
2. [8-9-hh-world-gameplay-viet-nam-plan.txt](zdoc/8-9-hh-world-gameplay-viet-nam-plan.txt) — game HH World, nhận package GT-10 rồi mới mở rộng gameplay và bản đồ Việt Nam.
3. [18-9-superagent-2d-y8-plan.txt](zdoc/18-9-superagent-2d-y8-plan.txt) — game Superagent 2D mới, đủ functional parity Y8 trừ nhân vật/map mới; không kế thừa Vault Fighters cũ. Hiện chỉ planning, triển khai sau GT-10 và lệnh mở sản phẩm.

Đọc bảng tiến độ và CURRENT_VALID_WP trong đúng file. Plan công cụ kiểm bằng
fixture độc lập; plan game kiểm lại trên workload thật. Không tạo master plan thứ tư. Các file 5-9 và unified cũ chỉ lịch sử/routing, không tick và không bổ sung
DoD. Review/static evidence nằm trong zdoc/reviews/, không phải nguồn tiến độ.

Thứ tự ưu tiên hiện tại: GT-01→GT-10. HH World đi H2-P0-01→H2-P9-02;
Superagent đi SA-01→SA-16 khi được mở. Hai game độc lập, không là dependency
của nhau; research/plan không tự mở triển khai game. Không fork lõi Godot lúc đầu;
không chạy Blender trên server người chơi; không coi số tài khoản đăng ký là
số avatar realtime. Routing Grok/Codex workers của các phiên trước chỉ là lịch
sử trong plan archive/reviews. Coordinator giữ một writer/file, kiểm dependency
và tự thực hiện phần đủ dependency, scope rõ. Giữ checkpoint,
actual process exit, source hash và evidence; không bịa cờ hay chữ ký critic.

Owner đã cho phép triển khai theo dependency; đọc trạng thái hiện hành từ
bảng đầu plan công cụ và CURRENT_VALID_WP, không giữ bản sao tiến độ ở đây.
Quyền triển khai không thay evidence/critic/legal/human acceptance. Không có
engine/game/server nào được nghiệm thu chỉ vì plan tồn tại. Một writer/lease/
path allowlist; worker không tự tick. Không sửa scope Vault Fighters/platform.

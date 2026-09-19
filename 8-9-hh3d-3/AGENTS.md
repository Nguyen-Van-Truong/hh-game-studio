# HH3D-3 — routing hiện hành

Owner steering mới nhất 19-09-2026: coordinator tự làm, không tạo thêm worker.
Quyền ba Codex Astra ultra ngày18-09 là lịch sử; giữ hai critic độc lập ở gate
cuối khi đủ điều kiện. Model/effort theo lệnh owner mới nhất, không giả cờ fast.
Đọc WP và tiến độ mới nhất ở đầu plan; không lấy tên worker hoặc trạng thái
trong báo cáo lịch sử làm dispatch hiện hành. Coordinator giữ một writer/file,
tích hợp kết quả và tuần tự hóa các lượt chạy engine; không thêm engine/test
nặng cạnh phép đo. Giữ actual exits, source/evidence hash và checkpoint.
Hai critic độc lập chỉ đọc cùng final closure vẫn bắt buộc cho gate mới.
Worker implementation/preflight và coordinator tự review không thay hai critic;
không chuyển chữ ký từ source cũ sang source mới.

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
và chỉ dispatch lane đủ dependency, scope rõ. Giữ checkpoint,
actual process exit, source hash và evidence; không bịa cờ hay chữ ký critic.

Owner đã cho phép triển khai theo dependency; đọc trạng thái hiện hành từ
bảng đầu plan công cụ và CURRENT_VALID_WP, không giữ bản sao tiến độ ở đây.
Quyền triển khai không thay evidence/critic/legal/human acceptance. Không có
engine/game/server nào được nghiệm thu chỉ vì plan tồn tại. Một writer/lease/
path allowlist; worker không tự tick. Không sửa scope Vault Fighters/platform.

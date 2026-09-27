# HH3D-3 — routing hiện hành

Owner steering mới nhất 27-09-2026: "giờ bạn tự làm không cần worker hay
subagent gì nữa tổng hợp lại tiến độ subagent đã làm và tiếp tục".
Coordinator tự đọc kết quả/code/evidence đã có, tiếp quản việc còn thiếu và
thực hiện tuần tự. Không spawn worker/subagent, không mở Cursor session hoặc
chuyển việc sang thread khác. Chỉ đạo ba worker Astra ở S158 là lịch sử,
không còn là dispatch hiện hành. Không gán kết quả coordinator làm thành
kết quả worker hoặc chữ ký critic độc lập.

Resume đúng workspace/checkpoint sau gián đoạn; không làm lại phần đã chứng
minh. Giữ một writer/file, tuần tự hóa engine runs, không thêm engine/test
nặng cạnh phép đo formal. Giữ actual exits, source/evidence hash và raw lỗi.
Không rerun test/commit metadata khi source và blocker không đổi.

Chế độ solo không tự tạo bằng chứng hai critic độc lập mà gate còn yêu cầu:
giữ phần nghiệm thu đó pending, không tự ký thay và không gọi critic trái
chỉ đạo solo. Đọc CURRENT_VALID_WP và trạng thái thật ở đầu plan; không lấy
báo cáo lịch sử hay số test làm nguồn tick. Không chuyển chữ ký từ hash cũ.

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

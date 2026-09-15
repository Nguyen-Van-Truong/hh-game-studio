# HH3D-3 — routing hiện hành

Owner steering mới nhất 15-09-2026: tạm dừng subagent, coordinator làm solo.
Không tạo/đánh thức worker hoặc critic, không dùng Grok CLI. Kết quả và phần
dở S32 đã bàn giao lại coordinator; một writer/file. Nghiệm thu vẫn cần hai
critic độc lập cùng frozen source; solo self-review không thay chữ ký.
Plan đầu file giữ trạng thái hiện hành.

Chỉ có đúng hai plan TXT đang hoạt động:

1. [8-9-godot-blender-agent-studio-plan.txt](zdoc/8-9-godot-blender-agent-studio-plan.txt) — bộ công cụ Godot + Blender + agent, làm trước.
2. [8-9-hh-world-gameplay-viet-nam-plan.txt](zdoc/8-9-hh-world-gameplay-viet-nam-plan.txt) — game HH World, nhận package GT-10 rồi mới mở rộng gameplay và bản đồ Việt Nam.

Đọc bảng tiến độ và CURRENT_VALID_WP trong đúng file. Plan công cụ kiểm bằng
fixture độc lập; plan game kiểm lại trên workload thật. Không có plan tổng thứ
ba. Các file 5-9 và unified cũ chỉ lịch sử/routing, không tick và không bổ sung
DoD. Review/static evidence nằm trong zdoc/reviews/, không phải nguồn tiến độ.

Thứ tự: GT-01→GT-10 rồi H2-P0-01→H2-P9-02. Không fork lõi Godot lúc đầu;
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

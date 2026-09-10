# HH3D-3 — routing hiện hành

Chỉ có đúng hai plan TXT đang hoạt động:

1. [8-9-godot-blender-agent-studio-plan.txt](zdoc/8-9-godot-blender-agent-studio-plan.txt) — bộ công cụ Godot + Blender + agent, làm trước.
2. [8-9-hh-world-gameplay-viet-nam-plan.txt](zdoc/8-9-hh-world-gameplay-viet-nam-plan.txt) — game HH World, nhận package GT-10 rồi mới mở rộng gameplay và bản đồ Việt Nam.

Đọc bảng tiến độ và CURRENT_VALID_WP trong đúng file. Plan công cụ kiểm bằng
fixture độc lập; plan game kiểm lại trên workload thật. Không có plan tổng thứ
ba. Các file 5-9 và unified cũ chỉ lịch sử/routing, không tick và không bổ sung
DoD. Review/static evidence nằm trong zdoc/reviews/, không phải nguồn tiến độ.

Thứ tự: GT-01→GT-10 rồi H2-P0-01→H2-P9-02. Không fork lõi Godot lúc đầu;
không chạy Blender trên server người chơi; không coi số tài khoản đăng ký là
số avatar realtime. Theo lệnh owner 10-09-2026, worker/search/critic dùng
Grok CLI chính thức: model grok-4.6, reasoning-effort xhigh, --no-subagents.
Không Codex worker/Cursor/Auto/fallback/hidden subagent. Kiểm --help và grok
models theo phiên; không bịa cờ fast nếu CLI không cung cấp. Mỗi worker có
attempt/session riêng, phạm vi ghi riêng và host exit thực. Tối đa hai lần
poll mỗi batch; supervisor/watcher báo terminal để coordinator review.

Owner đã cho phép triển khai theo dependency; GT-01 đang IN_PROGRESS.
Quyền triển khai không thay evidence/critic/legal/human acceptance. Không có
engine/game/server nào được nghiệm thu chỉ vì plan tồn tại. Một writer/lease/
path allowlist; worker không tự tick. Không sửa scope Vault Fighters/platform.

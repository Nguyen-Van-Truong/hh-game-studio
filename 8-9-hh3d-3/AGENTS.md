# HH3D-3 — routing hiện hành

Chỉ có đúng hai plan TXT đang hoạt động:

1. [8-9-godot-blender-agent-studio-plan.txt](8-9-godot-blender-agent-studio-plan.txt) — bộ công cụ Godot + Blender + agent, làm trước.
2. [8-9-hh-world-gameplay-viet-nam-plan.txt](8-9-hh-world-gameplay-viet-nam-plan.txt) — game HH World, nhận package GT-10 rồi mới mở rộng gameplay và bản đồ Việt Nam.

Đọc bảng tiến độ và CURRENT_VALID_WP trong đúng file. Plan công cụ kiểm bằng
fixture độc lập; plan game kiểm lại trên workload thật. Không có plan tổng thứ
ba. Các file 5-9 và unified cũ chỉ lịch sử/routing, không tick và không bổ sung
DoD. Review/static evidence nằm trong reviews/20260908, không phải nguồn tiến độ.

Thứ tự: GT-01→GT-10 rồi H2-P0-01→H2-P9-02. Không fork lõi Godot lúc đầu;
không chạy Blender trên server người chơi; không coi số tài khoản đăng ký là
số avatar realtime. Mọi worker/search/critic dùng Cursor CLI đúng model
cursor-grok-4.6-xhigh-fast, không Composer/Auto/fallback/hidden subagent.

Hiện tài liệu chỉ ở PLAN_ONLY; không có engine/game/server nào được nghiệm thu
chỉ vì plan tồn tại. Một writer/lease/path allowlist; worker không tự tick.

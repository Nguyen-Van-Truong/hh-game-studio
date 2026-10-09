# HH3D-3 — routing hiện hành

Owner steering 03-10-2026, credit và lượt theo O13.6 của tools plan (08-10): một coordinator, một
thread; subagent chỉ cho thiết kế khó, worker K13 và hai critic cuối, fork_turns=none với brief
≤ 1 trang; ultra (gpt-6-astra, gpt-6.1-sol) chỉ cho thiết kế khó và critic. Đọc log, chạy test,
closeout, status làm trực tiếp; không spawn audit trạng thái/gói/next-step; không tự tạo
heartbeat/automation; final, diễn tập và soak chạy qua Scheduled Task có receipt, không là con của
shell agent (O13.6); chờ bằng lệnh chặn 5–10 phút, không poll dưới 60 giây; không kết thúc lượt
khi run nền/subagent chưa xong. Credit workspace dùng chung cho mọi agent.
Giữ một writer/file, tuần tự hóa workload đo và tiếp tục từ checkpoint đã kiểm chứng.
Theo quyền audit mới nhất của owner, coordinator được dispatch hai critic
độc lập khác model trên cùng hash; giữ nguyên report, kiểm hash trước nghiệm thu.
Không tự ký thay critic hoặc tái dùng chữ ký hash cũ. Quyết định nghiệm thu GT-06, GT-07,
GT-08A: mục Đã nghiệm thu của tools plan.

Resume đúng checkpoint; không làm lại phần đã chứng minh. Một Godot/Blender mỗi
project path; không chạy engine hay test nặng cạnh formal/soak đang giữ khóa đo.
Giữ actual exits, source/evidence hash và raw lỗi. Không rerun test/commit metadata
khi source và điều kiện không đổi. Preflight/watchdog O4.1 chỉ cho formal/soak; app
người dùng là inventory, không tự đóng. Không thay counter/status-gap/timeout của O1.

Governance (plan, AGENTS.md) chỉ coordinator sửa; chi tiết run ghi vào
studio/AUTHORING_STATUS.md (Hiện trạng ≤ 15 dòng + bảng K1–K15 + Next), sửa trong cùng commit
mốc; giữ DSL sáu effect. GT-09 làm theo NEXT của O13 (B6a xong, B6b final, B7 critic theo
checklist O13.9) trên ma trận K1–K15: dry-run trước run native, bằng chứng tầng D chỉ ở .local,
một runner run_gt09_matrix.py. Final chỉ nhận source đã freeze và tự chạy mọi producer (O13.3a),
dừng ở hàng FAIL đầu; mỗi FAIL ghi loại PRODUCT/VERIFIER/INFRA (O13.4); bản sửa kiểm bằng hàng
đó hoặc smoke ngắn (O13.3f) và --verify-only trên raw thật trước final; playtest 15 phút chỉ
trong final; freeze gồm cả subagent, không có writer khi final chạy; commit WIP trước run dài.
Không lập gói hay gọi critic trước self-check O13.3; không tự tick WP; nghiệm thu GT-09 cần gói
cuối và hai critic cùng hash. AGENTS.md ở gốc repo (Vault Fighters) không áp dụng cho tools plan.
Đọc CURRENT_VALID_WP và bảng trạng thái
trong tools plan, không lấy số test/diagnostic làm nguồn tick.

Ba plan TXT có scope riêng theo lệnh owner 18-09-2026:

1. [8-9-godot-blender-agent-studio-plan.txt](zdoc/8-9-godot-blender-agent-studio-plan.txt) — bộ công cụ Godot + Blender + agent, làm trước.
2. [8-9-hh-world-gameplay-viet-nam-plan.txt](zdoc/8-9-hh-world-gameplay-viet-nam-plan.txt) — game HH World, nhận package GT-10 rồi mới mở rộng gameplay và bản đồ Việt Nam.
3. [18-9-superagent-2d-y8-plan.txt](zdoc/18-9-superagent-2d-y8-plan.txt) — game Superagent 2D (SA5 Classic-first, gate ba tầng A/B/C, rig đo Y8): hoàn thành cơ chế/chức năng giống bản Y8 trước, phím theo keymap owner 04-10; biến thể và hệ tùy biến bị khóa sau Classic; không kế thừa tick Vault Fighters cũ. Owner mở triển khai 03-10: agent riêng làm trong worktree nhánh superagent/main, không chờ GT-10, kiểm measure-window.lock trước lệnh nặng.

Đọc bảng tiến độ và CURRENT_VALID_WP trong đúng file. Plan công cụ kiểm bằng
fixture độc lập; plan game kiểm lại trên workload thật. Không tạo master plan thứ tư. Các file 5-9 và unified cũ chỉ lịch sử/routing, không tick và không bổ sung
DoD. Review/static evidence nằm trong zdoc/reviews/, không phải nguồn tiến độ.

Thứ tự ưu tiên hiện tại: GT-01→GT-10. HH World đi H2-P0-01→H2-P9-02;
Superagent đi SA-01→SA-13 (SA-14 khóa sau Classic), owner mở 03-10 cho agent riêng; coordinator công cụ
không kiêm. Hai game độc lập, không là dependency của nhau; research/plan không
tự mở triển khai game khác. Không fork lõi Godot lúc đầu;
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

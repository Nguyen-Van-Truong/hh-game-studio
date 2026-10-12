# HH3D-3 — routing hiện hành

GT-11 ACCEPTED_O15_QUICK 12-10-2026 18:35 (gamekit W1–W12, selftest all 226/226, critic Grok vòng
cuối 2 TICK=yes trên 2a03cc2f); lease GT-11 đã hết. GT-10-PC ACCEPTED 12-10 14:47 theo O14 (kiểm
ngắn: gói diễn tập c3h, hai critic Grok). Plan công cụ xong cho PC; GT-08B (Android) hoãn theo O12.
Agent làm game dùng công cụ và lệnh `hh` theo
[12-10-huong-dan-dung-cong-cu-godot-blender.txt](zdoc/12-10-huong-dan-dung-cong-cu-godot-blender.txt)
(mục 13 cho gamekit). Lỗi công cụ: sửa trong `studio/` bằng test ngắn liên quan và selftest của
lệnh đó, giữ contract, mỗi change request một commit (O14.5); không tự sửa được thì ghi thêm dòng
vào `zdoc/12-10-gt11-yeu-cau-tu-agent-game.txt` (ngày giờ, game, lệnh, lỗi thấy).

Owner steering 03-10-2026, credit và lượt theo O13.6 của tools plan (08-10): một coordinator, một
thread; subagent dùng khi cần (audit, research, việc không quá khó, hai critic), fork_turns=none,
brief ≤ 1 trang; owner 12-10 (O14.7): mọi subagent và critic dùng grok-4.7-xhigh. Đọc log, chạy test,
closeout, status làm trực tiếp; không spawn audit trạng thái/gói/next-step; không tự tạo
heartbeat/automation; final, diễn tập và soak chạy qua Scheduled Task có receipt, không là con của
shell agent (O13.6); chờ bằng lệnh chặn 5–10 phút, không poll dưới 60 giây; không kết thúc lượt
khi run nền/subagent chưa xong. Credit workspace dùng chung cho mọi agent.
Giữ một writer/file, tuần tự hóa workload đo và tiếp tục từ checkpoint đã kiểm chứng.
Theo quyền audit mới nhất của owner, coordinator được dispatch hai critic
độc lập trên cùng hash (O14.7: hai instance grok-4.7-xhigh); giữ nguyên report, kiểm hash trước
nghiệm thu.
Không tự ký thay critic hoặc tái dùng chữ ký hash cũ. Quyết định nghiệm thu GT-06, GT-07,
GT-08A, GT-09: mục Đã nghiệm thu của tools plan.

Resume đúng checkpoint; không làm lại phần đã chứng minh. Một Godot/Blender mỗi
project path; không chạy engine hay test nặng cạnh formal/soak đang giữ khóa đo.
Giữ actual exits, source/evidence hash và raw lỗi. Không rerun test/commit metadata
khi source và điều kiện không đổi. Preflight/watchdog O4.1 chỉ cho formal/soak; app
người dùng là inventory, không tự đóng. Không thay counter/status-gap/timeout của O1.

Governance (plan, AGENTS.md) do coordinator và reviewer owner giao ở O13 sửa, đọc HEAD trước khi
sửa; chi tiết run ghi vào studio/AUTHORING_STATUS.md (Hiện trạng ≤ 15 dòng ≤ 160 ký tự, bảng hàng
của gate đang mở, Next), sửa cùng commit code, không commit chỉ để ghi sổ; giữ DSL sáu effect.
GT-09, GT-10-PC đã nghiệm thu. Chạy lại ma trận P1–P12 (O13.8) khi sửa gói thì dùng một runner
run_gt10pc_matrix.py, bằng chứng tầng D chỉ ở .local. Final chỉ nhận source đã freeze và tự chạy
mọi producer (O13.3a), dừng ở hàng FAIL đầu; mỗi FAIL ghi loại PRODUCT/VERIFIER/INFRA (O13.4).
Lỗi một bước native: reproducer gọi thẳng lệnh đó tới khi qua, rồi mới chạy hàng qua Scheduled
Task; timeout từng producer lấy từ số đo, không trần chung; tool native chạy ở gốc ngắn trong
ngân sách đường dẫn (O13.3g). Final dài chỉ sau diễn tập toàn ma trận và pre-review (O13.3h),
khởi chạy buổi tối qua Scheduled Task; freeze gồm cả subagent; commit WIP trước run dài. Không
lập gói hay gọi critic trước self-check O13.3; không tự tick WP; nghiệm thu cần gói final và hai
critic cùng hash (GT-10-PC dùng gói diễn tập c3h theo O14). AGENTS.md ở gốc repo (Vault
Fighters) không áp dụng cho tools plan.
Đọc CURRENT_VALID_WP và bảng trạng thái
trong tools plan, không lấy số test/diagnostic làm nguồn tick.

Ba plan TXT có scope riêng theo lệnh owner 18-09-2026:

1. [8-9-godot-blender-agent-studio-plan.txt](zdoc/8-9-godot-blender-agent-studio-plan.txt) — bộ công cụ Godot + Blender + agent, làm trước.
2. [8-9-hh-world-gameplay-viet-nam-plan.txt](zdoc/8-9-hh-world-gameplay-viet-nam-plan.txt) — game HH World, nhận package GT-10 rồi mới mở rộng gameplay và bản đồ Việt Nam.
3. [18-9-superagent-2d-y8-plan.txt](zdoc/18-9-superagent-2d-y8-plan.txt) — game Superagent 2D (SA5 Classic-first, gate ba tầng A/B/C, rig đo Y8): hoàn thành cơ chế/chức năng giống bản Y8 trước, phím theo keymap owner 04-10; biến thể và hệ tùy biến bị khóa sau Classic; không kế thừa tick Vault Fighters cũ. Owner mở triển khai 03-10: agent riêng làm trong worktree nhánh superagent/main, không chờ GT-10, kiểm measure-window.lock trước lệnh nặng.

Đọc bảng tiến độ và CURRENT_VALID_WP trong đúng file. Plan công cụ kiểm bằng
fixture độc lập; plan game kiểm lại trên workload thật. Không tạo master plan thứ tư. Các file 5-9 và unified cũ chỉ lịch sử/routing, không tick và không bổ sung
DoD. Review/static evidence nằm trong zdoc/reviews/, không phải nguồn tiến độ.

Plan công cụ: GT-01→GT-10-PC xong cho PC (O14); GT-11 ACCEPTED_O15_QUICK 12-10. HH World đi H2-P0-01→H2-P9-02;
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

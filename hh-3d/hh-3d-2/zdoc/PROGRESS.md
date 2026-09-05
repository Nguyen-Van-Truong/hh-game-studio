# Trạng thái HH World 2

UPDATED=2026-09-05 Asia/Saigon
SCOPE=hh-3d/hh-3d-2
BASELINE_GIT=0d88141b1a5e085eb3661660e39597af8fb4f2c5
CANONICAL_ROADMAP=zdoc/06-ROADMAP.md
SESSION_AUTHORIZATION=PLAN_ONLY
IMPLEMENTATION=NOT_STARTED
CURRENT_VALID_WP=H2-P0-01
CURRENT_ACTION=Bộ plan để owner review; không thực thi WP game.
ENGINE_DECISION=Godot native stock; giữ sau technical gate; no core fork.
ENGINE_INSTALLED_FOR_NEW_PROJECT=NO
RUNTIME_ACCEPTANCE=NONE
HUMAN_ACCEPTANCE=NONE

## Kết quả được phép tuyên bố

- Có thiết kế/roadmap mới, tách khỏi Web cũ và Vault Fighters.
- Không có game mới, backend mới, FPS/capacity mới hoặc bản đồ thật được chứng minh.
- Các WP trong roadmap còn PLANNED; hoàn thành tài liệu không tick WP triển khai.
- Review nghiên cứu/plan xem `reviews/` và `09-RESEARCH.md`; chỉ phản biện tài liệu.

## Handoff

Khi owner yêu cầu bắt đầu, giao H2-P0-01 bằng template trong
`08-AGENT-WORKFLOW.md`. Coordinator cập nhật quyền thực thi theo câu yêu cầu
thực tế, không bắt lặp một magic phrase. Không nhảy thẳng clone engine,
địa lý thật, public server hoặc crowd hàng nghìn người.

Repo trước lượt này đã có dirty evidence Vault Fighters và một handoff Web
cũ untracked. Không sửa, stage hoặc gộp chúng vào checkpoint HH World 2.

# HH World 2 — phạm vi mới, chỉ lập kế hoạch ở lần khởi tạo

Owner ngày 2026-09-05 yêu cầu làm lại sản phẩm trong `hh-3d/hh-3d-2`,
trước mắt **chỉ tạo plan A–Z**. Không suy ra quyền clone/cài engine, tạo game,
chạy server, tải bản đồ, dùng dịch vụ trả phí hoặc phát hành từ bộ tài liệu này.
Một yêu cầu tiếp theo như “bắt đầu làm theo plan” mở các WP local theo phạm vi
đã ghi; không cần bắt owner đọc lại một câu xác nhận đặc biệt.

Đọc `zdoc/00-START-HERE.md`, `zdoc/PROGRESS.md`, rồi WP hiện hành trong
`zdoc/06-ROADMAP.md` và đúng các contract WP đó viện dẫn.
Đây là routing riêng cho subtree này. Không bắt đầu WP Vault Fighters hay
tiếp tục backlog Web cũ khi làm HH World 2. Mọi file bên ngoài subtree giữ
nguyên; `hh-3d/app/` và các plan cũ chỉ là tài liệu tham khảo.

Coordinator chia việc, viết/sửa plan, kiểm tra bằng chứng và quyết định.
Worker, researcher và critic chỉ được gọi qua Cursor CLI với
`--model cursor-grok-4.6-xhigh-fast`; cấm Composer/Auto/model fallback,
Task/Explore/subagent có model không kiểm soát. Không có đúng model thì báo
gap; không âm thầm đổi. Không sửa cùng file với worker.

Không dùng một marker authority toàn repo mới. Thẩm quyền roadmap chỉ thuộc
scope `hh-3d/hh-3d-2`; không thay đổi acceptance/engine pin của sản phẩm khác.
Chi tiết giao việc, lease, evidence và giới hạn quyền: `zdoc/08-AGENT-WORKFLOW.md`.

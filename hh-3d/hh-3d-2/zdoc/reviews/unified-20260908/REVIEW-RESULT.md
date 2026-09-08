# Bản hợp nhất U2 — kết quả bàn giao tài liệu ngày 08-09-2026

CURRENT_PLAN_REVISION=U2
DOCUMENT_WRITTEN=YES
COORDINATOR_STATIC_CHECK=PASS_STATIC_ONLY
INDEPENDENT_REVIEW_U2=PENDING_CURSOR_USAGE_LIMIT
PLAN_DESIGN_ACCEPTED=NO
IMPLEMENTATION=NOT_STARTED
RUNTIME_ACCEPTANCE=NONE
HUMAN_ACCEPTANCE=NONE
ENGINE_INSTALL_ACCEPTANCE=NONE
REQUIRED_WORKER_MODEL=cursor-grok-4.6-xhigh-fast

Một plan thực thi duy nhất: sibling
hoan-hao/zdoc/8-9-hh-studio-godot-blender-hh-world-plan.txt.
File này chỉ là báo cáo evidence; không có WP hay nguồn tiến độ thứ hai.

## Nội dung đã giao và phạm vi kiểm tra

Plan có bảng 40 WP ở đầu, 40 đặc tả công việc, 54 cạnh phụ thuộc, 48 tình
huống ngoại lệ, contract Godot/Blender/agent, gameplay, UX/art, multiplayer,
durability, map Việt Nam, gate hiệu năng và mô hình dự toán server/chi phí.
Các file plan cũ giữ nội dung lịch sử và trỏ tới TXT mới. Không sửa code game,
không clone/install/fork engine, không deploy, không tick nghiệm thu sản phẩm.

Coordinator đã kiểm cấu trúc, liên kết, dependency DAG, đủ mục đặc tả,
UTF-8, sentinel, hash nguồn và số học dự toán bằng validate-document.ps1.
Đây không phải benchmark, kiểm chứng giao thức chạy thật hay bảo đảm hết lỗi.
Hai worker nghiên cứu đã đọc tài liệu/repo và nguồn chính thức; xem
research-tools-a.md và research-game-b.md. Các thông số chưa đo được ghi là
mục tiêu/giả thuyết, không phải năng lực thực tế được chứng nhận.

## Source U2

Manifest: freeze-u2.json, 15 file; thuật toán ghi trong manifest.
SOURCE_MANIFEST_SHA256=0fa81a96099432e9d6f2b086600780b2580e222a8b88b5dc591579279c5cab22

static-u2.json và final-static-u2.json kiểm đúng source này. Thay đổi source
sau đó phải tạo revision/freeze mới và review lại; không dùng báo cáo cũ để
chứng nhận hash mới.

CLAUDE.md có thêm ngoại lệ routing đúng TXT owner yêu cầu sau freeze U2.
Phần routing này do coordinator kiểm riêng, không thuộc tập nguồn gửi critics.
Hash/path/phạm vi được ghi tại claude-routing-addition.json. Không thay
contract trong plan hoặc truy cập nội dung secret/settings.

## Kết quả các lượt phản biện độc lập bằng Cursor

| Lượt | Host exit / stdout | Kết quả thực tế |
| --- | --- | --- |
| Critic A U1 | 0 / có báo cáo | REVISE: phạm vi P1-01 chồng ST-01/ST-04/ST-05; xem critic-a-u1.md |
| Critic B U1 | 0 / có báo cáo | REVISE: admission khi chuyển room và atomic multi-grant; xem critic-b-u1.md |
| Critic A U2 | 1 / 0 byte | ActionRequiredError: out of usage, không có verdict |
| Critic B U2 lần đầu | 1 / 0 byte | EPERM khi CLI đổi tên config tạm, không có verdict |
| Critic B U2 thử lại | 1 / 0 byte | ActionRequiredError: out of usage, không có verdict |

Hai critic U1 đối chiếu cùng freeze-u1.json và đều yêu cầu sửa. Coordinator
đã sửa các finding vào U2 và ghi cách xử lý tại coordinator-resolution-u2.md.
Điều này không đồng nghĩa hai critic đã chấp thuận U2.

Host records cho U2: critic-a-u2-host.json (18:31:25 +07),
critic-b-u2-host.json (18:28:51 +07), critic-b-u2-retry-host.json
(18:31:21 +07). stderr của A và B retry cùng báo:
"ActionRequiredError: Increase limits for faster responses You're out of usage."
Các lệnh lỗi không tạo báo cáo review; không diễn giải exit 1 thành REVISE/PASS
của model. Không đọc config, không tự đổi sang Auto/Composer/model khác,
không dùng model khác làm critic và không tiếp tục retry khi đã rõ hết quota.

## Việc còn thiếu để chấp thuận thiết kế

Cần hai lượt critic độc lập bằng đúng model yêu cầu, trên cùng source U2
còn nguyên hash (hoặc revision/freeze mới nếu đã sửa), rồi xử lý finding và
ghi verdict rõ ràng. Chưa có lượt đó vì giới hạn sử dụng Cursor. File vẫn
được bàn giao để owner/agent đọc và review, nhưng chưa được gắn ACCEPTED.
Các gate chạy thật trong 40 WP vẫn phải làm khi owner mở thực thi.

Không commit trong lượt lập plan này: thay đổi tài liệu nằm ở hai repo và
working tree social còn có nội dung khác của owner. Không stage nội dung
không thuộc phạm vi; không thay root authority của Vault Fighters.

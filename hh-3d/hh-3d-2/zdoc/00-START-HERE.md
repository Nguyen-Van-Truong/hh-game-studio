# HH World 2 — đọc từ đây

Ngày lập: 2026-09-05 · Múi giờ: Asia/Saigon · Scope: `hh-3d/hh-3d-2`.

**Mục tiêu:** game xã hội 3D nguyên bản, cảm hứng trải nghiệm Play Together,
không khí Việt Nam; làm gameplay trước, tích hợp địa lý Hoàn Hảo sau.
Chọn hướng **Godot native nguyên bản + công cụ mở rộng ở cấp project**.
Không clone/fork lõi engine trong giai đoạn khởi đầu. Lựa chọn phải vượt
bài thử kỹ thuật sớm; không coi đây là lời hứa FPS hoặc sức chứa.

## Thẩm quyền và thứ tự đọc

1. `../AGENTS.md`: routing và yêu cầu owner mới.
2. `PROGRESS.md`: đang ở đâu, được phép làm gì, WP tiếp theo.
3. `06-ROADMAP.md`: nguồn duy nhất về thứ tự, dependency, trạng thái WP,
   điều kiện nghiệm thu. Không lấy số file/code/screenshot làm tiến độ.
4. Đọc đúng contract mà WP viện dẫn:

| File | Nội dung có thẩm quyền trong scope mới |
|---|---|
| `01-DECISIONS.md` | Quyết định engine, mục tiêu, phạm vi, giả định và quyền |
| `02-PRODUCT.md` | Trải nghiệm người chơi, nội dung v0.1/v0.2, social/shop |
| `03-ARCHITECTURE.md` | Client, server, protocol, dữ liệu, persistence |
| `04-GODOT-TOOLS.md` | Engine pin, editor workflow, semantic tools, art pipeline |
| `05-QUALITY-GATES.md` | Các bộ kiểm thử và ngưỡng chất lượng |
| `07-GEOGRAPHY.md` | Tích hợp địa lý thật và bản đồ Hoàn Hảo |
| `08-AGENT-WORKFLOW.md` | Hợp đồng giao Cursor, lease, critic, evidence |
| `09-RESEARCH.md` | Nguồn, mức tin cậy, giới hạn nghiên cứu |

Không có hai bảng checkbox. `PROGRESS.md` chỉ trỏ WP, không tự tạo thứ tự.
Các report trong `reviews/` là đầu vào phản biện, không có quyền thay contract.
Nếu source đổi sau critic, review cũ không còn nghiệm thu cho source mới.

## Quan hệ với sản phẩm cũ

`hh-3d/app/PROGRESS.txt` và plan real-application cũ vẫn quản lý Web cũ.
Không đổi/tick chúng. `GATE-U1` cũ không chặn việc lập plan/game mới, cũng
không được coi là đã đạt nhờ game mới. Root Vault Fighters là sản phẩm khác.

Giữ bài học: chuyển động/camera cần kiểm tra bằng chơi thật; local demo khác
Internet; shop tồn tại khi owner offline; trạng thái hiện diện khác GPS;
FPS trung bình không thay thế kiểm tra khựng lúc bắt đầu/chuyển khu.

## Điểm kết thúc cụ thể

- **v0.1 closed alpha:** một khu phố tự dựng, avatar hoàn chỉnh, một hoạt động
  câu cá nguyên bản, nhiệm vụ nhỏ, phòng riêng/trang trí, cửa hàng vật phẩm
  ảo, bạn bè/party, chat/emote có moderation, room server và lưu dữ liệu thật.
- **v0.2 pilot Việt Nam:** một quận/khu phố giới hạn từ dữ liệu được duyệt,
  giữ gameplay v0.1; tích hợp địa điểm/shop Hoàn Hảo qua adapter; vận hành
  thử có giới hạn, rồi release sau các gate về thiết bị, bảo mật và người dùng.
- Hàng vạn CCU, cell liền mạch, voice, tiền thật, UGC tự do, toàn Việt Nam
  walkable là các nhánh tương lai có gate riêng; không được quảng cáo là v0.2.

## Cách bắt đầu sau khi owner yêu cầu triển khai

Giao đúng `H2-P0-01` trong roadmap. Không tải engine trước khi kiểm tra máy,
pin và artifacts hiện có. Không làm ngay phần địa lý hoặc crowd cực lớn.
Plan đủ để bắt đầu; mọi ngưỡng dự kiến vẫn phải đo và ghi bằng chứng thật.

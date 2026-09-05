# Quyết định và giới hạn

Ngày: 2026-09-05. Đây là quyết định thiết kế của coordinator từ yêu cầu mới;
không phải chữ ký nghiệm thu người dùng, benchmark hay chứng nhận phát hành.

## D01 — Chuyển trọng tâm sang game

Owner muốn sản phẩm giống trải nghiệm game xã hội Play Together, gameplay
trước, địa lý Việt Nam sau. Web cũ thiên về app bản đồ/shop. Không lấy chi phí
đã viết Web làm lý do bắt game mới tiếp tục bằng cùng renderer.
Tên làm việc: **HH World 2**. Tên phát hành sẽ được duyệt riêng; không đưa
tên/logo/nhân vật/map/UI/âm thanh của Play Together vào sản phẩm.

## D02 — Godot native, có gate kiểm chứng

Hướng mặc định: Godot **4.7.2-stable official standard build**, typed GDScript,
matching export templates; **trang release/archive** được Cursor đọc ngày 2026-09-05
(xem `09-RESEARCH.md`), chưa acquire/khóa artifact. Commit prefix công bố
`ed1daf0bf`; full commit và
SHA-256 từng artifact phải được kiểm tra ở H2-P0-01, không suy ra từ prefix.
Pin riêng này không đổi 4.7.1 của Vault Fighters. Windows phục vụ phát triển,
Android là thiết bị cần đo sớm; iOS có gate Mac/Xcode/thiết bị riêng.
Không coi iOS đạt khi chỉ có Windows/Android. Không mặc định Web export.

| Phương án | Lợi thế | Giới hạn | Quyết định |
|---|---|---|---|
| Web/R3F hiện tại | Link vào ngay, DOM/shop/MapLibre, có demo | Cần pipeline game/perf tốt; mobile phải đo | Giữ nguyên; fallback nếu no-install trở thành yêu cầu số một |
| Godot native stock | Scene/animation/physics/UI game, tooling tự chủ | Client phải làm mới, backend/geo vẫn phải xây | Chọn cho benchmark và sản phẩm mới |
| Godot Web | Một project game và link | Giới hạn Web/export riêng, không bảo đảm chữa lag | Nhánh tùy chọn sau, không gate v0.1 |
| Fork lõi Godot ngay | Có quyền can thiệp sâu | Build/export/merge/security maintenance, chưa có gap engine | Không chọn |
| Unity native | Phương án game 3D mobile thực tế | Hệ công cụ/điều khoản/chi phí chuyển đổi khác | So lại nếu stock Godot thất bại ở gate kỹ thuật |
| Unreal/custom engine | Có khả năng phục vụ các yêu cầu khác | Chưa thấy lợi ích bù phạm vi cho game stylized này | Ngoài roadmap mặc định |

Không gán điểm số tổng hợp thiếu trọng số. Godot native không mặc nhiên đẹp
hơn hoặc nhanh hơn Three.js. Dữ liệu tối thiểu để giữ quyết định: cùng cảnh,
rig, số avatar, camera, mức bóng, độ phân giải và thao tác; build release;
máy/renderer/driver/power/thermal được ghi; raw frame timings và video thực.

**Gate H2-P1-03:** đo Q01-B (Windows + ít nhất một Android thật); Q01-F đủ
matrix cuối ở P5-03. Nếu 32 avatar không đạt floor của gate tương ứng,
khoanh CPU/GPU/animation/streaming bằng profile.
Thử tối đa hai lượt sửa có giả thuyết và số đo. Không hạ tiêu chí để tick.
Nếu vẫn thất bại (kể cả P5-03 với final content): dừng mở rộng nội dung,
đưa ADR so sánh giảm scope hình ảnh,
renderer phù hợp, hoặc một spike Unity/Web trong scope riêng. Đổi engine là
quyết định mục tiêu lớn cần owner; thất bại không phải giấy phép fork ngay.

## D03 — Tùy chỉnh ở cấp project trước

Addons, importer, editor dock, semantic command/API, test runner, scene
templates và shaders thường đủ cho workflow người+agent. GDExtension chỉ
khi profile chứng minh phần native có lợi và thử được trên mọi target.
Fork C++ chỉ sau repro giới hạn API/bug, không có giải pháp stock/extension
phù hợp, có chi phí bảo trì + export CI + upstream/rollback và owner cho phép.

Không đặt cả source Godot vào Git của game. Nếu sau này cần đọc/debug source,
dùng checkout tách biệt hoặc `.local/godot-source/` đã ignore, tag/hash khớp
binary. Đó là mirror phục vụ tra cứu, không tự chuyển sản phẩm sang custom
engine. Engine binary/export templates ở cache công cụ, game chỉ lưu lock.
Không đổi pin hay addons của Vault Fighters để giúp HH World 2.

## D04 — Giả định sản phẩm có thể đảo ngược

- Desktop dùng keyboard/mouse; Android có touch controls. Gamepad bổ sung.
- Camera góc nhìn thứ ba, stylized, không photoreal/GTA; không GPS tracking.
- Mặc định social **Friends/private** giữ ý cũ. Có lựa chọn **Public plaza**
  rõ ràng trong game mới để gặp người lạ; không âm thầm bật hay sửa Web cũ.
- **Solo** không phát presence, không thấy avatar khác. Online connectivity
  là trục riêng; vẫn đọc shop public khi còn mạng. Không có mạng chỉ xem cache
  có nhãn thời điểm; giao dịch durable chỉ khi server xác nhận.
- Party/join đưa người chơi đến cùng room có chỗ, không hứa xuyên mọi instance.
- Soft currency + vật phẩm game; không thanh toán tiền thật, cash-out, lootbox
  trả tiền hay đặt hàng marketplace thật trong v0.1. Shop Hoàn Hảo là adapter
  v0.2 với nhãn rõ; không tự biến listing ngoài đời thành inventory game.
- Một room alpha có trần **32 người**, stress **64 avatar** để đo render.
  Đây là target, chưa là capacity. 64 actor test không chứng minh 64 khách WAN.
- Một khu authored nhỏ (~256–400 m), một gameplay loop hoàn chỉnh trước;
  kích thước chính xác chốt bằng chơi thử và ngân sách scene, không copy Y8/HAEGIN.

## D05 — Quyền lần này và quyền về sau

**Lần này:** chỉ tài liệu và review nghiên cứu trong subtree mới. Chưa clone,
cài engine, viết game/server, fetch dataset hay chạy benchmark.
Sau lời yêu cầu bắt đầu: được tự làm các WP local thuộc roadmap, đọc nguồn
công khai và tải dependency free đã pin/ghi nguồn khi WP cần, nếu không có
chỉ dẫn mới hạn chế. Đây không mở quyền sửa sản phẩm cũ.

Hỏi owner khi thực sự cần: secret/chi phí, ký hoặc public publish, quyết định
legal/brand/phạm vi dữ liệu, thay mục tiêu lớn. Trước đó chuẩn bị đầy đủ kết
quả/review package. Thiếu thiết bị/human test ghi UNVERIFIED và tiếp tục phần
độc lập; không giả chữ ký, không âm thầm giảm matrix.
Import bản đồ thật phải qua H2-P7-01. Public stranger room/chat phải có policy
audience/moderation thực tế ở H2-P6-02; lựa chọn public trong thiết kế không
tự cho phép mở một dịch vụ public chưa kiểm soát.

## D06 — Không hứa MMO liền mạch

AOI giảm dữ liệu liên quan; instancing giảm mật độ; LOD giảm render/animation.
Ba kỹ thuật khác nhau, không cái nào chứng minh server shard/handoff đã có.
v0.1 dùng room/instance có giới hạn, giao diện giải thích khi đầy/chuyển room.
Dữ liệu account/shop/friends chung qua backend; simulation từng room riêng.
Cell liền mạch chỉ mở sau load thực tế và ngân sách vận hành có số liệu.

# Nghiên cứu và quyết định sau phản biện

Ngày truy cập: **2026-09-05**. Research được giao qua Cursor CLI đúng
`cursor-grok-4.6-xhigh-fast`, theo yêu cầu owner; coordinator tổng hợp dưới đây.
Các nhận định là thiết kế đề xuất, không benchmark và không legal opinion.

## Lịch sử nghiên cứu

| Report | Cursor session | Host exit | Kết quả |
|---|---|---|---|
| `reviews/worker-01-engine.md` | `801e955d-8a62-4429-a075-f3baf0a49a13` | 0 | Đọc repo được; WebSearch/WebFetch bị từ chối, nguồn sống chưa verify |
| `reviews/worker-02-architecture.md` | `7127be95-8cb5-48d5-941f-e66a77aa67f7` | 0 | Đọc source/plan cũ; nguồn sống chưa verify |
| `reviews/worker-03-official-sources.md` | `a4440132-14e2-4047-974e-8e4f0bfcafe4` | 0 | WebSearch/WebFetch hoạt động; một số docs timeout/429 có ghi riêng |

Model là model được ghim trong invocation và worker report; CLI result JSON
không trả model attestation độc lập. Không gọi model name tự khai là bằng
chứng nội bộ nhà cung cấp. Reports giữ nguyên, lỗi/ý kiến worker không tự có
thẩm quyền thắng các contract của coordinator.

## Nguồn chính đã được lượt 03 đọc

| ID | Nguồn chính | Điều hỗ trợ và giới hạn |
|---|---|---|
| S01 | [Windows download](https://godotengine.org/download/windows/) và [archive](https://godotengine.org/download/archive/) | Worker xác minh current stable 4.7.2, 4.8 dev; không tự cập nhật pin sản phẩm cũ |
| S02 | [4.7.2 archive](https://godotengine.org/download/archive/4.7.2-stable/) và [maintenance release](https://godotengine.org/article/maintenance-release-godot-4-7-2/) | Release 2026-08-18, commit prefix ed1daf0bf; checksum/full commit cần verify lúc acquire |
| S03 | [EditorUndoRedoManager](https://docs.godotengine.org/en/stable/classes/class_editorundoredomanager.html) | EditorPlugin dùng undo manager trên stock; không tự bảo đảm multi-file transaction atomic |
| S04 | [GDExtension 4.6](https://docs.godotengine.org/en/4.6/tutorials/scripting/gdextension/what_is_gdextension.html) | Shared libraries không compile vào engine. Đây là page 4.6; ABI/build 4.7.2 phải kiểm trước dùng |
| S05 | [Web export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html) | WebGL/Wasm và khác native mobile; không cung cấp benchmark Godot vs HH Web |
| S06 | [Large world coordinates](https://docs.godotengine.org/en/stable/tutorials/physics/large_world_coordinates.html) | Double precision cần build editor/templates và có chi phí; ưu tiên local coordinates cho game nhỏ |
| S07 | [High-level multiplayer](https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html) | Transport/RPC/auth hooks; gameplay/account security do ứng dụng, không phải MMO hoàn chỉnh |
| S08 | [ENetConnection](https://docs.godotengine.org/en/stable/classes/class_enetconnection.html) | DTLS setup methods; encryption khác account authentication, phải test target build |
| S09 | [Hướng dẫn Play Together](https://hub.playtogether.haegin.kr/vi/homegame-guide/whats-the-play-together) | Social town, fishing, house/decorating, friends Follow/Summon, travel/server-transfer player UI, minigames; không mô tả backend/capacity |
| S10 | [Photon interest management](https://doc.photonengine.com/fusion/current/manual/advanced/interest-management) | Culling replication theo interest; không chứng minh sharding/handoff/CCU game mình |
| S11 | [OSM copyright](https://www.openstreetmap.org/copyright) | ODbL/attribution và chính sách service riêng; phải đánh giá sản phẩm/dataset thật ở geo gate |

Stable GDExtension URL cũ trả docs navigation, retry HTTP 429; worker dùng
versioned 4.6/4.4 và đánh dấu version. Không suy nhãn experimental 4.4 thành
trạng thái 4.7.2. Web fetch timeout không được đổi thành verified.
Không tải game packages, map extracts, asset reference hoặc source engine.

## Reference ledger gameplay nguyên bản

| Beat quan sát qua tài liệu S09 | Áp dụng cho HH World 2 | Không sao chép/không suy diễn |
|---|---|---|
| Avatar/nhà có trang trí | Catalog nguyên bản, rig/house do mình thiết kế | Không lấy model, outfit, floor plan hay UI của HAEGIN |
| Câu cá/hoạt động/sưu tầm | Một loop mới với quy tắc/UI của mình | Không khẳng định timing/reward probabilities giống game gốc |
| Follow/Summon bạn bè | Join/invite consent + room policy | Không nói backend HAEGIN dùng cell/Photon |
| Travel chuyển khu vực | Room/lobby UI rõ khi chuyển/đầy | Không hứa seamless toàn quốc |
| Game Party có nhóm người | Roadmap future activity rooms | Số người trong guide không phải room cap của HH World 2 |

## Coordinator giữ và sửa gì từ worker

- Giữ Godot stock native, workflow addon trước core fork, instance-first,
  geography-later, dedicated authority và same-hash critic.
- Không nhận claim “Web stack đã chứng minh không phù hợp” hoặc engine khác
  “đắt/thừa” như kết quả đo. Repo chỉ chứng minh demo Web còn gap FPS; D02
  chọn theo sản phẩm và có gate, không phán mọi Web game.
- Giữ shop tồn tại khi owner offline và privacy filtering; viết social public
  opt-in mới riêng, không coi “friends-only làm game chết” là sự thật bắt buộc.
- Không nhận cap 32–64 như kết quả. Chọn target alpha 32; 64 chỉ stress renderer.
- Không cấm mọi `.tscn` bootstrap text đến mức không tạo được project; T02
  phân biệt generator bootstrap và editor-owned mutation.
- Không ép physics bitwise deterministic xuyên thiết bị; epsilon/fixed clocks
  và authority test theo Q03/Q04. Không áp “một process tổng” lên test multiplayer.
- Không mặc định 13+ legal label từ worker; adult invite alpha và policy gate
  trước public. Không dựng auth/password production tự phát.
- Khóa pin mới 4.7.2 sau nghiên cứu bổ sung; binary/full checksum chưa acquire
  và phải kiểm H2-P0-01. Không clone/fork/cài trong PLAN_ONLY.

## Uncertainty còn lại, đã có WP xử lý

Thực tế GPU/Android của owner; FPS và thermal; art quality/fun; network budgets;
identity/provider/hosting có thể dùng; Hoàn Hảo API/schema/coverage/rights;
audience/moderation operator; tên phát hành/brand; iOS build/device availability.
Tất cả có gate trong roadmap. Không cần hỏi hàng chục câu trước khi owner có
prototype và dữ liệu cụ thể để quyết định; cũng không giả đã được giải quyết.

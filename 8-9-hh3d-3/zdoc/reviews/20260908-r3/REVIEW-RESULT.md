# Review hai plan HH3D-3

## Trạng thái hiện tại

Hai file active đã được chỉnh thành **Revision S5**, giữ đúng hai plan, \`PLAN_ONLY\`, 10 GT + 32 H2 đều \`PLANNED\`, không tick và không có runtime, human acceptance hay scale acceptance. Freeze chính xác nằm ở [freeze-s5.json](freeze-s5.json):

- Tools: \`6a82935e94bee3dbcfdba38b1a01549f55734f668dda465dca8e673c7d544561\`, 61,060 bytes.
- Game: \`e0861b1c2e1406de3f0aacb0c7ed611dbdcd4d2cb6fe77f807d7c3276dcc5f83\`, 146,697 bytes.
- Aggregate manifest: \`6739bda567b457d57a4d215206dbfe82da574c420492930c09b1ecb1fdf26bf6\`.

## Những gì đã sửa trong S5

Hai critic độc lập của S4 đều trả \`REVISE\` trên cùng freeze S4. Các lỗi blocking đã được xử lý:

1. Q01-B từng kéo inventory/shop/activity/house của các phase sau vào P1-03. S5 tách Q01-B tối thiểu thành plaza/avatar/walk/turn/emote và Q01-F thành route nội dung hoàn chỉnh.
2. Q04-L từng là một closure duy nhất, khiến P1-02 phải chứng minh block/chat. S5 tách L0 (P1-02), L1 (P3-03), L2 (P4-01), L3 (P4-04); P6 mới kiểm tuyến tích hợp.
3. EX41 từng đặt memory 0/8/32 và packed fleet vào P1-02. S5 phân lại cho P6-01 và P8-02; P1 chỉ giữ spike disposable.
4. EX44 từng đặt starter kit/house Online vào closure Solo P2-03. S5 tách EX44-A/B/C theo Solo, economy và house lifecycle.
5. Starter award ordering được ghi \`RESULT_RECORDED\` trước, sau đó ledger/mailbox/outbox cùng transaction \`COMMITTED\`; P3-03 dùng test double có nhãn, P3-04 mới chứng minh receipt kinh tế thật.
6. GT-08/GT-10 hiện tách producer verifier \`TQ08-B/TX16-C\` và installer \`TQ08-I/TX16-I\`, nhưng Android thật là hard gate của toàn gói; không còn desktop-only hoặc partial handoff mơ hồ.
7. Bổ sung typed \`script_text.replace\` có allowlist, revision, lease, staged parse/import, sandbox và readback hash; agent không được sửa script bằng raw shell/eval.
8. House owner leave hủy guest holds, process idle-stop rõ ràng, wake dùng lease/fencing + CAS single-flight để hai request không tạo hai process.
9. Bổ sung \`OTHER_PLAN\` trong game handoff, đơn vị \`kB/s\`, phân biệt \`actor_lod_sleep\` với house process stop và ghi rõ P1 MTU spike không khóa WAN profile.

## Kiểm tra đã chạy

[validate_plans.py](validate_plans.py) chạy PASS_STATIC_ONLY trên freeze S5. Nó kiểm encoding/control residue, exact two-file set, hash/bytes, revision/sentinels, WP order/count/status, spec bijection, exception sequence, local links, quality gates, stale routing, DAG và các sizing example. Kết quả đầy đủ ở [static-s5.json](static-s5.json).

[validator-selfcheck-s5.json](validator-selfcheck-s5.json) ghi sáu ca âm tính chạy trên bản copy trong memory: cycle, future network gate, Solo/Online closure, missing spec, sai sizing và broken link đều bị reject; source thật không bị sửa. Diff review nằm ở [s4-to-s5-8-9-godot-blender-agent-studio-plan.txt.diff](s4-to-s5-8-9-godot-blender-agent-studio-plan.txt.diff) và [s4-to-s5-8-9-hh-world-gameplay-viet-nam-plan.txt.diff](s4-to-s5-8-9-hh-world-gameplay-viet-nam-plan.txt.diff).

Các nguồn official được ghi trong hai plan và dùng để đặt yêu cầu kiểm chứng, gồm Godot archive/dedicated export/MultiplayerSynchronizer, Blender threading, RFC 8785 JCS, TUF, PostgreSQL partition/WAL, Google SRE overload, RFC 9700 OAuth, Android page-size và OSM tile/Nominatim policy. Nguồn chỉ hỗ trợ thiết kế; không được dùng làm benchmark dự án.

## Critic và giới hạn còn lại

S4 có hai verdict độc lập \`REVISE\` và các findings trên đã được sửa trong S5. Tôi đã khởi chạy lại hai critic đúng model \`cursor-grok-4.6-xhigh-fast\` trên cùng freeze S5, nhưng cả hai dừng trước khi đọc với \`ActionRequiredError: Increase limits for faster responses / You're out of usage\`, exit 1, stdout 0. Hồ sơ raw là [critic-a-s5.host.json](critic-a-s5.host.json) và [critic-b-s5.host.json](critic-b-s5.host.json). Không đổi model, không suy diễn thành \`ACCEPT\`; vì vậy trạng thái thiết kế S5 là **INSUFFICIENT_EVIDENCE**, chờ hai critic mới trên chính hash S5.

Các ví dụ 13 rooms/16 rooms/91 rooms, 5–8 nodes và 77.76/15.552 TB là phép tính minh họa đã kiểm, không phải capacity. Claim hàng trăm triệu account/CCU, FPS, WAN, durability, UX với người thật, legal/brand, giá cloud và public release đều chưa được chứng minh. Việc cần làm tiếp theo là chạy đúng hai Cursor critic S5 khi quota có lại; nếu có finding mới thì tăng revision, freeze lại và chạy static check + hai critic trên hash mới. Không dùng \`research.md\` cũ có timeout/exit 1 hoặc verdict S4 làm acceptance cho S5.

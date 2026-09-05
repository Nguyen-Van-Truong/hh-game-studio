# Quality gates và công thức đo

Các con số là **ngưỡng thiết kế dự kiến**, chưa có kết quả. H2-P0-02 khóa
SKU/OS/renderer/preset; muốn đổi ngưỡng sau đó phải có decision + reason +
review, không hạ âm thầm để hợp code. Người thật/thiết bị chưa có ghi UNVERIFIED.

## Q00 — Gate chung cho mọi WP

Dependency ACCEPTED; files đúng lease; code/import sạch lỗi; warning phải có
giải thích và review rõ, không blanket suppress. Không crash/leak chưa giải
thích, lost/duplicate durable updates, secret, fabricated acceptance. Worker
báo candidate, critic độc lập đúng hash, coordinator mới ACCEPTED.
Ghi run_id/command_id/seed/config/source manifest/artifact/trace hash, timestamp,
repro command, expected/actual, process exit và leftovers từ host. Parser phải
fail closed khi evidence thiếu/stale; banner PASS hoặc caller supplied exit
không đủ. Xem workflow cho mức reviewer mỗi WP.

## Q01 — Benchmark tái lập và thiết bị

**Q01-B (basic, P1-03):** Windows + ít nhất 1 Android thật đã khóa SKU, load
0/8/32, cold/warm 3 run theo công thức; thermal quan sát 10 phút có nhãn, chưa
là final. Thiếu Android thứ hai không chặn gate B. Thiếu mọi Android thì B GAP.
**Q01-F (final, P5-03/P8-03):** đủ Windows + Android tầm trung + Android thấp,
final content, cold/warm + thermal 20 phút và tất cả ngưỡng dưới. Gate B không
thay gate F. P0-02 profile phải ghi required test IDs theo WP, không dẫn Q01 chung.
**Q01-C (cold)** và **Q01-W (warm)** là hai phép đo cấu thành cả B/F, quy định
ngay dưới bảng. Không đánh tráo cold run đã cache bằng warm run.

Matrix Q01-F bắt buộc: 1 Windows laptop iGPU hoặc cấu hình thấp được chọn, 1 Android
tầm trung thật, 1 Android thấp thật để quyết định support floor. iOS chỉ được
claim sau máy thật + toolchain Mac; không là điều kiện của Windows/Android
closed alpha nếu release scope chưa gồm iOS. Thiếu máy không ngăn test logic,
nhưng không được tick gate mobile/release.

Benchmark fixture v1: cùng plaza, GLB/rig/material/animation/hash, camera route,
0/8/32 avatar; 64 avatar stress render riêng. Avatar có đi/emote/trang phục,
không chỉ cube đứng. Cảnh gồm khu đông, chỗ bị che khuất, UI inventory/shop,
chạy/nhảy/quay nhanh, lần đầu activity và vào nhà. Ghi nguồn tạo actor.

Release build, đúng renderer, vsync/FPS cap, độ phân giải render và display,
quality/DPR, CPU/GPU/driver/RAM, power mode, network, nhiệt và app nền.
Mỗi cấu hình 3 run riêng: cold launch có first-use; 60 s warmup + route 180 s;
soak 20 phút Android để thấy thermal. Không chỉ đo đứng nhìn trời. Capture
profiler để chẩn đoán riêng; capture nghiệm thu không bật overlay nặng.
Raw frame times theo ms + p50/p95/p99, slowest windows và hitch count.
1% low = 1000 / mean của 1% frame-times lớn nhất; ghi cách tính, không lẫn
với FPS trung bình hay reciprocal p99. Không bỏ startup/hitch ra mà không nhãn.

| Target 32 avatar | Ngưỡng nghiệm thu warm route | Ngưỡng stall |
|---|---|---|
| Windows Low/Med 1080p trên SKU khóa | median frame ≤16.7 ms; p95 ≤22 ms; p99 ≤33.3 ms | Không >100 ms trong route đã warm; ≤1 frame >50 ms/phút |
| Android tầm trung Low 720p render | median ≤33.3 ms; p95 ≤40 ms; p99 ≤50 ms | Không >150 ms trong route; không cửa sổ 10 s trung bình <25 FPS |
| Android thấp Low 540–720p, preset khóa | median ≤33.3 ms; p95 ≤50 ms; p99 ≤66.7 ms | Không sustained 10 s <20 FPS; không crash/OOM |

Q01-C: cold playable ≤15 s desktop / ≤25 s Android với gói local, bao gồm
phase asset/shader warmup có tên nếu dùng; UI loading vẫn responsive. Đo cả
thời gian đó, không bỏ khỏi kết quả. Sau khi UI cho phép điều khiển, first
move/emote hitch phải ≤150 ms. Q01-W: route sau warmup áp bảng frame/stall
phía trên. Không đánh dấu “playable” rồi freeze compile, không kéo loading
vô hạn để che hitch. Chuyển nhà/khu có
loading hợp lý ≤5 s local; WAN/content streaming đo tách băng thông/cache.
Headless dùng logic/network, **không nghiệm thu GPU FPS**. Client render bots
không chứng minh multiplayer. Không giả “cùng GPU” khi cloud software render.
Thermal final: route lặp 20 phút, cửa sổ 3 phút đầu/cuối và checkpoint 5 phút
đều áp ngưỡng bảng của SKU; sustained stall cũng áp toàn soak. Nóng/throttle
làm trượt ngưỡng là FAIL, không chỉ observation. Ghi nhiệt/clock/power nếu đo
được; unavailable không thay frame-time evidence. P5-03 fail xử lý theo D02:
profile → tối đa hai vòng sửa → ADR scope/renderer/engine, không giảm số để tick.

## Q02 — Ngân sách cảnh ban đầu

Các budget này là diagnostic guardrails; vượt cần review số đo, không tự
đồng nghĩa FAIL nếu vẫn đạt Q01. Không dùng đạt polygon budget thay cho FPS.

- Android scene visible ~300k triangles, ~150 draw calls, ≤128 MB texture GPU
  cho slice, process working set mục tiêu ≤750 MB; phải xác định cách đo OS.
- Avatar near mục tiêu ≤8k triangles, ≤2 materials, skeleton ≤60 bones;
  LOD xa ≤2k triangles, giảm animation/nameplate/shadow. 32 near worst case phải đo.
- Props static dùng atlas/instances, culling theo chunk; texture ưu tiên 512/1K,
  chỉ dùng 2K khi rõ lợi ích. Mobile compression tested, không ship source PNG
  không nén thay imported export. Audio voices/pool và stream music có cap.
- Sau 10 vòng vào/ra nhà và 20 phút soak: sau warmup/GC, retained memory không
  tăng đơn điệu >10% baseline; explicit resources/orphan/leak report phải sạch.
- Frame main thread budget phân rõ scripts/physics/animation/render submission;
  GPU time đo nếu tool hỗ trợ; không đo được ghi unavailable, không suy CPU=GPU.

## Q03 — Gameplay, art và usability

### Q03-A — Gameplay tự động và replay qua input thật

Player-route E2E: launch → preset → đi/chạy/nhảy/dốc → mở tương tác → câu cá
→ item → đặt nội thất → quầy → save/relaunch. Touch có deadzone/multi-touch,
di chuyển trong khi xoay camera, không cướp focus menu; keyboard binding remap.
30/60/120 render caps không làm đổi speed quá epsilon 1% trên route phẳng
đã pin, collision/physics tolerance chốt riêng. Camera không xuyên tường hoặc
che nhân vật trong tuyến chuẩn; settings mute/reduced motion thật sự tác dụng.

### Q03-R — Art/runtime review

Art review: 6 góc player (gần avatar, di chuyển, plaza, nhà, shop, touch HUD),
video 60–90 s có animation và scene transition; kiểm tra chữ Việt, clipping,
silhouette, màu, lighting, feet sliding, costume intersection, safe area.
Không kết luận “đẹp như Play Together” từ code hay một screenshot. Checklist
phải chỉ ra artifact/runtime hash; tham chiếu style guide của mình.
### Q03-H — Human usability

Human usability theo P07: 5 người, 4/5 đạt hành trình và điều khiển. Không yêu
cầu họ hiểu marker kỹ thuật. Ghi consent tối thiểu, anonymized feedback.

## Q04 — Multiplayer / WAN / capacity

### Q04-L — Hai client local thật và authority/cleanup

2 client process thật + 1 server, tách user dirs: A đi/nhảy/emote, B thấy đúng
hướng; B tương tác; disconnect A → B hết ghost trong 10 s; logout/block có
kết nối → revoke visibility/chat ≤2 s. Duplicate/out-of-order/session cũ
không resurrect avatar/item. No source editor writes trong official run.

### Q04-N — Network impairment/reconciliation

Network emulator profiles: LAN; RTT 100 ms/jitter 20 ms/loss 1%; stress RTT
200 ms/jitter 50 ms/loss 3%, disconnect 10 s, reconnect. Đây là simulated
conditions, ghi seed/config; WAN gate thêm 2–4 máy khác mạng thật. Interactive
route không teleport. Target remote presentation age p95 ≤250 ms ở profile
100 ms, correction position p95 ≤0.25 m trên đường phẳng không teleport;
không hứa số này trong stress, nhưng stress phải hồi phục không mất state.

### Q04-C — Capacity kỹ thuật

Target room 32 connected clients có message/input/interaction thực, không chỉ
idle socket: server tick 30 Hz, p95 tick ≤16 ms, p99 ≤25 ms; không backlog tăng
qua soak 60 phút. Measure host specs, process/room count và CPU headroom.
Per client average gameplay traffic mục tiêu ≤30 KB/s xuống / ≤10 KB/s lên,
chưa gồm tải content; record bursts/p95 separately. DoD mặc định bắt buộc 32
đạt trên cấu hình ghi rõ. Nếu chỉ đạt ít hơn, FAIL/GAP; proposal đổi cap v0.1
phải được owner quyết định vì đổi trải nghiệm, cập nhật D04/P03/Q04-C và chạy
lại trước ACCEPT. Không công bố cap 16 rồi tick target 32. Nếu budget fail điều tra
AOI/update rate/delta/serialization, không cắt ACK hoặc bỏ actor tương tác.

### Q04-W — Máy/mạng thật và người dùng WAN

Q04-W1: 2–4 máy thật trên ít nhất hai kết nối Internet độc lập, secure account,
join/move/interaction/reconnect theo Q04-L; không phải emulator.
Q04-W2: WAN human alpha ít nhất 8 người được mời cùng phiên 30 phút, party/join/house/
shop/block/reconnect; không item mất/nhân đôi; operator ghi incidents và cost.
8 người thật không chứng minh 32 người thật; tải 32 network clients là bằng
chứng capacity kỹ thuật riêng. Claims phải ghi đúng loại evidence.

## Q05 — Economy, security và persistence

Adversarial tests: owner_id giả; expired/replayed ticket; command cùng id
khác payload; inventory grant client tự gửi; oversized chat/payload; spam;
draft leakage; blocked user's lookup; last-item race; double-spend/retry;
crash before/after commit; restore backup; migration rollback; account deletion.
Durable invariant: tổng currency/items chỉ đổi bởi transaction được journal;
không ACK success trước commit/readback. Outbox duplicate delivery idempotent.
Solo save không thể đưa currency vào Online bằng sửa JSON local.
Secrets scan cho source/evidence/export; TLS/DTLS/certificate fail-closed
tested; không `verify=false` cho production. Catalog images/UGC không mở rộng
ngoài scope. Threat review là checklist kỹ thuật, không tự chứng nhận compliance.

## Q06 — Geo và vận hành/release

Geo: fixture tọa độ thật → local → roundtrip ≤0.10 m numerical error trong
chunk test (không phải độ chính xác thực địa); 4 biên/chunk/negative values;
đường/nav/collision seam, ID migration, tombstone, stale tiles, provider offline.
Không có coordinates hợp lệ ngoài VN scope đã định; check dataset polygon
và policy biển đảo, không chỉ bbox camera. Nguồn/license/attribution/version
có trong release manifest và credits; bỏ watermark không làm dữ liệu original.

Ops: restore backup trên instance sạch; alpha target RPO ≤24 h/RTO ≤4 h,
đo thực tế. Crash/restart/drain/update/rollback không dupe ledger. Alert test,
rate/abuse quotas, cost cap và kill switch có operator. Public release cần
review audience/privacy/moderation/brand, quyền dữ liệu và ký-publish thực.
Chưa có approval thì package release-ready local, không tự deploy.

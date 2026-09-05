Tôi sẽ đọc tài liệu kiến trúc local (01/03/05/06/07) và các nguồn chính thức Godot/PostgreSQL, rồi trả sizing có công thức — không sửa file, không chạy server.Đang đọc các file canonical 01/03/05/06/07 và mở tài liệu Godot/PostgreSQL chính thức.Đã khóa hợp đồng local. Tiếp theo mở tài liệu Godot/PostgreSQL và vài trang mạng/CPU của nhà cung cấp.Đang mở đúng trang Godot/PostgreSQL chính thức, không dùng blog bên thứ ba làm nguồn capacity.Một số trang Godot timeout; đang đọc các file đã tải và lấy thêm trang WAL/backup/dedicated-server.Cần vài trang Godot/PostgreSQL/AWS nữa để khóa `--headless`, DTLS, standby và steal time.Đã đọc đủ tài liệu local và 8 trang chính thức. Dưới đây là stdout sizing — cấu hình khởi đo, không phải bảo đảm capacity.

---

HH WORLD 2 — KẾ HOẠCH SIZING/SERVER (STDOUT, 2026-09-05)
MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast | FILES_CHANGED=NONE | RUNTIME_PROOF=NONE
Phạm vi: `hh-3d/hh-3d-2` PLAN_ONLY (`06`: CURRENT_VALID_WP=H2-P0-01; mọi WP PLANNED). Đây là cấu hình khởi đo + công thức, không phải CCU đã chứng minh, không giá, không mua.

## 1. Hợp đồng local (thắng blog)

`01` D02/D04/D06: Godot 4.7.2 stock chưa acquire; plaza **target 32**, stress render 64; **không** cell liền mạch/MMO. `03` A01–A08: client 60 Hz + room Linux x86_64 headless 30 Hz; API monolith + PostgreSQL authority; ticket HTTPS; realtime UDP; shop sống khi chủ offline; pose ephemeral. `05` Q01: headless **không** nghiệm thu GPU FPS; Q04-C: 32 client thật, tick 30 Hz, **p95 wall ≤16 ms / p99 ≤25 ms**, soak 60 phút, ≤30 KB/s xuống / ≤10 KB/s lên (chưa content); Q06 alpha **RPO ≤24 h / RTO ≤4 h**. `06` đo Linux+transport khóa ở P3-02/P6-01; đa room/cost ở P8-02; 10k/cell ngoài P9-02. `07`: geo/job tách sim; CDN hash package.

## 2. Godot không “MMO-ready”

Docs Godot mô tả dedicated/headless, HL multiplayer (ENet/UDP), DTLS API — **không** shard, CCU, AOI quốc gia, hay bảo đảm 32 WAN. `03` A04: không ngầm coi WebSocket = ENet; UDP chặn = fail-closed. HTML5 thiếu UDP thô. Parallel đúng: Solo/art (P2) và API (P3 sau P1-03) độc lập hardware 1000/10k. Không mua fleets trước P6-01.

## 3. Không GPU server; FPS thuộc client

Godot 4.x: máy không GPU/display dùng `--headless` (= display headless + audio Dummy) hoặc export dedicated server (strip texture; template nhỏ hơn editor). Sim/authority chạy CPU. **FPS do máy người chơi** (Q01 Windows/Android). Cloud render không thay Q01. Server GPU không cần cho room headless; GPU chỉ nếu sau này encode/stream — ngoài scope.

Nhiều room vs một hotspot: CCU 300 trong 20 plaza 15 người rẻ hơn 300 trong **một** sim. Cap 32; đầy → overflow instance + UI (`01` D06, `03` A05). Degrade: giảm snapshot xa/đứng (10–20 Hz), LOD client, **không** cắt ACK/interact. Crowd proxy ≠ tương tác đủ. Mất 1 node: plaza đó chết (không seamless); N+1 + drain; reservation 30 s / actor TTL 10 s.

## 4. Công thức (đo rồi mới điền)

Đơn vị thập phân: 1 kB=1000 B, 1 MB=1e6, 1 GB=1e9, 1 TB=1e12. Tick 30 Hz: `T_budget=1000/30≈33.33 ms`.

`cpu_ms_tick` = CPU-ms **tổng** (mọi thread) một room/tick lúc N client + input/interact — **không** bằng tick wall.  
`wall_p95` = đồng hồ tường một tick (Q04-C). Một thread chính: wall≈cpu; nhiều thread: cpu_ms có thể > wall; nhiều room tuần tự trên 1 loop: wall≈Σ cpu.

```
C_eff      = nhân vật lý dành riêng * (1 - steal)   # vCPU shared/burst ≠ C_eff
rooms_cpu  = floor( (C_eff * 1000 * H) / (cpu_ms_tick * 30) )
rooms_ram  = floor( (RAM_usable - RAM_base) / mem_room )
rooms_net  = floor( BW_ok / (n_cli * (B_down + B_up)) )
rooms_tick = số room giữ wall_p95≤16ms và p99≤25ms (1 process/1 loop thường = 1 room nóng)
N_node     = min(rooms_cpu, rooms_ram, rooms_net, rooms_tick)
N_loss1    = min(...) trên (nodes-1)   # admission phải chịu mất 1 host
CCU_cap    = Σ n_cli_i   # chỉ session đang nối
```

`H` đề xuất đo 0.4–0.6 (chưa đo thì không chọn 0.9). Shop published, user idle, nhà trống, package geo = **không** CCU; chúng tốn DB/RAM/CDN/IO. AWS: 1 vCPU thường = 1 SMT thread; T3 baseline ví dụ t3.large **30%/vCPU** — hết credit thì rơi baseline (docs burstable). Soak Q04-C trên CPU **cố định**, đo `%steal`; burst chỉ dev.

## 5. Egress giả định (nhãn giả định, không đo)

Q04-C mục tiêu ≤30 kB/s xuống, ≤10 kB/s lên — **chưa đo**.

Giả định 1000 CCU × 30 kB/s xuống: `1000*30000 = 30e6 B/s = 30 MB/s = 240 Mbit/s` chỉ downlink gameplay.  
Uplink 10 kB/s: +10 MB/s. Cộng ≈40 MB/s ≈320 Mbit/s peak NIC (chưa DTLS/header/burst p95).

30 ngày **peak liên tục** (cận trên sai): `1000*30000*86400*30 = 7.776e13 B = 77.76 TB` chỉ down.  
30 ngày **CCU trung bình 200**, peak 1000: `200*30000*86400*30 = 15.552 TB` down.  
NIC/LB theo **peak**; hóa đơn theo **trung bình**. CDN mesh/audio **cộng thêm**, tách UDP.

## 6. Kịch bản = STARTING BENCH, không bảo đảm

Pin: Linux **x86_64** headless (`06` P0-01). Không tái dùng số Windows/WSL/ARM. Vùng: Asia gần VN; Q04-N 100/200 ms. Lat xuyên lục địa ≠ “cần 10k CCU”.

| Kịch bản | Vai trò / CPU | RAM·ổ·mạng (khởi đo) | Durability | Ghi chú |
|---|---|---|---|---|
| Local | 1 máy dev, vCPU dùng chung; room Linux VM/container | 16–32 GiB host; SSD laptop; loopback | `pg_dump` đủ; RPO lỏng | DEV_ONLY; 2 client thật Q04-L |
| Alpha mời 8–32 | **1** room Linux CPU cố định (không T-burst soak); API+PG có thể chung máy nếu chấp nhận chung số phận | 4 nhân / 16 GiB / NVMe+WAL disk riêng nếu được / NIC 1 Gbit | Nếu có ACK tiền/đồ: WAL archive **ngay** | 8 người ≠ 32 kỹ thuật |
| Pilot 100–300 **đề xuất** | Room **N+1** cố định; API tách; PG primary riêng; job/geo/backup **cô lập IO** | Bắt đầu 2 room-node (mỗi ~4–8 nhân / 16–32 GiB) + API 2–4 nhân / 8 GiB + PG 4 nhân / 16–32 GiB / SSD đồng bộ; NIC đủ giả định 300×40 kB/s≈12 MB/s | Primary+WAL offbox+base backup; replica đọc/failover | P8-02; cap công bố = đo, không 300/32 |
| 1000 CCU **có thể** | Nhiều room-node; PG HA; API stateless N; CDN | Chỉ sau `cpu_ms_tick`,`mem_room`,`B_*` | PITR + replica đã diễn tập | 1000/32≈32 plaza **đầy** — hotspot event phá CPU |
| 10k “cả phố” | Ngoài v0.2; cell không có | Không mua | Như public + multi-region nghiên cứu | Conditional: demand+ops P9-02 |

Cố định vs shared: room + PG primary = dedicated/reserved. API/registry/monitor = shared được nếu p95 API đo. Geo convert/OSM (`07`) = máy IO riêng, **cấm** chung tick. Content = object/CDN; gameplay UDP không đi CDN.

## 7. RPO 24h là nguy hiểm kinh tế

Q06 **cho phép** alpha mất tới 24 h dữ liệu. `03` A03/A06: client chỉ “đã nhận” sau commit+readback. Mất WAL sau ACK = mất tiền/đồ đã thừa nhận.

`pg_dump` **không** PITR. Công thức chính thức: `wal_level≥replica` + `archive_mode` + archive_command/library **trả 0 chỉ khi file bền**; chuỗi WAL liên tục từ base (`pg_basebackup`); restore+replay. Archive chậm/đầy: `pg_wal` phình → **PANIC**, committed không mất trên disk đó nhưng **offline**. Replica/hot standby = trễ, đọc-only, **không** thay archive (lỗi logic nhân bản). Reliability: fsync/cache; SSD consumer có thể bỏ flush; ECC RAM giả định.

Kế hoạch thực dụng:
- Local: dump + bài restore.
- Alpha có ledger: archive WAL offbox + 1 base/ngày + restore trống; RPO đo = độ trễ archive (phút), **không** ngủ 24 h.
- Public/pilot: thêm replica cùng region; diễn tập promote; tombstone deletion replay trước mở traffic (`03` A06).
- Room journal ≠ ledger.

## 8. UDP+HTTPS, không đổi WebSocket

API: HTTPS/TLS, LB L7. Room: UDP (HL API Godot **chỉ UDP**). LB UDP = L4/passthrough hoặc ticket `host:port`; NAT pin. Không giả HTTP proxy “upgrade” = ENet. DTLS: `ENetConnection.dtls_server_setup` / `dtls_client_setup` — phải chứng minh trên **đúng** 4.7.2 Win/Android/Linux (P3-02). Cert hết hạn = fail-closed (Q05). CDN bất biến (`world_release_id`/hash) tách packet. `bandwidth_limit` hỗ trợ trần; vẫn cần quota API.

## 9. Benchmark + acceptance sự cố hiếm

H2-P6-01/P8-02 trên Linux pin: 0/8/32 interact; ghi `cpu_ms_tick`, `wall_p95/p99`, `mem_room`, B/s p50/p95, steal, drops. Pass Q04-C **và** headroom `H` + `N_loss1`.

| Sự cố | Chấp nhận |
|---|---|
| Failover PG | Promote; RPO/RTO **đo**; không mint kép (command_id) |
| Mất room host | Drain/fail; reconnect reservation; không ghost >TTL |
| Disk đầy | Alert trước; archive fail visible; không im lặng |
| Cert hết hạn | Probe fail-closed; runbook xoay |
| CPU steal/burst | Soak chính thức loại host steal cao / hết credit |
| Lat vùng | Q04-N; không “sửa” bằng tăng CCU |
| Bão reconnect | Rate limit ticket; 30 s hold; không kick peer |
| Abuse băng thông | Quota/size; kick; CDN riêng |

## 10. Parallel hiệu quả

P0 khóa OS/engine. P1-02 ∥ P1-01. P2 art không chờ 1000 CCU. P3-01 sau P1-03. P6-01 chốt 32+Linux. P8-02 mới đa room. Geo P7+ trên job node. Một overview sizing **không** tạo checkbox thứ hai — `06` vẫn authority.

## 11. Khuyến nghị và rủi ro

Làm: bench 4 nhân x86_64 cố định + PG WAL-aware cho alpha ACK; tách CDN/UDP; overflow room; công thức §4; RPO phút khi có economy. Không làm: mua 10k; gọi 32×nodes là load; GPU room; WS thay UDP; RPO 24h cho ledger đã ACK.

Rủi ro/conditional: DTLS/NAT 4.7.2 chưa verify; issuer thật chặn P6-02; UDP ISP; steal ẩn; `cpu_ms_tick` hotspot >> idle; Godot main-thread (multithread không toàn engine); replica ≠ backup; P1-03 fail có thể đảo engine (`01` D02) — mọi số bench đổ. 1000/10k chỉ **có điều kiện** sau số đo + ops người thật.

## Nguồn chính (đã mở phiên này)

1. https://docs.godotengine.org/en/4.4/tutorials/export/exporting_for_dedicated_servers.html — headless/Dummy, không cần GPU; template vs editor. (stable cùng URL timeout)
2. https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html — `--headless` bắt buộc khi không GPU
3. https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html — UDP-only HL; không tự MMO/secure account
4. https://docs.godotengine.org/en/latest/classes/class_enetconnection.html — UDP+DTLS+bandwidth_limit (latest; ABI 4.7.2 phải khớp P0-01)
5. https://www.postgresql.org/docs/current/continuous-archiving.html — WAL+PITR; dump ≠ PITR; archive fail → đầy `pg_wal`/PANIC
6. https://www.postgresql.org/docs/current/wal-reliability.html — commit cần lưu phi-bay hơi; cache/SSD
7. https://www.postgresql.org/docs/current/hot-standby.html — replica trễ, đọc-only
8. https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-credits-baseline-concepts.html — vCPU burst/baseline; không suy C_eff

Không cited: giá cloud (không kiểm date/SKU); CCU Godot (không có).

MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast
FILES_CHANGED=NONE
RUNTIME_PROOF=NONE

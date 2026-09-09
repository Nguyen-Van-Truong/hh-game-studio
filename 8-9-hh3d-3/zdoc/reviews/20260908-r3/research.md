Tôi sẽ chỉ đọc snapshot đóng băng và tự kiểm tra nguồn chính thức, không đụng plan đang sửa hay verdict cũ.Hai snapshot đã xác định. Tiếp theo tôi đọc nội dung đóng băng và đối chiếu nguồn chính thức song song.Snippet tìm kiếm chưa đủ. Tôi sẽ mở trang chính thức và đọc các mục kiến trúc còn lại trong snapshot.Phiên bản đã khớp trang chính thức. Tiếp theo tôi xác nhận binary/checksum và các tài liệu Godot, PostgreSQL, SRE, HAEGIN.Nguồn chính thức đã mở được. Tôi đang lấy thêm trang gốc còn thiếu và các đoạn snapshot về room, RAM, shard, outbox.# Báo cáo nghiên cứu độc lập (read-only) — 2026-09-08

**Vai trò:** researcher/design critic, model `cursor-grok-4.6-xhigh-fast`, không subagent, không ghi file, không cài/chạy game.  
**Input plan:** chỉ `zdoc/reviews/20260908-r3/before/*.snapshot` (S2, PLAN_ONLY). Không đọc plan live, verdict cũ, config/secret.  
**Ngày truy cập web:** 2026-09-08 (Asia/Saigon). URL `/stable` `/current` `/latest` là trang động — không phải lock.

Phân biệt: **QUAN SÁT** = trang chính thức trả nội dung; **ĐỀ XUẤT** = yêu cầu plan, chưa nghiệm thu runtime.

---

## 1. Phiên bản Godot / Blender

| Ứng viên snapshot S2 | Kết quả 2026-09-08 | Mức |
|---|---|---|
| Godot **4.7.2-stable** | Trang tải Windows ghi **Godot 4.7.2**, ngày **18 August 2026**. Archive: **4.7.2 Current state: stable**. Bài official “Maintenance release: Godot 4.7.2”. | **CONFIRMED tồn tại / đang được quảng bá là stable hiện hành** |
| Godot 4.8 | Archive: **4.8 Current state: dev4**. Release policy: 4.8 (master) *Development*, ước Q4 2026. | **CONFIRMED không phải pin sản phẩm** |
| Godot LTS kiểu Blender | Release policy: hỗ trợ *stable branch*; LTS nêu cho **nhánh major cũ (3.x)**. Trong một minor, **chỉ patch mới nhất được support**. 4.7 (June 2026) đang nhận bug/security/platform. | **CONFIRMED: không có “Godot 4.7 LTS”** |
| Blender **5.2.1 LTS** | `blender.org/download` và `/download/lts/`: **5.2.1**, **25 Aug 2026**; series 5.2 LTS hỗ trợ đến **July 2028**. `download.blender.org/release/Blender5.2/` có `blender-5.2.1-*` + `blender-5.2.1.sha256` (25-Aug-2026). | **CONFIRMED tồn tại** |
| Fallback **4.5.13 LTS** | LTS page: 4.5 “Last updated to **4.5.13** on August 25, 2026”. Mirror có `blender-4.5.13-*` cùng ngày. Hỗ trợ đến July 2027. | **CONFIRMED tồn tại** (không còn 4.5.12 làm patch mới nhất) |

**Chưa xác minh lượt này:** SHA256/full commit/`--version` trên máy; không tải binary. File `blender-5.2.1.sha256` thấy trong listing, **không mở nội dung**. Không gắn VERIFIED-pin.

**ĐỀ XUẤT (không phải proof cài):** GT-01 khóa Godot **4.7.2-stable standard + matching templates** và Blender **5.2.1 LTS**; fallback **4.5.13 LTS** chỉ khi addon 5.2 bất tương thích đã tái hiện. Không pin 4.8-dev.

**URL Godot:**  
https://godotengine.org/download/windows/ — OK  
https://godotengine.org/download/archive/index.html — OK  
https://godotengine.org/download/archive/4.7.2-stable/ — OK  
https://godotengine.org/article/maintenance-release-godot-4-7-2/ — search hit; bài tồn tại  
https://docs.godotengine.org/en/stable/about/release_policy.html — OK (title: Godot 4.7 docs)

**URL Blender:**  
https://www.blender.org/download/ — OK (5.2.1 LTS, 25 Aug 2026)  
https://www.blender.org/download/lts/ — OK  
https://www.blender.org/releases/5-2/ — OK (5.2.1 + 5.2.0)  
https://download.blender.org/release/Blender5.2/ — OK  
https://download.blender.org/release/Blender4.5/ — OK

---

## 2. Godot: dedicated server, visibility, render

### Dedicated / headless / strip — QUAN SÁT

https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_dedicated_servers.html — **OK**  
https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html — **OK** (cùng dòng 4.7)

Official 4.0+: `--headless` **hoặc** project *exported as dedicated server*; **không** còn binary server riêng như 3.x. Máy không GPU/display: **headless display server + Dummy audio**. **Export template** (không editor) cho dedicated server — editor lớn hơn, kém tối ưu. Export thường: PCK **cùng kích thước client**, gồm texture; headless **không tự bật** trừ dedicated export / cờ `--headless`. Có thể **strip texture/material** và **giữ reference** trong scene/resource.

https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html — **OK**  
`--headless` = `--display-driver headless --audio-driver Dummy`. `--version` tồn tại. Export CLI: `godot --headless --export-release …` cần **editor binary + templates**.

**UNCERTAIN:** ma trận UI Strip / Keep / Remove không lấy đủ từ HTML official (trang cắt ở “change its export mode”). Không VERIFIED nhãn UI từ W4/proposal.

Snapshot đã nói Linux headless + EX20 “strip visual, giữ collision/nav”. **Chưa** khóa: preset dedicated-server, template≠editor, PCK server immutable/hash, cấm texture editor trong process room.

### Visibility / AOI — QUAN SÁT

https://docs.godotengine.org/en/4.7/classes/class_multiplayersynchronizer.html — **OK**

Mặc định sync **mọi peer**. `public_visibility` mặc định **true**. Lọc: `set_visibility_for` / `add_visibility_filter` / `update_visibility`. **MultiplayerSpawner** theo visibility synchronizer **chỉ khi** node `root_path` được spawn bởi một spawner. `replication_interval`/`delta_interval` mặc định **0** = mỗi network process frame.

https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html — **OK**: SceneMultiplayer có auth built-in; **không** mô tả AOI không gian.

**ĐỀ XUẤT:** visibility Godot ≠ AOI plaza. Default = lộ spawn toàn room. Forum/community **không** dùng làm contract.

### Render — QUAN SÁT

https://docs.godotengine.org/en/stable/tutorials/performance/index.html — OK  
https://docs.godotengine.org/en/stable/tutorials/performance/optimizing_3d_performance.html — OK (search + nội dung)  
https://docs.godotengine.org/en/stable/tutorials/3d/mesh_lod.html — OK  
https://docs.godotengine.org/en/stable/tutorials/3d/visibility_ranges.html — OK  
https://docs.godotengine.org/en/stable/tutorials/3d/occlusion_culling.html — OK  

Frustum culling tự động. LOD: mesh import + visibility ranges (HLOD) + distance fade. Occlusion: CPU/Embree, bật project setting, **tốn CPU**; hiệu quả indoor; open scene ưu tiên mesh LOD/HLOD. MultiMesh không cull từng instance.

**ĐỀ XUẤT:** plaza ngoài trời không bật occlusion “cho chắc”. Server headless không thay FPS client.

---

## 3. PostgreSQL — QUAN SÁT

Docs `/current` title **PostgreSQL 18** (2026-09-08).

**Partition + UNIQUE** — https://www.postgresql.org/docs/current/ddl-partitioning.html — **OK**  
UNIQUE/PK trên partitioned table: partition key **không** expression/function; cột constraint **phải gồm mọi cột partition key**. Index con chỉ unique **trong partition**; cấu trúc partition phải tự loại trùng **giữa** partition. Không có global unique index.

**`synchronous_commit`** — https://www.postgresql.org/docs/current/runtime-config-wal.html — **OK**  
Giá trị: `remote_apply` | `on` (default) | `remote_write` | `local` | `off`.  
`synchronous_standby_names` **rỗng**: `remote_*`/`local` ≡ local `on`.  
`on` + standby: chờ standby **flush WAL durable**. `remote_apply`: thêm **query-visible trên standby**. `remote_write`: **không** chịu OS crash standby. `off`: mất TX gần khi crash, không incoherence. **SET LOCAL** đổi từng TX.

**Replication** — https://www.postgresql.org/docs/current/warm-standby.html#SYNCHRONOUS-REPLICATION — **OK**  
Streaming **mặc định async**. File log shipping async. Sync: chờ RTT primary↔standby. Slot có thể **đầy `pg_wal`**. Replica read ≠ durable commit.

Snapshot DB-D2 (`synchronous_commit=on` + sync standby, không hạ khi mất standby) **khớp hướng official**. Lỗ: partition time vs `UNIQUE(command_id)` / `UNIQUE(account,attempt)` toàn cục; “partition rotation” có thể xóa dedupe.

---

## 4. Overload / backoff — QUAN SÁT

**Google SRE (đủ dùng; không cần AWS để có contract):**  
https://sre.google/sre-book/handling-overload/ — OK  
https://sre.google/sre-book/addressing-cascading-failures/ — OK  
https://sre.google/sre-book/service-best-practices/ — OK (search)

Đo capacity bằng **tài nguyên (CPU)**, không QPS tĩnh. Quá tải: degraded → shed. Client throttle khi reject. Retry: **exponential backoff + jitter**; **giới hạn retry/request**; **retry budget** process; **không retry nhiều tầng**; tách lỗi retryable/permanent; deadline + hủy lan truyền. Load test **vượt** rated capacity.

**AWS:**  
https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ — **truy cập được, body chỉ SPA/JS** → **nội dung Builders Library UNVERIFIED**.  
https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/ — **OK** (Architecture Blog, May 2023 update; trỏ tiếp Builders Library). Jitter cắt cụm retry; không jitter = sóng đồng pha.

Snapshot có jitter/shed/EX16/EX35; **thiếu** retry budget / một tầng retry / DLQ outbox.

---

## 5. HAEGIN Play Together — chỉ mặt người chơi

Không suy backend, CCU, shard, RAM từ UI.

| Nguồn | Kết quả | Quan sát (player-facing) |
|---|---|---|
| https://www.haegin.kr/game_play_together.php?lang=en | OK | Friends, Social, Minigames, Customization, Homeparty, Downtown, Metaverse; fishing, minigames, traveling, treasure hunting, decorating/gardening |
| https://help-playtogether.haegin.kr/hc/en-us/articles/1500008493722-What-is-Play-Together | OK | Thị trấn tưởng tượng; game/home party, fishing, school, camping, pets, customize, house, traveling |
| https://hub.playtogether.haegin.kr/homegame-guide/whats-the-play-together | OK | Phone: minigame, home party, customize, recycle, mission, map, friends, collection; Bag; Achievements; Inbox; Settings (invite, FPS/resolution, account link). **Travel = “server transferring” — nhãn UX, không chứng cứ kiến trúc.** Vùng East/SE Asia, Europe, America, Vietnam. Friends: online, Follow, Summon, home party/minigame. Game Party: **30** người, last standing. Pet shop/care. |
| https://help-playtogether.haegin.kr/hc/en-us/articles/1500008786522-How-do-I-place-furniture | Cloudflare challenge | **UNCERTAIN** lượt này |
| https://help-playtogether.haegin.kr/hc/en-us/categories/1500001670141-Game-Guide | **404** | Không dùng |
| https://help-playtogether.haegin.kr/hc/en-us/articles/30510767634457-Resort | search snippet | Resort/fishing/boat — **chưa fetch đủ body** |

HH World snapshot đã chọn beat chức năng hẹp (đi, câu, nhà, shop, bạn/party 4, plaza 32) và cấm copy asset/UI PT — phù hợp. **Không** lấy 30-player Game Party hay “server transferring” làm sizing.

---

## 6. Tối đa 12 lỗ hổng thiết kế + sửa tối thiểu

Không nhắc routing/section thiếu đã biết. Mỗi mục: lỗ trên snapshot S2 → sửa nhỏ cho coordinator.

### G1 — Gói server immutable ≠ editor/client PCK
**Lỗ:** Linux headless + “strip visual” chưa khóa official: preset dedicated-server, **export template**, PCK hash, Keep collision/nav/sim. Editor `--headless` vẫn kéo texture/editor.  
**Sửa:** H2-P0-01/P1-02: một **server asset package** (template Linux + PCK dedicated), hash/manifest; ma trận file Keep=collision/nav/catalog sim, Strip=texture/material (nếu UI official xác nhận ở GT-01); cấm editor binary trên room. So RSS PCK server vs client.

### G2 — Visibility Godot ≠ AOI / privacy
**Lỗ:** `public_visibility=true` + interval 0 = mọi peer nhận spawn/pose. Block/ẩn có thể chỉ ẩn mesh.  
**Sửa:** P4-01: `public_visibility=false`; filter authority (gần + party + interact); spawn theo cùng filter; test peer ngoài AOI **không** nhận spawn; block/revoke re-check lúc commit (đã có hướng, cần gắn API Godot).

### G3 — RAM room/connection vs kho account
**Lỗ:** Tách 4 chỉ số và `mem_room`, nhưng không cấm room load catalog/bạn/lịch sử trăm triệu.  
**Sửa:** Allowlist process room: sim + actor AOI + session ticket. Account/catalog/ledger **chỉ** API/DB. Cap hàng đợi snapshot/connection; vượt RSS → từ chối join, không swap vô hạn.

### G4 — Baseline 1 process / 1 room
**Lỗ:** “Không nhồi room nếu chưa đo” — chưa có cổng đo overhead Godot rỗng.  
**Sửa:** v0.1: **1 dedicated process = 1 room**. Packing chỉ sau RSS(0 room), RSS(1 room 0 player), RSS(cap 32). Overhead process là chi phí hạng nhất.

### G5 — UNIQUE toàn cục vs partition theo thời gian
**Lỗ:** `UNIQUE(account,attempt,…)` + partition `account/region/time` + “partition rotation” mâu thuẫn limitation PG. Xóa partition = mất dedupe → replay award.  
**Sửa:** Bảng nóng kinh tế **không** range-time, **hoặc** unique gồm partition key **và** bảng **idempotency/tombstone không partition** là authority. Cấm DROP partition khi tombstone còn trong retry horizon.

### G6 — Một owner-DB / một economic realm
**Lỗ:** Tránh TX xuyên shard nhưng mua = buyer + seller + listing + outbox.  
**Sửa:** v0.1 **một `economic_realm_id`**, một DB owner: wallet+inventory+listing+mailbox+outbox cùng TX. Không chuyển item/tiền sang realm khác. Cross-account trong realm = cùng DB, không saga.

### G7 — Admission atomic trên DB, không bộ đếm router
**Lỗ:** Registry TX/CAS đã viết; occupancy cache có thể check-then-act.  
**Sửa:** Cấp ticket + unique hold/cap **một TX Postgres**. Router = cache. EX12: cache “còn chỗ” + unique reject = fail sạch, không overbook.

### G8 — Test dataset/index tách khỏi CCU Godot
**Lỗ:** Synthetic 100k/1M/10M đã nêu, chưa có SLO truy vấn độc lập.  
**Sửa:** Job P3-01/P6-01: N hàng account/command/friend **không** mở room; p95 `command_id` / `account_id` / friendship; chứng minh partition prune. Không lấy 32 CCU làm proof trăm triệu account.

### G9 — Thu hồi visibility ≠ khôi phục account
**Lỗ:** EX14 revoke ≤2s; EX32 tombstone xóa. Thiếu restore **unhide/unblock** vs cấm undelete kinh tế.  
**Sửa:** Hai hợp đồng: (a) `visibility_restore` — resubscribe AOI, không phát pose lúc ẩn; (b) xóa account: không hồi ledger/shop/bạn. Unblock ≠ replay lịch sử ẩn.

### G10 — Outbox at-least-once không bounded
**Lỗ:** Dedupe consumer; thiếu max attempt, jitter, retry budget, một tầng. SRE: retry nhân tải.  
**Sửa:** Outbox: N attempt + backoff+jitter + DLQ; hết N → UNKNOWN/operator, **không** `command_id` mới. Client/API/room: **một** tầng retry. Grant permanent fail = không retry.

### G11 — UX UNKNOWN / shed / hết hạn replay
**Lỗ:** UNKNOWN→lookup đã có; người chơi dễ thấy “thất bại” khi shed, mất standby, hoặc command hết retention.  
**Sửa:** 5 lớp UI: hàng đợi đầy; đang bảo vệ dữ liệu; UNKNOWN+tra cứu; hết hạn/không cộng thưởng; từ chối quyền. Cấm “thất bại” khi server có thể đã commit. Hết retention: “phiên cũ hết hạn”, không mint.

### G12 — Addon: main thread + save đa file
**Lỗ:** TQ03 đã nói không ACK chỉ vì `commit_action`. H2-P1-01 dễ ACK sớm / dùng ObjectID. Official: object Godot trên main thread; ObjectID không sống qua reload.  
**Sửa:** ACK chỉ khi journal liệt kê **mọi path** + readback hash. Target = stable ID+revision, resolve lại trên main thread. Mutation editor **không** trên process Play. Generated addon game = hash package, không sửa tay.

---

## 7. CONFIRMED / UNCERTAIN (ngắn)

**CONFIRMED:** Godot 4.7.2-stable (18 Aug 2026) là stable được quảng bá; 4.8 chỉ dev; Godot không LTS 4.7. Blender 5.2.1 LTS và 4.5.13 LTS (25 Aug 2026) có trang + file mirror. Headless/Dummy/dedicated export/template vs editor. Synchronizer visibility mặc định public. PG UNIQUE phải chứa partition key. `synchronous_commit=on` ≠ `remote_apply`; streaming mặc định async. SRE: backoff+jitter, retry budget, shed, đo bằng CPU. HAEGIN public: bạn/Follow/Summon, nhà, câu, party, customize, Phone/Bag/Inbox — **không** suy capacity.

**UNCERTAIN:** checksum/fullcommit chưa tải; Strip/Keep/Remove UI official chưa đọc hết; Builders Library body (JS); help furniture (Cloudflare); Resort article body; số DAU/download marketing (không dùng). `/stable` `/current` có thể đổi sau 2026-09-08.

---

## 8. Yêu cầu đề xuất (plan, không acceptance runtime)

1. Pin ghi **phiên bản + URL archive/mirror + SHA256 + `--version`** tại GT-01; docs khóa `/4.7` không chỉ `/stable`.  
2. Room = dedicated-server **template** + PCK strip visual, hash bất biến.  
3. AOI/privacy = authority + visibility Godot tắt public; test không lộ spawn.  
4. RAM room bounded; account store ngoài process; v0.1 một process/room.  
5. Idempotency/tombstone **sống lâu hơn** partition drop; unique PG theo limitation official.  
6. Một economic realm / một owner DB; không chuyển xuyên shard.  
7. Admission = unique TX, không tin bộ đếm RAM.  
8. Load dataset/index **tách** load CCU; overload test có shed + jitter + retry budget (SRE).  
9. Revoke/restore visibility ≠ undelete kinh tế.  
10. Outbox bounded + một tầng retry; UX UNKNOWN/hết hạn rõ.

Đây là yêu cầu thiết kế từ nguồn official + snapshot S2. **Không** phải PASS runtime, **không** hứa đã phủ mọi trường hợp. Coordinator sửa plan; researcher không tick, không implement.
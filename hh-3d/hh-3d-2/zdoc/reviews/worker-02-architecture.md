Tôi sẽ đọc tài liệu sản phẩm cũ và nguồn chính liên quan, rồi trả báo cáo kế hoạch A–Z (chỉ đọc, không triển khai).Đã có cấu trúc tài liệu. Tiếp theo tôi đọc PROGRESS, owner-modes, kế hoạch ứng dụng thật và các review hiện có.PROGRESS rất dài; tôi sẽ lấy phần đầu, phần hiệu năng và các bằng chứng avatar/shop/map, rồi đối chiếu kế hoạch canonical.Tiếp theo tôi lấy bằng chứng shop/avatar/map trong mã và tài liệu, rồi đối chiếu nguồn Godot/OSM/multiplayer.Tôi đang đọc hợp đồng avatar/shop/presence và các nguồn chính thức về Godot, glTF, mạng và OSM.Tìm web bị từ chối; tôi đọc hợp đồng local và thử lấy tài liệu chính thức từng URL.Tìm web bị từ chối; tôi đọc thêm mã local và thử lấy tài liệu chính thức từng URL.Web bị từ chối nên tôi bổ sung hợp đồng local (manifest, graph, demo-bus) và đánh dấu phần web là chưa xác minh.Tôi đã đủ bằng chứng local. Báo cáo dưới đây là PLAN_ONLY: không triển khai, không nhập blocker cũ vào scope mới.

---

# HH-3D-2 — Tư vấn plan A–Z (PLAN_ONLY, 2026-09-05 +07)

**Phạm vi:** game xã hội nguyên bản (cảm giác Play Together), vị Việt, chơi trước, địa lý Hoan Hao sau. Cũ `hh-3d/app` và Vault Fighters **không đổi**. Godot native là **ứng viên**, không phải điều phải bảo vệ. Coordinator viết plan; đây là lời khuyên + bẫy.

**Web chính thức:** `WebSearch`/`WebFetch` bị từ chối phiên này. Mọi claim Godot/glTF/UndoRedo/tọa độ lớn/OSM/PostGIS/MapLibre/Play Together backend = **CHƯA XÁC MINH NGUỒN SỐNG 2026-09-05**. URL dưới là chỉ dẫn coordinator phải mở lại trước khi khóa stack.

---

## 1. Kho sản phẩm cũ (có mã ≠ plan PASS)

Live cũ: Vite + React + R3F + MapLibre, preview **chỉ** `127.0.0.1:4175`. Checkbox `31-8-hh3d-real-application-plan.txt` vẫn `[ ]`. `GATE-U1` (3 người, 5 phút) **chưa có**. `AUTHORIZE_MAP_FETCH=NO`.

| Hạng | Trạng thái | Nguồn local |
|---|---|---|
| Fixture 400 m authored, tâm 10.7725, 106.6980; **không** OSM | Có artifact + honesty | `hh-3d/app/manifests/world-manifest.json` (`authored_or_source=authored`, `fetch_performed=false`, forbidden 1:1/digital twin/GTA) |
| MapLibre 2D + extrusion 60 thửa | Local, FPS Play **không** đạt R2 | `PROGRESS.txt` idle MapLibre median 56.82; Harbor Play idle mean 44 / first-W min ≈10; owner headed ~16 FPS · `NOT_60` |
| Đi phố self, A/D strafe, yaw −1, walk 2.55 / sprint 4.35, collision vòng + bán kính 0.55 m | CDP + critic hash; **không** M0-WP1 | `walk.ts`, `look.ts`; `NEARBY_SHOP_M=4` |
| Shop authored + kệ public khi chủ Offline | Schema + fixture | `shop-catalog.schema.json`, `shops.json` (`shop-lantern-fish`, listing draft ẩn) |
| Tạo shop / đăng / nháp + `idempotency_key` | LocalStorage + `/demo-bus`; **không** R3/M1 | `localListings.ts`; J2/J4 OBSERVED |
| Bạn A/B, người lạ C không hiện | 2 ghế máy này; **không** M2 | `seats.ts`, `graph.ts` (chỉ cặp a–b), `presence.ts` |
| Presence TTL 10 s; ẩn tab = leave một lần, không đổi Offline | Local | `PRESENCE_TTL_MS=10000`; `shouldPublishStreetPresence` |
| Store this-PC, loopback 403 | **Không** WAN/OIDC | `vite.demo-bus.ts`; persist `web/.data/this-pc-shared.json` |

**Đã chứng minh local (fixture/CDP, không phải multiplayer thật):** T01–T05 một phần trên 2 tab/profile cùng 4175; shop persist sau Offline; C không vẽ; nháp không lên kệ.

**Chưa chứng minh:** account thật, PostGIS, moderation vận hành, WAN, 20 bạn, mobile headed, GATE-U1, OSM, thanh toán, chat, crowd người lạ.

**Giữ làm hợp đồng hành vi (copy ý, không copy runtime web):**
- Tách **mode xã hội** khỏi **internet**.
- Presence = vị trí avatar ảo, **không** GPS/camera.
- Shop published sống độc lập chủ Online.
- Lọc visibility **phía authority**, không gửi tọa độ rồi ẩn client.
- Catalog: `shop_id` / `listing_id` ổn định, `version`, vòng đời draft→published→hidden/sold_out/deleted, nháp + idempotency, STALE ≠ UNAVAILABLE ≠ EMPTY.
- Honesty: không 1:1, không digital twin, không “đã mua”.
- Geo sau này: nguồn WGS84, sim local ENU; `osm_id` ≠ `shop_id`.
- Quy trình: một writer, critic độc lập cùng hash, không bịa chữ ký người.

**Mặc định MỚI — phải ghi quyết định, không lặng sửa file cũ:**
1. **Ai thấy ai:** cũ = chỉ bạn; Play Together-like = **cùng instance** (bạn là overlay, không phải trần duy nhất).
2. **Sản phẩm:** cũ = web map; mới = **game** (emote, party, hoạt động, nhà, sưu tầm).
3. **Không** lấy `GATE-U1` / `AUTHORIZE_GODOT2_CITY=NO` / web-first / “không Godot” làm veto lane mới.
4. Không dùng `/demo-bus` làm server alpha.
5. Không dùng lng/lat làm tọa độ sim (trượt float + dính MapLibre).
6. Không tiền thật / IAP ở slice đầu.

---

## 2. Chuỗi A–Z (dependency; spike mạng sớm, không backend toàn quốc)

Ký hiệu: **G** = gate tự động; **H** = người thật (không bịa).

**A. Khóa dự án (G)** — Root mới `hh-3d/hh-3d-2/` (tách `app/`). Decision record: tên làm việc, nền tảng client, pin toolchain, instance-first, không IAP, ODbL nếu đụng OSM sau. Một `PRODUCT_PLAN` trong folder này; **không** thêm `AUTHORITATIVE_PLAN` repo-wide (VF đang giữ).

**B. Editor + agent (G)** — Semantic command + schema + UndoRedo/transaction; cấm sửa `.tscn`/`.godot` thô. Editor ≠ Play process. Stop/Pause drain ACK. Nếu **không** Godot: cùng hợp đồng trên DCC/editor đã chọn.

**C. Offline fun slice (G+H nhỏ)** — Một quảng trường ~80–150 m, 1 player: đi/nhảy/emote/1 hoạt động/1 nhà trống/1 quầy catalog. Fun **trước** map VN.

**D. Art/perf (G + 1 máy thật)** — glTF pin, LOD, ngân sách GPU. Headless ≠ nghiệm thu máy.

**E. Spike mạng sớm (G, trước persistence lớn)** — 1 host authoritative + 2 client process **cùng máy**. Ownership item, nhảy/emote, disconnect/reconnect, packet cũ. Fixture bot **không** thay 2 process người. Chưa shard, chưa PostGIS city, chưa matchmaking.

**F. Persistence tối thiểu (G)** — SQLite/Postgres local: account invite, inventory, shop version. Snapshot/migrate `schema_version`.

**G. Friends / shop / moderation (G)** — Graph request/accept/block; catalog-first UGC (preset + text schema, không mesh tự do); report/hide/suspend **trước** UGC rộng.

**H. WAN closed alpha (G+H)** — 2–4 máy/mạng khác, TLS, token ngắn hạn, 1 region. Capacity: 16–32 body/instance, 2–4 instance.

**I. Geography adapter (G, sau fun+net)** — Job offline: OSM/PostGIS → collision/navmesh authored. MapLibre = báo cáo/minimap, **không** tick sim. Chỉ sau license ledger + grant fetch.

**J. Pilot VN hẹp (H)** — 1 thành phố-theme, allowlist, attribution ODbL nếu derived.

**K. Vận hành/release** — Observability, backup, cost, chính sách, store listing. Không public UGC trước moderation.

**Bẫy thứ tự:** đừng chờ GATE-U1 web; đừng xây PostGIS/OSM trước E; đừng seamless Việt Nam trước instance; đừng gọi R3F Harbor là baseline perf của game mới.

---

## 3. Lựa chọn thực dụng

**Client (mặc định đảo được):** Godot 4.x **stock**, desktop + Android, **không fork**, không GDExtension trừ gap report. Đảo sang Unity (hoặc giữ web chỉ shell account) nếu fail: export Android lighting, dedicated server headless, hoặc agent UndoRedo không idempotent. Pin Godot **riêng** — đừng tự lấy pin VF 4.7.1. Web R3F cũ đã cho thấy cảnh 60 hộp + Html nametag không đạt mượt; **không** chọn web làm runtime gameplay chính vì “đã có app”.

**Server:** Dedicated authoritative process (cùng engine hoặc service mỏng). Client đoán pose; server chốt transform, inventory, shop publish, friend/block. HLAPI engine = vận chuyển, không phải “MMO xong”.

**Protocol:** Snapshot unreliable + sequence/session (pose ~10 Hz đi, 2 Hz đứng); RPC reliable cho inventory/shop/party. Lease 1 publisher/account. Reconnect: session mới, **không** phát lại pose cache. TTL leave ≤10 s; revoke ≤2 s khi còn mạng (số đo, chưa SLA).

**Persistence:** Alpha: Postgres (+ đối tượng ảnh). PostGIS **chỉ** pipeline geo, không hot path pose. Outbox + idempotency key cho publish. Optimistic `version`; conflict hiện, không last-write-wins.

**Offline / private / public:**
- Offline: 1 player, catalog đã tải, không presence.
- Private: instance invite.
- Public: match vào plaza, **không** “thấy cả nước”.

**Sở hữu:** Mọi grant item/shop do authority + journal. Client không tự `owner_id`.

**UGC an toàn:** Catalog preset (quầy, biển, 3–5 slot hàng, text/ảnh quota). Không upload mesh/script. Không tiền thật; giá = soft currency hoặc “Trưng bày”.

**ID & migrate:** `account_id`, `instance_id`, `prop_id` (nội bộ), `shop_id`, `listing_id`, `geo_feature_id` (osm/way tùy chọn, **không** FK bắt buộc). Đổi snapshot geo không xóa shop (neo `anchor_id` + offset local). `schema_version` + expand/contract.

**Bảo mật:** Loopback dev; alpha TLS + device/account token; không secret trong log/ảnh. Rate-limit mutate. Filter visibility trên server theo instance∩(không block)∩opt-in.

**Geo:** Nguồn EPSG:4326 → ENU quanh origin instance (≤~2 km). Origin shift nếu vượt; **Large World Coordinates 64-bit** chỉ sau đo mobile (CHƯA XÁC MINH docs sống). Không tin `osm_id` bất biến.

---

## 4. Hợp đồng agent

- Một WP, một `command_id`, một writer, một Play/runtime.
- Mutation: command có schema → validate → UndoRedo/atomic → đọc lại postcondition.
- Cấm: sửa scene thô, RPA chuột làm nguồn, 2 runtime ghi một path, tick plan từ chat.
- Critic: 2 người/agent **độc lập, chỉ đọc**, cùng `source_hash` + artifact; cố FAIL. `HASH_MISMATCH` hoặc recycle giữa chừng → `TICK=no`. Implementer ghi `TICK=n/a`.
- Human (fun, legal, store, GATE người) **tách** test tự động. **Cấm** bịa `OWNER_SIGN`.
- Determinism: chỉ claim trong pin + seed + epsilon đã ghi (vật lý/item). WAN/render/input thiết bị = không universal.
- Stop/Pause ưu tiên; hủy không mất ACK; editor không ghi state Play.
- Evidence: timestamp, run/trace/hash, lệnh repro. Fixture/teleport không phải E2E duy nhất.

---

## 5. Nghiệm thu đo được + fallback

| Cổng | Đo | Không chấp nhận |
|---|---|---|
| Fun offline | 8/10 tester hoàn thành: đi → emote → hoạt động → mở nhà → xem quầy <8 phút; không nhầm GPS | Screenshot đẹp |
| Art | glTF import 0 warning; 1 look-dev plaza | “Giống Y8/PT” |
| Perf desktop | Idle ≥50, walk p1 ≥30, 1280×720, 1 cửa sổ, **không** DevTools; 1 hash | Headless thay headed |
| Perf Android | Cùng scene, 1 SKU pin: walk p1 ≥25, 15 phút không OOM/context-loss | Ước từ PC |
| Mạng (2 process) | A đi/emote; B thấy cùng hướng; disconnect A → B mất body ≤ TTL; reconnect không hồi sinh nếu block | 2 tab BroadcastChannel; bot giả 32 người |
| Economy | Publish idempotent; retry không double; conflict version; draft không public | “Giá” = tiền thật |
| Capacity fixture | 16 dummy **cùng host** để đo CPU — nhãn `NOT_MULTIPLAYER_PROOF` | Dummy = alpha |
| Alpha WAN | 8 người thật, 1 instance, 20 phút; 0 item mất; 0 ghost >TTL | |

**Rủi ro → đảo:** Godot mobile/editor fail → Unity hoặc hybrid (Godot play, web account). Precision run → instance nhỏ + rebase, không world 64-bit vội. Net authority fail → dừng persist, sửa E. OSM legal/cost fail → giữ plaza authored, MapLibre chỉ báo cáo nội bộ. Perf fail → cắt shadow/Html-tương đương, instance 80 m, cap 16 body.

---

## 6. Thiếu yêu cầu + mặc định đảo được

Không hỏi owner hàng chục câu. Ghi mặc định; đảo bằng 1 decision record:

| Thiếu | Mặc định (đảo được) |
|---|---|
| Tên phát hành / brand | Tên làm việc nội bộ; không Superfighters; không claim Play Together |
| Ai thấy ai | Cùng instance ≤32; bạn = party/HUD; không crowd thành phố |
| Chat/voice | Tắt đến sau moderation |
| Nhà / plot | 1 slot/account, preset |
| Tiền | Soft currency; 0 IAP |
| Account | Invite + device link; OIDC sau |
| AOI geo | Chưa; plaza hư cấu. Adapter sau, AOI ≤ 400 m, không fetch đến khi ledger + YES |
| Tuổi / chính sách hàng | 13+; cấm vũ khí/hàng cấm (fold dấu như J4); legal owner chốt trước public |
| Engine | Godot stock; đảo nếu 2 cổng D/E fail |
| Region | 1 region SEA alpha |

**Cấm nhập blocker cũ:** GATE-U1, freeze 01-09, “web-first bắt buộc”, “không Godot city”, “multiplayer out of scope”, checkbox 31-8, pin VF.

**Dừng:** PLAN_ONLY. Không scaffold, không cài engine, không fetch map, không commit. Coordinator soạn plan dưới `hh-3d/hh-3d-2/zdoc` khi được phép **viết tài liệu**; triển khai chỉ khi user hỏi start.

**URL coordinator phải tự mở lại (chưa verify phiên này):**  
`https://docs.godotengine.org/en/stable/classes/class_undoredo.html`  
`https://docs.godotengine.org/en/stable/tutorials/plugins/editor/making_plugins.html`  
`https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/index.html`  
`https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html`  
`https://docs.godotengine.org/en/stable/tutorials/3d/introduction_to_3d.html` (precision / large world)  
`https://wiki.openstreetmap.org/wiki/Open_Database_License`  
`https://postgis.net/docs/ST_Transform.html`  
`https://maplibre.org/maplibre-gl-js/docs/`

---

MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast  
TOOLS_USED=Read, Grep, Glob; WebSearch/WebFetch rejected  
WEB_VERIFIED=no  
IMPLEMENTATION_PERFORMED=no

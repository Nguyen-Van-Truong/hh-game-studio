Đọc freeze manifest, hash độc lập, rồi đọc toàn bộ TXT kế hoạch — không đọc verdict/research khác.Đang hash độc lập toàn bộ file trong freeze, rồi đọc TXT kế hoạch theo chunk.Hash freeze khớp. Đọc hết TXT và chỉ lấy heading/HISTORY của tài liệu cũ.Tiếp tục đọc phần Q04–specs–capacity; chỉ lấy heading/HISTORY của master cũ, không đọc verdict trong reviews.Đang mở tối đa 2 nguồn official để xác minh HAEGIN (không lộ backend) và `synchronous_commit`.VERDICT=REVISE  
SOURCE_MANIFEST_HASH=a6fe3e49d81f93b6dd4db81cc20e9a7db5155a0be9466b9995ede7356761de93  
HASH_BEFORE=a6fe3e49d81f93b6dd4db81cc20e9a7db5155a0be9466b9995ede7356761de93  
HASH_AFTER=a6fe3e49d81f93b6dd4db81cc20e9a7db5155a0be9466b9995ede7356761de93  
MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast  

Phạm vi: PLAN_DESIGN U1, không runtime. Đọc hết `hoan-hao/zdoc/8-9-hh-studio-godot-blender-hh-world-plan.txt` (sha256 `6473dc70f740fa54cb8ab60ce403b34d6b962e0c76ef6fa1ebed0ce73673992a`). Freeze 15 file: hash từng file + aggregate UTF8 `sorted path + space + sha256` nối LF, không LF cuối, khớp `freeze-u1.json`. Hash sau đọc không đổi. Olddocs chỉ HISTORY/pointer (00, PROGRESS, AGENTS, banner 01–09, hai master 5-9/8-9). Không đọc verdict/research/REVIEW-RESULT trong `reviews/`. Không Composer/Auto/Task/Explore/subagent.

Nguồn official (2): HAEGIN hub Play Together (S21) — beats công khai (avatar/bạn/Follow/Summon/câu cá/nhà/Phone/Bag); Game Party “30” là minigame, không CCU/shard/AOI/backend. PostgreSQL 18 `runtime-config-wal` — `synchronous_commit=on` chờ standby flush durable; RPO0 một host khi standby còn WAL là đúng docs, không phải region/PITR.

---

**Phủ sóng đạt (không bịa bảo đảm runtime)**  
Bảng đầu = 40 hàng (32 H2 + 8 ST), `CURRENT_VALID_WP=H2-P0-01`, một authority. Spec 2.6 + mục 5 đủ BUILD/VERIFY/DoD. DAG không cycle; 8.1 A–I khớp bảng (P1-02∥ST-01; sau ST-01: P1-01∥ST-02; ST-08∥P7 sau P6-03). Geo P7+ sau gameplay. Solo≠Online, không import, P2 không cloud (EX09). Room 32 kết nối ≠ 64 stress render ≠ fleet 100–300 (Q04-C/P). Cùng room đầy: một TX rebind+CAS+fence, occupied không +1 (L523–534, EX01). Khác room: 1 active + 1 pending, TTL, một authority (L546–555, EX13). Reward: cùng attempt/seed/quota; EXPIRED chỉ trước RESULT_RECORDED; CAS một winner; không reroll (L572–636, EX07). DB-D1–D4: sync flush, fail-closed, không hạ async; PITR/region RPO riêng; tombstone không đúc số dư; credential/human/ký = GAP/UNVERIFIED. Sizing: CPU-time ≠ wall; NIC 1Gbps/hướng; occupancy+nhà riêng; N+1; pack Q04-P ≠ một room Q04-C. `4*1000*0.6/(6*30)=13.33→floor 13`; RAM `10/0.6→16`; `32*30kB`; 1000@occ1 r_node8 → 5 node; occ0.6 → 8; peak 77.76TB / avg200 15.552TB. Không giá giả, không GPU room server, operator không tự ký.

---

**HIGH (2) — phải sửa chữ trong cùng TXT**

1) EX01 L1372–1377 vs L550–555 / L533.  
EX01: “DB uniqueness ngăn double hold” + “Không hai reservations”. Mục 3.2 cho phép source-active + target-pending (cả hai tính cap), cấm hai active. UNIQUE(account) thuần phá handoff; “không hai chỗ” L533 là cùng room.  
Sửa tối thiểu EX01: unique **một active/account**; pending ≤1 theo `transition_id`+TTL; cùng room = rebind in-place, occupied không +1; khác room đầy = không tạo pending, giữ session cũ; cấm hai active/hai pending.

2) L624–630 vs unique grant L630.  
Lifecycle một attempt, nhưng unique `(account_id,attempt_id,grant_type)` có thể để expiry thắng một grant và result thắng grant khác.  
Sửa: **khóa hàng attempt** (CAS/row-lock) làm terminal duy nhất; mọi grant cùng `attempt_id` một TX; grant_type chỉ dedupe trong TX đó, không terminal riêng.

---

**Không nâng CRITICAL:** không cycle; gate người/máy/credential ghi UNVERIFIED/GAP; runtime còn PLAN_ONLY đúng. 8.1 C L1742 tóm “P2 sau P1-03” trong khi bảng L18 cần thêm P1-01 — bảng thắng, không phải cycle. L1261 mảnh tiếng Anh, không đổi DoD. Old 06 vẫn ghi CANONICAL dưới HISTORY — pointer, không override U1.

**Giới hạn:** critic tài liệu ≠ PASS tool/game/DB/WAN/người. `/docs/current/` PG phải khóa version ở P3-01. Không suy cap 32 từ HAEGIN. Không tick WP từ review này.

Tôi sẽ đọc AGENTS.md, bộ zdoc freeze v2 và các nguồn chính thức liên quan, rồi chỉ trả báo cáo khoảng trống — không sửa file hay chạy runtime.Đã thấy freeze v2 và bộ critic; tiếp theo đọc AGENTS.md, 12 file canonical và các review đã đóng để tránh lặp gap v1.Tiếp tục đọc contract kiến trúc, chất lượng, roadmap và các critic v1/v2 để tách gap còn lại.Đã có khung kiến trúc/roadmap; tiếp theo đọc product, research, critic v1/v2 và resolution để lọc gap còn lại.Tiếp tục đọc công cụ Godot, địa lý, workflow và hai critic v2 để biết gap nào đã đóng.Đang đối chiếu các chủ đề còn lại trong plan và mở tài liệu chính thức Godot/PostgreSQL/OWASP.Đã xác định các chủ đề v1 đã đóng. Tiếp theo mở tài liệu chính thức và xác minh hash freeze.Đang mở trang chính thức (không dùng bản tóm tắt) và tính hash 12 file freeze.Đã mở được các trang chính thức. Tiếp theo lấy đoạn cụ thể về WAL/PITR, session fencing, ENet/DTLS và hash freeze.Đang xác minh hash 12 file freeze và vài đoạn contract còn thiếu.Báo cáo dưới đây chỉ audit kế hoạch. Hash 12 file khớp freeze v2; không sửa file, không chạy game/server.

---

# Audit kế hoạch master — HH World 2 (sau v2)

Ngày: 2026-09-05 Asia/Saigon  
Phạm vi: `hh-3d/hh-3d-2` freeze v2 · `PLAN_MANIFEST_HASH=4762d1cc05354ef9798431d035b6fb49a68526f8c716fddb0412c3329cdx689a2`  
Hash 12 file: **khớp** `plan-freeze-v2.json` (Get-FileHash SHA256).  
`IMPLEMENTATION_AUTHORIZATION=PLAN_ONLY` · Không tick WP · Sản phẩm cũ không đổi.

**Đã đóng ở v1 (không lặp):** Q-ID; trần 32; matrix thiết bị; onboarding BUILD; Solo≠Online; reservation 30/10/15; crash journal hai phía; tombstone restore; 60→30 held/edge; ẩn/block/ACK; DEV_ONLY loopback; Linux/transport; N-only drain; pin trang ≠ artifact.

**Vai trò master `.txt` (đề xuất, coordinator viết):**  
`hh-3d/hoan-hao/zdoc/5-9-hh-world-2-master-overview.txt` (sibling `hh-3d-2`, **không** đụng `hh-3d/app` / VF).  
`PLAN_ROLE=OVERVIEW_INDEX_NON_AUTHORITATIVE`. Bảng đầu = liên kết + ID WP có sẵn. **Cấm** checkbox, `CURRENT_VALID_WP`, số tiến độ.  
Thẩm quyền duy nhất: `06-ROADMAP.md` + con trỏ `PROGRESS.md`. `reviews/` và master không tick. WP mới chỉ sau khi thêm hàng vào `06`.  
Sóng song song (lease tách file/runtime): sau P0-03 → P1-01 ∥ P1-02; sau P1-03 → P2-0x ∥ nền P3-01; art P2-02 ∥ schema net nếu không chung scene. Không hai writer một `.tscn`.

Không hứa phủ hết lỗi hiếm hay HA doanh nghiệp. Alpha = invite 8–32, một protocol/content N, một cụm DB.

---

## 13 khoảng trống còn lại

### G1. Hai thiết bị / fencing session — **CHẶN ALPHA**
**File:** `03` A03:152–153, A04:116–124; `06` H2-P3-02.  
**Kịch bản:** Account A đang plaza (session e1) + điện thoại 2 login (e2). Máy cũ còn gửi input/mua/đặt nhà. OWASP: timeout idle/absolute phải **server-side**; regenerate ID lúc auth; logout hủy server. Plan chỉ “epoch mới thắng, không hai reservation” — thiếu fence API+room+ticket cùng lúc, idle/absolute, và lệnh durable từ e1.  
**Bất biến:** Một `session_epoch` sống/account; ticket/channel gắn epoch; lệnh e1 sau fence = `STALE_SESSION` không apply; regenerate sau login.  
**UX:** Máy cũ: “Đăng nhập nơi khác / phiên hết hạn” + về Solo/menu; không mất item đã commit; giao dịch dở = thất bại rõ.  
**WP:** H2-P3-02, H2-P3-04, H2-P4-02/03.  
**Test:** Login 2 client; e2 join; e1 gửi input + `command_id` mua. **ACCEPT:** e1 bị kick ≤2 s; 0 apply wallet/placement; e2 giữ slot; idle/absolute hết hạn hủy session server.

### G2. Sequence wrap, NaN/Inf, overflow, lệch giờ — **CHẶN ALPHA**
**File:** `03` A03:70–77, A04:121–125; `06` H2-P1-02, H2-P3-03/04.  
**Kịch bản:** `sequence`/`client_tick` uint16/32 wrap → gói mới bị coi cũ; pose/giá `NaN`/`Inf`; ví/stock int overflow; `issued_at` client lệch ±hours (cửa sổ lệnh mở/đóng sai).  
**Bất biến:** Reject non-finite trước apply; seq monotonic theo cửa sổ + epoch (wrap chỉ trong cửa sổ đã pin); ví/stock checked arithmetic, không wrap âm; `issued_at` lệch >±N s (vd 30–120 s, khóa P3) = reject; cooldown theo **server clock**.  
**UX:** Resync/snapshot; “Lệnh không hợp lệ”; không teleport/item ảo.  
**WP:** H2-P1-02, H2-P3-03, H2-P3-04.  
**Test:** Seq `MAX-2…0`; payload NaN velocity/price `-1e308`; `issued_at` ±1 h. **ACCEPT:** 0 apply; không crash; client nhận resync; số dư không đổi.

### G3. Journal thưởng trên host mất đĩa — **CHẶN ALPHA**
**File:** `03` A03:90–96; `06` H2-P3-03/04, H2-P6-01.  
**Kịch bản:** v1 cover crash **cùng đĩa**. Host VM/disk mất **trước** API commit: journal local biến; player thấy animation; reconnect room mới không có journal → mất thưởng im lặng **hoặc** mint lại.  
**Bất biến:** Intent durable (`attempt_id`) ghi **API/outbox** trước hoặc cùng lúc room được phép hiện “chờ nhận”; room journal ≠ ledger; host mới **chỉ** query API theo `attempt_id`; không ACK “đã nhận” trước readback.  
**UX:** “Đang xác nhận…” / “Chưa ghi — thử lại”; sau reconnect: có receipt hoặc pending, không mất nếu đã “đã nhận”.  
**WP:** H2-P3-03, H2-P3-04, H2-P6-01.  
**Test:** Kill -9 + xóa thư mục journal room sau animation, trước commit; spawn room mới cùng account. **ACCEPT:** 0 mint kép; inventory = 0 hoặc 1 đúng receipt; UI không “đã nhận” khi DB không có.

### G4. Shop: ẩn/đổi giá giữa mua, bảo toàn, overflow — **CHẶN ALPHA**
**File:** `03` A06:174–179; `06` H2-P4-02, H2-P3-04.  
**Kịch bản:** Last-item đã có. Còn: unpublish/đổi `expected_version` khi B đang thanh toán; hai listing một `item_instance_id`; hoàn tiền không trả stock; ví overflow.  
**Bất biến:** Một TX: khóa version listing+wallet; stock+∑ví+escrow bảo toàn; ẩn/đổi giá giữa chừng = fail + rollback đủ; một instance một listing published; int checked.  
**UX:** “Hết hàng / giá đổi / giao dịch hủy — tiền hoàn”; không “mua thành công” rồi túi trống.  
**WP:** H2-P3-04, H2-P4-02.  
**Test:** Race hide+buy; đổi giá; listing trùng instance; spend `MAX-1`+2. **ACCEPT:** đúng 1 thành công hoặc cả fail sạch; invariant kế toán; 0 số âm/wrap.

### G5. RPO 24h mâu thuẫn ACK durable — **CHẶN ALPHA (chính sách)**
**File:** `05` Q06:171–173; `03` A06; `06` H2-P3-01, H2-P6-02.  
**Kịch bản:** Q06 alpha RPO≤24h. Postgres: commit đồng bộ = WAL flush rồi mới success; `synchronous_commit=off` có thể **mất giao dịch vừa báo thành công** (cửa sổ ~3×`wal_writer_delay`). `pg_dump` **không** đủ PITR. Archive chậm = RPO thực = độ trễ archive (`archive_timeout`). ACK mua/thưởng + backup đêm = mất tiền đã “thành công”.  
**Bất biến:** Ledger/award: `fsync=on`, `synchronous_commit` ≠ `off` (khóa P3-01); WAL archive + `archive_timeout` (phút, không 24h) **hoặc** UI cấm gọi ACK là bền nếu chỉ dump đêm. RPO 24h chỉ cho telemetry/log.  
**UX:** Mất máy: “Đang khôi phục”; item đã ACK vẫn còn sau crash DB; nếu chọn RPO thô — **không** hiện “đã lưu vĩnh viễn”.  
**WP:** H2-P3-01, H2-P6-02. P8 HA replica = tùy chọn.  
**Test:** Commit mua → crash ngay (không async commit); restore từ base+WAL tới LSN sau commit. **ACCEPT:** receipt còn; cấu hình cấm `fsync=off` trên DB alpha.

### G6. Failover/PITR/tombstone/journal lệch — **CHẶN ALPHA (restore một nút)**; HA split-brain = **P8**
**File:** `03` A06:187–197; `05` Q06; `06` H2-P3-01, H2-P6-02, H2-P8-02.  
**Kịch bản:** Postgres: WAL phải **liền** từ base backup; `pg_wal` đầy → PANIC; config (`pg_hba`) không nằm trong WAL. PITR **trước** tombstone = account sống lại (v1 replay tombstone — chưa: journal room **mới hơn** snapshot; hai primary).  
**Bất biến:** Restore: replay tombstone **và** đối chiếu `command_id`/receipt; room journal > DB → pending/retry, không apply mù; cấm hai writable; gap WAL = FAIL đóng, không “gần đúng”.  
**UX:** Bảo trì; “Một số giao dịch chưa xác nhận — kiểm túi”; shop đã xóa không hiện.  
**WP:** H2-P3-01, H2-P6-02; dual-primary/sync standby → H2-P8-02.  
**Test:** Delete account → restore backup **trước** delete + tombstone store; host room có award chưa flush. **ACCEPT:** 0 resurrect shop; 0 mất/đúp ledger đã ACK; traffic chỉ sau verify.

### G7. Lệch version / hash asset / import / dedicated strip — **CHẶN ALPHA**
**File:** `03` A08:215–221; `04` T01/T05; `07` G04; `06` H2-P5-02, H2-P8-03. Godot: server export **strip** texture; RPC đòi cùng `NodePath` + chữ ký `@rpc` hai phía.  
**Kịch bản:** CDN một phần (client content N, room N-1); `.godot` import đổi hash im lặng; save có `item_type` đã gỡ; PCK server strip nhầm collision; RPC lệch sau hotfix một phía.  
**Bất biến:** Handshake: `protocol` + `content_release` + `catalog_hash` + `world_release_id`; thiếu/lệch = từ chối; save: missing asset = quarantine, không crash; strip preset pin, collision/nav **Keep**; import settings trong source manifest. N/N-1 chỉ P8 sau test.  
**UX:** “Cần cập nhật gói N”; spawn fallback/lobby; đồ lạ = “không tải được”, không mesh vỡ.  
**WP:** H2-P0-03, H2-P3-02, H2-P4-03, H2-P5-02, H2-P6-01.  
**Test:** Client N / room N-1; xóa 1 GLB khỏi package; strip nhầm `.tres` collision. **ACCEPT:** fail-closed join; 0 play lệch catalog; nav không thủng.

### G8. Quota, bão retry, admission, drain — **CHẶN ALPHA (biên)**; DDoS ISP = **không alpha**
**File:** `03` A05:149–155, A08:210–214; `05` Q06:173; `06` H2-P4-04, H2-P6-01/02. OWASP: giới hạn request/session/timeout; slow-HTTP; lockout login = DoS.  
**Kịch bản:** Mất điện → 32 client reconnect cùng lúc (giữ slot 30 s) + retry API không jitter → bão; ticket UDP flood; drain giữa award.  
**Bất biến:** Admission: hàng đợi/từ chối có mã; reconnect jitter+cap/account; quota ticket/login/chat; circuit khi API/DB lỗi (fail nhanh, không queue vô hạn); drain: ngừng vào, **flush** durable rồi mới tắt; lockout không khóa cả IP NAT. Không hứa chống volumetric.  
**UX:** “Máy chủ đông / thử lại sau Xs”; đang mua: pending tới timeout rồi fail sạch.  
**WP:** H2-P3-02, H2-P4-04, H2-P6-01, H2-P6-02.  
**Test:** 64 client reconnect cùng lúc; 1000 ticket/s một account; drain lúc award. **ACCEPT:** cap 32 không vượt; p95 tick giữ ngưỡng hoặc degrade có nhãn; 0 đúp/mất item; không plaintext fallback.

### G9. Party chuyển room / block / va chạm “vô hình” — **CHẶN ALPHA**
**File:** `02` P04:66–80; `03` A05:134–155; `06` H2-P4-01/03.  
**Kịch bản:** v1: không hard-collide player, known-ACK 2 s. Còn: leader disconnect lúc reserve 15 s; block member giữa join; party 4 vào plaza 30/32; AOI despawn cửa/ghế câu — client còn collider local; member trong nhà khi party mời plaza.  
**Bất biến:** Reserve all-or-none; block hủy invite/reserve; thiếu slot = cả nhóm fail hoặc đồng ý tách **có UI**; tương tác thế giới chỉ actor còn replicate; collider client không là authority.  
**UX:** “A vào được, B hết chỗ — chờ/hủy”; “Đồng bộ…”; không kẹt tường/ghế vô hình.  
**WP:** H2-P4-01, H2-P4-03.  
**Test:** Kill leader giây 8/15; block lúc ticket; 30+party4; despawn AOI tại cửa. **ACCEPT:** 0 slot mồ côi; 0 join vượt cap; 0 tương tác với peer/object chưa spawn; không kẹt cứng.

### G10. Parser/giải nén/gói nội dung — **CHẶN ALPHA**; OSM zip = **P7**
**File:** `03` A04:125; `04` T05; `07` G03; `06` H2-P3-01, H2-P5-02, H2-P7-02. OWASP: giới hạn size **sau** decompress; zip/XML bomb; không tin header uncompressed.  
**Kịch bản:** Snapshot/GLB/world package nén nhỏ, phình RAM; catalog image; v0.1 không UGC — vẫn có pipeline import/CDN.  
**Bất biến:** Trần byte nén **và** đã giải nén + số file + độ sâu; magic/allowlist; stream cắt khi vượt; path không traversal.  
**UX:** “Gói hỏng/quá lớn”; về lobby.  
**WP:** H2-P3-01, H2-P5-02; geo → H2-P7-02.  
**Test:** Fixture nén 10 kB → >cap; path `../`. **ACCEPT:** reject trước OOM; process sống; 0 ghi ngoài allowlist.

### G11. Cert hết hạn, `client_unsafe`, khóa riêng — **CHẶN ALPHA**
**File:** `03` A04:104–118; `06` H2-P3-02, H2-P6-02; `08` W03. Godot: `dtls_client_setup` + `TLSOptions.client_unsafe()` **tắt** verify CN.  
**Kịch bản:** Cert hết hạn giữa phiên; xoay key; `verify=false` lọt release; PEM trong evidence/Git.  
**Bất biến:** Fail-closed hết hạn/sai hostname; cấm `client_unsafe`/verify tắt ngoài DEV_ONLY loopback; khóa ngoài Git, scan evidence; xoay: session mới, drain cũ.  
**UX:** “Chứng chỉ/kết nối không an toàn — cập nhật/thử lại”; không chơi WAN.  
**WP:** H2-P3-02, H2-P6-02.  
**Test:** Cert hết hạn; hostname sai; grep artifact. **ACCEPT:** join fail; 0 secret trong log/screenshot.

### G12. Hai room một `instance_id` sau thay host — **CHẶN ALPHA**
**File:** `03` A03:78–79, A01 registry; `06` H2-P3-02, H2-P6-01.  
**Kịch bản:** Registry timeout, host cũ sống lại (split-brain): hai authority, mint kép.  
**Bất biến:** Lease room (owner+epoch+fencing token); host cũ fence từ chối input; API chỉ nhận proof epoch hiện tại.  
**UX:** Một phía “phòng đóng”; reconnect ticket mới.  
**WP:** H2-P3-02, H2-P3-03, H2-P6-01.  
**Test:** Hai process cùng `instance_id`; award hai phía. **ACCEPT:** 1 authority; 0 đúp ledger.

### G13. Drain + outbox sau PITR — **CHẶN ALPHA (kịch bản restore)**
**File:** `03` A08:213–214, A06 outbox; `06` H2-P3-04, H2-P6-02.  
**Kịch bản:** Drain giữa award; restore LSN cũ trong khi room nhớ `command_id` mới → outbox gửi lại / mint.  
**Bất biến:** Drain: ACK hoặc `RETRYABLE`; không im lặng; restore: idempotency key bền **ngoài** snapshot hoặc đối chiếu receipt; replay an toàn.  
**UX:** “Máy chủ bảo trì — phần thưởng sẽ có nếu đã xác nhận”.  
**WP:** H2-P3-04, H2-P6-01/02.  
**Test:** SIGTERM lúc outbox; PITR lùi 1 TX. **ACCEPT:** 0 đúp; client không “thành công” khi DB không có.

---

## Chặn alpha vs nghiên cứu

| Phải có trước v0.1 (P6) | Không xây lúc alpha |
|---|---|
| G1–G5, G7–G13; G6 restore **một nút** + WAL | Multi-AZ, `remote_apply`, DDoS thương mại, N/N-1, 1000+ CCU, cell, voice, UGC, OSM bomb (P7), double-precision |

Công thức sizing (master **trích** `03`/`05`, không thay Q04-C): `n_rooms ≈ min(CPU, RAM, net, 1/p95_tick)` từ **số đo** P6-01; headless không GPU (Godot `--headless` + Dummy audio — đã mở docs). Không nhân 32×số máy.

---

## Nguồn đã mở (2026-09-05)

| URL | Trạng thái | Dùng cho |
|---|---|---|
| https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html | **MỞ** (docs 4.7) | Headless, Dummy audio, strip PCK, không cần binary server riêng |
| https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html | **MỞ** | ENet/RPC; authority; validate arg; **không** MMO |
| https://docs.godotengine.org/en/stable/classes/class_enetconnection.html | **MỞ** | `dtls_*_setup`; `client_unsafe`; `refuse_new_connections` |
| https://www.postgresql.org/docs/16/continuous-archiving.html | **MỞ** | WAL+PITR; `pg_dump`≠PITR; `archive_timeout`; gap WAL |
| https://www.postgresql.org/docs/current/wal-async-commit.html | **MỞ** (PG 18, trang ghi 2026-08-13) | `synchronous_commit=off` mất TX đã “success” |
| https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html | **MỞ** | Quota, timeout, giới hạn request |
| https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html | **MỞ** | Idle/absolute, regenerate, hủy server |
| https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html | **MỞ** | Zip bomb, limit **sau** decompress |

OWASP Session/File vượt 6 URL — giữ vì G1/G10. Không bịa throughput/giá cloud. Pin PG exact = H2-P3-01 (chưa khóa).

**Khuyến nghị coordinator:** Nhúng G1–G13 vào contract `03`/`05` và VERIFY đúng WP trên; master chỉ mục lục. Đừng tạo bảng tick thứ hai.

PLAN_REVIEW_VERDICT=REVISE_FOR_MASTER_CONTRACTS  
PLAN_MANIFEST_HASH=4762d1cc05354ef9798431d035b6fb49a68526f8c716fddb0412c3329cd689a2  
HASH_CHECK=PASS  
MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast  
FILES_CHANGED=NONE  
RUNTIME_PROOF=NONE

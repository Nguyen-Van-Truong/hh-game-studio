Tôi sẽ đọc freeze manifest và toàn bộ tài liệu được liệt kê, rồi tự tính SHA256 để review kế hoạch một cách độc lập.Đang tự tính SHA256 từng file và đọc toàn bộ tài liệu freeze để đối chiếu với manifest.Lệnh hash vừa bị chặn; tôi sẽ tính lại SHA256 bằng cách chỉ đọc file và tiếp tục đọc phần còn lại của plan.Tiếp tục đối chiếu SHA256 và các điểm hợp đồng dễ lệch (transport, 60/30, xóa dữ liệu, reservation).Lệnh hash và tìm kiếm bị chặn; tôi thử cách chỉ-đọc hẹp hơn và đối chiếu lại các đoạn hợp đồng then chốt.Đã đọc đủ 12 tài liệu trong freeze và `plan-freeze-v1.json`. Lệnh hash/web bị từ chối nên **không tự tính lại SHA256** trong phiên này; đối chiếu path/thuật toán thì khớp freeze. Không đọc critic khác. Không có blocker làm vô hiệu cả bộ plan hay lời hứa MMO.

## Kết luận ngắn

Plan tách subtree, PLAN_ONLY, pin VF 4.7.1, Q01/1% low, ENet ≠ identity, Solo ≠ ledger, geo ID/CRS/rollback — đủ để làm thiết kế. Freeze **chưa** nên ACCEPT: vài hợp đồng để trống sẽ khiến worker đoán sai (nhà Solo/Online, chỗ reconnect, ACK thưởng room→API, xóa tài khoản vs restore).

## Findings (ưu tiên)

**1. Nhà hành trình đầu ≠ nhà Online — `02-PRODUCT.md:20-24` vs `:51-59`, `03-ARCHITECTURE.md:22-23`**  
P02: Solo → trang trí nhà → mời bạn. P04: không chuyển Solo→Online; nhà Online là instance/account (`P03`, `H2-P4-03`). Worker có thể đồng bộ save local (cấm) hoặc xóa nhà vừa trang trí khi login.  
**Làm:** Một câu: v0.1 hai sandbox; mời bạn/visit chỉ nhà Online; nhà Solo không visit được; login không import inventory/placement. Khóa ID ở `H2-P2-04`/`H2-P4-03`.

**2. Disconnect: giữ chỗ hay trả slot? — `03-ARCHITECTURE.md:70-71`, `:116-118`**  
Cleanup TTL + “reconnect không kick” không nói slot có giữ cho cùng account trong TTL không. Trả ngay → room 32 mất chỗ sau mất sóng; giữ không TTL → rò slot. Party 4 vào phòng 30/32 cũng không atomic (`02-PRODUCT.md:62-63`).  
**Làm:** Disconnect giữ reservation T giây rồi release; hết T / hết chỗ → fail rõ, không kick. Party reserve 4 chỗ một transaction hoặc cả nhóm fail.

**3. Room “đề nghị” thưởng / API chốt — `03-ARCHITECTURE.md:22-23`, `:73-76`**  
Hai authority. Room ACK “câu được” trước commit API → cá ảo rồi mất; API commit / room crash → ledger có, sim không. `command_id` ở API không đủ.  
**Làm:** Reward durable chỉ ACK sau API commit+readback; room hiện pending; outbox room→API idempotent; crash hai phía trong `H2-P3-03`/`H2-P3-04`.

**4. Xóa tài khoản + restore làm sống lại — `05-QUALITY-GATES.md:118`, `:135-136`; `03-ARCHITECTURE.md:146-148`**  
Q05 bắt test deletion; A06 chỉ “delete/hide giữ audit”; P06 dời retention. Không có: user vs operator delete; shop/bạn/chat/ledger/báo cáo; file Solo; unlink Hoàn Hảo; backup RPO 24h restore account đã xóa.  
**Làm:** Invariant ở A06 + DoD `H2-P3-01`/`H2-P6-02`: tombstone sống lâu hơn backup; restore không revive nếu tombstone còn; ledger/audit giữ theo policy, không hard-delete hàng giao dịch.

**5. Tool editor chặn gate giữ Godot — `06-ROADMAP.md:38-40`; `04-GODOT-TOOLS.md:23-28`**  
T02: tool nhỏ, mở khi WP cần. Bảng: P1-02←P1-01←P0-03; P1-03←P1-02. Spike net/perf không cần lease/UndoRedo/crash-save. Cộng `H2-P3-01`←`H2-P2-04` thì API chờ hết slice Solo.  
**Làm:** P1-02 phụ thuộc P0-03; P1-01 song song hoặc sau P1-03; P1-01 đúng 6 lệnh T02. P3-01 được dispatch sau P1-03, ACCEPT vẫn cần P2-04 nếu schema activity chưa khóa. Không nhảy `CURRENT_VALID_WP` trừ dispatch ghi rõ.

**6. 60 Hz → 30 Hz chưa khóa — `03-ARCHITECTURE.md:58-65`; `05-QUALITY-GATES.md:75-76`**  
Q03 1% là render cap, không phải gộp input. 2 tick client / 1 tick server: lấy tick cuối, cả hai, hay buffer? Jump/cooldown theo đồng hồ nào?  
**Làm:** Contract `H2-P1-02`/`H2-P3-03`: server sample 30 Hz; cooldown/speed theo server time; 60 Hz chỉ predict; epsilon reconcile riêng (Q04 0.25 m ≠ Q03 1%).

**7. Thermal/soak không có ngưỡng — `05-QUALITY-GATES.md:33-34`, `:41-44`; `06-ROADMAP.md:248-249`**  
Công thức 1% low, cold/warm, 3 run — ổn. Soak 20 phút “để thấy thermal” nhưng bảng là warm route 180 s. P5-03 ghi thermal mà không nói FAIL khi throttle.  
**Làm:** Soak dùng lại ngưỡng stall Android **hoặc** ghi observe-only (không tick P5-03 bằng soak). Thermal = sau 20 phút, route ấm vẫn đạt bảng; ghi clock/power nếu có.

**8. Public / ẩn / block / AOI — `02-PRODUCT.md:55`, `:64-70`; `03-ARCHITECTURE.md:104-111`**  
Ẩn không lộ tọa độ qua friends API, nhưng cùng plaza thì AOI vẫn vẽ. “Biết actor” chưa = spawn ACK / N tick. Block ≤2 s; actor còn trong sim, không va chạm — vẫn chiếm chỗ câu/interactable.  
**Làm:** Ẩn = không public **hoặc** public thì bạn thấy model, API không đưa room/tọa độ. `known` = hai phía replicate + grace đã đo. Block: revoke interactable/priority, không chỉ ẩn mesh.

**9. Pin “đã xác minh” vs ledger — `01-DECISIONS.md:17-19`; `09-RESEARCH.md:21-27`, `:67-68`**  
Prefix `ed1daf0bf`; S01–S03 worker-03; checksum/full commit **chưa** acquire. D02 “Cursor xác minh” dễ đọc thành artifact đã khóa. A04/P1-02 đúng: DTLS theo target; TLS API ≠ kênh movement. P1-03 có thể ACCEPT DEV_ONLY + DTLS Android UNKNOWN.  
**Làm:** D02 = “trang archive đã đọc; artifact lock ở P0-01”. P1-02: ma trận ENet/DTLS/phương án × Win/Android export; UDP bị chặn là rủi ro WAN. P1-03 không khóa transport sản xuất; P3-02 mới khóa mã hóa + gắn identity (ticket/channel auth), fail-closed nếu plaintext WAN.

**10. Nâng cấp client và xác minh nguồn — `03-ARCHITECTURE.md:166-167`; `06-ROADMAP.md:328-335`; freeze hash**  
Handshake từ chối client lệch — ổn alpha; P8/P9 rolling update thiếu cửa sổ N/N-1 và dual-version. Geo G02–G06 (CRS, không `osm_id` PK, pin package, rollback DB+artifact, ODbL không tự ký) đủ cho plan.  
**Làm:** P8-03: số version protocol đồng tồn tại; save Solo có `schema_version` + migrate (`H2-P2-03`). P0-01: domain chính thức + SHA từng editor/template/OS; cache tách VF. **Critic B không attest `manifest_sha256`** — host cần in hash 12 file + payload `path + space + sha256` nối LF, không LF cuối.

Không đòi schema/code đủ trước WP khóa hợp đồng. 32 người là trần đo, không phải CCU.

Không blocker triển khai plan-only. Vá 1–4 và 5 trước khi coi freeze là baseline.

PLAN_REVIEW_VERDICT=REVISE  
PLAN_MANIFEST_HASH=3477424499f1922b003cf07638503c98a84fb1acd68cc107b5e15706f9c9934a  
MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast  
FILES_CHANGED=NONE  
RUNTIME_ACCEPTANCE=NONE

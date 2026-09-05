Tôi sẽ đọc freeze manifest, đối chiếu SHA256, rồi lần lượt kiểm tra toàn bộ tài liệu canonical trong plan.Đang tính SHA256 từng file trong manifest và đọc toàn bộ tài liệu canonical.Lệnh hash bị chặn; tôi đọc tiếp toàn bộ tài liệu canonical và thử kiểm tra SHA256 lại theo cách hẹp hơn.Đang đối chiếu hash, rà soát mâu thuẫn giữa các contract, và kiểm tra ledger nguồn — không đọc verdict critic khác.Đã đọc đủ 12 file trong freeze và `zdoc/reviews/plan-freeze-v1.json`. Không đọc verdict critic khác. Worker01/02 chỉ dùng để xác nhận coordinator đã sửa claim quá mạnh; contract canonical thắng. Ledger 4.7.2 ghi prefix/`ed1daf0bf`, thiếu full commit/checksum, trang GDExtension 4.6, timeout/429 — trung thực. SHA256 độc lập không chạy được (shell/web bị từ chối); 12 path tồn tại, đọc đủ, không rỗng.

Không bịa blocker: 32 WP unique, dependency tuyến tính không cycle, `CURRENT_VALID_WP=H2-P0-01` khớp, một bảng tick, PLAN_ONLY không mở clone/cài/chạy, VF 4.7.1 và Web cũ tách, clean-room/Play Together chỉ beat chức năng, editor UndoRedo/ACK/lease đủ, workflow owner+agent đủ.

Còn lỗ hợp đồng làm nghiệm thu bị treo hoặc bị “gaming”. Phải sửa text plan trước khi coi là đóng băng thực thi.

**1. [P0] Q03/Q04 không có ID phân lớp — gaming hoặc đòi quá**  
`zdoc/05-QUALITY-GATES.md:70-111` gộp automation, art, 5 người, 2-client, emulator, 32 soak, 8 người WAN. WP chỉ trích miệng: `06-ROADMAP.md:112` “Q04 local cases”, `:130` “Q03 30/60/120”, `:154` “full Q03 automated”, `:199` “Q04 +”, `:233` “art look-dev Q03”, `:248` “Q03 regression”, `:274` “Q03 5-person + Q04 8-person”, `:315/:323/:332` “Q03/Q04… / complete relevant Q00–Q06”. Rule `:23-24` (“đúng phần feature; human tại P6-03”) không thắng document Q.  
**Impact:** P1-02/P5-01/P5-03 có thể bị bắt 8 người/32 soak, hoặc worker bỏ reconnect.  
**Sửa:** Trong `05` đặt Q03-A/R/H và Q04-L/N/C/W; mọi VERIFY/DoD/P0-02 `quality-profile.json` chỉ được dẫn ID đó. Xóa “relevant”/“local cases”.

**2. [P0] Trần 32 mạng: VERIFY cứng vs DoD mềm vs D04**  
`05:101-106` và `06:258` bắt 32 connected / soak 60 phút. `06:260` “measured technical cap published”. `01-DECISIONS.md:72-73` 32 là target, chưa capacity.  
**Impact:** Worker công bố cap 16 và gọi DoD; critic fail vì VERIFY 32 — hoặc hạ trần âm thầm.  
**Sửa:** VERIFY = đo tới 32 với cấu hình máy. DoD = (32 đạt) **hoặc** ADR owner/coordinator chốt trần v0.1 thấp hơn kèm số đo. Cấm ghi 16 như 32.

**3. [P1] “matrix cần thiết” vs Android sớm — stop/proceed lệch**  
`05:20-24,40-44` bắt Windows + 2 Android + thermal 20 phút. `06:86-87` thiếu máy không ACCEPT P1-03/P5-03. `06:120-123` P1-03 = full Q01 + thermal + “matrix cần thiết”. `06:111` P1-02 còn “secure… Windows+Android”. `01:38-43` fail 32 avatar thì dừng nội dung.  
**Impact:** Không có 2 điện thoại thì toàn bộ P2+ không ACCEPT; hoặc P1-03 được tick chỉ Windows.  
**Sửa:** Q01-B (P1-03): Windows + ≥1 Android thật, 0/8/32, cold+warm; low-end/thermal 20 phút được GAP-label, không được bỏ 32 avatar hay Android. Q01-F (P5-03): đủ 3 SKU + thermal. P1-02: DTLS/Android là feasibility; thiếu máy ghi GAP, không chặn DoD Windows.

**4. [P1] Hành trình P02 không có WP BUILD**  
`02-PRODUCT.md:20-24` (tên → preset → Solo → gợi ý → quest → skip tutorial; không login wall) và `:106-110` là cửa 10 phút. `06:89-95` chỉ menu/quit; `:134-148` rig/câu cá; `:237-241` “onboarding diagnostics”; `:272-278` P6-03 có VERIFY/DoD, **không BUILD**.  
**Impact:** Slice có thể không có first-run; P6-03 fail hoặc bot thay người.  
**Sửa:** Gán BUILD+VERIFY cho P0-03 (tên/preset/skip), P2-03 (3 quest + skip), P2-04 (vòng 10 phút Solo). P3-02 VERIFY: Solo cold-start không bắt login. P6-03 thêm BUILD: 5+8 người lớn, script, consent; thiếu người = UNVERIFIED, không ACCEPT.

**5. [P1] First hitch 150 ms có thể bất khả thi sau khi đã khóa Godot**  
`05:46-48` cấm coi loading là đạt nếu first move/emote >150 ms. `06:239` có shader strategy; `06:245-250` P5-03 = đủ Q01, chậm = GAP, không ADR. ADR engine chỉ `01:38-43` / `06:122-123`.  
**Impact:** Stock Godot Android dễ fail hitch lần đầu sau P1-03 đã khóa engine.  
**Sửa:** Tách Q01-cold (budget 15/25 s, warmup là phase có tên) và Q01-warm (hitch ≤150 ms **sau** warmup). P5-03 fail → proposal cắt nội dung `02:45-46` hoặc ADR visual-scope; không hạ số im lặng và không GAP vô hạn.

**6. [P1] DEV_ONLY / issuer trống trên WAN**  
`03-ARCHITECTURE.md:30-31` fixture DEV_ONLY. `06:170-175` cấm DEV_ONLY trong release, “không claim WAN production auth”. `06:266-268` P6-02 “secure login” + credential thật. Không câu “cấm DEV_ONLY trên mạng thật”.  
**Impact:** Alpha WAN chạy identity giả, hoặc P6-02/P6-03 treo.  
**Sửa:** P3-02/P6-02 DoD: DEV_ONLY chỉ loopback; thiếu issuer/secret = GAP chặn P6-02, không dùng fixture trên WAN.

**7. [P2] OS room server và transport WAN khóa muộn**  
`03:25-28,84-88` headless + “Trước WAN: khóa transport… NAT”. `04-GODOT-TOOLS.md:5-8` checksum theo OS. `06:70-77,107-114` spike Windows; `06:262-270` mới deploy.  
**Impact:** P6-01 đo ENet Windows rồi P6-02 đổi Linux/DTLS/WebRTC → số vô hiệu; UDP chặn trên mobile VN không có lối thoát.  
**Sửa:** P0-01/P0-02 ghi `room_server_os` và pin headless/templates khớp. P3-02 khóa transport (DTLS hoặc phương án secure đã test) + hành vi UDP-block (UI fail-closed hoặc TURN/alt). P6-01 phải đo trên đúng OS+transport đó.

**8. [P2] Style guide và font Việt lệch pipeline**  
`06:140` P2-02 “đạt style guide” nhưng `06:230` style guide thuộc P5-01. `02:76-77`, `04:83`, `05:80` bắt chữ Việt; P03/P5-01 không có font+license.  
**Impact:** Look-dev không chuẩn; chữ vỡ hoặc font không phép vẫn “art PASS”.  
**Sửa:** P2-02 BUILD xuất style guide + 1 font/stack đủ dấu, license trong manifest. P5-01 chỉ cập nhật, không tạo lần đầu. VERIFY Q03-R kiểm font runtime.

Không phát hiện mâu thuẫn quyền PLAN_ONLY vs “bắt đầu làm theo plan”, hay hứa MMO/Y8/ripping. Sửa 1–6 rồi có thể đóng băng; 7–8 nên sửa cùng lượt.

PLAN_REVIEW_VERDICT=REVISE
PLAN_MANIFEST_HASH=3477424499f1922b003cf07638503c98a84fb1acd68cc107b5e15706f9c9934a
MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast
FILES_CHANGED=NONE
RUNTIME_ACCEPTANCE=NONE

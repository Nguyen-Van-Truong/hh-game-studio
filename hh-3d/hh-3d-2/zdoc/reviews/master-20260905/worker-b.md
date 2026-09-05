I'll research the HH World 2 plan docs and official Play Together HAEGIN guides read-only, then return a plan-only UX report with visited URLs.Reading new-game AGENTS, canonical 00–09 docs, and locating official HAEGIN guides plus old HH Web progress.Canonical docs are in. Next I’ll pull PROGRESS, old HH Web social lessons, and official HAEGIN Play Together guides.Fetching official HAEGIN guide pages and old HH Web social-mode docs so claims stay source-backed.Searching for more official HAEGIN character/home/activity pages and Godot font/UI docs.Fetching the Korean HAEGIN guide (consent wording) and official Godot font docs so those URLs are first-hand.I have first-hand HAEGIN and Godot font pages. Drafting the plan-only research report next. Checking word count as I write so it stays under 1800.

```
HH WORLD 2 — UX / ART / GAMEPLAY RESEARCH (PLAN ONLY)
DATE=2026-09-05 Asia/Saigon
ROLE=read-only researcher
MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast
FILES_CHANGED=NONE
RUNTIME_PROOF=NONE
DESTINATION_IF_SAVED=sibling hoan-hao/zdoc/2026-09-05-hh-world-2-ux-art-gameplay-research.txt
(Ask-mode: content only; no write.)

================================================================================
1. TÓM TẮT + TIẾN ĐỘ + LIÊN KẾT
================================================================================

HH World 2 là game xã hội 3D nguyên bản, cảm hứng beat Play Together, không khí
Việt Nam; Godot stock 4.7.2 planned; gameplay trước, địa lý Hoàn Hảo sau.
PLAN_ONLY: chưa clone/cài engine, chưa scene/server/asset, chưa tick WP.

Tiến độ (zdoc/PROGRESS.md, 06-ROADMAP.md):
  SCOPE=hh-3d/hh-3d-2
  CURRENT_VALID_WP=H2-P0-01  STATUS=PLANNED
  IMPLEMENTATION=NOT_STARTED  ENGINE_INSTALLED=NO
  RUNTIME_ACCEPTANCE=NONE  HUMAN_ACCEPTANCE=NONE
  v0.1 = plaza authored + fishing + nhà/quầy + friends/party + room 32 TARGET
  v0.2 = một khu VN sau H2-P7; không quảng cáo CCU/cell/voice/tiền thật

Liên kết thẩm quyền mới:
  hh-3d/hh-3d-2/AGENTS.md
  zdoc/00-START-HERE.md  01-DECISIONS.md  02-PRODUCT.md
  04-GODOT-TOOLS.md  05-QUALITY-GATES.md  06-ROADMAP.md
  08-AGENT-WORKFLOW.md  09-RESEARCH.md
  (03/07 đọc khi WP viện dẫn; không thay 06.)

Web cũ CHỈ tham khảo, không tick:
  hh-3d/app/PROGRESS.txt — leftover GATE-U1; local 4175; NOT_PLAN_PASS
  hh-3d/zdoc/03-9-hh-world-owner-modes.txt — friends-only phố; shop sống khi
  chủ Offline; mode ≠ Internet; presence ≠ GPS; không người lạ trên phố

Bài học giữ: chơi thật mới nghiệm thu camera; shop durable ≠ avatar chủ;
presence filter server-side; cache phải nhãn thời điểm; không dùng FPS Web
làm proof Godot; không gộp evidence VF/Web vào HH2.

================================================================================
2. PLAY TOGETHER — QUAN SÁT GUIDE vs ĐOÁN BACKEND
================================================================================

Đã đọc HTTPS official hub HAEGIN 2026-09-05 (VI/EN/KO + index). Đây là
hướng dẫn người chơi, không phải spec engine/AOI/CCU.

QUAN SÁT (player-facing):
- Thị trấn xã hội: knockout minigame, tiệc nhà, câu cá, trường, cắm trại,
  thú cưng, trang trí nhân vật/nhà.
- Menu “Điện thoại” góc trên phải: minigame, tiệc, trang trí, nhiệm vụ,
  bản đồ, bạn bè, sổ sưu tầm. Túi góc trên phải: xe/pet/công cụ/cá/đồ.
- Bạn bè: xem online; Follow = đi tới vị trí bạn; Summon = yêu cầu bạn
  tới chỗ mình. Cả hai chỉ giữa Friends. KO: Summon cần bạn chấp nhận.
  EN/VI: Summon = “ask”; Follow không ghi consent đích.
- Tiệc nhà / minigame cùng bạn khi online.
- Travel: NPC tiếp viên plaza; văn bản gọi “chuyển máy chủ”; vùng gồm
  cả Việt Nam; về nhà miễn phí. Đây là nhãn UI, không chứng minh shard.
- Game Party: giải đấu; “30 người chơi” last-standing. Đây là size
  minigame, KHÔNG phải sức chứa plaza/nhà/party của HH2.
- Settings: âm/rung, lời mời, ngôn ngữ, push, FPS, độ phân giải, liên kết
  tài khoản. Inbox nhận vật phẩm/thông báo.
- Pet: đổi tên; ToS có thể đổi tên/cấm tài khoản.

KHÔNG CÓ TRONG GUIDE — cấm claim:
  engine (Unity/Godot/custom); Photon/AOI; tick; room/plaza cap thật;
  Follow có/không teleport instance; protocol auth; monetization backend;
  map-stream. Không rip client để “xác minh”.

================================================================================
3. BEAT NÊN GIỮ vs KHÔNG CLONE
================================================================================

GIỮ (chức năng, tự thiết kế):
  Vòng 10–15 phút: đi → hoạt động → thưởng → nhà/quầy → gặp bạn.
  Một skeleton + wardrobe catalog; một câu cá đọc được bằng hình/âm/thời điểm.
  Friends hai chiều + invite/join có consent + block.
  Nhà instance + visit; shop public sống khi chủ Offline.
  Menu gộp (không bắt chước icon Điện thoại HAEGIN).
  Travel = leave/join room có UI đầy/chờ; không hứa seamless.

BỎ / KHÔNG CLONE:
  Tỷ lệ chibi, UI Phone/Bag, Kaia/Captain Jack, hộ chiếu/tem, Game Party 30,
  pet egg/combine, tên item, nhạc, screenshot, trademark.
  Follow một chạm không consent vào nhà private (an toàn hơn: luôn ticket +
  policy + block + chỗ; nhà/private cần host/party accept).
  Không lấy 30 Game Party hay “thị trấn đông” làm cap HH2. Cap kế hoạch
  D04/A05: party 4 / nhà 8 / plaza 32 TARGET; 64 = stress render. Chưa đo.

================================================================================
4. ART / RIG / LOD / UI / FONT NGUYÊN BẢN
================================================================================

Hướng: “Phố hiên ấm” — stylized vừa người, silhouette rõ mobile; mái/hiên/
biển chữ Việt/cây/đèn nguyên bản; ánh sáng chủ đạo 1 sun + 1 bounce; atlas
vật liệu; không PBR đắt che mesh sơ. Palette: tường kem, ngói đất, biển
xanh ngọc, áo người chơi bão hòa vừa. Không GTA, không copy PT.

Rig/wardrobe (H2-P2-02 → bulk H2-P5-01):
  1 humanoid; xương ≤60; slots Body/Hair/Top/Bottom/Shoes/Acc.
  Skin: bind pose lock, weight paint review nách/cổ/đùi; test mix 6 outfit.
  Animation: idle/walk/run/jump/land + 6 emote; root-motion policy ghi;
  feet-slide = FAIL Q03-R. Không UGC mesh.

LOD/occlusion/nameplate (T05, Q02):
  Near ≤8k tri / ≤2 mat; far ≤2k; giảm anim/shadow/nameplate theo khoảng.
  Collision proxy ≠ render. Nameplate: pool, distance gate, hide khi
  occluded/blocked/ẩn; không Label3D ×32 update mỗi frame.
  Camera: sphere cast chống xuyên; reduced-motion tắt shake.

Âm thanh: nhạc/ambience license; pool bước/UI/câu cá; mute nhạc/SFX/UI
tách; không voice v0.1; cap voice count.

Touch/HUD (P05, H2-P2-01, H2-P5-02):
  Stick trái + drag cam phải; deadzone; multi-touch đi+xoay; nút ≥48 dp;
  chữ ≥16 sp; safe-area/notch; contrast; không chỉ màu/âm.
  Keyboard/mouse desktop; gamepad bổ sung, remap; layout hiện khi cắm pad.
  HUD tối thiểu: tương tác, emote, túi, bạn, settings. Diagnostics ở menu dev.

Font Việt (Godot 4.7 ResourceImporterDynamicFont, truy cập 2026-09-05):
  Bundle TTF/OTF/WOFF2 license rõ, đủ Latin + Vietnamese (ăâêôơưđ + sắc
  huyền hỏi ngã nặng). Preload range tiếng Việt để tránh hitch glyph.
  fallbacks[] = font dự phòng bundled; allow_system_fallback chỉ extra,
  không phụ thuộc (docs: appearance lệch OS; system font không phải iOS
  parity). MSDF/mipmaps chỉ nếu Label3D xa cần; đo memory. Test tên
  “Nguyễn Thị Đỗ Ước” trên biển, HUD, shop, nameplate.

Placeholder nội bộ + WP thay; screenshot placeholder ≠ art PASS.

================================================================================
5. BẢNG UX TRẠNG THÁI → HÀNH ĐỘNG → WP / ACCEPTANCE
================================================================================

Mỗi hàng: UI copy cụ thể + postcondition đọc lại server/runtime. Không
“handle gracefully”.

ID | State | Player action / UI | Pass rule | WP + Q
---|---|---|---|---
S1 | Invite hết hạn | Banner “Lời mời hết hạn”; Join disabled; Refresh | Ticket expired ≠ full ≠ block; retry xin mới | P3-02, P4-01; Q05
S2 | Room đầy | “Phòng đầy (n/n)”; Waitlist hoặc “Mời cả nhóm phòng khác” cần 4 accept | Không kick người đang chơi; reservation atomic party hoặc all-fail 15s | P4-01, P6-01, P8-02; Q04-C
S3 | Party mixed (2 in, 2 out) | Hiện ai đã vào; “Hủy chỗ chưa vào”; không claim cả nhóm đã join | Reservation atomic; join network không atomic | P4-01
S4 | Private house | Khách không ticket: “Nhà riêng — cần lời mời” | Không spawn; không lộ pose chủ | P4-03; Q04-L
S5 | Block | A block B: hết invite/chat/target; model B biến với ACK ≤2s | Filter server; không chỉ ẩn client; hủy invite in-flight | P4-01, P4-04
S6 | Ẩn hoàn toàn | Confirm: rời Public → Solo/private; “Người khác không thấy bạn trên phố” | Không vừa Ẩn vừa mesh Public; friends API không trả tọa độ | P4-01; P04
S7 | Hidden presence (không ẩn hết) | Friends thấy “Không hiện trên phố” | Không phân biệt tắt app vs ẩn | P4-01; lesson Web
S8 | Buy pending | Nút khóa; “Đang xác nhận…”; không +item | ACK chỉ sau journal commit + readback | P3-04, P4-02; Q05
S9 | Buy fail (hết hàng/tiền/version) | “Giao dịch thất bại — [lý do]”; rollback UI | Một last-item thắng; retry cùng command_id không nhân | P4-02; Q05
S10 | Buy unknown (timeout) | “Chưa rõ kết quả — kiểm tra lại”; nút Query | Không success sớm; query command_id | P3-04, P5-02
S11 | Reward room pending | Anim câu được; túi “Chưa ghi sổ” | “Đã nhận” chỉ API receipt | P3-03
S12 | First-run offline | Solo: tên+preset+đi+câu+nhà; badge “Không mạng — chơi thử Solo” | Không login wall; không mint Online | P0-03, P2-04; Q03-A
S13 | No/low storage | “Không đủ bộ nhớ lưu”; chặn save; giữ RAM session | Không silent fail; không đè ledger | P2-04, P5-02
S14 | Low RAM / thermal | Auto quality 1 bước + toast; giữ input | Q01-B observe 10m; Q01-F 20m FAIL nếu trượt ngưỡng | P1-03, P5-03
S15 | Background / cuộc gọi | Pause render; Online: lock input, room chạy; “Vẫn Online — tạm rời?” | Tab-hide không ghost (lesson Web TTL 10s) | P5-02; Q04-L
S16 | Touch focus | Tap UI không giro cam; đóng menu trả analog | Multi-touch đi+xoay; 48dp | P2-01, P5-02
S17 | Controller | Prompt layout; stick=move, look, South=interact | Unplug về touch; remap | P2-01
S18 | Unicode / a11y | Tên/shop/chat normalize; font đủ dấu; text-scale; contrast | Bypass Unicode = FAIL chat | P2-02, P4-04, P5-02
S19 | Missing asset | Prop = cube tagged MISSING; không crash | Catalog stale: “Đồ này đã gỡ — hoàn tác?” | P4-03, P5-01
S20 | Safe spawn | Join/desync → điểm nav đã author, không xuyên/lọt map | Reconcile pose; không teleport-as-proof duy nhất | P2-01, P3-03, P8-01
S21 | Map/chunk desync | “Bản đồ lệch — tải lại khu”; freeze move | Version mismatch fail-closed; không trộn origin | P7-02, P8-01; Q06
S22 | Solo vs Online economy | Login: “Nhà/tiền Solo không chuyển Online” | JSON Solo không mint; namespaces tách | P2-04, P3-04; Q05
S23 | Offline browse shop | Kệ cache “Bản lúc HH:MM”; Buy disabled | EMPTY ≠ STALE ≠ UNAVAILABLE | P4-02, P7-03
S24 | Offline publish | “Chưa đăng — không có mạng” | Không auto-queue thành public | P4-02; Web modes
S25 | Stranger plaza | Dialog 2 bước: Public = người lạ cùng phòng; Block/Report | Default Friends/private; không bật thầm | P4-01, P6-02
S26 | Chat trước mod | Chat toggle OFF; emote ON | Không mở public chat thiếu operator | P4-04, P6-02

================================================================================
6. NGƯỜI LẠ OPT-IN vs FRIENDS-ONLY CŨ
================================================================================

Web cũ: phố chỉ bạn hai chiều + Online + không block. Phố trống là đúng.
Shop public không cần bạn; không GPS.

HH2: mặc định Friends/private giữ ý đó. Public plaza là lựa chọn mới trong
game, có copy trước khi vào, có block/report, có cap/AOI. Không backport
người lạ vào Web 4175. Ẩn hết = rời Public. Join luôn: consent + block +
policy + chỗ. Friends API: online/room được phép, không stream transform xa.

================================================================================
7. OFFLINE BROWSE vs MUA — KHÔNG TIN CLIENT
================================================================================

Internet ⊥ social mode.
  Có mạng: đọc catalog mới; Solo vẫn không publish presence.
  Mất mạng: cache có timestamp; Buy/Publish/Invite disabled.
  Mua: một transaction DB (stock+wallet+item+journal+outbox) → receipt.
  Pending / Failed / Unknown là 3 UI khác nhau (S8–S10).
  Shop published sống khi owner logout. Draft không lộ.
  Client không mint, không tin owner_id/giá/kết quả câu.

================================================================================
8. SÓNG SONG SONG (SAU DEPENDENCY)
================================================================================

Không mọi worker cùng một .tscn. Không migrate geo trước v0.1.

W0  PLAN_ONLY — xong tài liệu; chờ owner “bắt đầu”.
W1  sau P0-03: P1-01 tools (addon/contracts) ∥ P1-02 net spike (throwaway
    scenes). P1-03 cần P1-02 + 1 Android; không chờ full T03.
W2  sau P1-03: P2-01..P2-04 Solo trên game/scenes/player|activity|house.
    P3-01 foundation sau P1-03; schema domain chốt sau P2-03.
    Art look-dev (1 hero, font, LOD) trên assets-src/ — không plaza final.
W3  P3-02..P4-04: API/contracts/backend ≠ client UI files; 1 writer/file.
W4  P5 art bulk + audio + a11y sau social đúng; P5-03 perf-only lease.
W5  P6 alpha ops. P7+ geo converter riêng; authored plaza giữ chơi được
    nếu thiếu quyền dataset.

Hợp đồng sớm (không implement): quality-profile, net ticket, inventory
command, font/license manifest, wardrobe slot table.

================================================================================
9. URL ĐÃ MỞ (2026-09-05) / UNKNOWNS
================================================================================

1. https://hub.playtogether.haegin.kr/vi/homegame-guide/whats-the-play-together
   Hỗ trợ: beat xã hội/nhà/câu/bạn Follow+Summon; Phone/Bag. Không engine/cap.
2. https://hub.playtogether.haegin.kr/homegame-guide/whats-the-play-together
   Hỗ trợ: EN “Summon = ask”; Travel = “server transferring” (nhãn UI).
3. https://hub.playtogether.haegin.kr/ko/homegame-guide/whats-the-play-together
   Hỗ trợ: Summon cần chấp nhận; Follow không ghi consent đích.
4. https://hub.playtogether.haegin.kr/homegame-guide
   Index/chrome; không thêm rule nhà/character. Store links không dùng.
5. https://docs.godotengine.org/en/4.7/classes/class_resourceimporterdynamicfont.html
   Hỗ trợ: TTF/OTF/WOFF2, fallbacks, system-fallback lệch OS, preload glyph,
   MSDF/mipmaps. Không đo FPS.

Hub index không liệt kê guide nhà/character riêng; chi tiết decorate/fishing
timing = UNKNOWN (không đoán, không rip).

UNKNOWN: máy Android owner; fun; identity provider; quyền Hoàn Hảo; nhân sự
mod; tên phát hành; iOS. Có gate P0–P9. Không giả FPS/CCU.

MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast
FILES_CHANGED=NONE
RUNTIME_PROOF=NONE
```

Let me count words more carefully. The user said max 1800 words. My draft looks like it might be around 1400-1700. Let me count...

I'll count the body... It's probably close to 1600-1800. Good.

The user said "Return stdout only" - so this document IS the response. I should not add extra commentary after it.

One issue: I should not invent the sibling path as if I wrote the file. I noted Ask-mode no write.

Also "4-6 actually visited primary URLs" - I have 5. Good.

Game Party 30 - I correctly said it's minigame not plaza cap.

I did not claim engine.

I think this is complete. I'll output this as the sole response.

Wait - should I refine a few things?

"sibling hoan-hao/zdoc" - I couldn't find hoan-hao in the workspace. That's fine - recommend the path.

Double-check word count with a rough estimate:
Section 1: ~280 words
Section 2: ~220
Section 3: ~150
Section 4: ~280
Section 5: ~450 (table is dense)
Section 6: ~90
Section 7: ~80
Section 8: ~140
Section 9: ~150
Header: ~80
Total ~1920 - might be slightly over 1800.

I need to trim ~150 words.

Let me tighten sections 1, 2, 4, 5.Trimming the report to stay under 1800 words, then returning stdout only.

```
HH WORLD 2 — UX/ART/GAMEPLAY RESEARCH (PLAN ONLY)
DATE=2026-09-05 Asia/Saigon
ROLE=read-only researcher
MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast
FILES_CHANGED=NONE
RUNTIME_PROOF=NONE
SAVE_IF_OWNER_WRITES=sibling hoan-hao/zdoc/2026-09-05-hh-world-2-ux-art-gameplay-research.txt
(Ask-mode: stdout only; no file write.)

================================================================================
1. TÓM TẮT + TIẾN ĐỘ + LIÊN KẾT
================================================================================

HH World 2: game xã hội 3D nguyên bản, beat Play Together, không khí Việt Nam.
Godot stock 4.7.2 planned; gameplay trước, địa lý Hoàn Hảo sau. PLAN_ONLY:
chưa clone/cài engine, chưa scene/server/asset, chưa tick WP.

Tiến độ (PROGRESS.md, 06-ROADMAP.md): SCOPE=hh-3d/hh-3d-2;
CURRENT_VALID_WP=H2-P0-01 PLANNED; IMPLEMENTATION=NOT_STARTED;
ENGINE_INSTALLED=NO; RUNTIME/HUMAN_ACCEPTANCE=NONE.
v0.1 = plaza authored + câu cá + nhà/quầy + friends/party + room 32 TARGET.
v0.2 = một khu VN sau H2-P7. Không quảng cáo CCU/cell/voice/tiền thật.

Thẩm quyền mới: hh-3d/hh-3d-2/AGENTS.md; zdoc/00-START-HERE.md,
01-DECISIONS.md, 02-PRODUCT.md, 04-GODOT-TOOLS.md, 05-QUALITY-GATES.md,
06-ROADMAP.md, 08-AGENT-WORKFLOW.md, 09-RESEARCH.md. 03/07 chỉ khi WP trỏ.

Web cũ tham khảo, không tick: hh-3d/app/PROGRESS.txt (GATE-U1 leftover,
4175 local, NOT_PLAN_PASS); zdoc/03-9-hh-world-owner-modes.txt
(friends-only phố; shop sống khi chủ Offline; mode ≠ Internet; presence ≠ GPS).

Giữ bài học: camera phải chơi thật; shop durable ≠ avatar chủ; filter
server-side; cache có timestamp; FPS Web ≠ proof Godot; không gộp VF/Web.

================================================================================
2. PLAY TOGETHER — GUIDE vs ĐOÁN BACKEND
================================================================================

Đọc HTTPS hub HAEGIN 2026-09-05 (VI/EN/KO + index). Hướng dẫn người chơi,
không spec engine/AOI/CCU.

Quan sát: thị trấn xã hội (minigame, tiệc nhà, câu cá, trường, cắm trại,
pet, trang trí nhân vật/nhà). Menu Điện thoại góc trên phải: minigame, tiệc,
trang trí, nhiệm vụ, bản đồ, bạn, sổ. Túi: xe/pet/công cụ/cá. Bạn: xem
online; Follow = tới chỗ bạn; Summon = xin bạn tới chỗ mình; cả hai chỉ
Friends. KO: Summon cần chấp nhận. EN/VI: Summon = “ask”; Follow không ghi
consent đích. Travel: NPC tiếp viên; nhãn “chuyển máy chủ”; có Việt Nam;
về nhà miễn phí — nhãn UI, không chứng minh shard. Game Party: “30 người”
last-standing = size minigame, không phải cap plaza/nhà HH2. Settings:
âm/rung, lời mời, ngôn ngữ, push, FPS, độ phân giải, liên kết tài khoản.
Pet đổi tên; ToS có thể đổi tên/cấm.

Không có trong guide — cấm claim: engine; Photon/AOI; tick; room cap thật;
Follow có teleport instance hay không; auth; monetization backend. Không rip.

================================================================================
3. BEAT GIỮ vs KHÔNG CLONE
================================================================================

Giữ (tự thiết kế): vòng 10–15 phút đi → hoạt động → thưởng → nhà/quầy → gặp
bạn; 1 skeleton + wardrobe catalog; 1 câu cá đọc hình/âm/thời điểm; friends
hai chiều + invite/join + block; nhà instance + visit; shop public khi chủ
Offline; menu gộp (không icon Phone HAEGIN); chuyển khu = leave/join có UI.

Không clone: tỷ lệ chibi, UI Phone/Bag, Kaia/Captain Jack, hộ chiếu, Game
Party 30, pet egg, tên item, nhạc, screenshot, trademark. Không Follow một
chạm vào nhà private. HH2: ticket + policy + block + chỗ; nhà cần host/party
accept. Cap kế hoạch D04/A05: party 4 / nhà 8 / plaza 32 TARGET; 64 = stress
render. Chưa đo. Không lấy 30 minigame làm cap.

================================================================================
4. ART / RIG / LOD / UI / FONT
================================================================================

Hướng “Phố hiên ấm”: stylized vừa người, silhouette mobile; mái/hiên/biển
chữ Việt nguyên bản; 1 sun + bounce; atlas; không PBR đắt, không GTA, không
copy PT. Palette: tường kem, ngói đất, biển ngọc, áo bão hòa vừa.

Rig (P2-02, bulk P5-01): 1 humanoid, ≤60 xương; slot Body/Hair/Top/Bottom/
Shoes/Acc; weight nách/cổ/đùi; mix 6 outfit. Anim idle/walk/run/jump/land +
6 emote; root-motion ghi; feet-slide = FAIL Q03-R. Không UGC mesh.

LOD/occlusion/nameplate (T05/Q02): near ≤8k/≤2 mat; far ≤2k; giảm
anim/shadow/nameplate theo khoảng. Collision ≠ render. Nameplate pool +
distance + ẩn khi occluded/block; không 32 Label3D/frame. Camera sphere-cast;
reduced-motion tắt shake.

Âm: nhạc/ambience license; pool bước/UI/câu; mute tách; không voice v0.1.

Touch (P2-01, P5-02): stick trái + drag cam; deadzone; đi+xoay cùng lúc;
nút ≥48 dp; chữ ≥16 sp; safe-area; contrast; không chỉ màu/âm. Desktop
kb/mouse; pad bổ sung, hiện layout khi cắm. HUD: tương tác, emote, túi,
bạn, settings. Diagnostics ở menu dev.

Font (Godot 4.7 ResourceImporterDynamicFont): bundle TTF/OTF/WOFF2 đủ
Latin+Việt (ăâêôơưđ + thanh). Preload range Việt. fallbacks[] bundled;
allow_system_fallback chỉ extra (docs: lệch OS). MSDF/mipmaps chỉ nếu
Label3D xa cần. Test “Nguyễn Thị Đỗ Ước” trên biển/HUD/shop/nameplate.
Placeholder nội bộ + WP thay; ảnh placeholder ≠ art PASS.

================================================================================
5. BẢNG UX → HÀNH ĐỘNG → WP / ACCEPTANCE
================================================================================

Mỗi hàng: copy cụ thể + postcondition đọc lại. Không “handle gracefully”.

ID | State | UI / action | Pass | WP+Q
---|---|---|---|---
S1 | Invite hết hạn | “Lời mời hết hạn”; Join tắt; Refresh | expired ≠ full ≠ block; xin ticket mới | P3-02 P4-01 Q05
S2 | Room đầy | “Phòng đầy (n/n)”; chờ hoặc “Cả nhóm phòng khác” cần 4 accept | không kick người đang chơi; reserve party all-or-fail 15s | P4-01 P6-01 P8-02 Q04-C
S3 | Party mixed | hiện ai đã vào; “Hủy chỗ chưa vào” | reserve atomic; join mạng không atomic | P4-01
S4 | Private | “Nhà riêng — cần lời mời” | không spawn; không lộ pose chủ | P4-03 Q04-L
S5 | Block | hết invite/chat/target; model biến ACK≤2s | filter server; hủy invite in-flight | P4-01 P4-04
S6 | Ẩn hết | confirm rời Public→Solo/private | không vừa Ẩn vừa mesh Public; API không trả tọa độ | P4-01 P04
S7 | Ẩn một phần | friends: “Không hiện trên phố” | không lộ tắt app vs ẩn | P4-01
S8 | Buy pending | khóa nút; “Đang xác nhận…”; không +item | ACK sau commit+readback | P3-04 P4-02 Q05
S9 | Buy fail | “Thất bại — [lý do]”; rollback | last-item một thắng; retry cùng id không nhân | P4-02 Q05
S10 | Buy unknown | “Chưa rõ — kiểm tra lại”; Query | không success sớm; query command_id | P3-04 P5-02
S11 | Reward pending | anim câu; túi “Chưa ghi sổ” | “Đã nhận” = API receipt | P3-03
S12 | First-run offline | Solo tên+preset+đi+câu+nhà; “Không mạng — chơi thử” | không login wall; không mint Online | P0-03 P2-04 Q03-A
S13 | Hết chỗ lưu | “Không đủ bộ nhớ lưu”; chặn save | không silent; không đè ledger | P2-04 P5-02
S14 | Low RAM/thermal | hạ quality 1 bước + toast; giữ input | Q01-B 10m observe; Q01-F 20m FAIL nếu trượt | P1-03 P5-03
S15 | Nền / cuộc gọi | pause render; Online lock input, room chạy; “Vẫn Online?” | không ghost; actor TTL 10s | P5-02 Q04-L
S16 | Touch focus | tap UI không giro cam; đóng menu trả analog | multi-touch; 48dp | P2-01 P5-02
S17 | Controller | hiện layout; South=interact | unplug về touch; remap | P2-01
S18 | Unicode/a11y | normalize tên/shop/chat; đủ dấu; text-scale | bypass Unicode = FAIL | P2-02 P4-04 P5-02
S19 | Missing asset | cube MISSING; không crash | catalog stale: “Đồ đã gỡ — hoàn tác?” | P4-03 P5-01
S20 | Safe spawn | join/desync → nav đã author | reconcile pose; teleport không phải E2E duy nhất | P2-01 P3-03 P8-01
S21 | Map desync | “Bản đồ lệch — tải lại”; freeze move | version fail-closed | P7-02 P8-01 Q06
S22 | Solo≠Online | login: “Nhà/tiền Solo không chuyển” | JSON Solo không mint | P2-04 P3-04 Q05
S23 | Offline browse | kệ “Bản lúc HH:MM”; Buy tắt | EMPTY≠STALE≠UNAVAILABLE | P4-02 P7-03
S24 | Offline publish | “Chưa đăng — không mạng” | không auto thành public | P4-02
S25 | Plaza lạ | 2 bước: Public = người lạ cùng phòng; Block/Report | default Friends/private; không bật thầm | P4-01 P6-02
S26 | Chat trước mod | Chat OFF; emote ON | không public chat thiếu operator | P4-04 P6-02

================================================================================
6. NGƯỜI LẠ OPT-IN vs FRIENDS-ONLY CŨ
================================================================================

Web: phố chỉ bạn hai chiều + Online + không block. Phố trống là đúng. Shop
public không cần bạn. Không GPS.

HH2: mặc định Friends/private giữ ý đó. Public plaza là lựa chọn mới, copy
trước khi vào, có block/report/cap. Không backport người lạ vào 4175. Ẩn hết
= rời Public. Join: consent + block + policy + chỗ. Friends API: online/room
được phép, không stream transform xa.

================================================================================
7. OFFLINE BROWSE vs MUA — KHÔNG TIN CLIENT
================================================================================

Internet ⊥ mode. Có mạng: catalog mới; Solo không publish presence. Mất mạng:
cache có timestamp; Buy/Publish/Invite tắt. Mua = một transaction
stock+wallet+item+journal+outbox → receipt. Pending/Failed/Unknown tách UI.
Shop published sống khi logout. Draft không lộ. Client không mint, không tin
owner_id/giá/kết quả câu.

================================================================================
8. SÓNG SONG SONG
================================================================================

Không nhiều writer một .tscn. Không migrate geo trước v0.1.

W0 PLAN_ONLY — chờ owner “bắt đầu”.
W1 sau P0-03: P1-01 tools ∥ P1-02 net (throwaway scenes). P1-03 cần P1-02 +
1 Android; không chờ full T03.
W2 sau P1-03: P2 Solo trên player/activity/house. P3-01 sau P1-03; schema
domain sau P2-03. Look-dev 1 hero+font+LOD trên assets-src, không plaza final.
W3 P3-02–P4-04: backend/contracts ≠ client UI; 1 writer/file.
W4 P5 bulk art/audio/a11y sau social đúng; P5-03 chỉ lease perf.
W5 P6 ops. P7+ converter riêng; plaza authored vẫn chơi nếu thiếu dataset.

Hợp đồng sớm (chưa code): quality-profile, net ticket, inventory command,
font/license, wardrobe slots.

================================================================================
9. URL ĐÃ MỞ (2026-09-05) / UNKNOWNS
================================================================================

1. https://hub.playtogether.haegin.kr/vi/homegame-guide/whats-the-play-together
   Beat xã hội/nhà/câu/bạn Follow+Summon; Phone/Bag. Không engine/cap.
2. https://hub.playtogether.haegin.kr/homegame-guide/whats-the-play-together
   EN Summon=ask; Travel=“server transferring” (nhãn UI).
3. https://hub.playtogether.haegin.kr/ko/homegame-guide/whats-the-play-together
   Summon cần chấp nhận; Follow không ghi consent đích.
4. https://hub.playtogether.haegin.kr/homegame-guide
   Index/chrome; không thêm rule nhà/character.
5. https://docs.godotengine.org/en/4.7/classes/class_resourceimporterdynamicfont.html
   TTF/OTF/WOFF2, fallbacks, system-fallback lệch OS, preload, MSDF. Không FPS.

Hub không có guide nhà/character riêng; timing/reward fishing = UNKNOWN.
Không đoán, không rip.

UNKNOWN: Android owner; fun; identity; quyền Hoàn Hảo; nhân sự mod; tên
phát hành; iOS. Có gate P0–P9. Không giả FPS/CCU. Không chữ ký người.

MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast
FILES_CHANGED=NONE
RUNTIME_PROOF=NONE
```

Tôi sẽ đọc master TXT, AGENTS.md và các file canonical 00–09/plan-freeze-v2, rồi đối chiếu link, hash và các điểm adversarial — chỉ đọc, không sửa.Tiếp theo tôi đọc 00–09, PROGRESS, freeze/review và đối chiếu 32 WP cùng các link/hash.Tôi đang đối chiếu contract canonical, freeze hash, mapping 32 WP và các URL/công thức dễ gây hiểu nhầm.Đang tính hash, kiểm tra path/link và đọc nốt contract còn lại để bắt mâu thuẫn thứ tự/đơn vị.Hash canonical khớp freeze. Tiếp theo tôi kiểm tra các URL công khai còn lại và vài chỗ dễ gây hiểu nhầm thẩm quyền.Critic A độc lập, chỉ đọc. Bảng đầu đứng ngay sau tiêu đề và đọc được theo giai đoạn. `PLAN_ONLY` / `IMPLEMENTATION=NONE` khớp `PROGRESS.md`. 12 file freeze `4762d1cc…` vẫn MATCH. Godot 4.7.2 là stable hiện tại (18-08-2026, prefix `ed1daf0bf`); master không tuyên bố đã acquire binary. Không clone/fork, gameplay trước địa lý, cảm hứng Play Together sạch phòng. UX/cổng A–M, session/economy/restore/AOI đủ; CCU/FPS không bịa. File không cụt (40279 byte). Có **một blocker** đường dẫn thẩm quyền.

**1. BLOCKER — «Cách đọc và nguồn»**  
Cụm: `Nếu có mâu thuẫn, AGENTS.md và roadmap canonical thắng về routing/thứ tự`. `AGENTS.md` không path. Trong `hh-game-studio` đó là plan Vault Fighters (`CURRENT_VALID_WP=VF6-WP5`). Trong `hoan-hao` đó là AGENTS service. Agent có thể làm nhầm sản phẩm.  
Sửa: `hh-3d/hh-3d-2/AGENTS.md` + `06-ROADMAP.md` thắng routing HH World 2; `hoan-hao/AGENTS.md` chỉ thắng code Hoàn Hảo; root/`hh-3d/AGENTS.md` không áp dụng.

**2. CAO — Bảng đầu hàng 1–2 vs mục 2 W1 vs `06`**  
Hàng 1 đòi `UndoRedo/lease/readback đúng` trước hàng 2 (spike). W1 ghi `bootstrap; network risk spike; editor tool spike` như việc song song. `06` bắt P1-01/P1-02 **sau** P0-03 ACCEPTED, rồi mới song song; P1-03 không chờ hết P1-01.  
Sửa: hàng 1 chỉ P0; W1 = P1-01∥P1-02 sau P0-03; cấm P0-03∥P1.

**3. CAO — mục 11**  
`Bắt đầu triển khai từ hh-3d-2/zdoc/00-START-HERE.md` không resolve từ `hoan-hao/zdoc` (Test-Path false).  
Sửa: `../../hh-game-studio/hh-3d/hh-3d-2/zdoc/00-START-HERE.md` như các link khác.

**4. CAO — mục 7.2**  
`rooms = min(..., network_ingress/down, ...)` trong khi `B_down/up` là bytes/s/**client** → ra số client, không phải room.  
Sửa: `rooms_net = floor(net_budget / (N_room × B_down_p95))` cùng đơn vị; giữ headroom 30%.

**5. VỪA — bảng 0–10 vs W0–W8**  
Hàng 0 `ĐÃ LẬP KẾ HOẠCH` ≠ W0 `chốt 4.7.2 + checksum`. “Làm mục/wave 3” lệch nhau (P2 vs nhà+API).  
Sửa: cột Wave ghi `H2-P…`; hàng 0 ghi `KẾ HOẠCH XONG — lock ở P0-01`.

**6. VỪA — mục 12**  
`đọc bản stable 4.7.2 ngày 18-08-2026` — 18-08 là ngày **release**; trang được đọc 2026-09-05.  
Sửa: `release 2026-08-18; đọc trang 2026-09-05; acquire/SHA256 ở P0-01`.

**7. VỪA — sau Kết luận và dòng cuối**  
`PLAN_DESIGN=MASTER_ADDENDUM_COMPLETE` rồi mới có mục 12–13; `LAST_UPDATED=…10:xx` lặp hai lần. Agent có thể dừng sớm hoặc ghi timestamp giả.  
Sửa: một `LAST_UPDATED` lấy metadata file; COMPLETE để sau mục 13; giữ `MASTER_STATUS=…FOR_REVIEW_ONLY`.

**8. VỪA — mục 13**  
`Có máy Windows và ít nhất một Android cho early gate` như cửa trước “bắt đầu”. `06` P0-02: thiếu Android = gap, bootstrap local vẫn dispatch.  
Sửa: Android bắt buộc từ P1-03/Q01-B; P0-01 không chờ máy.

Mọi markdown `../../hh-game-studio/...` tồn tại. URL official mở được (Photon bị cookie-wall, không 404). Addendum A–M không mâu thuẫn Q04-C (tick 30 Hz, p95 ≤16 ms, 32 client). Không có runtime.

MASTER_REVIEW=REVISE  
MASTER_SHA256=f5816b91c71153de5e17f5e7983902a4b2ef560916654f560ae4f45bee6b609b  
LINKS=PASS  
FILES_CHANGED=NONE  
RUNTIME_PROOF=NONE  
MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast

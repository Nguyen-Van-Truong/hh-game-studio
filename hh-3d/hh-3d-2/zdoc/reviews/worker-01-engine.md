Tôi sẽ đọc tài liệu nội bộ được chỉ định và đối chiếu nguồn chính thức hiện hành, rồi trả báo cáo planning — không sửa file, không implement.Tiếp tục đọc header/performance của app cũ và các zdoc mới, đồng thời đối chiếu tài liệu Godot/Unity/Play Together.Đang đọc thêm mục hiệu năng nội bộ và đối chiếu tài liệu chính thức Godot, Play Together, Unity, Photon.Web search bị chặn; tôi sẽ gọi trực tiếp các URL tài liệu chính thức và đọc thêm phần hiệu năng trong handoff.# Báo cáo planning — engine cho game mới `hh-3d/hh-3d-2`

Phạm vi: **game đời sống xã hội nguyên bản** (gameplay trước, địa lý Việt Nam sau). App web cũ `hh-3d/app` (HH World) **không** bị sửa và **không** phủ quyết plan mới. Vault Fighters / pin Godot 4.7.1 của repo **không** chuyển sang sản phẩm này. Không implement.

**WEB_VERIFIED=no.** WebSearch và WebFetch bị từ chối ngày 2026-09-05; không giả đã mở tài liệu sống. Claim “chính thức” dưới đây là **kiến thức tài liệu đã biết**, ghi UNCERTAIN cho currentness.

---

## 1. Engine: Godot stock native — không fork lõi

**Khuyến nghị dứt khoát cho game mới:** client + editor **Godot official stable, binary stock**, xuất **Windows desktop + Android native**. Server authoritative **tách process** (Godot dedicated *hoặc* service riêng). Addon GDScript + **GDExtension** khi cần native. **Không** fork/custom engine. **Không** lấy Web R3F/MapLibre hiện tại làm client game. Unity/Unreal/engine tự viết **không** phải mặc định.

Lý do khớp sản phẩm + studio, không phải “Godot nhanh hơn”:

- Thể loại stylized (đi bộ, emote, nhà, tiệm, hoạt động) cần vòng lặp editor/agent, animation, instance room — không cần globe/photoreal hay vehicle/crowd Unreal.
- Owner muốn agent thao tác **đúng semantic trong Godot** (EditorPlugin, UndoRedo). Studio đã có kỷ luật đó ở lane khác; chuyển **quy trình**, không chuyển code VF.
- Web cũ đã chứng minh **khung browser + R3F + MapLibre + Html portal** khó đạt ngân sách frame cho phố 3D; đó **không** chứng minh Godot sẽ 60 FPS, chỉ chứng minh **không nên mặc định lặp stack đó** cho game mới.
- Unity mạnh live-ops/mobile commercial; Unreal mạnh cinematic/thế giới lớn. Cả hai đắt hơn về license/tooling/agent và thừa cho MVP.
- Godot HLAPI **không** phải MMO. Scale nằm ở **server/instance**, không ở việc chọn logo engine.

**Không tiếp tục Web làm client chính:** `PRODUCT_TYPE=WEB_FIRST` và `R7` Unreal trong plan 31-8 là hợp đồng **app bản đồ**. Game mới là sản phẩm khác. Godot HTML5 chỉ là kênh sau, không phải target nghiệm thu.

**Không fork lõi.** Fork = nợ merge, trễ vá, agent/docs lệch official, phá pin. GDExtension là đường native official (mở rộng mà không sửa cây engine). Module C++ trong source engine = custom build — chỉ khi owner ký gate có thời hạn.

**Đảo khuyến nghị khi (ghi trước, đo sau):**

1. Bake-off cùng asset/camera/avatar (mục 4): Godot **trượt** ngưỡng tạm **và** Unity (hoặc Unreal) **đạt** trên cùng máy đích.
2. Ngày 1 bắt buộc một client vừa chơi vừa globe/3D Tiles (khi đó Godot + adapter địa lý là rủi ro; xem lại Unity/native + layer map, không lặng lẽ nhồi Cesium vào MVP).
3. Server cần ngôn ngữ/ops mà Godot dedicated không gánh — giữ **Godot client**, đổi server (Go/C#/Rust), không fork renderer.
4. Console/middleware chỉ có SDK Unity/Unreal.
5. Team/agent **không** kiểm soát được editor Godot sau spike UndoRedo — đảo sang Unity.

**Bố cục workspace (đề xuất, chưa tạo):**

- `hh-3d/hh-3d-2/zdoc/` — plan/hợp đồng (lane này).
- `client/` — một Godot project stock; `addons/` có lock/license.
- `gdextension/` — mã native + artifact build **không** commit cache.
- `server/` — sim authoritative + persistence API; không nhét PostGIS vào process frame.
- `tools/` — replay, packer, lệnh editor.
- `geo/` — adapter sau (hợp đồng ID/CRS), không phải mesh đi bộ MVP.
- `third_party/godot-<tag>/` **tuỳ chọn, read-only**, khớp tag official — để đọc/debug, **không** phải binary ship.

Không để source engine trong project chơi. Không đụng `godot/dogfood/superfighters/` hay pin VF.

**Pin / nâng / rollback:**

- Pin **một** bản official stable trong decision record của **hh-3d-2**. Không ghi `latest`. Không sao chép 4.7.1 vì VF đang dùng; **không** đổi pin VF.
- **Current official stable trên godotengine.org: chưa xác minh được turn này.** Trước khi lock, owner/agent mở [Godot Download](https://godotengine.org/download/) và [Release policy](https://docs.godotengine.org/en/stable/about/releases.html).
- Nâng bản: change record + giữ binary cũ + import + hết warning chưa giải thích + chạy lại công thức mục 4. Rollback = đổi binary + revert feature `project.godot` nếu cần.
- Addon/GDExtension theo **minor đã pin**; ABI lệch thì rebuild extension, không “sửa engine cho khớp”.

---

## 2. Play Together: hành vi người chơi vs đoán backend → MVP gốc

**Không tải/rip/RE game.** Không mở được trang HAEGIN hôm nay.

**Có thể coi là hành vi người chơi** (store/hướng dẫn công khai theo kiến thức cũ; **UNCERTAIN 2026-09-05**): tạo/đổi avatar và trang phục; đi/chạy trên map theo chủ đề; emote; bạn bè / vào nhóm / chat; vào nhà/trang trí; hoạt động/minigame/sự kiện; sưu tầm đồ; cửa hàng/giao dịch **trong game**. Đây là **beat chức năng** để làm bản gốc, không phải spec pháp lý hay “giống 1:1”.

**Đoán backend — không dùng làm kiến trúc:** số người/đảo, cách shard, interest management, authority, chống gian lận, doanh thu nội bộ. Thể loại này **thường** dùng **instance/room** (đảo, nhà, minigame) chứ không phải một cell liền mạch toàn quốc; đó là suy luận ngành, **không** phải tài liệu HAEGIN đã mở.

**MVP gốc khả thi (offline → 2–4 process LAN):** một khu stylized **không** OSM; đi/camera/va chạm authored; avatar vài slot + ~6 emote; nhà một instance + catalog nội thất; 1–2 hoạt động chung trong room; shop persist catalog-first, **không** tiền thật; kết bạn + party 2–4; persistence local/LAN. Nghiệm thu: tự chơi được 15 phút, vui, mượt trên desktop headed.

**Sau MVP:** nhiều map/cosmetic/activity; **plaza công cộng có người lạ bị cap**; friend presence thô + join room; shop moderation; WAN alpha đóng. **Địa lý VN** chỉ sau khi gameplay đứng: snapshot OSM/PostGIS → local ENU, visual MapLibre/minimap; đường đi vẫn authored. Không hứa 1:1 hay “mọi người thấy mọi người”.

### Hợp đồng cũ friends-only ≠ mặc định game mới

File `03-9-hh-world-owner-modes.txt` (**AUTHORITY=1** cho app cũ): phố Online **chỉ bạn hai chiều**; không người lạ; shop public sống khi chủ offline; presence = avatar ảo, không GPS. Plan 31-8: “thấy người lạ trên phố” **out of scope mãi** cho HH World.

Game mới (Play Together-like) **cần** người lạ trong plaza/activity — nếu không, “đời sống” chết. **Đây là quyết định ghi file mới** dưới `hh-3d/hh-3d-2/zdoc/`, ví dụ `social-visibility-contract`. **Cấm** sửa thầm `03-9` / `31-8` / `PROGRESS.txt`.

Giữ từ app cũ (vẫn đúng): shop persist ≠ chủ online; mode Online/Offline + consent; lọc server-side; marker ≠ avatar; không GPS. **Đổi có chủ đích:** visibility plaza = instance + cap người lạ; bạn bè = danh sách + join, không phải nguồn duy nhất của body trên phố.

---

## 3. Scale thật: AOI ≠ shard

| Khái niệm | Làm gì | Không làm gì |
|---|---|---|
| **AOI** | Server **không gửi** entity ngoài vùng/cap | Không thêm CPU khi 500 người cùng một process |
| **Instance/room** | Tách sim (plaza/nhà/minigame) | Không đi liền mạch giữa room |
| **Shard/cell** | Cắt **một** map liền thành nhiều process | Đắt: biên, authority, teleport ẩn |
| **Friend routing** | Presence thô: online / `instance_id` / activity | Không stream transform bạn ở map khác |

**Instance trước, cell liền mạch sau.** Hotspot (event một plaza): AOI vẫn để N body trong **một** sim — vỡ CPU. Xử lý: **room tràn**, cap hiển thị, tương tác hẹp hơn nhìn, bạn bè hiện list dù ngoài cell.

**Thấy ≠ tương tác.** Tách: visual cap (plaza ~24, nhà ~8), interact cap (~8), friend list thô (~50). Không hứa mọi CCU thấy nhau.

**Ngân sách giai đoạn — để đo, không phải kết quả:**

| Giai đoạn | Chứng minh | Trần tạm (đo, không SLA) |
|---|---|---|
| 0 Offline | 1 người, 0 remote | 1 client |
| 1 LAN | 1 server + 4 client, 1 plaza | 4 CCU / room |
| 2 Alpha đóng | Nhiều room, 1 region | **32–64 CCU / plaza instance** (đo p95 tick + bandwidth) |
| 3 | Presence + friend join + shop API | Nhiều instance; catalog **không** trên game tick |
| 4 | Chỉ nếu walk liền Việt Nam bắt buộc | Cell + origin-shift; chưa mở |

App cũ ghi browse catalog “thousands-class plausible” và presence friends-only ~20 @ 1–5 Hz — **ý định app**, chưa build, không phải benchmark game. Bắt đầu gần: gửi ~10–20 Hz gần khi chạy, ~2 Hz đứng; TTL/revoke có số; **chốt sau đo**.

---

## 4. Công thức benchmark (cùng load) + ngưỡng tạm

**Không dùng số web cũ để kết luận Godot/Unity.** Số nội bộ chỉ dạy **không tin headless** và **chưa có root-cause profiler**.

Quan sát `PROGRESS` / handoff (app cũ, **không** chuyển): MapLibre idle median **56.82** (không phải phố Play); Harbor sau LOD idle mean **44** / walk **49.98**; first-W min **9.99** / mean **23.73** (headless 1280×720); chip headed+DevTools ~**16**; CDP ~**5–14**. R2 muốn idle ≥50 và first-W min ≥20 — **UNFILLED**. Handoff liệt kê Html/shadow/DPR/minimap là **thứ tự cắt dự đoán**, chưa profile. Owner mở DevTools làm lệch số.

**Công thức bake-off (Godot vs đối thủ, cùng gói):**

1. Một scene plaza + cùng glTF avatar, shader, bóng, camera follow, chất lượng Low/Med, cùng số remote (0 / 8 / 24), cùng emote/VFX.
2. **Desktop headed** 1280×720 và 1080p, DevTools/profiler overlay **tắt** lúc ghi nhận; settle 5 s; lấy 30 s. Lặp 1 tab.
3. **Android thật** (một máy tầm trung + một máy yếu), không lấy emulator làm nghiệm thu; 10 phút theo dõi nhiệt/pin.
4. Ghi: p50/p95 frame, 1% low, RAM/GPU, draw call/triangle, hitch first-walk/first-emote (compile shader), nhiệt.
5. Godot `--headless` / Chrome headless: **logic/mạng thôi**. Không nghiệm thu FPS. Pointer-lock/GPU/rAF headless đã lệch app cũ.

**Ngưỡng tạm (hành động được, chưa chứng minh):**

- Desktop Med, 24 avatar: p50 ≥ **60**, p95 ≤ **22 ms**, 1% low ≥ **45**.
- Android tầm trung Low, 24 avatar: p50 ≥ **30**, 1% low ≥ **20**; 10 phút không kẹt <20 vì nhiệt.
- Android yếu: Low + nửa độ phân giải, p50 ≥ **30**, hoặc **fail** quality gate (không tự hạ silent).
- Mạng LAN 4 client: không extrapolate WAN.

Đạt Godot → lock pin. Trượt → Unity bake-off cùng recipe, rồi mới đảo mục 1.

---

## 5. Sổ nguồn + claim rủi ro

Truy cập sống **thất bại** 2026-09-05. URL vẫn là nguồn phải mở trước khi lock:

| # | URL | Trang (dự kiến) | Claim sẽ lấy | Currentness |
|---|---|---|---|---|
| 1 | https://godotengine.org/download/ | Download | Bản **stable hiện tại** (tách khỏi pin VF 4.7.1) | **UNAVAILABLE** |
| 2 | https://docs.godotengine.org/en/stable/about/releases.html | Release management | Pin/support; không dùng “latest” trong source | **UNAVAILABLE** |
| 3 | https://docs.godotengine.org/en/stable/tutorials/scripting/gdextension/what_is_gdextension.html | What is GDExtension | Mở rộng native **không** fork | **UNAVAILABLE** |
| 4 | https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html | High-level multiplayer | RPC/replication; **không** ghi shard/MMO | **UNAVAILABLE** |
| 5 | https://docs.godotengine.org/en/stable/tutorials/plugins/editor/making_plugins.html | Making plugins | EditorPlugin + UndoRedo cho agent | **UNAVAILABLE** |
| 6 | https://docs.unity3d.com/Manual/com.unity.netcode.gameobjects.html | Netcode for GameObjects | Unity official netcode; không phải MMO | **UNAVAILABLE** |
| 7 | https://doc.photonengine.com/fusion/current/getting-started/fusion-intro | Fusion Intro | Room/session commercial; cap phụ thuộc mode | **UNAVAILABLE** |
| 8 | https://dev.epicgames.com/docs/epic-online-services | Epic Online Services | Lobby/session/dedicated; không = AOI world | **UNAVAILABLE** |
| 9 | Store/help HAEGIN Play Together (domain chính thức tại thời điểm lock) | Player guide | Chỉ beat người chơi; không backend | **UNAVAILABLE** |
| 10 | https://docs.godotengine.org/en/stable/tutorials/performance/index.html | Performance | Profiler/monitor; headless ≠ acceptance | **UNAVAILABLE** |

**Ấn bản chưa biết:** Godot stable **sống** 2026-09-05; danh sách feature Play Together 2026; số CCU/room Photon/Godot trên **đúng** scene này; FPS Godot/Unity trên máy owner.

**Claim rủi ro (plan/handoff cũ — đừng nhập silent vào hh-3d-2):**

1. **Web-first / Unreal-native** đúng cho **app bản đồ**, sai nếu biến thành veto/default của **game**.
2. **Cấm Godot** trong plan 31-8 là biên **app cũ + folder VF**, không áp plan mới đã được hỏi.
3. **“Thousands browse”** ≠ capacity hiện diện.
4. **VISIBLE_FRIEND_CAP=20** là ý M2, **chưa** live.
5. **Giả thuyết FPS** (Html/shadow/DPR) chưa thay profiler.
6. **Friends-only mãi** nếu copy sang game mới sẽ giết plaza — phải **file hợp đồng mới**.
7. **Godot HLAPI / pin 4.7.1** không chứng minh scale hay đúng bản official hôm nay.

**Việc coordinator nên viết tiếp (chưa code):** decision record engine+pin (sau khi mở được godotengine.org); `social-visibility-contract` (người lạ/instance vs friends-only cũ); recipe bake-off; cấm đụng file authority app cũ.

MODEL_REQUESTED=cursor-grok-4.6-xhigh-fast  
TOOLS_USED=Read, Grep, Glob, GetDynamicTools, WebSearch(rejected), WebFetch(rejected)  
WEB_VERIFIED=no  
IMPLEMENTATION_PERFORMED=no

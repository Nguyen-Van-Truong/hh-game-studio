# Superagent — hướng nâng chất lượng hình và tiếng, 13-10-2026

Tài liệu thiết kế hỗ trợ hai plan, **không phải nguồn tick hay plan thứ tư**. Owner đang tạm hoãn phát triển bản chính; Grokdo là nơi thực hiện màn mẫu trước. Đây là kết quả đọc hai ảnh owner gửi, đọc code trình bày hiện có và nghiên cứu nguồn công khai. Chưa chạy game, chưa nghe audio, chưa có ảnh sau cải thiện trong đợt này.

## Quyết định

Giữ Godot stock/Compatibility và gameplay hiện có. Làm **một Relay Yard hoàn chỉnh về hình, chuyển động và tiếng** trước khi nhân bộ art sang sáu map. Hướng hình: pixel art công nghiệp nguyên bản, nhân vật nhỏ nhưng có dáng rõ, nền có kiến trúc và chiều sâu, tương tác dễ nhận biết. Không đổi engine, không dựng lại lõi và không lấy số particle làm thước đo đẹp.

Yêu cầu nhân vật bổ sung 13-10: tạo hình **pixel art anime nguyên bản** theo cảm giác trong ảnh owner, dùng source có layer và atlas với pose/anchor contract chung. [Brief pipeline nhân vật](13-10-superagent-character-pipeline.md) chốt phương pháp, dữ liệu và hai nhân vật thử trước khi nhân roster. Phần này cụ thể hóa nhân vật trong màn mẫu; không mở chiêu hero hoặc đổi thể loại/gameplay Classic.

Khả năng đạt mức chăm chút tương đương reference là mục tiêu khả thi với công cụ hiện có, không phải kết luận game đã đạt. Điểm còn thiếu chủ yếu nằm ở cách tạo và phối hợp asset, bố cục, animation, UI và kiểm tra bản đang chạy. Hướng dẫn công cụ tại [12-10](../12-10-huong-dan-dung-cong-cu-godot-blender.txt), mục 13–14, cũng yêu cầu Play/quan sát sau khi dựng scene.

## Chẩn đoán có căn cứ

| Quan sát | Việc phải sửa | Giới hạn kết luận |
|---|---|---|
| Ảnh Grok có nhiều khoảng tối trống, sàn mỏng và vật thể đơn giản | Dựng khối kiến trúc, bộ vật liệu và lớp nền cho Relay Yard | Không kết luận mọi map đều giống ảnh này |
| Nhân vật gần dạng khối, trang bị khó nhận ra | Vẽ silhouette, pose và vũ khí riêng; giữ pivot chân | Không suy chất lượng animation từ ảnh tĩnh |
| Nhiều item là ô tím tương tự nhau | Icon theo item/weapon ID, dùng chung trên sàn và HUD | Không thay catalog hay luật nhặt |
| HUD P2 bị cắt, quá nhiều chữ thường trực | Control root đầy khung, container/margin, thanh và icon gọn | Cần kiểm bản chạy ở nhiều kích thước để xác định hết nguyên nhân |
| Presenter dùng chiều cao pose để co cả frame vốn đã vẽ pose thấp | Kiểm double-compression khi cúi/lăn/lặn/ngã; scale ổn định theo art, bounds theo pose | Đây là rủi ro thấy từ code, cần ảnh từng pose để xác nhận mức độ |
| Có sprite sheet, nhạc/SFX, tile và các test kỹ thuật | Nâng asset và tận dụng hook có sẵn | Sự tồn tại của file/test không chứng minh hình đẹp hay tiếng tốt |

Ảnh reference được dùng để so độ rõ và mức hoàn thiện. Không chép layout, sprite, bảng màu đặc trưng, HUD hay audio của reference. Ảnh nằm ở attachment owner, không đưa vào asset phát hành. Chênh kích thước/crop của hai ảnh không cho phép suy tỉ lệ hay số đo gameplay.

## Chuẩn hình cho màn mẫu

**Pixel scale và camera.** Chọn art-space 640×360 làm điểm thử ban đầu; đây là đề xuất thiết kế, không phải độ phân giải đã đo của Y8. Trước khi đổi cấu hình, ghi rõ một art pixel bằng bao nhiêu world units, cách scale sprite/tile, viewport thật và near/far camera. Giữ nguyên đơn vị mô phỏng, tốc độ, collider, tầm đánh và vùng camera cần thấy hai người. Không chỉ đổi 1280×720 thành 640×360 rồi sửa physics để bù. Thử phần render riêng; nếu gây hỏng bố cục thì giữ cấu hình hiện tại và sửa mapping trình bày. Nearest filtering và integer output scaling giúp pixel đều, nhưng zoom phân số vẫn cần xem clip để phát hiện rung/crawl. Snap chỉ ở bản vẽ/camera, không lượng tử hóa body mô phỏng. [Godot: multiple resolutions](https://docs.godotengine.org/en/stable/tutorials/rendering/multiple_resolutions.html)

**Màu và vật liệu.** Điểm khởi đầu: khoảng 24–32 màu chủ đạo, thép xanh xám, bê tông lạnh, gỗ nâu ấm, tín hiệu hổ phách; không bắt buộc đúng số màu. Nền ít tương phản hơn nhân vật, vật nhặt và cạnh đứng được. Mỗi vật liệu có cách tạo mảng sáng/tối nhất quán; tránh rải noise lên mọi mặt phẳng. Dáng lớn phải còn đọc được khi thu nhỏ. Đây là art direction của dự án, dựa trên nguyên tắc giới hạn màu, hình khối và độ rõ trong bài của [Derek Yu — Basics](https://www.derekyu.com/makegames/pixelart.html) và [Common Mistakes](https://www.derekyu.com/makegames/pixelart2.html).

**Nhân vật.** Giữ yêu cầu cao hơn bản tham chiếu một chút (+15% là seed hiện tại, chưa là số đo reference). Một nhân vật hoàn thiện trước, P1/P2 phân biệt bằng màu trang phục và dấu hiệu, không phủ tint lên toàn da/vũ khí. Vai, tay, mặt và chân cần thành dáng người ở kích thước chơi. Khởi đầu với idle, run, jump/fall, crouch, climb, punch/kick, aim/fire, throw, roll/dive, hit/downed. Số frame theo khả năng đọc chuyển động: thử run 6–8 frame và attack 3–5 frame, không biến thành quota nghiệm thu. Gắn tay/vũ khí theo facing, góc ngắm và pose; muzzle/cue khớp điểm bắn hiện có. Frame có pivot chân nhất quán; không nén cả canvas lần nữa để tạo pose thấp. Animation đọc state/event; không kéo dài startup/recovery gameplay để khớp hình. Có thể giữ presenter hiện tại hoặc dùng SpriteFrames/AnimationPlayer ở phần cần thiết, không refactor chỉ để đổi loại node. [Godot: sprite animation](https://docs.godotengine.org/en/stable/tutorials/2d/2d_sprite_animation.html)

**Relay Yard.** Giữ collision/topology; thêm kiến trúc nguyên bản quanh đường đi: trụ đỡ, dầm, sàn có độ dày nhìn thấy, hốc tường, máy relay, cáp/ống, đèn và vài dấu hao mòn có chủ ý. Ba lớp đủ dùng: xa ít chi tiết, kiến trúc nền, foreground tương tác. Không lấp mọi khoảng trống hoặc tạo nền giống sàn đứng được. Vật gỗ/kim loại/kính phải khác silhouette và trạng thái hư hại; phần vẽ gợi va chạm phải khớp body. Giữ lối thang, miệng hố và vật nguy hiểm rõ ở Low lẫn High. Dùng atlas/tile kit chung; TileMapLayer hỗ trợ chia lớp nhưng không cần thay collider đang đúng. [Godot: TileMaps](https://docs.godotengine.org/en/stable/tutorials/2d/using_tilemaps.html)

**HUD/menu.** CanvasLayer chứa một Control full-rect; dùng margin/container quản lý hai cụm P1/P2. Mỗi cụm: nhận diện người chơi, HP/stamina, bốn slot melee/gun/grenade/power với icon/count. Không biến bốn slot thành bốn chiêu hero. Round/mode/score gọn ở giữa; hướng dẫn đầy đủ đặt trong Help/Pause, không phủ cảnh chơi thường trực. Item trên sàn chia sẻ icon identity với HUD. Kiểm chuỗi dài nhất và tên đội ở 960×540, 1280×720, 1366×768; không cắt chữ, đè nhau hoặc tràn mép. Root/containers cũng quản lý pause/result/menu và touch safe area, không chữa từng label bằng offset mới. [Godot: Containers](https://docs.godotengine.org/en/stable/tutorials/ui/gui_containers.html)

## VFX, ánh sáng và âm thanh

- Ưu tiên muzzle flash, hit cue, spark kim loại, splinter gỗ, mảnh kính, explosion/smoke, burning và landing dust. Mỗi nhóm có hình, hướng và thời gian đọc rõ; hiệu ứng phải bám đúng điểm tác động. Chọn flipbook/sprite burst cho phần chủ đạo, CPU particle hoặc pool đơn giản cho phần phụ. Không thay toàn bộ bằng circle/line noise hay bloom.
- Đèn nền và bóng tiếp xúc nhẹ chỉ hỗ trợ khối; có thể dùng texture đã vẽ sáng tối trước. PointLight2D dùng chọn lọc nếu tạo khác biệt rõ. Low bỏ trang trí tốn chi phí nhưng vẫn báo cháy, nguy hiểm, trúng đòn và pickup. [Godot: 2D lighting](https://docs.godotengine.org/en/stable/tutorials/2d/2d_lights_and_shadows.html)
- FX/SFX tiêu thụ event sau tick, dedup và giới hạn lifetime/voice; không sửa RNG gameplay, pause clock, damage hoặc replay hash. Shake là offset có biên độ thấp, giảm/tắt được; hit flash/recoil là trình bày. Không tự thêm hit-stop toàn mô phỏng hay timeScale mới. Bullet time vẫn là cơ chế Classic riêng.
- Compatibility có particle, nhưng `GPUParticles2D.emit_particle()` không được hỗ trợ trên renderer này theo tài liệu hiện hành. Chọn đường CPU/flipbook đã chạy được, không suy mọi tính năng GPU đều dùng được trên Web. [Godot: GPUParticles2D](https://docs.godotengine.org/en/stable/classes/class_gpuparticles2d.html)
- Giữ audio hooks có sẵn; chọn tiếng theo vật liệu/vũ khí, thêm 2–3 biến thể cho sự kiện lặp nhiều, khoảng cách/pan vừa phải, ưu tiên cue nguy hiểm. Tách Music/SFX/UI/Ambience với mức âm rõ; kiểm pause, mute và hai người bắn cùng lúc. Có thể thử **Kenney Impact Sounds**, gói công bố CC0, cho va đập/foley rồi chọn và mix; đây chưa phải bộ tiếng súng đầy đủ và chưa được nghe thử trong đợt này. [Kenney: Impact Sounds](https://kenney.nl/assets/impact-sounds)
- Mix cần headroom và nghe thực tế, tránh clipping. Web Sample playback không hỗ trợ bus effects; Stream hỗ trợ nhưng có đánh đổi latency. Vì vậy asset phải nghe ổn khi không có DSP; không bắt buộc compressor/reverb mới nghe được. Xác nhận trên Godot pin của project, không tự nâng engine theo bản docs mới. [Godot: Audio buses](https://docs.godotengine.org/en/stable/tutorials/audio/audio_buses.html), [Web export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html)

## Dùng công cụ và thư viện để làm nhanh

| Lựa chọn | Quyết định cho Classic |
|---|---|
| Godot SpriteFrames/AnimationPlayer, tile atlas, Control, audio, CPU particles | Dùng sẵn; chưa cần addon runtime mới |
| Sprite/atlas hiện có và generator | Giữ pose/state ID qua adapter; source có layer → atlas/metadata. Generator chuyển sang pack/validate, không đè lại art bằng placeholder |
| Pixelorama / Aseprite | Pixelorama là đường ngân sách 0; Aseprite nếu đã có. Giữ nguồn editable và sidecar anchor; không buộc addon runtime mới |
| Blender | Tùy chọn cho prop khó hoặc pose blockout nếu nhanh hơn; render góc/ánh sáng cố định rồi sửa pixel. Không bắt buộc chuyển toàn bộ nhân vật sang low-poly |
| Gói art/SFX ngoài | Chọn từng asset hợp style; nguồn, license và tác giả trong sổ. Theo guide hiện hành: asset mới CC0 hoặc self-made, không gom nhiều pack lệch phong cách |
| AI concept | Chỉ tham khảo phong cách/ý tưởng nếu hữu ích; không coi ảnh concept là sprite sheet dùng được hay là ảnh game chạy |
| Đổi Unity/Unreal, dựng shader framework, hệ tùy biến hero | Không cần cho màn mẫu này; SA-14/online vẫn khóa |

Theo guide 12-10, scene mutation `hh` không tự đánh giá hình. Dùng `hh check`, `hh play`, `hh shot`, `hh vcheck`, `hh perf` đúng việc; đọc help/schema hiện hành, không bịa flags. `hh vcheck` bắt ảnh rỗng/lệch baseline, **không chấm được đẹp**. Không lấy pixel-diff với screenshot Y8 làm thước đo tương đương. Không mở engine thứ hai cùng project hoặc sửa scene bên dưới editor của agent đang làm.

## Thứ tự giao việc và điều kiện hoàn tất màn mẫu

Đây là trình tự triển khai trong SA-10, không thêm checkbox/WP. Grokdo coordinator sửa code; reviewer lần này chỉ sửa plan/tài liệu. Trước bước tiếp theo đọc Git, giữ WIP mới nhất và kết thúc checkpoint đang sửa; không hủy công việc cũ.

| Bước | Đầu ra xem được | Đường sửa Grokdo dự kiến |
|---|---|---|
| 1. HUD + hợp đồng scale | Hai player panel không tràn; ảnh camera gần/xa cùng thông số scale | `game/ui/match_room.tscn`, `fighter_hud.gd`, `match_camera.gd`, `project.godot` nếu thật sự cần |
| 2. Fighter A + item kit | Source có layer, pose sheet pixel anime, nhân vật nhìn rõ, vũ khí đúng tay/góc, item khác nhau | `game/fighter/fighter_view.gd`, `fighter_visual_profile.gd`, `art/`, `tools/make_fighter_sheet.py`, `_draw_pickups()` trong `match_room.gd` |
| 3. Relay Yard | Một cảnh có khối kiến trúc/vật liệu/độ sâu và đường chơi rõ | Presenter trong `game/ui/`, `art/`, `tools/make_world_sheet.py`; giữ map/collider |
| 4. Cảm giác trận | Clip có animation, âm thanh và phản hồi va chạm đồng bộ | Hook FX/audio hiện có; tách module nhỏ khi cần, không dồn mọi thứ vào `match_room.gd` |
| 5. Fighter B + review rồi mở rộng | Nhân vật khác silhouette qua cùng renderer/data, sửa clip rồi mở rộng roster/map/menu/result | Theo brief nhân vật; ghi một receipt gọn trong `docs/evidence/SA-10.md`, không thêm micro-log vào đầu plan |

Kiểm nhanh sau một nhóm thay đổi: import/parse cần thiết và một lượt Play 45–60 giây với input thật ở Relay Yard. Kịch bản gồm hai người di chuyển gần/xa, ngắm trái/phải/lên/xuống, cúi/lăn/lặn, nhặt đồ, bắn/trúng/nổ/cháy, bật/tắt power đã nhặt, pause/resume. Giữ ba still cùng framing: toàn cảnh, nhân vật/item, HUD/resize; kèm clip có tiếng. Quay qua capability được phép; tool không thu audio thì ghi rõ GAP, không lấy waveform hay exit code để giả là đã nghe. 60 fps cần cho đo timing, không ép đủ ma trận timing mới được sửa hình.

Review màn mẫu đạt khi: (1) hình nhận ra người/vũ khí/item ở kích thước chơi; (2) pixel/pivot không biến dạng hay rung rõ khi camera đổi; (3) nền có chủ đề, đường đi và hazard rõ; (4) HUD không clip; (5) hành động và phản hồi đọc được khi hai người giao chiến; (6) tiếng có phân biệt, không lặp gắt/clipping hay trễ thấy rõ; (7) nguồn asset rõ, không làm đổi gameplay. Mục chưa xem/nghe được ghi **chưa kiểm**, không tự PASS. Không bù điểm đẹp cho một lỗi blocker như HUD mất thông tin.

Chỉ chạy kiểm tra liên quan đến phần sửa; art-only không cần lặp full 100 trận bot. Sau khi có thêm tile/đèn/particle, đo ngắn trước/sau ở cùng máy/cảnh bằng `hh perf`; đây là smoke so sánh, Q2 vẫn nghiệm thu ở cảnh nặng theo plan. Test hồi quy gameplay chỉ mở rộng khi sửa simulation/input hoặc có triệu chứng mới.

Agent tự review để tiếp tục sửa/mở rộng phần không phụ thuộc; gửi build/ảnh/clip cho owner ở gate SA-10. Chưa có phản hồi không có nghĩa đã được duyệt. **Màn mẫu đẹp hơn**, **SA-10 được duyệt**, **Classic giống reference** và **đủ phát hành** là bốn kết luận khác nhau.

## Bài học và nguồn tham khảo

Không dùng số assertion, số commit, file PNG/WAV tồn tại hay thêm particle để suy chất lượng. Làm một cảnh hoàn chỉnh trước khi nhân rộng giúp tránh sáu map cùng sai style. Đánh giá static pose và chuyển động riêng; giữ gameplay boundary trong mọi đổi cỡ/vẽ FX. Cải thiện từ checkpoint đang có, không thay engine hoặc làm lại game vì ảnh prototype còn thô.

Các link nguồn đã đọc ngày 13-10-2026 nằm ngay bên cạnh quyết định liên quan. [Trang Superfighters do tác giả đăng trên Newgrounds](https://www.newgrounds.com/portal/view/575163) có ghi cập nhật khả năng nhìn rõ người/vũ khí; dùng làm bối cảnh thiết kế. Nội dung 2011 và Deluxe không thay thế quan sát bản HTML5 Y8 hiện tại, không chép số map/vũ khí của phiên bản cũ vào ledger. Số màu/frame/viewport đề xuất trong tài liệu là lựa chọn thử của dự án, không phải số đo reference hoặc bảo đảm thẩm mỹ từ nguồn.

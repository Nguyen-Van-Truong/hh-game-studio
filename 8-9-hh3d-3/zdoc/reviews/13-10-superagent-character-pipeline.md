# Superagent — nhân vật pixel art anime và cách tái sử dụng

Ngày 13-10-2026. Brief dùng chung cho hai plan Superagent, bổ sung [brief hình/tiếng](13-10-superagent-visual-quality-brief.md). Đây là quyết định thiết kế để triển khai SA-10, chưa phải asset đã tạo, pipeline đã chạy hay nghiệm thu. Bản chính vẫn tạm hoãn; Grokdo triển khai trên checkpoint riêng. Mỗi product giữ source/asset của mình, không phụ thuộc runtime vào repo bên kia.

## Hướng đã chọn

**Vẽ pixel art theo từng frame, giữ source có layer, xuất atlas + metadata theo một quy ước pose/anchor chung.** Giữ Godot và presenter hiện có, thay nội dung hình từng phần. Với ngân sách hiện hành, chọn Pixelorama cho đường miễn phí; dùng Aseprite nếu đã có bản dùng hợp lệ. Không buộc mua công cụ hoặc viết một editor mới trước khi có nhân vật đẹp.

Ảnh owner gửi có dáng anime, tóc/áo thành mảng rõ, tay chân tách được và các pose hành động mạnh. Đây là hướng tạo hình; không lấy ảnh đó làm số đo kích thước, thời gian animation hoặc bằng chứng pipeline của game tham khảo. Thiết kế nhân vật, trang phục, icon và FX nguyên bản theo mục 12 của hai plan. Classic vẫn là arena platform shooter với các hành động chung; ảnh có phân thân/chiêu năng lượng không mở SA-14.

| Phương pháp | Quyết định cho mục tiêu này |
|---|---|
| Frame-authored pixel art, source có layer, atlas khi chạy | Hướng chính: kiểm soát silhouette, nét và pose; cần công vẽ/cleanup nhưng phù hợp vẻ pixel anime trong ảnh |
| Ghép/biến dạng toàn thân bằng skeleton 2D | Tốt cho hoạt hình cutout; chưa chọn làm nền của toàn bộ fighter vì xoay các mảnh nhỏ dễ làm nét pixel và khớp tay chân khó kiểm soát. Chỉ dùng cục bộ nếu mẫu thực tế đẹp hơn |
| Blender rig → render → chỉnh pixel | Tùy chọn làm pose/blockout hoặc prop khó; có thể tiết kiệm dựng chuyển động nhưng vẫn cần chỉnh silhouette, nét và palette. Không bắt cả roster qua Blender |
| Sinh hình bằng nhiều rectangle hoặc chỉ đổi màu một thân | Giữ làm placeholder; không coi đây là dàn nhân vật đã hoàn thiện |

Đây là lựa chọn thiết kế cho game này, không phải khẳng định một kỹ thuật luôn đẹp hơn kỹ thuật khác. Godot hỗ trợ cả [sprite animation](https://docs.godotengine.org/en/stable/tutorials/2d/2d_sprite_animation.html) và [cutout animation](https://docs.godotengine.org/en/stable/tutorials/animation/cutout_animation.html). Trang cutout đang có cảnh báo chưa cập nhật đầy đủ cho 4.7; không suy giới hạn runtime IK toàn engine từ ví dụ editor trên trang đó.

## Art direction có thể kiểm trong game

- Dáng anime có đầu, vai, thân và chân rõ; vai/hông có độ nghiêng, bàn tay và bàn chân diễn tả hướng lực. Học cách tạo pose mạnh từ ảnh, không phóng to nhân vật thành game đấu tay đôi hoặc thu camera làm mất đường đi.
- Mỗi thiết kế có silhouette, tóc/mũ, trang phục và màu nhấn riêng. Mảng sáng/tối lớn, viền nhất quán; chi tiết mặt và nếp áo chỉ thêm khi còn nhìn được ở camera xa. Tách nhân vật khỏi nền bằng tương phản vừa đủ; trang phục vẫn hợp bối cảnh công nghiệp nguyên bản.
- Vẽ key pose có chủ đích: chuẩn bị, ra đòn, thu đòn; chạy có nhịp tiếp đất và co chân; nhảy khác rơi; lăn/lặn/ngã khác nhau. Frame trung gian phục vụ độ rõ, không tăng frame chỉ để tăng số lượng. Thử run 6–8 frame và đòn ngắn 3–5 frame, rồi chọn bằng clip ở tốc độ chơi thật.
- FX dùng sprite/flipbook riêng cho muzzle flash, tia va đập, vệt vung và bụi. Giữ silhouette của người, điểm trúng và hazard còn thấy khi hai người đánh nhau. Không mặc định vẽ aura hoặc chiêu hero cho nhân vật thường.

Chốt pixel scale bằng một mẫu trong Relay Yard trước khi vẽ đủ bộ. Code Grokdo đã đọc dùng ô 32×48; đây là dữ liệu legacy, không phải chuẩn đẹp. Điểm thử mới: canvas logic 64×64 để có chỗ cho tay/chân vươn, thân đứng khoảng 40–48 art pixel; các số này chỉ là seed. Dùng **chiều cao thân đứng** để tính art-to-world, không dùng toàn chiều cao ô có padding. Nếu mẫu không đủ rõ ở camera thật, sửa mapping/source density rồi chốt một lần, không vẽ cả roster trước. Giữ seed hiển thị +15% đã có, không cộng thêm +15% lần nữa; không đổi collider, reach hoặc viewport chỉ để làm sprite lớn.

Một character giữ cùng canvas/pivot quy ước trong mọi frame. Pose thấp đã vẽ trong canvas thì không co cả canvas thêm lần nữa. Kích thước canvas khác giữa các họ dáng được phép qua metadata, nhưng cùng quy ước tọa độ và pixel density. Nearest filtering, scale/pivot ổn định; sửa lỗi pixel ở render, không snap physics.

## Gói nhân vật và hợp đồng dùng chung

Chỉ thêm phần tối thiểu quanh `FighterVisualProfile`/`FighterView` hiện có. Tách lựa chọn **pose gameplay** khỏi dữ liệu **frame của từng nhân vật**; không tạo controller hoặc nhánh `if character_id` riêng cho từng người. ID pose hiện có được giữ qua adapter khi thay sheet. Dữ liệu dùng chung là read-only; pose/frame/facing của P1, P2 và bot là trạng thái riêng của từng instance. [Godot Resources](https://docs.godotengine.org/en/stable/tutorials/scripting/resources.html) hỗ trợ dữ liệu lưu `.tres` và dùng chung giữa nhiều instance.

| Nhóm metadata tối thiểu | Nội dung và ý nghĩa |
|---|---|
| Identity | `schema_version`, `character_id`, `body_family`, source path/hash, tool/version, author/license |
| Scale | `canvas_size`, `standing_art_height`, `art_to_world`, pivot gốc chân; tọa độ art gốc trên-trái, y hướng xuống, mặc định vẽ quay phải |
| Frames | ID frame ổn định, atlas path + region; nếu trim thì thêm `source_size`/`trim_offset` để khôi phục canvas, không lấy kích thước rect đã trim làm kích thước nhân vật |
| Clips | Semantic clip ID, danh sách frame, thời lượng trình bày/loop, quy tắc lấy phase từ state/event; số frame có thể khác giữa character |
| Anchors | `foot/root`, `head`, `hand_main`, `hand_off`, điểm FX trên thân; track theo frame khi di chuyển. Vũ khí có grip/muzzle riêng trong định nghĩa vũ khí |
| Layers | Thứ tự trước/sau thân, visibility/occlusion của tay và vũ khí theo pose; mask màu đội hoặc palette slot, không tint toàn da/vũ khí |

Đây là schema dự án cần triển khai, không phải trường được Godot hoặc mọi editor tự xuất sẵn. Metadata hình không chứa HP, damage, stamina, mana, passive, skill hay collider. Trong pilot, chọn **một metadata canonical** (JSON + sidecar anchor là mặc định); nếu presenter cần `CharacterVisualDefinition` typed Resource thì sinh `.tres` một chiều từ canonical và không sửa hai bản song song. Validator/adapter là nơi kiểm schema, anchor và source hash. Giữ format trung gian đơn giản, đọc được, có version; chưa cần plugin import tổng quát.

Các clip semantic cần bao phủ hành động Classic hiện có: `idle`, `run/sprint`, `jump`, `fall`, `land`, `crouch`, `climb`, `punch`, `jump_kick`, `aim/fire`, `throw`, `power_pickup_use`, `roll`, `dive`, `hit`, `downed/get_up`. Đây là các cách vẽ, không tạo thêm mechanic. `power_pickup_use` là dùng đồ nhặt Classic. Các hành động đang dùng chung `attack` được tách hình nhờ action/attack/state đã có; fallback tạm phải ghi rõ, không tính là pose hoàn thiện.

Simulation vẫn sở hữu startup, active/recovery, damage, projectile origin, góc ngắm, pause và bullet time. Presenter lấy phase từ tick/state đã commit; animation callback không gây damage hoặc quyết định hết hitstun. Idle/run có thể loop theo vận tốc/clock phù hợp; pause và tốc độ cục bộ trong bullet time phải đúng. Chuyển skin không thay snapshot hoặc kết quả replay cùng trace/seed.

Tay/vũ khí là phần runtime tách nhỏ khi cần ngắm: body bake sẵn, overlay tay/vũ khí theo pose và góc. Grip phụ giữ súng hai tay; frame có mask/visibility tránh hai bàn tay chồng lên tay đã bake. Đổi facing phải đổi cả anchor và thứ tự lớp; đồ bất đối xứng cần frame hướng kia hoặc exception trong dữ liệu. Muzzle và flash khớp đường bắn thật; không dời nguồn đạn simulation theo một sprite. Nếu lượng tử hóa góc vẽ để giữ nét thì chỉ áp dụng hình, không đổi góc ngắm gameplay.

## Authoring và export để thêm nhiều nhân vật

Luồng sản xuất: **thiết kế → source có layer → pose sheet → atlas PNG + metadata → presenter chung → xem trong trận**. Phân lớp ở file gốc giúp sửa và phối trang phục; Classic xuất các bộ cố định. Không xây hệ đổi quần áo trong game ở lượt này.

1. Mỗi source giữ layer body/face/hair/outfit/accessory và guide anchor riêng. Dùng chung palette, pose reference và các cel thật sự giống nhau; tách cel khi pose cần khác. Aseprite có [linked cels](https://www.aseprite.org/docs/linked-cels/) để một sửa đổi áp dụng cho các cel được liên kết. Đây không phải tự retarget quần áo sang mọi tư thế.
2. **Pixelorama mặc định ở ngân sách 0:** giữ `.pxo`, xuất PNG/spritesheet và JSON; CLI desktop hỗ trợ headless, JSON và split layers. Anchor lưu trong sidecar của dự án. Tài liệu hiện ghi chưa nhập được slices của Aseprite, nên kiểm round-trip trước khi đổi editor. Ghi tool/version/options/hash thật vào metadata; nếu Pixelorama không có sẵn thì dùng Aseprite đã được owner cấp phép hoặc editor pixel hiện có, không tự tải/cài công cụ mới và không ghi là pipeline đã chạy. [CLI](https://pixelorama.org/user_manual/cli/), [Save and Export](https://pixelorama.org/user_manual/save_and_export/), [Import](https://pixelorama.org/user_manual/Import/), [repo chính thức/MIT](https://github.com/Orama-Interactive/Pixelorama).
3. **Aseprite nếu đã có:** giữ `.aseprite`, dùng tag phân clip, slice/pivot hoặc sidecar cho anchor, batch export atlas PNG + JSON. [Tags](https://www.aseprite.org/docs/tags/), [Slices](https://aseprite.org/docs/slices/), [CLI](https://www.aseprite.org/docs/cli/). Chốt version/options sau một mẫu export thật; không giả CLI của hai công cụ tương đương.
4. Adapter nhỏ chuẩn hóa output về một schema và validate ID/tag/frame/duration/anchor/path. Validator phải fail-closed khi thiếu frame, tag, `trim_offset`, anchor, facing hoặc source/license; ghi source hash, tool/version và export options. Tận dụng script pack hiện có, chuyển nó sang đóng gói source đã vẽ; không tiếp tục overwrite hình đã sửa bằng generator placeholder. Xuất vào thư mục tạm, kiểm xong mới thay package đang tốt; nếu lỗi sửa/re-export character đó, không tạo lại cả roster.
5. Dùng presenter đọc region hiện có, hoặc `AtlasTexture` + `SpriteFrames` khi có lợi. `AnimationPlayer` chỉ thêm cho layer/property track cần đồng bộ, không bắt đổi toàn scene. Grid không trim là đường đầu tiên; chỉ pack/trim khi có lợi đã đo, giữ offset/padding để không rung hoặc bleed. [AtlasTexture](https://docs.godotengine.org/en/stable/classes/class_atlastexture.html), [SpriteFrames](https://docs.godotengine.org/en/stable/classes/class_spriteframes.html).

Đường đặt file gợi ý, nằm trong từng product: `art/source/characters/<id>/` chứa file editable + metadata nguồn; `art/characters/<id>/` chứa PNG/JSON xuất; resource sinh tương ứng và definition ở phần visual/data hiện có. Dùng tên `character_id` bền vững, không buộc rename source cũ trước pilot. Nguồn editable được version control nhưng loại khỏi gói phát hành; runtime chỉ tải nhân vật được chọn, không preload cả roster tương lai. Ghi provenance vào LICENSES.tsv; license phần mềm authoring không tự trở thành license asset. Mỗi repo giữ bản asset/source độc lập, không runtime-link qua thư mục plan chung.

Thêm nhân vật sau pilot: chọn họ dáng → duplicate **template source** → vẽ silhouette/trang phục riêng → sửa pose và anchor đặc thù → export/validate → đăng ký data → review trận ngắn. Reuse nhiều nhất ở canvas contract, pose names, layout layer, palette rules, exporter và runtime. Reuse cel/animation trực tiếp chỉ tốt với dáng tương đồng; dáng khác cần vẽ lại một phần. Không hứa tạo hàng loạt nhân vật đẹp chỉ bằng đổi tóc/màu.

## Hai nhân vật pilot và review nhanh

Hoàn thiện nhân vật A trước, rồi áp template cho nhân vật B trong các slot roster hiện có. A có silhouette gọn với áo ngắn; B có vai/trang phục rộng hơn và đường viền khác. Đây chỉ là hình: cùng HP, movement, collider và bốn hành động Classic. P1/P2 vẫn phân biệt được khi chọn cùng nhân vật bằng dấu hiệu/mask màu đội. Không thêm menu/editor hay stats khác nhau để chứng minh reuse.

Đầu ra: hai nguồn editable, hai package atlas/metadata, contact sheet pose ở 1× và kích thước chơi, và một clip Relay Yard 45–60 giây. Kiểm nhanh file/schema/import phần đã thay đổi bằng validator package; kiểm riêng rect/`trim_offset`, foot/grip/muzzle/head/FX anchors và facing trái/phải trước khi nạp Godot. Một lượt input thật gồm hai người chạy/nhảy, ngắm hai hướng, cúi/lăn/lặn/leo, đấm/ném/trúng/ngã và pause. Preview pose chỉ bổ sung, không thay clip trong trận. Kiểm mẫu xuất tái lập một lần và một trace gameplay ngắn khi thay renderer để phát hiện thay đổi state; không full suite chỉ vì sửa palette.

Review cần trả lời: silhouette A/B có khác và rõ ở camera xa; chân/anchor có rung hay tay/vũ khí tách khỏi thân; pose có bị nén/cắt; animation có theo đúng pause/bullet time/action; FX có che người; P1/P2 có đọc được ở cùng skin. Character B phải đi qua cùng renderer/loader bằng data, không thêm nhánh ID riêng. Chưa nhìn thấy/đo được thì ghi GAP. Hai pilot đạt tự review mới nhân rộng roster; owner vẫn duyệt SA-10 theo plan, không thêm WP hay tick bằng brief này.

## Bài học áp dụng ngay

Giữ pipeline nhỏ quanh presenter đã có, đầu tư vào nét/pose thay vì framework trước. Phân lớp source không đồng nghĩa ghép hàng chục sprite runtime. Một sheet static không chứng minh animation; thêm nhiều frame không tự làm chuyển động tốt. Pivot theo canvas và scale thân đứng tránh lỗi co pose hai lần. Vũ khí có hình/grip/muzzle riêng thay cho line. Không sửa combat timing để hợp animation đã vẽ. Nguyên tắc tái sử dụng được chốt sau hai nhân vật thật, rồi mới mở rộng nội dung.

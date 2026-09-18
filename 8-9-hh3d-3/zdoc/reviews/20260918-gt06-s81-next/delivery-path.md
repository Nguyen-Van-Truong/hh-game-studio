# Đường bàn giao từ công cụ đến game

2026-09-18, Asia/Saigon. `AUTHORITY=0`. Ghi chú delivery theo lease riêng;
không là plan thứ ba, critic verdict, nghiệm thu hay quyền mở WP.
Đọc tools plan S81, game plan S21 và research 20260918 đã có. HEAD khi đọc:
`30920627f226c44f770226f53c52e728dc9364a7`; benchmark được plan ghi là
`gt06-s81-campaign-01`, source checkpoint `b3862a10`. Không theo dõi lại
campaign, đổi source/profile, chạy engine/test hoặc kiểm hash toàn bộ.

**Kết luận:** Godot + Blender vẫn là tuyến đã chọn; nút thắt từ công cụ đến
game là năng lực authoring công khai và bằng chứng trên workload sản phẩm.
GT-10 bàn giao gói công cụ có giới hạn rõ, không chứng minh agent đã làm
trọn game. Scope hiện tại trong cùng repo: hoàn tất GT-06→10, rồi nhận gói
vào HH World theo H2. Không mở Vault Fighters, một game 2D mới hoặc plan mới.

## Gap → tiêu chí nghiệm thu của consumer

| Khoảng trống / gate tools | Consumer phải chứng minh ở đâu | Điều không được suy từ fixture |
| --- | --- | --- |
| Catalog scene box/declarative script chưa author được controller, UI, physics, audio đa scene; pipeline rig/clip chưa là API authoring rig | H2-P0-01 khóa operations/profile/version/limits; P1-01 kiểm trên project game. Nhu cầu chưa được cấp trả GAP/minimal repro tới GT owner; mở rộng bằng release có version theo tools §6 | Tên `script_text.replace` hoặc trusted fixture producer không chứng minh agent viết gameplay/asset tổng quát |
| GT-06 play/input/observe/repair; GT-09 conformance của client đã pin | H2-P2-01→04 và Q03-A: player-route launch→preset→di chuyển/camera→câu cá→item→nhà/quầy→save/relaunch; dùng source/art của game, package và input thật | Seeded repair một biến không chứng minh sửa controller, hoàn thành game hoặc sản phẩm vui |
| GT-07 lease/publish/crash recovery bảo vệ việc authoring | H2-P3/P4, Q04-L và Q05 kiểm authority, persistence, reconnect, duplicate request, quyền nhà/shop bằng server + client thật | Recovery của editor không chứng minh durable economy hoặc multiplayer |
| GT-08 build/export và một Android thật; GT-10 install/upgrade/rollback | H2-P1-03 rồi P5-03/Q01 đo workload đại diện và final game trên thiết bị thật; P8-03/P9-01 kiểm release theo scope/quyền hiện hành | Export fixture được không chứng minh FPS/thermal của game; target Windows/Android/Linux-headless không bao hàm Web |
| GT-09/10 khóa client/model/host, route công cụ và package | H2-P0-01 intake, P1-01 integration, P2-04 asset→game loop. Trace chỉ rõ thao tác agent và hành động người; thiếu capability quay về đúng GT owner | Không hidden shell edit, không sửa generated addon, không tự nâng package toàn cục |
| Nội dung, chất lượng và người thật chưa có runtime acceptance | H2-P5 art/UI/device, P6 capacity/WAN/human; P7/P8 mới mở dữ liệu Việt Nam và pilot | Q03-H 5 người, Q04-W2 8 người và Q04-C 32 clients là ba proof khác nhau; tools PASS không thay proof nào |

Nếu sau này owner yêu cầu một arena 2D giống trải nghiệm Superfighters, cần
consumer contract riêng cho menu→move/jump/ladder→pickup/combat/hazard→
win/lose→restart/quit, bot nếu có trong brief, original art/audio và target
export. Web phải có profile/browser evidence riêng. Đây là mô tả giới hạn
claim, không thêm WP hoặc dispatch 2D trong lượt này. Blender có thể phục vụ
art/sprite; không bắt một game 2D phải đi qua GLB/rig nếu art contract không cần.

## Năm quyết định giúp đi nhanh hơn

### So sánh đường nội dung sau khi tools được nghiệm thu

| Mục tiêu | Đường nhanh hợp lệ | Vì sao không dùng đường kia |
| --- | --- | --- |
| Arena 2D tương lai | Godot 2D cho scene, gameplay, UI và input; Blender chỉ tạo sprite/render/art khi contract cần | Không ép asset 2D qua GLB/rig; Blender một mình không cung cấp runtime, input, physics, save hay export contract |
| HH World | `GT-10 → P0-01 → P0-02 → P0-03 → (P1-01 || P1-02) → P1-03 → P2-01→04`; Blender tạo asset nguồn rồi xuất GLB được kiểm, Godot giữ layout/script/runtime | Không đưa gameplay ngược vào Blender; không mở H2 trước package GT-10 và không thay device/human gates bằng fixture |

Hai đường trên là route triển khai sau các gate, không phải bằng chứng rằng bộ
tools hiện tại đã làm trọn game. Giữ một capability map; mỗi gap phải gắn vào
owner GT và acceptance của H2 thay vì thêm checklist/API rời.

1. **Giữ tuyến và một nơi ghi trạng thái.** Chỉ hai bảng GT/H2 là tiến độ.
   Ghi chú mới chỉ nối tới requirement/evidence sẵn có; không thêm checklist
   nghiệm thu song song. Báo người dùng ba mốc rõ: tools dùng được trong phạm
   vi catalog, H2-P2-04 có vòng Solo, H2-P6-03 có closed alpha qua người thật.
   Việt Nam/release tiếp tục theo P7→P9; không gộp các mốc thành “xong game”.
2. **Mở rộng công cụ theo nhu cầu vòng chơi, không theo danh sách API engine.**
   Khi H2 được mở, mỗi gap ghi một hàng: hành vi người chơi → operation/profile
   thiếu → owner GT → acceptance H2 → bằng chứng cần có. Gom các thao tác đủ
   cho một slice thành contract có version; tránh từng wrapper nhỏ thiếu đường
   hoàn thành hành vi. Hướng staged typed gameplay scripts cần boundary và
   validation rõ; không đưa raw eval vào editor. Không sửa catalog S81 đang đo.
3. **Một final seal và một requirement→test→evidence index cho mỗi candidate.**
   Link evidence đúng source/dependency, giữ raw/failure cũ; sửa metadata bằng
   collector trên raw khi đủ dữ liệu. Chỉ remint lane bị ảnh hưởng; source đổi
   thì audit lại phạm vi cần thiết. Hai critic mới vẫn độc lập trên cùng final
   hash. Không chạy lại native chỉ để đổi văn phong hoặc tên báo cáo.
4. **Chuẩn bị điều kiện hard gate trước khi tới gate.** Xác định đường tiếp cận
   Android thật cho GT-08, sau đó thiết bị game và nguồn human playtest cho H2.
   Có thể chuẩn bị availability/checklist/contract theo scope; không chạy
   engine/test nặng cạnh S81, không mở implementation GT-07/H2 sớm. Thiếu máy
   vẫn GAP; thiếu người vẫn UNVERIFIED. Không đổi thành emulator hoặc bot PASS.
5. **Theo dõi thời gian tới hành vi chơi được, bên cạnh độ bền công cụ.** Sau
   handoff, ưu tiên critical path H2 đã có: intake→bootstrap→technical gate→
   Solo loop trước bulk content/map. Ghi thời gian thêm/sửa/xuất/replay một
   hành vi, số vòng sửa và gap capability thực tế. Đây là thông tin điều hành,
   không thêm quota/gate và không thay benchmark GT-06 10×35 hiện hành.

## Phần có thể cắt và phần bắt buộc giữ

**Có thể cắt:** đọc lại toàn bộ lịch sử Sxx để làm việc ở WP hiện hành; copy
status/timeline campaign vào mỗi memo; mở thêm research chung về “engine có
làm game được không”; giữ nhiều bảng capability/consumer gap giống §6;
remint toàn bộ dependency đã exact chỉ vì source ngoài closure hoặc báo cáo đổi.
Research 20260918 chứa quan sát S76 có thời điểm: giữ làm lịch sử, không chép
thành trạng thái S81. Plan front nên trỏ history/evidence và nêu next gate.

**Bắt buộc giữ:** campaign đầy đủ cùng source/profile/threshold, actual exits
và cleanup; evidence closure và hai critic đúng hash; GT-07 conflict/crash/
Stop; GT-08 clean export và Android thật; GT-09 conformance thật; GT-10 trust,
install/upgrade/rollback; H2 player-route, authority/durability, target device,
art/human, capacity/WAN và release gates theo plan. Không ghép partial runs,
chuyển chữ ký source cũ hoặc hạ acceptance sau failure.

## Nguồn và giới hạn

- Nguồn scope/acceptance: [tools plan](../../8-9-godot-blender-agent-studio-plan.txt)
  GT-06–10, §6; [HH World plan](../../8-9-hh-world-gameplay-viet-nam-plan.txt)
  front, P02, Q03–Q05 và H2 specs. Hai file này quyết định dispatch/tiến độ.
- [Research đã có](../20260918-end-to-end-game-claim-research.md) giữ audit catalog
  và đầy đủ primary sources; không lặp lại audit code hoặc coi baseline cũ là S81.
- Primary sources được research trước dùng để phân biệt năng lực engine/pipeline:
  [Godot 2D](https://docs.godotengine.org/en/stable/tutorials/2d/introduction_to_2d.html),
  [Blender glTF exporter](https://github.com/KhronosGroup/glTF-Blender-IO/blob/main/docs/blender_docs/scene_gltf2.rst),
  [Godot Web export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html),
  [Godot multiplayer](https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html).
  Không kiểm lại API trên binary pin trong audit delivery này. Đề xuất throughput
  là suy luận từ contract/evidence đã có, không phải kết quả benchmark mới.

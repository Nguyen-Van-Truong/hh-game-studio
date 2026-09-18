# Điều kiện để claim agent làm trọn game

Ngày: 2026-09-18, Asia/Saigon. `AUTHORITY=0`. Research/capability audit,
không phải plan thứ ba, kết quả runtime, critic verdict hay quyền mở game WP.
Baseline code: `e297283f`; benchmark runtime checkpoint `04b2f4dc` không đổi.
Ba worker read-only: `end_to_end_claim_audit`, `game_2d_research`,
`game_3d_research` (Codex Astra xhigh). Coordinator tổng hợp và kiểm catalog.
Không chạy thêm engine/test/hash audit toàn bộ cạnh benchmark.

## Kết luận và trạng thái quan sát

GT-01–05 đã ACCEPTED trong phạm vi công cụ/fixture. GT-06 chưa ACCEPTED;
GT-07–10 chưa mở. HH World còn 32 WP PLANNED, không lấy 5/10 tools làm 50%
game. Nguồn tiến độ duy nhất vẫn là hai plan TXT hiện hành.

Quan sát live khoảng 2026-09-18T00:13Z: campaign `gt06-s76-campaign-01`,
launch 2, run-00-attempt-02 có scheduler state 4/một instance; ba batch
capture hoàn chỉnh, host xử lý batch 3, native heartbeat cùng run; stderr
trống, chưa có terminal/failure. Đây là ảnh chụp tiến độ, không full-run PASS
hoặc cam kết campaign hiện vẫn chạy. Dùng trạng thái live ở lượt tiếp theo.

Quan sát tiếp lúc 00:18:36Z (07:18:36 local): scheduler vẫn state 4/một instance,
đủ năm warmup captures 00–04; host đang commands batch 5 (measured đầu tiên),
editor PID 38684 có heartbeat batch 5 cùng run ID; native stderr 0 byte.
Chưa có full run hoàn chỉnh trong quan sát này; không suy năm warmup thành
năm measured batch hoặc kết quả nghiệm thu.

Launch 1 lỗi import vượt 20 giây trước mọi sample đã được giữ raw/cleanup.
Launch 2 import actual exit 0 sau 5.797 giây. Retry này chưa chứng minh căn
nguyên timeout đã sửa. Những lỗi RSS/handle/status-gap trước đó không được
xóa hoặc miễn bằng 800-cycle diagnostic. Vẫn cần full campaign, final closure
và hai critic độc lập. Android thật còn UNVERIFIED cho GT-08.

## Ma trận năng lực hiện có và phần còn thiếu

| Nhu cầu | Bằng chứng/phạm vi hiện có | Thiếu để claim tạo game từ brief |
| --- | --- | --- |
| Tạo/sửa project Godot | Fixed scene/script paths, ≤64 nodes; Node3D, MeshInstance3D, BoxMesh | Authoring đa scene/resource, 2D nodes, UI, collision, InputMap, signals, animation, audio |
| Viết/sửa gameplay | Profile chỉ `extends Node3D` + bốn biến export; không method/expression/resource load | Logic controller, combat, AI, save/load và network có thể được agent tạo, validate, chạy và sửa |
| Tạo art Blender | Box, transform, opaque material, undo/redo; ba fixed publication profiles | Mesh/UV/texture/rig/skin/clip authoring và iteration đủ cho art contract cụ thể |
| Pipeline GLB | GT-05 đã kiểm rig/clip/import/reimport từ trusted fixture producer | Tách rõ producer fixture khỏi API agent tạo/sửa asset theo brief |
| Play/repair | GT-06 functional fixture có real input/replay, seeded repair; đo dài chưa nghiệm thu | Game mới hoàn chỉnh, lỗi thực vượt chỉnh một biến; exported artifact và full loop |
| Browser game | Manifest tools dự kiến Windows/Android/Linux-headless | Web profile, hosting assumptions và browser tests; Windows PASS không bao hàm Web |
| HH World | Plan gameplay/multiplayer/device/human acceptance đã có | Runtime sản phẩm chưa triển khai; room capacity, save/backend, touch, thermal và playtest chưa chứng minh |

Local sources (đường dẫn tương đối với `8-9-hh3d-3/`):
- `studio/godot-addon/operations.json`: `scope`, fixed paths, `node_types`,
  `resource_types`, `managed_script_policy.general_gdscript=false`.
- `studio/godot-addon/SCRIPT_PROFILE.md`: exact grammar và unsupported methods.
- `studio/host/replay/repair.py`: seeded `move_speed` repair không phải viết controller.
- `studio/host/blender/client_write_catalog.py`, `CLIENT_WRITER.md`: edit catalog,
  publication scope, arbitrary blend/texture/library intake và writable restart limits.
- Tools plan GT-09/10 và mục 6: fixture conformance, finite capabilities,
  consumer adoption/change request; game plan P0/P1/P2/P5/P6/P8/P9.

## Sáu cải tiến ưu tiên

1. **Chốt lời claim có thể kiểm.** Ví dụ: “agent nhận brief arena nhỏ, tạo
   source/art, xuất Windows + Web và người chơi hoàn thành một trận”. Tách
   capability của engine, capability của adapter, hành vi game và chất lượng
   người chơi cảm nhận. Một demo không chứng minh làm mọi thể loại. Ma trận
   trên phải đi cùng package, không giấu giới hạn sau nhãn GT đã accepted.

2. **Mở rộng authoring theo một vòng chơi, tránh viết từng wrapper nhỏ vô hạn.**
   Thiết kế profile project/scene/resource có scope rõ và route staged typed
   script: kiểm syntax/dependencies, chạy trong sandbox, kiểm thực thi,
   publish/rollback có version. Typed GDScript không tự tạo sandbox; vẫn cần
   ranh giới process/filesystem/capability. Không mở raw eval trong trusted
   editor. Godot cung cấp UndoRedo/EditorInterface/PackedScene, còn schema,
   checkpoint, ownership và đọc lại sau reopen là trách nhiệm adapter.
   Đây là hướng mở rộng có version sau khi xác định consumer contract,
   không sửa lén catalog/source của campaign đang đo. [R1–R3]

3. **Hai workload đại diện riêng nếu muốn claim cả 2D và 3D.** Với arena 2D:
   menu → di chuyển/nhảy/leo → pickup/combat/hazard → win/lose → restart/quit,
   pause/resume, UI/audio và bot nếu brief yêu cầu. Bot phải thực hiện jump/
   ladder/drop/line-of-sight và thoát kẹt; navigation links không tự cung cấp
   logic đó. Blender là lựa chọn làm art/sprite, không điều kiện bắt buộc.
   Với HH World: dùng chính lộ trình đã có—server + hai client, avatar/touch,
   Solo loop rồi social/persistence/room capacity. Không đổi target 32/room
   của plan thành một con số thấp hơn chỉ để PASS. [R4–R7, R10]

4. **Kiểm sản phẩm được xuất và việc sửa lỗi thực.** Tạo project mới hoặc
   snapshot độc lập; giữ brief, operation trace, source/assets trước–sau và
   declared human actions. Agent phải quan sát failure, sửa đúng nguyên nhân,
   replay và xuất lại bằng route công bố. Có bài input qua engine và một lượt
   keyboard/mouse/touch/focus trên artifact thật; `action_press` không gọi
   `_input`, `parse_input_event` không điều khiển OS. Với Web cần kiểm load,
   Start/audio, focus, resize, persistence và restart trong trình duyệt;
   Compatibility/WebGL2 và thread/hosting constraints theo export profile.
   Nhu cầu Web phải thành capability/version claim riêng; chưa thêm nó vào
   gate GT-08 hiện tại bằng báo cáo này. [R8–R9]

5. **Art pipeline và online có proof riêng.** Asset thật cần scale/orientation,
   skeleton/skinning/clip/material/texture/collision/budget readback trong
   Godot và artifact xuất. Khronos validator giúp kiểm định dạng, không chấm
   art đẹp. Multiplayer cần server kiểm ý định client, quyền sở hữu/phần thưởng,
   duplicate request, reconnect, loss/jitter và concurrent edits. Save proof
   đọc lại qua normal game/login sau crash/restart, không chỉ “file tồn tại”.
   Godot multiplayer/serialization API không tự triển khai backend bền vững.
   Phần lớn các mục này đã nằm ở H2-P2…P6; không tạo thêm plan trùng. [R10–R13]

6. **Tách correctness, vận hành và chất lượng chơi.** Android phải dùng máy
   thật, touch, background/resume, nhiều tình huống cảnh và sustained thermal
   test theo budget H2 đã khóa. Không suy khả năng duy trì FPS từ đoạn cold run.
   Playtest người thật đánh giá dễ hiểu, điều khiển, hình/âm thanh, vui và muốn
   chơi lại; test tự động không thay kết quả ấy. Việc build local không tự cấp
   quyền ký production/publish. [R14–R16]

## Làm nhanh hơn mà giữ kết quả có giá trị

- Đo tốc độ bằng khả năng thêm một vòng chơi có thể dùng, ngoài độ bền pipe.
  Tránh mở rộng cơ chế phòng thủ vô hạn mà không nêu capability thực sự phục vụ.
- Hoàn tất campaign S76 cố định; sửa observation/metadata trên raw nếu engine
  đã hoàn tất, không chạy lại engine chỉ vì báo cáo. Không đổi threshold sau fail.
- Reuse lane có dependency closure không đổi; sửa code thì chỉ remint lane bị
  ảnh hưởng, gom full integration ở milestone. Không chạy tải engine song song
  với benchmark chính. Đủ useful work thì worker nghiên cứu/schema chạy song song.
- Sau một retry được kiểm soát mà cùng failure tái diễn, chẩn đoán trước lần
  kế tiếp; giữ completed runs hợp lệ nếu resume contract cho phép, không ghép
  partial failed sample để tạo PASS.
- Tool package vẫn cần GT-06/07/08/09/10 và hai critic. Năng lực authoring mới
  cần change request/contract/versioned release; chứng minh product theo plan
  game. Đây là khoảng trống thật, không thể đóng bằng đổi câu chữ hoặc thêm quota.

## Nguồn chính thức đã nghiên cứu

Các khuyến nghị acceptance ở trên là suy luận kỹ thuật của nhóm từ tài liệu
và audit code; không phải tiêu chuẩn bắt buộc do nhà cung cấp ban hành.
Trang `/stable/`, Android và nhánh `main` có thể thay đổi. Khi triển khai phải
đối chiếu binary tools pin **Godot 4.7.2** và Blender/exporter lock; không dùng
pin 4.7.1 của Vault Fighters cho scope này. Chưa chạy API research trên pin.

- R1 [Godot EditorUndoRedoManager](https://docs.godotengine.org/en/stable/classes/class_editorundoredomanager.html): undo history theo scene/context.
- R2 [Godot EditorInterface](https://docs.godotengine.org/en/stable/classes/class_editorinterface.html): editor integration/save/play controls.
- R3 [Godot PackedScene](https://docs.godotengine.org/en/stable/classes/class_packedscene.html): ownership khi lưu scene.
- R4 [Godot 2D](https://docs.godotengine.org/en/stable/tutorials/2d/introduction_to_2d.html): renderer, physics và animation 2D.
- R5 [Godot TileMaps](https://docs.godotengine.org/en/stable/tutorials/2d/using_tilemaps.html): tile-based level authoring.
- R6 [Godot 2D navigation](https://docs.godotengine.org/en/stable/tutorials/navigation/navigation_introduction_2d.html): paths/links và trách nhiệm movement.
- R7 [Blender Grease Pencil animation](https://docs.blender.org/manual/en/4.2/grease_pencil/animation/introduction.html): một lựa chọn pipeline art 2D; nguồn phiên bản 4.2, không coi là exporter pin hiện hành.
- R8 [Godot Input](https://docs.godotengine.org/en/stable/classes/class_input.html): phân biệt simulation action/event và OS input.
- R9 [Godot Web export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html): renderer, browser/hosting/audio constraints.
- R10 [Godot high-level multiplayer](https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html): authority/RPC và cảnh báo secure multiplayer design.
- R11 [Godot 3D formats](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html), [Blender glTF exporter documentation](https://github.com/KhronosGroup/glTF-Blender-IO/blob/main/docs/blender_docs/scene_gltf2.rst): interchange/import behavior.
- R12 [Khronos glTF Validator](https://github.com/KhronosGroup/glTF-Validator): validation cấu trúc và dữ liệu glTF.
- R13 [Godot saving games](https://docs.godotengine.org/en/stable/tutorials/io/saving_games.html): serialization/loading, không backend multiplayer hoàn chỉnh.
- R14 [Android Thermal API](https://developer.android.com/games/optimize/adpf/thermal): thermal state và throttling.
- R15 [Android game launch testing](https://developer.android.com/games/distribute/guide-launch-game): thiết bị, input/audio, stress và beta feedback.
- R16 [Godot Android export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_android.html): SDK/export/signing requirements.

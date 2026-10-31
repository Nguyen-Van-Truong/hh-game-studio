# Chibi R5 — bản sửa Mẫu B để xem trong game

Ngày 28/10/2026 (Asia/Saigon). Phạm vi duy nhất: `8-9-hh3d-3/superagent`.
Đây là gói kiểm tra kỹ thuật và xem mỹ thuật, chưa phải nghiệm thu phát hành
hoặc xác nhận mọi animation/ngoại lệ đã được kiểm chứng.

## Xem nhanh

- [Ba đòn đánh chuyển động, GIF](three_punches_preview.gif)
- [Ba đòn đánh, MP4](three_punches_preview.mp4)
- [Súng và cách cầm](02_guns_diagnostic.png)
- [Nhóm động tác](03_actions_diagnostic.png)
- [22 nhân vật](04_roster_diagnostic.png)
- [HUD 8 người tại 960x540](08_live_960_f245.png)
- [Menu / tạm dừng](runtime_paused.png)

GIF/MP4 ghép từ 36 khung hình Godot, phát 12 fps để quan sát pha đánh. Đây là
sampler pose từ source frame, không phải clip input của một trận đấu và không
dùng để suy ra tốc độ game. Ảnh live và runtime được ghi từ viewport của chính
Godot; không chụp desktop hay điều khiển chuột/màn hình của người dùng.

## Kết quả chạy cuối

**Run cuối: `chibi-r5-final-27` — PASS 9/9 bước, actual exit 0 từng bước,
stderr rỗng, không có source drift, không có Godot còn sót.**

- Command ID: `cmd.chibi-r5-final-27`; ngày chạy UTC `2026-10-28`.
- Source closure: `11DB628667FB18CF1B38F39F2942ED9C8B5933A5B6C068F4A4F5AFB92408739E`.
- Đối chiếu đủ **2016 file nguồn** giữa snapshot và thư mục chính: trùng hash.
- **51 PNG/JSON** từ 4 producer được kiểm mới/không rỗng và SHA256, rồi copy
  về thư mục này và đọc lại hash. GIF/MP4 là file dẫn xuất từ 36 PNG đã kiểm.
- Receipt/log/freeze: `.local/verification/chibi-r5-final-09/project/.local/reviews/chibi-r5-final-27/`.
- Engine: `4.7.2.stable.official.ed1daf0bf`, SHA256
  `C8F0A6BC45A19B33541501E57F6F7CD972AB18453743266339D495CBBE846643`.
- Static `hh check superagent-chibi-r5`: 37 file, không error/warning.
- Audit đọc độc lập `/root/final_evidence_review_r5` xác nhận 9 stage, toàn bộ
  2016 source hash và 51 output hash khớp thư mục chính; không còn finding cụ
  thể trong phạm vi rà soát. `/root/audio_shutdown_audit` đã đọc cơ chế drain;
  kết quả engine lấy từ receipt, không thay bằng nhận xét của auditor.
- Các Scheduled Task tạm `HH-Chibi-R5-*` do lượt này tạo đã được xóa sau khi
  hoàn tất; giữ snapshot, checkpoint, receipt và raw log để tái kiểm tra.

| Bước | Kết quả thực tế |
|---|---|
| Regression | 4531 checks |
| Temporal | 50 checks |
| Pause fixture | 13 checks; không phải E2E |
| Debris fixture | 23 checks; không phải E2E |
| Master | 148/148 |
| Diagnostic sheets | 4 ảnh 1280x720 |
| Match integration | 3 cấu hình, mỗi cấu hình 420 bước input/step; 7 ảnh |
| Runtime input | 448 checks, 20 vòng menu/Tutorial/play/pause/resume/return; 3 ảnh + JSON |
| Animation | 36 PNG 960x360 |

CPU fixture 8 Chibi: `rig_p95=0.53ms`, `full_tick_p95=3.22ms`.
CPU manual match tick p95: 2 người/1280 `2.082ms`, 8 người/1280 `5.640ms`,
8 người/960 `3.206ms`. Đây là hai workload khác nhau; số 5.640ms không được
so trực tiếp với gate fixture 5ms. **Chưa đo GPU frame time hoặc FPS, chưa có
baseline before/after cùng điều kiện để kết luận giảm lag bao nhiêu.**

Giữ nguyên các lần thất bại: `final-20` có MP3 leak lúc runtime, `final-25`
có 8 ObjectDB/4 resources lúc match thoát. Runner v3 đã từ chối `final-25`
mặc dù engine exit 0. Sau đó mới thêm cơ chế drain theo WeakRef có deadline;
`runtime-26` và toàn bộ `final-27` thoát sạch. Không coi một lượt sạch là bằng
chứng mọi phiên chơi dài sẽ không leak.

## Những lỗi đã sửa

- Bỏ nhánh dùng ảnh đứng/đấm tĩnh cho nhiều hành động và đường kẻ/chấm cam giả
  súng. Giữ metadata khớp vai, frame và socket nguồn; vẽ bitmap riêng của súng
  cùng bàn tay Chibi. Không bật lại lớp arm cũ có lẫn đầu pixel.
- Ba đòn jab/cross/finisher có windup/contact/recovery riêng; mốc contact theo
  source frame lần lượt 3 / 3.5 / 4. Không tạo thêm sự kiện sát thương từ art.
- Bổ sung family pose đi/chạy, nhảy/ngã, né/lăn, leo/bám, cúi/núp, mang/ném,
  vũ khí cận chiến, hurt/KO và skill. Phép lấy pose dùng đồng hồ controller;
  animation không lặp được giữ ở cuối thay vì tua lại.
- Atlas đầu thực sự được dựng/render bằng Blender; 22 identity, 7 biểu cảm
  cùng blink, thêm hai hàng Goku/Naruto thức tỉnh. World/menu/HUD dùng cùng
  identity; không dùng mặt Johnny cho toàn bộ danh sách.
- Timer trình bày chạy một lần mỗi simulation step; pause/hitstop không tiêu
  thêm thời gian. Sửa mặt chiến thắng, flash sau chết, reset khi dùng lại fighter
  và dọn afterimage/aura/deflect khi chết.
- HUD ưu tiên 2 thẻ người chơi, bot thu gọn; tách portrait, trạng thái, 4 ô vật
  phẩm và 4 nút skill. Nút skill tối thiểu 24px ở 960x540. Prune fighter ID cũ,
  ẩn CanvasLayer HUD khi về menu; menu fit cả chiều ngang/dọc và input inverse
  dùng cùng phép biến đổi.
- `Esc`: tạm dừng/tiếp tục; `Shift+Esc`: về menu. Khi kết thúc hiệp, `Esc` vẫn
  về menu. Nhãn P1 `5/6/7/8`, P2 `U/I/O/P` theo binding hiện tại; bot không có
  nhãn phím giả.
- Cache node/metadata/texture, bỏ cập nhật trail legacy ẩn. Sửa hạt vụn bắn vào
  tường bị hiểu nhầm là chạm sàn, và thứ tự tham số floating text khi vứt súng
  hết đạn. Không đổi damage/range, AI, geometry map hoặc engine pin.
- Theme menu có một nơi khởi động ở bootstrap. AudioManager theo dõi WeakRef
  sau mỗi `play()` để bao phủ cả playback cũ đã rời pool; khi thoát chặn sound
  mới, stop/null stream/cache, chờ ref hết với deadline 1000ms. Quá hạn báo lỗi
  và exit 1. Bootstrap dùng cùng drain khi nhận yêu cầu đóng cửa sổ. Không có
  sleep cố định, strong ref qua await hoặc bỏ qua leak warning. Runtime/match
  đã chạy drain; đóng cửa sổ bằng desktop không được tự động hóa trong task.

## Pipeline đã chọn và các lựa chọn khác

| Cách | Ưu điểm cho game này | Nhược điểm / quyết định |
|---|---|---|
| **Blender head atlas + thân khớp cel trong Godot + súng nguồn** | Sửa mặt tập trung trong `.blend`, ít ảnh, cầm/ngắm súng động, không đổi socket | Có chênh mật độ pixel giữa súng và cơ thể; silhouette vẫn cần xem ở zoom chơi. Đã triển khai R5. |
| Full-body sprite vẽ/render từng frame | Kiểm soát silhouette và smear theo từng đòn | Nhiều frame cho 22 nhân vật, nhiều súng/góc ngắm; khó sửa đồng bộ pivot. Chưa chọn làm runtime chính. |
| Full 3D rig/render từ Blender | Dùng lại chuyển động và góc quay | Cần model/rig/lighting tốt; prototype hình khối trước chưa đạt kiểu Chibi mong muốn. Chưa chọn. |
| Skeleton2D/Polygon2D deform | Thuận tiện chỉnh bone và animation trong editor | Cần topology/weight và tránh gãy polygon khi co mạnh; có thể chuyển dần nếu tác giả cần chỉnh bằng editor. Hiện sampler thuần dễ kiểm tra timing hơn. |

Đây là đánh giá cho repository hiện tại, không phải khẳng định một pipeline
luôn đẹp hơn. [Godot 2D skeletons](https://docs.godotengine.org/en/stable/tutorials/animation/2d_skeletons.html)
mô tả khả năng bone/deform và lỗi biến dạng cần xử lý; chính trang này ghi
chưa được cập nhật đầy đủ cho 4.7. Blender hỗ trợ camera orthographic cho ảnh
phẳng ([tài liệu Blender](https://docs.blender.org/manual/en/dev/editors/3dview/navigate/projections.html)).
Số đo CPU và GPU cần tách biệt; xem [tài liệu profiler chính thức](https://github.com/godotengine/godot-docs/blob/master/tutorials/scripting/debug/debugger_panel.rst).

## Nguồn và dọn dẹp

- Editable Blender: `art/chibi_r5/chibi_r5_heads.blend`;
  builder `tools/build_chibi_blender_heads.py`;
  atlas/manifest `assets/sprites/chibi_brawler/r5_heads/`.
- Generation `R5.blender.cel.heads.2`, atlas 1024x3072, 24x8 cells.
  SHA256 atlas: `b09303d5e73656140c0e8a14638af4f6e67e3c113f7bc3ae86d47b6ef70412ee`.
- Runtime code: `chibi_action_pose.gd`, `chibi_head_atlas.gd`,
  `chibi_weapon_view.gd`, painter/view/controller cùng HUD/menu.
- Đã bỏ nhánh static cutout/fake gun khỏi render runtime. Giữ fallback
  procedural khi atlas lỗi và compiled rig cho metadata/chế độ không Chibi;
  chúng còn có caller nên không xóa như code chết.
- Không xóa art/reference/source cũ của owner hoặc đổi sibling
  `superagent-TacticalStriker`, `superfighters-y8`, Vault/platform.
- Checkpoint trước sửa: `.local/checkpoints/chibi-r5-20261028/`.
  Dirty work có sẵn được giữ; chưa tạo commit để tránh gom nhầm thay đổi.

---

## Technical coverage and reproduction

This folder contains diagnostic viewport captures and host-run evidence for the
Mẫu B Chibi-Tactical Expressive Brawler presentation layer. The package keeps
the original gameplay/socket metadata and adds a Blender-authored head atlas,
articulated Godot body poses, source weapon pickup bitmaps, Chibi hands and a
three-phase punch sampler.

## What is covered

- Three distinct punches: `PUNCH_01` jab, `PUNCH_02` cross and `PUNCH_03`
  finisher, each with windup/contact/recovery and source-frame contact markers.
- Original gun-only bitmaps for pistol, magnum, UZI, rifle, shotgun, sniper,
  bazooka and flamethrower. The compiled arm containing the old pixel head is
  hidden in Chibi mode; the original muzzle/socket calculation is retained and
  Chibi hands follow the grip. Shotgun frame 3 pumps the support wrist and
  chainsaw uses a dedicated procedural prop.
- Blender source `art/chibi_r5/chibi_r5_heads.blend`, pinned builder
  `tools/build_chibi_blender_heads.py`, 22 authored identities, 7 expressions
  and blink plus Goku/Naruto awakening rows.
- Adaptive HUD layouts for 1/2/4/8 fighters at 1280x720 and 960x540, including
  four local inventory slots and four local skill buttons.
- Runtime keyboard coverage through the actual menu and match scene, including
  pause/resume, Shift+Escape return and 20 Tutorial launch/return cycles.

## Reproduction

Run the checked Godot executable from the studio tooling directory:

```powershell
& '.\tools\run_chibi_r5.ps1' -RunId <fresh-id> -Stage all -Schedule
```

The v3 runner records an ordinal source closure, actual process exits,
stderr/stdout hashes, source drift and produced PNG/JSON evidence. Each stage
requires its completion marker; expected outputs must be nonempty and newer
than the stage start. It stops on the first failed stage and rejects unexplained
`SCRIPT ERROR`, `ERROR:` or `WARNING:` output.
The final package used the isolated verification snapshot under
`.local/verification/chibi-r5-final-09/project` so a game window already open
on the main checkout could not share a Godot process with the tests.

## Evidence limits

The master suite and fixtures are regression evidence; they do not prove public
release clearance, full combat coverage, every map or measured GPU frame time.
The live match capture reports a manual CPU tick p95 and explicitly labels GPU
frame time as not measured. Visual quality still needs owner review at actual
play zoom. Blender output publication replaces the atlas/manifest sequentially,
so an interrupted build is recoverable from the saved `.blend` and checkpoint
but is not an atomic multi-file generation swap.

The previous R4 claims of `83 states`, `148/148` and `100%` remain historical.
The R5 review must use the host receipt and source hash from the current run;
the number of manifest rows alone is not animation coverage.

Luffy/Gear has no dedicated Blender awakening atlas row in this generation;
only Goku/Naruto do. Unknown states and missing heads have safe presentation
fallbacks; this is not evidence that every visual combination is artistically
finished. Atlas hot replacement while the game is running is outside this
package's verified scope. Builder output replacement remains sequential.

The Antigravity walkthrough artifact was inspected at
`C:/Users/truon/.gemini/antigravity/brain/fb4592d9-c914-4d42-b275-d495b41a423b/chibi_brawler_25head_walkthrough.md`.
`agy help` exposed no conversation-history read/list command; the full named
conversation was not retrieved through CLI. R4 assertions were checked against
the repository and new runtime evidence instead of accepted from that artifact.


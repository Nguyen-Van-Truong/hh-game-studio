# Chibi R7 — nối liền tay/chân, vai và hông

28/10/2026. Chỉ sửa `8-9-hh3d-3/superagent`. Không sửa game tham khảo, TacticalStriker hoặc Vault. Không điều khiển màn hình/chuột; PNG lấy từ viewport Godot chạy ẩn.

## Kết quả và lựa chọn

Lỗi thực tế ở bản trước: mỗi đoạn xương được vẽ như một capsule có viền đen và hai đầu tròn riêng. Khi ghép tay/chân, các đường viền tạo vòng đen tại khuỷu/gối; chân trước còn đè cap hông lên thắt lưng. Tay cầm súng dùng renderer thứ hai nên sửa thân thôi chưa đủ.

R7 dùng **một đường bao ngoài cho cả chuỗi chi**, phần áo/da/bàn tay là các mảng màu bên trong. Cả hai đùi nằm sau pelvis/thân; gốc vai để mở viền nơi nối với thân. Bàn tay nhập cùng đường bao cánh tay; tay bám súng dùng chung renderer và hai vai thật của pose. Viền được gom thành polyline liên tục, không phát một lệnh vẽ cho mỗi cạnh.

- Giữ đầu/biểu cảm từ Blender `art/chibi_r5/chibi_r5_heads.blend`; không cần sinh lại đầu để chữa lỗi đường nối thân.
- Phân biệt áo dài, áo ngắn, tay trần; chỉnh cổ áo gi, áo vest và áo choàng/cổ suit cho đúng nhóm nhân vật hơn. Bỏ helper capsule và palm cũ không còn dùng.
- Đồng bộ màu tay cầm súng khi thức tỉnh, cháy đen và hit flash; phân thân dùng alpha 0.85 cho cả lớp súng/tay. Thay cờ trạng thái làm mất hiệu lực cache đúng lúc.
- Không đổi endpoint/timing của ActionPose, ba đòn đấm, hurtbox, vật lý, input, đạn hoặc biến đổi đầu nòng. Khe thang và đồ ném R6 được giữ nguyên và chạy regression lại.

## Vì sao không đổi toàn bộ pipeline?

| Cách | Điểm mạnh | Đánh đổi / quyết định |
|---|---|---|
| Đường bao cel liên tục + đầu Blender hiện tại | Sửa chung toàn roster; giữ bộ động tác/ngắm hiện có; không thêm atlas khổng lồ | **Chọn cho bản hiện tại.** Tay có thể vẫn hơi ống/góc cạnh khi phóng lớn; không tự có diễn xuất của animator |
| Vẽ sprite nguyên người từng frame | Kiểm soát silhouette, quần áo, foreshortening và diễn xuất tốt nhất khi có artist giỏi | Cần bộ hoạt ảnh nhất quán cho roster, vũ khí, góc ngắm và các biến thể; nhiều công vẽ và QA hơn |
| Mesh 2D có skin weights | Chuyển động mềm, nhiều pose từ ít artwork | Phải dựng mesh/weights và sửa biến dạng vai/hông; không tự chữa artwork hoặc layer sai |
| Dựng full body Blender rồi render atlas | Khớp 3D và trang phục nhất quán; dễ đổi camera/ánh sáng | Cần model/rig/animation tốt; dễ thành cảm giác nhựa/3D, khác mẫu B; thêm bước render và atlas |

Ảnh MUGEN tham khảo có đường nét toàn thân thống nhất. Không thể xác định quy trình tạo riêng ảnh đó từ screenshot. Tài liệu chính thức MUGEN mô tả animation bằng các phần tử tham chiếu sprite group/image, offset và thời lượng: [Elecbyte AIR](https://www.elecbyte.com/mugendocs-11b1/air.html). Đây không phải bằng chứng rằng mọi game MUGEN đều dùng cùng một pipeline mỹ thuật.

Nguyên tắc phối hợp cutout/cel, pivot và thứ tự lớp: [Godot cutout animation](https://docs.godotengine.org/en/stable/tutorials/animation/cutout_animation.html). Hợp đường bao dùng API [Geometry2D](https://docs.godotengine.org/en/stable/classes/class_geometry2d.html). Trang tutorial có phần chưa cập nhật; implementation ở đây đã được kiểm trực tiếp bằng Godot 4.7.2, không dựa vào API cũ trong tutorial.

## Ảnh và chuyển động

- `before-joints.png` và `joints.png`: cùng 12 pose, cùng zoom 8x và 3.4x. Gồm đứng, chạy, nhảy, ba đòn đấm, crouch, pistol, shotgun 45°, lăn, rơi, cháy.
- `motion_frames/`: 48 ảnh, 4 cột đứng/chạy/combo/ngắm, ở 7x và 3.4x. Combo có ba đoạn 16 mẫu (windup/contact/recovery), mỗi mẫu cách 0.5 source frame.
- `motion-preview.mp4`: playback 56fps tương ứng source 28Hz. `motion-review-slow.gif`: 28fps để xem chậm 0.5×, không phải tốc độ gameplay.
- Các ảnh là **presentation fixtures**, không phải video người chơi điều khiển trận. Súng che một phần vai/mặt ở vài góc; không dùng các vùng bị che làm bằng chứng nối khớp.

Media cuối SHA-256: sheet `49F72E7033EACB0ECD37E6B731406B269DA5B9B30BBB43CE0870ADF145A0AF5C`; MP4 `9564E18CA47AA0C18AA11616B54150F72DB57F681D40A83D648ACB75AE843255`; GIF `71592C50E77108A927EB6CA1AB544B2D2F8EF2A83864DA2779781B6F01119217`. Hai video encode bằng ffmpeg7.1 từ đúng48 PNG; không sinh/retouch nhân vật bằng công cụ ảnh.

## Kiểm chứng (Cập nhật 30/10/2026 — Full 148/148 PASS & SF-M36.4 Perf Gate PASS)

**Đã hoàn tất nâng cấp hình ảnh lửa cháy 3 lớp S-curve, tư thế action/hoảng loạn, ném bom 2 chiều qua Portal & Khe thang, sửa lỗi lưu ảnh vệt chém (`melee_traces`), và vượt qua toàn bộ 148/148 kiểm tra (bao gồm SF-M36.4 CPU Performance Gate).**

- **Master E2E Test Runner (`res://tests/test_runner.gd`)**: **148/148 PASS (100% PASS, EXIT 0)** — trong đó **SF-M36.4** đạt `rig_p95=0.57ms <= 1.0ms` và `full_tick_p95=2.17ms <= 5.0ms` (giảm từ `5.81ms..8.86ms` xuống `2.17ms` nhờ cache hình học tay/chân lượng tử hóa trong `ChibiLimbRenderer`, cache `get_chibi_pose_snapshot()` và static sheet/offset cache trong `FighterRigView`, cùng broadphase va chạm prop theo khoảng cách trong `FighterController`).
- **Chibi R7 Render Perf (`res://tests/chibi_r7_render_perf.gd`)**: **PASS** (`samples=120 actors=8 callbacks=960 p50=3.4900ms p95=4.3190ms max=6.0900ms`).
- **Chibi R7 Visual Capture (`res://tests/chibi_r7_visual_capture.gd`)**: **PASS** (`frames=48 sheets=1`, xuất lại `docs/chibi-r7/joints.png` và 48 frame chuyển động với hiệu ứng lửa cháy S-curve 3 lớp mới).
- **Chibi R6 & R7 Regressions**:
  - `chibi_r6_pose_regression.gd`: **PASS** (`869 checks`)
  - `chibi_r6_projectile_regression.gd`: **PASS** (`41 checks, failures=0` — thêm kiểm tra ném bom qua Portal 2 chiều trên ↔ dưới và ném bom từ dưới lên trên qua khe cầu thang)
  - `chibi_r6_pickup_regression.gd`: **PASS** (`27 checks, failures=0`)
  - `chibi_r6_hatch_regression.gd`: **PASS** (`36 checks, failures=0`)
  - `chibi_r6_integration_regression.gd`: **PASS** (`20 checks, failures=0` — thêm kiểm tra vệt chém `melee_traces` tự xóa sạch trên canvas khi hết hạn)
  - `chibi_r7_geometry_regression.gd`: **PASS** (`127208 checks, failures=0, 24.296 µs/chain`)
  - `chibi_r7_style_regression.gd`: **PASS** (`29161 checks, failures=0`)

### Lịch sử chẩn đoán trước khi tối ưu SF-M36.4 (28/10/2026)

Source closure 28/10/2026: `845E5A67291864928CEDBC2706A85676BB2DDDAFBC8F8820B563B0E5AB15CFF8`, 2043 files.

- `chibi-r7-final2-20261028`: regression4531, temporal50, pause13, debris23 đều PASS; master **147/148**, FAIL SF-M36.4 (rig0.87ms,8fighterstep5.81ms >5ms). Full run dừng tại gate như thiết kế.
- `chibi-r7-final1-20261028`: cùng runtime, master cũng FAIL SF-M36.4 (rig1.22ms >1ms,step8.86ms >5ms). Không nới ngưỡng hoặc che hai lần fail.
- Các receipt `chibi-r7-verify-{STAGE}-20261028` chạy tiếp riêng, cùng closure cuối: r6pose869, r6projectiles37, r6hatches36, r6pickups27, r6integration18, r7geometry127208 checks/8019chains, r7style29161 checks, r7visual49 PNG, r7perf120 mẫu, runtime448 checks/20cycles. Tất cả actualexit0,stderr sạch,drift0,leftovers0. Đây là **14/15 stage PASS tổng hợp từ các lần chạy**, không giả thành full-run PASS.
- `r7geometry` đo25.135µs/chain ở lần cuối; normal geometry nhiều nhất22 vertices trong tập kiểm.
- Đo8 painter callbacks (không gồm world/súng/GPU): perf1 p50=6.104/p95=10.038/max34.820ms; perf2 p50=5.547/p95=17.068/max32.906ms; verify cuối p50=7.967/p95=54.503/max70.203ms. Baseline checkpoint trước R7 p50=8.883/p95=32.374/max40.147ms. Chênh lệch/dao động lớn, **không đủ để kết luận speedup, nguyên nhân lag, hay đạt60fps**. PASS ở fixture này chỉ xác nhận phép đo hợp lệ, không phải đạt performance budget.
- Root xem sheet cuối và frame chuyển động; subagent xem sheet trước/sau và12 frame đại diện, xác nhận các vòng đen/khớp rời đã được loại bỏ trong mẫu. Critic không thấy blocker mới về nối chi hoặc cờ visual, nhưng giữ các residual bên dưới.

Tiếp theo về hiệu năng: profile full-world + renderer trên trace cố định; cân nhắc native bulk geometry và cache exact-key có giới hạn sau A/B. Chưa thêm cache/quantization vào game vì chưa chứng minh cần và lợi ích. Không coi lần PASS R6 cũ là bảo đảm R7 hết lag.

Chẩn đoán trước final được giữ nguyên:

- `chibi-r7-before-20261028`: visual stage exit0, stderr sạch,49 PNG. Host receipt KHÔNG PASS vì helper/test chưa được import vào runtime được thêm đồng thời; báo source drift. Ảnh trước chỉ dùng đối chiếu mỹ thuật, không dùng làm package nghiệm thu. Hai file painter/weapon baseline đã được checkpoint trước khi sửa.
- Lần import đầu phát hiện hằng PackedVector2Array không phải constant expression; đã sửa sang typed Array.
- `chibi-r7-geometry1-20261028`: fail1/127208 do mất độ chính xác float ở tọa độ ~32000. Không xóa test; đường xử lý ngoại lệ dùng phép kiểm triangulate, đổi điểm bắt đầu vòng, và fallback bảo toàn bao phủ khi cần. Tọa độ local thông thường không chạy nhánh đắt này.
- `chibi-r7-geometry2-20261028`: PASS, stderr sạch,exit0,drift0,leftovers0.
- `chibi-r7-look1-20261028`: PASS49 PNG; subagent đọc ảnh gốc và12 frame đại diện, không thấy khe hở khớp. Đây là trước bước chỉnh thêm cổ áo/tint.
- `chibi-r7-style1-20261028`: PASS kiểm palette/tint/clone/cache/shoulder/muzzle cho Goku và Naruto, pistol/rifle, cả hai hướng và ba góc ngắm.

Không coi số checks là điểm mỹ thuật. Không claim hết lag hay mọi tổ hợp gameplay. R6 từng có CPU fixture fail/dao động; lịch sử đó giữ trong `../chibi-r6/README.md`. R7 đo riêng CPU tạo hình và CPU callback vẽ, không quy đổi thành FPS hoặc GPU frame time.

Audit phát hiện thêm hai điểm có sẵn ngoài lỗi nối khớp: split-state thiếu/malformed arm frames có thể giữ socket cũ; mũi art chainsaw lệch danh nghĩa ~0.9u so với anchor riêng. Chưa xác nhận lỗi gameplay qua đường sử dụng bình thường, không sửa dữ liệu/socket trong gói mỹ thuật này; không tuyên bố đã xử lý mọi ngoại lệ của game.

Repro từ product root: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/run_chibi_r5.ps1 -RunId YOUR_NEW_ID -Stage r7`. Đóng game/editor của cùng project trước; runner chạy engine tuần tự, kiểm exit/log/output hash/source drift/leftover. Không dùng lại RunId.

Không commit vì worktree đã có rất nhiều thay đổi của owner từ trước. Checkpoint riêng của R7: `.local/checkpoints/chibi-r7-20261028/`.

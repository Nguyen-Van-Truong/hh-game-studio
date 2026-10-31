# Chibi R6 — dáng tự nhiên và khe thang thật

28/10/2026 · scope: `8-9-hh3d-3/superagent` · owner art review pending.

## Thay đổi

- Đứng thả tay bất đối xứng; đi/chạy có nhịp vung tay đối với chân. Bàn tay nhỏ có hướng; phân biệt tay trần, găng hở, găng kín, giáp tay và wristband.
- Nhảy lên, đỉnh quỹ đạo, rơi xuống, rơi nhanh, ngã do trúng đòn có silhouette riêng theo vận tốc controller. Không thay hurtbox hoặc thời điểm tiếp xúc ba đòn đấm.
- Cháy có nét mặt/phản ứng riêng; không ghi đè pose ngắm, đánh, mang đồ, leo, lăn, hurt và KO. Lửa bám hông/chân khi xoay/ngã, giữ mặt dễ đọc; không phát thêm puff tại thân đã gib. Không đổi burn damage/contagion.
- Theo lựa chọn owner: mở hai khe cầu trên rộng 20u và bỏ bốn tấm grating ở miệng thang Steel Harbor. Art/collision thống nhất, giữ sensor 16u và mép cảnh báo. Không thay dữ liệu các map khác.
- Đạn thường theo hướng bắn; bom/Molotov/súng rơi chịu trọng lực. Kiểm đoạn di chuyển qua sàn mỏng, dốc một chiều, cạnh/trần và prop; không hút vật từ dưới sàn lên.
- Đồ nằm trên thang máy được mang theo một lần mỗi bước; va chạm theo chuyển động tương đối và kiểm tiếp phần nâng còn lại để không xuyên trần. Mất điểm tựa thì tiếp tục rơi.

Nguồn đầu vẫn là Blender `art/chibi_r5/chibi_r5_heads.blend`; R6 không sinh lại atlas đầu. Thân/pose là rig cel code-native, không chạy Blender trong game.

## Xem trước

- `poses.png`: 12 trường hợp ở ba mức zoom 5x / 3.4x / 1.85x.
- `motion-preview.gif` / `motion-preview.mp4`: 36 ảnh từ rig thật, source step 0.5, playback 56fps tương ứng game FLASH_FPS=28. Đây là sampler theo thời gian, không phải video điều khiển trận đấu.
- `hatch_008.png`, `hatch_028.png`, `hatch_056.png`: map thật + projectile/pickup simulation; vị trí sinh được đặt sẵn. `hatch_trajectories.json` giữ quỹ đạo để kiểm đạn ngang, rơi qua hai tầng và bom đổi chiều tại sàn y=12.

Không ảnh nào là ảnh chụp desktop; đều lấy từ viewport Godot. Không điều khiển chuột/màn hình.

## Kiểm chứng

Hai full package `chibi-r6-final3-20261028` và `chibi-r6-final4-20261028` đã đạt cả 13 stages với exit 0, log sạch, không source drift hoặc engine leftover. Sau đó guard bot được siết thêm cho nhánh đi xuống; bản đóng gói sau guard được ghi riêng ở cuối mục này.

**Package cuối: `chibi-r6-final5-20261028` — PASS 13/13 stages.**

- Receipt: `.local/reviews/chibi-r6-final5-20261028/receipt.json`.
- Source closure SHA-256: `8C9B5915C2A058BD74681CA5D6C3007E8BD6FC19275BD7E41572699D97219A10` (2031 files; runtime/data/assets/authoring/tests/tools).
- Tất cả actual exits = 0; stderr rỗng; source drift = 0; engine leftover = 0; 45 file PNG/JSON đầu ra có hash.
- R5 regressions: 4531 pose/socket, 50 temporal, 13 pause, 23 debris; master 148/148.
- R6: pose 869, projectiles 37, hatch/bot 36, pickups 27, controller/fire integration 18 checks.
- Runtime smoke: 448 checks, 20 vòng menu→Tutorial→pause→resume→menu; không gọi đây là full combat parity.
- Presentation: 36 motion frames + 1 pose sheet; 3 hatch stills + trajectory JSON. GIF/MP4 là bản encode tiện xem từ cùng chuỗi frame, không đo FPS.
- CPU fixture cuối: rig p95=0.76ms, 8-fighter step p95=4.09ms. Không xóa các lần fail phía dưới.
- Read-only audit đã kiểm lift sweep, carry/ceiling, fire transforms/gib, SF-M31 và guard bot; bot hash cuối `5D3099537DE308473879FC6986D4A0370E1D2E170EFD4410A4AECEB98F66725C`. Concern double-advance/descending-edge đã sửa trước final5.

Repro từ product root: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/run_chibi_r5.ps1 -RunId YOUR_FRESH_ID -Stage r6`. Chỉ chạy khi không có game/editor/test khác dùng cùng project. Tên RunId phải mới; script không đè receipt đã có.

Các lần chẩn đoán được giữ trong `.local/reviews/chibi-r6-*`. Một full run `chibi-r6-final-20261028` thất bại ở CPU fixture SF-M36.4: rig p95=0.98ms, 8-fighter step p95=6.43ms > 5ms; ngưỡng không bị nới. Ba master riêng trước đó có p95 step 4.46/3.34/3.71ms. Không kết luận nguyên nhân do tải máy khi chưa có profile chứng minh.

Giới hạn: CPU fixture gọi tám `step_fighter` không đo toàn bộ AI/world/render/GPU và không chứng minh hết lag. Pose/collision fixtures không thay thế chơi dài, mọi phối hợp skill/hazard hoặc duyệt mỹ thuật của owner. Giữ lại các lần thất bại thay vì chỉ công bố lần PASS.

Bot: lần đầu `upper_exit_x=nan` đã giúp phát hiện route bị refresh/hoàn tất quá sớm. Đã giữ final LADDER đến khi rời thang thật, chấp nhận sàn bên cạnh thay vì kéo bot về tâm khe; hold hủy khi mất sàn/đổi mục tiêu/bị đẩy lệch. Có guard một lần advance mỗi tick và nhánh thoát vào không trung chỉ dành cho leo lên. Fixture sau sửa đi từ đáy lên sàn x=285, không quay về khe/không rơi. Kiểm đi xuống dùng hai cạnh LADDER ngược được đặt sẵn (A* tự do chọn portal); không gọi đây là toàn bộ E2E bot AI.

Hiệu năng vẫn cần theo dõi: `final2` cũng vượt ngưỡng (rig 1.54ms, step 10.39ms); ba lần recheck đạt step 4.26/2.81/3.89ms, `final3` đạt 0.75/4.31ms và `final4` đạt 0.61/3.29ms. Không thay đổi ngưỡng, không bỏ log fail, chưa có profile xác định nguồn dao động.

## Lựa chọn kỹ thuật và phương án khác

Chọn đầu Blender + thân cel có khớp vì sửa pose nhất quán, giữ socket súng và footprint nhẹ. Nhược điểm: không có nét vẽ biến dạng riêng từng frame như animation vẽ tay; súng pixel và thân cel vẫn khác mật độ. Vẽ tay toàn bộ cho chất lượng diễn xuất cao hơn nhưng chi phí sửa nhiều frame/22 nhân vật lớn; mesh 3D đầy đủ dễ xoay mọi góc nhưng thay phong cách và tăng công việc rig/material/render. R6 ưu tiên vấn đề người chơi vừa chỉ ra, không thay pipeline toàn bộ lần nữa.

Godot mô tả cutout có thể kết hợp cel riêng cho tay/chân/biểu cảm, và nhấn mạnh pivot/layer/rest pose: [tài liệu chính thức](https://docs.godotengine.org/en/stable/tutorials/animation/cutout_animation.html). Đây là cơ sở lựa chọn kiến trúc, không phải bằng chứng code hiện tại đúng. Trang tài liệu tự cảnh báo chưa cập nhật hoàn toàn cho 4.7; chỉ dùng nguyên tắc ổn định.

## Cleanup và an toàn

- Giữ checkpoint R6 `.local/checkpoints/chibi-r6-20261028` và bằng chứng R5.
- Bỏ các grating/collider không còn dùng trong map builder/data; không xóa hàng loạt art/source cũ của owner.
- Không sửa reference `superfighters-y8`, sibling TacticalStriker hay Vault/platform.
- Không commit vì workspace có nhiều thay đổi sẵn của owner. Không reset/revert chúng.
- Đã bỏ script trace tạm do agent tạo và gỡ 5 Scheduled Tasks chỉ phục vụ R6; log/receipt/checkpoint vẫn giữ để xem lại. Không xóa task/file của người dùng.

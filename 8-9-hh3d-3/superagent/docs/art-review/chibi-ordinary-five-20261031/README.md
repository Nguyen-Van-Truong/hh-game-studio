# Chibi Ordinary Five — bộ duyệt 31/10/2026

## Phạm vi

Theo đính chính của owner: **giữ chibi của game hiện tại**, không dùng hình thể người cao thực tế. Người thường nghĩa là không siêu năng và phản ứng có trọng lượng/cảm xúc; không có nghĩa chuyển sang tỷ lệ 7 đầu.

- Năm thiết kế: Johnny, Boris, Agent, Hideki, Blaire.
- Mục tiêu hình thể: khoảng 2,5 đầu như rig hiện tại, đầu lớn, thân/chân ngắn. Đây là chỉ đạo mỹ thuật; PNG chưa qua đo calibration để import.
- Bộ đã tạo và chọn: 1 roster và 30 bảng × 16 ô = 480 ô tư thế/biến thể/chân dung. Có các ô cùng họ động tác; **không phải 480 animation độc lập**.
- Bộ này là concept/key-pose để owner xem xét. Chưa tích hợp runtime, chưa tách sprite nền trong, chưa rig/animation.
- Không sửa gameplay, scene, plan, AGENTS, test hoặc tick/commit. Các thay đổi runtime đang có trong worktree thuộc công việc khác và được giữ nguyên.
- Bộ người cao cũ ở thư mục sibling ordinary-five-20261031 đã bị thay thế về hướng thiết kế. Không dùng bộ đó làm anchor cho chibi.

Mở [index.html](index.html) để duyệt. [manifest.json](manifest.json) ghi 31 PNG được chọn, kích thước và SHA-256; 13 bản cũ được liệt kê riêng để truy vết, không xuất hiện trong gallery.

## Sáu nhóm mỗi nhân vật

1. Di chuyển: idle, walk contact/passing, run hai chân, sprint, crouch/cover, nhảy/rơi, các pha lăn và dive.
2. Leo/tương tác: thang, ledge, rocket ride hai hướng, dive tackle và nạn nhân, đẩy/đá vật, nhặt đồ, thắng trận.
3. Súng/đồ ném: tám họ súng, grenade/molotov chuẩn bị và thả, hướng lên/xuống, quỳ/nấp ngắm.
4. Cận chiến: jab chuẩn bị/chạm/thu, cross/hook, đá/nhảy đá, machete/axe/sword/baton/bat/chainsaw.
5. Đau/cháy: trúng đòn, choáng, ngã trước/sau, tiếp đất nặng, knockdown/getup, sụp gối/chết, cháy đen, bén lửa, phản ứng trước/sau, chạy hoảng, lăn dập, sau cháy.
6. Biến thể: front/side/rear, guard, C4/mine dạng vật cầm, bỏ súng hết đạn, pump shotgun; tám chân dung biểu cảm.

Các trạng thái cháy là diễn xuất + material/VFX trên pose thường, không tự chứng minh game có state BURN độc lập. Carry trong controller là đối thủ bị dive tackle, không phải bê thùng. Rocket ride là cơ chế game có sẵn, không phải kỹ năng siêu năng mới. Không tạo SKILL_*, MUGEN_* hoặc biến hình.

## Nhận diện đã khóa theo game đang thấy

| Nhân vật | Nhận diện |
|---|---|
| Johnny | Tóc nâu nhấn cam, hoodie cam/navy, tay xám, giày đế sáng |
| Boris | Tóc ngắn xám, áo olive, thân chắc, không đổi thành đầu trọc |
| Agent | Tóc tối chải ngược, kính râm thường, suit navy, cà vạt cam |
| Hideki | Tóc tối, băng trán đỏ, áo quấn xanh nhạt/trắng |
| Blaire | Bob tím, áo teal; giữ bob tím cả phía sau |

Blaire front atlas và procedural back trong source có thiết kế tóc không khớp. Bộ đề xuất chọn bob tím đúng hình hiện đang thấy ở chính diện; không âm thầm sửa source.

## Tham khảo và cách áp dụng

Nguồn chính là ảnh và rig của chính project:
- docs/chibi-r5/04_roster_diagnostic.png
- docs/chibi-r7/joints.png
- docs/chibi-r5/runtime_play.png
- game/fighter/chibi_brawler_rig_painter.gd
- game/fighter/chibi_action_pose.gd
- tools/build_chibi_blender_heads.py
- data/chibi_atlas_manifest.json

Tham khảo nguyên tắc, không sao chép artwork:
- [Riot — Clarity in League](https://www.leagueoflegends.com/en-us/news/dev/clarity-in-league/): silhouette, hướng chuyển động và khả năng đọc nhân vật. Áp dụng suy luận vào mảng màu lớn và giới hạn chi tiết ở kích thước nhỏ; không phải “chuẩn tỷ lệ Riot”.
- [Sloclap — How Sifu’s kung fu combat works](https://blog.playstation.com/2021/11/18/how-sifus-kung-fu-combat-works/): trọng lượng/tư thế, tính đáng tin của hành động. Chỉ học nguyên tắc diễn xuất, không lấy tỷ lệ người thật hay animation.
- [Naughty Dog — Facial animation](https://blog.playstation.com/2020/08/28/the-story-behind-the-last-of-us-part-iis-staggeringly-realistic-in-game-character-facial-animation/): biểu cảm gắn với cảm xúc. Không claim có motion capture, facial rig hoặc chất lượng tương đương.

## Tạo ảnh và QA

Dùng **imagegen built-in**, không gọi CLI/API key, không vẽ lại bằng Python. [prompts.json](prompts.json) lưu kế hoạch prompt và roster; [executed-generation-prompts.json](executed-generation-prompts.json) lưu prompt thực thi, còn ba file revision-prompts*.json lưu các lượt sửa. Ảnh gốc công cụ vẫn giữ ở generated_images. PNG cuối được copy vào project. QA/giới hạn cụ thể ghi trong [QA.md](QA.md).

Đây là hình AI-generated nên số ô đúng hoặc pose đẹp không chứng minh:
- frame-to-frame consistency, contact timing, pha chuyển và hướng trái/phải;
- socket tay/súng, muzzle/aim, pivot, hitbox hoặc kích thước world;
- alpha/layer, atlas không lem và hiệu năng;
- khả năng đọc thực tế ở zoom gameplay.

Sau khi owner duyệt, bước sản xuất cần làm một nhân vật mẫu trong game: tách lớp hoặc rig, vẽ frame chuyển tiếp, chỉnh tay cầm/aim, xuất metadata rồi kiểm trái/phải và camera gameplay. Chỉ mở rộng bốn nhân vật còn lại sau khi mẫu đó đạt.


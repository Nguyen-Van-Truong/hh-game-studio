# QA — Chibi Ordinary Five

Ngày: 31/10/2026. **Kết quả: bộ concept để owner duyệt; không phải nghiệm thu sprite/animation/runtime.**

## Đã kiểm tra

- Main đọc rig/style/source và xem ảnh roster, joint fixture và ảnh trận hiện có. Không chạy thêm Godot.
- Main xem các ảnh tạo ra và các bản sửa. Subagent xem độc lập các nhóm Johnny, Boris, Hideki, Agent và Blaire. Đây là review mỹ thuật, không phải chữ ký gate sản phẩm.
- 30 bảng được chọn, mỗi bảng bố cục 4×4 = 16 ô. Nhóm 06 gồm 8 ô toàn thân/biến thể và 8 chân dung. Tổng 480 ô bao gồm các pose lặp/biến thể, không phải 480 animation độc lập.
- Năm nhận diện giữ theo game: Johnny nâu/cam/navy; Boris tóc xám/olive; Agent kính râm/suit; Hideki băng đỏ/áo xanh nhạt; Blaire bob tím/teal.
- Các sheet đầu lớn/thân-chân ngắn đúng hướng chibi. Tỷ lệ2,5 đầu là mục tiêu, **chưa đo từng hình để chứng minh đúng calibration**.
- Cả năm có fire sheet: đau/hoảng, lửa bám áo, chạy thoát, lăn dập, ám khói và cháy đen; không có aura/biến hình/siêu năng.
- HTML được kiểm cấu trúc và đường dẫn tĩnh. Trình duyệt IAB không khả dụng trong phiên này nên **chưa có screenshot/render QA của gallery**; không tuyên bố đã test responsive trực tiếp. FileHTML không cần server/network để dùng.

## Các lỗi đã sửa qua imagegen, giữ bản cũ để truy vết

| Nhóm | Bản được chọn | Sửa |
|---|---|---|
| Johnny movement | 01-movement-v2.png | Đổi nhãn RunA/B; không coi hai ảnh là loop đối chân đã đúng |
| Johnny traversal | 02-traversal-v2.png | Bỏ bàn tay thứ ba ở ledge release; đổi tay cao ở nhịp leo |
| Johnny firearms | 03-firearms-v2.png | Các ô09–14 có đầy đủ thân/chân, không còn crop ngang eo |
| Johnny melee | 04-melee-v2.png | Cross có xoay thân/gót chân rõ hơn jab |
| Boris, Hideki traversal | 02-traversal-v2.png | Đổi tay cao giữa hai nhịp leo |
| Boris, Hideki expressions | 06-variants-v2.png | Chớp cả hai mắt thay cho wink |
| Agent traversal | 02-traversal-v2.png | Đổi tay cao ở nhịp leo |
| Agent firearms | 03-firearms-v2.png | Bỏ label/đạo cụ foam rehearsal; đúng nhóm súng/đồ ném game thường |
| Blaire traversal | 02-traversal-v2.png | Đổi tay cao, buông ledge bằng tay mở |
| Blaire firearms/expressions | 03-firearms-v2.png,06-variants-v2.png | Bỏ kính râm sinh nhầm, trả lại mắt teal và biểu cảm |

Gallery chỉ dùng bản đã chọn. Các PNGbase đã bị thay thế vẫn ở thư mục để so sánh, không phải lựa chọn đề xuất. Các bản người cao ở sibling ordinary-five-20261031 là hướng sai theo đính chính owner, không thuộc gallery này.

## Hạn chế còn thấy — phải xử lý trước khi sản xuất

1. **Chu kỳ đi/chạy:** Johnny/Boris/Agent/Hideki có các cặp chạy gần nhau, chưa phải đối chân chuẩn. Blaire RunLeft/Right chủ yếu khác hướng quay. Agent/Blaire WALKPASSING còn gầncontact. Không cắt các ô rồi phátloop và gọi là animation hoàn chỉnh.
2. **Góc model:** một số ôFRONT vẫn hơi3/4; cần front/profile/rear chính xác khi rig.
3. **Cận chiến:** các họ vũ khí mới có vài key pose, chưa đủ mọi combo 1/2/3 với windup/contact/recovery. BlaireHOOK còn gần đấm thẳng; AXEREADY chưa rõ grip hai tay.
4. **Vũkhí:** stock/hand/muzzle/cover mới ở mứcminhhoạ. HidekiCOVERAIM có đầu súng chồng mặt thùng, chưa chứng minh đường bắn thoáng. AgentLAUNCHER vẫn đọc như tư thế kê/giữ, chưa phải grip bắn hai tay chuẩn. Không dùng ảnh này thay socket runtime.
5. **Chiều cao và scale:** scale nhân vật/đạo cụ có khác giữa ô; không có pivot/floorline chuẩn như atlas. Kích thước thật của action board 1254×1254, roster 1983×793; không gọi là 2048/4K.
6. **Fire:** là các mốc diễn xuất riêng; không có mô phỏng lửa hoặc loop VFX, một vài charred có tàn lửa nhỏ. Không phải hướng dẫn an toàn cháy.
7. **Production:** chưa alpha trong suốt, tách lớp, sprite frames, rig, frame contacts, metadata hoặc kiểmperformance. Chưa thay game và không ký PASS runtime.

## Đề xuất bước sau khi duyệt

Chọn Johnny làm mẫu sản xuất ở đúng 18 world units/hurtbox/socket đang có. Làm trước idle/run/punch/aim/ladder/roll/burning ở cả hai hướng, kiểm ở camera gameplay. Chỉ nhân rộng sang bốn người khác khi mẫu đó đạt. Các concept là nguồn diễn xuất/mỹ thuật, không phải file sẵn thay renderer.


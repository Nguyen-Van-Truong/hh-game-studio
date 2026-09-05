# Hợp đồng trải nghiệm game

Thẩm quyền: hành vi của game mới; không sửa nghĩa mode hoặc nghiệm thu Web cũ.
Tất cả số lượng dưới là scope/target v0.1, không phải đã triển khai.

## P01 — Trụ cột

1. Đi lại/camera/touch dễ dùng, phản hồi ngay và ít giật.
2. Người chơi có bản sắc: avatar, trang phục, emote, nhà và quầy hàng.
3. Gặp bạn thật, làm một việc cùng nhau; ưu tiên chất lượng tương tác hơn số CCU.
4. Bối cảnh Việt Nam nguyên bản, rõ nguồn địa lý; không giả digital twin.
5. Mở rộng bằng nội dung theo catalog và khu/room, không tùy ý nhân số hệ thống.

Không sao chép asset, hình dạng đặc trưng nhân vật, map, âm nhạc, UI screenshot,
tên item hoặc nội dung của Play Together. Tham khảo beat chức năng từ nguồn
công khai; mỗi reference có nguồn và ghi phần thiết kế nguyên bản của mình.

## P02 — Hành trình đầu tiên, có điểm kết thúc

Lần đầu: chọn tên hiển thị hợp lệ → chọn avatar preset → vào khu phố authored
ở Solo → học đi/xoay camera/tương tác bằng gợi ý ngắn → nhận một nhiệm vụ
câu cá → hoàn thành hoạt động → nhận item từ authority phù hợp chế độ →
trang trí nhà hoặc trưng bày item → chủ động mời bạn/vào Public khi được mở.
Cho bỏ qua hướng dẫn và xem lại. Không chặn chơi vì màn đăng nhập khi Solo.
Mời/visit chỉ hoạt động sau khi chuyển sang Online với account và nhà Online.
UI giải thích trước chuyển: nhà, placement, item và tiền Solo là sandbox riêng,
không được import vào Online; login không xóa nhà Solo nhưng không làm nó
thành nhà có thể mời bạn vào. ID/save namespaces của hai chế độ tách biệt.

Một vòng 10–15 phút phải tự đủ ý nghĩa: khám phá → hoạt động → phần thưởng
→ thể hiện bản thân/nhà/shop → quay lại hoặc gặp bạn. Không chỉ đi giữa hộp nhà.
Không dùng nhiệm vụ chờ vô nghĩa, paywall hay chuỗi menu để thay gameplay.

## P03 — Phạm vi nội dung v0.1

| Hệ | Bản nhỏ nhưng hoàn chỉnh | Không thuộc v0.1 |
|---|---|---|
| Khu phố | 1 quảng trường, đường/ngõ, hồ câu, quầy, cửa nhà, landmark Việt nguyên bản | Toàn tỉnh/quốc gia; scan nhà thật |
| Di chuyển | Đi/chạy/nhảy, dốc/bậc/va chạm, camera chống xuyên, touch và keyboard | Xe cộ/vật lý phá hủy |
| Avatar | 1 skeleton gốc; ít nhất 3 preset ngoại hình, 6 bộ trang phục phối hợp; idle/walk/run/jump/land, 6 emote | Hàng trăm body rig; sinh mesh tự do |
| Hoạt động | 1 trò câu cá nguyên bản với dấu hiệu bằng hình/âm/thời điểm; 3 nhiệm vụ onboarding; chơi cạnh bạn | 10 minigame nửa chừng |
| Sưu tầm | 6 loại vật phẩm/cá, thông tin, rarity công khai, trang sổ bộ nhỏ | Lootbox trả tiền, market đầu cơ |
| Nhà | 1 phòng instance/account, 12 món nội thất catalog, đặt/xoay/undo/lưu, mời party | Upload mesh/script; phá nhà người khác |
| Shop game | 1 quầy/account, 6 slot listing, draft/publish/unpublish; giá bằng soft currency hoặc trưng bày | Thanh toán/cash-out/đơn hàng thật |
| Social | Kết bạn hai chiều, party tối đa 4, invite/join, block, emote, text chat có giới hạn | Voice; bạn bè không giới hạn cùng render |
| UI | HUD gọn, túi đồ, emote wheel, bạn bè, house/shop, settings, reconnect | Debug/status nội bộ phủ màn chơi |
| Âm thanh | Nhạc/ambience nguyên bản hoặc license hợp lệ; bước chân, tương tác, activity, UI; mute riêng | Audio ripped, âm thanh quá dày theo từng avatar |

Đây là mức scope mục tiêu, có thể chia nhỏ trong WP. Nếu chất lượng/fun fail,
coordinator ghi proposal cắt nội dung, không tự xóa acceptance sau khi code xong.

## P04 — Mode, quyền riêng tư và tương tác

| Trạng thái | Avatar khác | Dữ liệu shop | Tiến trình |
|---|---|---|---|
| Solo có Internet | Không; không publish presence | Đọc public mới nhất, không lộ vị trí | Save Solo riêng; không tự mint item online |
| Solo mất Internet | Không | Cache có nhãn; không đặt giao dịch offline | Local save riêng, không ghi đè ledger online |
| Friends/private | Người được room/invite cho phép; block có ưu tiên | Theo quyền listing/nhà | Server authority khi có session |
| Public plaza (opt-in) | Người cùng room trong ngân sách AOI; có block/report | Shop public | Online authoritative |

Không đồng bộ phần thưởng Solo vào economy online bằng cách tin client.
Nếu sau này cần chuyển thưởng, phải có protocol chống replay và quyết định
riêng; v0.1 không có chuyển tự động. UI gọi rõ “chơi thử Solo” và “tiến trình Online”.

Friends service cung cấp online/room có quyền xem, không stream transform bạn
ở xa. Join kiểm tra consent, block, room policy và sức chứa. Room đầy: chờ,
hoặc mời cả party qua room khác bằng đồng ý rõ; không đẩy người đang chơi đi.
Offline/ẩn presence không tiết lộ tọa độ qua search/friends API. Chọn ẩn hoàn
toàn sẽ rời Public và chuyển Solo/private theo lựa chọn đã giải thích; không
cho vừa báo “ẩn hoàn toàn” vừa hiện model trong Public. Private vẫn hiện với
người được mời, UI gọi đúng là private, không gọi invisible.

Block: chặn invite/chat/direct interaction, xóa visibility phía server theo
policy và ACK; không chỉ ẩn model trên client. Bản thân actor vẫn có thể tồn
tại trên simulation; tránh collision vô hình bằng cách player-player không
va chạm cứng ở plaza. Tương tác trực tiếp giữa hai avatar chỉ mở khi cùng simulation,
có quyền và cả hai đã biết actor liên quan; không giao dịch với actor bị cull.
Block hủy invite/reservation tương tác/direct target và priority liên quan.
Chỗ câu là điểm tương tác không độc quyền giữa player để actor bị ẩn không
giữ một slot vô hình; visitor placement edit luôn bị chặn bởi ownership.
Mua ở shop là tương tác với shop/ledger authority, không đòi avatar chủ shop
cùng room hoặc đang Online. Rule hai avatar biết nhau không áp lên listing
public; quyền listing/stock/transaction vẫn được server kiểm tra.

## P05 — UI và art direction

- Tỷ lệ stylized nhất quán, silhouette rõ ở màn nhỏ; ánh sáng chủ đạo đơn giản,
  màu nhận diện địa điểm, material atlas, không dùng bóng đắt để che asset sơ sài.
- Đường nhà Việt có mái/hiên/biển/phố/cây thích hợp nhưng original; chữ Việt
  đủ dấu, không nhét mỗi biển thành một widget nặng cập nhật liên tục.
- HUD chỉ thông tin đang cần; thông tin nguồn dữ liệu ở map/credits/info panel.
  Không phủ banner “NOT_PLAN_PASS” lên game. Build info và diagnostics ở menu dev.
- Cỡ chữ tối thiểu theo thiết bị ước lượng 16 sp UI cơ bản; nút touch 48 dp;
  safe area/notch, text scale, tương phản, chỉ dẫn không phụ thuộc màu/âm thanh.
- Camera sensitivity/invert, âm lượng, quality, reduced motion; giới hạn
  camera shake mặc định thấp. Không dùng frame rate làm tốc độ đi/animation.
- Asset placeholder phải được gắn nhãn nội bộ và có WP thay; screenshot
  placeholder không được coi là art nghiệm thu.

## P06 — Người dùng, moderation và dữ liệu

Không tự gán đối tượng là trẻ em hay mặc định nhãn tuổi đã được duyệt. Closed
alpha dùng người thử trưởng thành được mời; public cần policy audience/age,
quyền riêng tư, retention và nhân sự xử lý báo cáo ở gate release.
Chat tắt trước khi moderation path hoạt động; emote preset dùng được sớm.
Display name/shop text qua normalize/length/rate limits, report/block/mute;
lọc từ đơn thuần không được gọi là moderation hoàn chỉnh.

Không upload ảnh/mesh/script trong v0.1; catalog-first giảm phạm vi quản lý.
Không GPS, danh bạ, địa chỉ nhà thật hoặc location history cần thiết cho chơi.
Telemetry giảm định danh; mỗi trường có mục đích/retention; log không có token.

## P07 — Nghiệm thu hành vi

Các test của `05-QUALITY-GATES.md` là bắt buộc, gồm onboarding, chặn xuyên nhà,
emote, item authority, đặt đồ, quầy tồn tại khi owner logout, party vào cùng
room, block, reconnect và touch. Không chỉ gọi hàm hoặc teleport đến đích.

Fun test: 5 người thử trưởng thành, ít nhất 4/5 hoàn thành vòng onboarding
trong 10 phút không hướng dẫn miệng; ghi thời gian, chỗ kẹt, lỗi hiểu mode,
và câu trả lời tự do về việc muốn làm tiếp. Ít nhất 4/5 đánh giá điều khiển
dễ dùng ở mức 4/5 trở lên. Đây là gate usability nhỏ, không chứng minh retention.
Nếu chưa có đủ người: HUMAN_UNVERIFIED, không đổi thành bot hoặc ký thay.

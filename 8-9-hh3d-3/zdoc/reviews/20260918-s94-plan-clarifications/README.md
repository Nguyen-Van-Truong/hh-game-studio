# S94 / S23 / SA2 — làm rõ điều kiện bàn giao

AUTHORITY=0

Ngày 18-09-2026. Đây là rà và sửa tài liệu theo sáu góp ý owner gửi, không
phải runtime acceptance, hai final critics hoặc bằng chứng game đã được tạo.
Ba plan vẫn giữ bảng tiến độ duy nhất của mình. Bản trước sửa nằm ở Git
`754186c456342795f648f8c35d45646aae6f81bd`; SA1/S22 được tạo tại `135cc588`.

## Kết luận sáu điểm

1. **Memory: đúng, wording cần khớp verifier.** Đã đọc working source và bản
   frozen S93 của `benchmark_profile.py` và `run_benchmark_campaign.py`.
   Baseline là observation quiescent batch 4; mọi batch 5–34 phải có RSS từng
   process ≤110% baseline và applicable counters ≤baseline. Tenth repetition
   chỉ là trường báo cáo. Một count tăng đã FAIL; không tự chứng minh leak
   tăng đều. Không sửa source/profile/threshold hoặc failure cũ. Host objects/
   resources là N/A theo profile, required missing counter vẫn GAP kể cả warmup.
   Cleanup owner handles khác OS handles đang đo. Tools S94 ghi đúng contract.
2. **P5 kit: đúng, thiếu producer output rõ.** HH World S23 giao kit kiến trúc
   tái dùng từ nội dung plaza, catalog/version/units/pivot/attachments/material/
   LOD/collision/source và assembly fixture. P7 nhận package đã kiểm, không
   tự mở art authoring trong converter hoặc đòi dữ liệu thật từ P5.
3. **P7 dữ liệu thật: đúng, trước đây readiness/schema chưa là export proof.**
   P7-01 nhận trách nhiệm bounded real snapshot sau review quyền nguồn, road
   polylines/building polygons, native IDs/version/CRS/hash/coverage/provenance.
   P7-02 tiêu thụ snapshot immutable có hash; source không đủ vẫn GAP. Road
   centroids/shop clusters không thay geometry. Không đụng dịch vụ Hoàn Hảo.
4. **Superagent performance/targets: đúng, cần tách simulation và render.**
   SA2 giữ máy phổ thông baseline và p95≤20ms/p99≤33.4ms, không coi chúng là
   proof render luôn60FPS. Required profiles/touch có điều kiện đi đến SA-16;
   jank metrics/budget phải khóa trước tuning, chưa đo vẫn UNVERIFIED. Mobile
   Web không tự yêu cầu native Android; Android fixture của tools không thay
   bằng chứng game. Giữ đầy đủ inventory/parity và hai ngoại lệ owner cho phép.
5. **Social test sớm: hợp lý; Solo sớm đã có.** Bổ sung protocol 2–4 người sau
   technical P4 trước bulk art. Thiếu người ghi HUMAN_UNVERIFIED, vẫn tiếp tục
   kỹ thuật và giữ P6 human gate. Không giả feedback, mở môi trường chưa đủ
   quyền/auth hoặc thêm minigame.
6. **Tool extensions: cơ chế đã có, cần giao được việc.** SA-T01–06/H2-T01–04
   là hàng consumer matrix với owner role, minimum capability, first use và
   proof. Named writer/lease được giao khi request mở sau GT-10. Common request
   được dùng chung implementation nhưng giữ consumer tests riêng; không thêm
   WP/gate vào lần GT-10 đầu, không sửa generated addon hoặc cấp hidden eval.

## Rà độc lập và giới hạn

Ba worker `gpt-6-astra`, reasoning `ultra`, chỉ đọc:

- `/root/s94_memory_review`: đối chiếu cả working và frozen verifier; mô tả
  ngưỡng cũ mơ hồ hơn code, giữ nguyên code và evidence.
- `/root/s94_hhworld_review`: producer/consumer, dữ liệu, social và extension;
  rà diff sau sửa không có blocking finding. Clarification rig có sẵn cho
  benchmark P1-03 đã thêm; authoring proof trước lần tạo/sửa đầu.
- `/root/s94_superagent_review`: input/device/render và extension; rà diff
  yêu cầu giữ chữ “máy phổ thông baseline”, coordinator đã sửa. Không có
  finding khác trong phạm vi đọc, không coi đây là final critic.

`document-checks.json` kiểm UTF-8, nguyên bảng10/32/16 WP và trạng thái, dependency
order, current WP/runtime claims và phạm vi tracked diff. Kiểm tĩnh tài liệu
không chạy engine/test suite và không xác nhận các link nguồn web còn hiện hành.

## Lượt công cụ đang chạy

Không đổi source/helper/profile của S93. Scheduler query 14:52:05Z:
`\HHStudio.GT06.gt06-s93-sparse-attribution-01`, state4, một instance.
Capture0–4 đã có; batch4 ACK Objects71128/resources6, host10984/editor33152;
raw joint có đúng current source `e05d6913…` và profile `0cd5b530…`.
Đây là quan sát tại thời điểm đó, không chứng minh terminal/PASS hoặc no-leak.
Run vẫn là instrumented diagnostic, không nhập dataset nghiệm thu.
Năm batch đầu khoảng7phút; ước lượng ban đầu cho cả lượt45–75phút còn phù hợp,
cần hiệu chỉnh bằng các batch tiếp theo. Lịch hiện hành kiểm mỗi10phút.
GT01–05 accepted; GT06 vẫn cần formal benchmark và hai final critics; GT07–10
chưa mở. Không có ETA đáng tin cậy cho toàn bộ tools hoặc game.

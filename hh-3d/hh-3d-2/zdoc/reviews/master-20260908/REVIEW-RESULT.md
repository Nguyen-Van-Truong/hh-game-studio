# Review revision 08-09-2026 — HH World 2

SCOPE=DOCUMENTATION_ONLY
IMPLEMENTATION=NOT_STARTED
RUNTIME_ACCEPTANCE=NONE
INDEPENDENT_REVIEW=PENDING
MODEL_REQUIRED=cursor-grok-4.6-xhigh-fast

Bản master mới: ../../../../../../hoan-hao/zdoc/8-9-hh-world-2-ke-hoach-tong-the-va-chat-luong.txt
Đường dẫn root rõ nhất được ghi trong freeze manifest cùng thư mục.
Không dùng ACCEPTED của freeze-v2 ngày 05-09 để nghiệm thu revision này.
Hai requests researcher 08-09 đều kết thúc host exit 1, stderr resource_exhausted,
stdout rỗng; không có research report mới và không đổi model. Request files
được giữ cạnh record này. Một lượt critic cuối sẽ ghi kết quả thật bên dưới.

Coordinator đã rà soát report cũ, sửa master thành một cửa đọc, gắn 32 WP
và 36 EX; bổ sung durability D1-D4 phân failure domains, reward capacity
reservation, fencing/room handoff, UX timeout/privacy, capacity CPU/RAM/wire
và dispatch theo dependency. Các sửa canonical chỉ là routing và hợp đồng
bổ sung; không đổi 32 trạng thái PLANNED hoặc dependency/WP tiếp theo.
DB synchronous-replication sources mới chưa được mở thành công ngày 08-09,
phải kiểm tài liệu đúng PostgreSQL version và fault injection khi P3 triển khai.
Chưa commit vì đây là tài liệu ở working tree của hai repo theo yêu cầu owner;
không stage các sửa sản phẩm khác có sẵn. Không clone/install/test game/deploy.

## Đối chiếu finding cũ và kiểm tra coordinator

- Routing AGENTS mơ hồ/nhầm sản phẩm: master R0/R3 ghi đúng subtree HH2;
  AGENTS và Start Here trỏ lại đúng TXT owner yêu cầu trong repo cạnh nhau.
- P0/P1/tools bị gộp sai: bảng đầu 32 WP theo roadmap; wave B chỉ sau P0-03,
  P1-01 song song P1-02; P1-03 không chờ hết tools, bootstrap không chờ Android.
- Link sai từ social zdoc: R0–R12 và các Markdown link đã resolve trên máy.
- Công thức network sai đơn vị room/client: chia n_clients_per_room*b_per_client;
  full-duplex tách hai hướng. CPU-time khác wall tick; packed load mới chứng
  minh rooms/node. N+1, occupancy và monthly average egress có ví dụ giả định.
- Ngày release khác ngày đọc nguồn: pin là đề xuất dựa research 05-09, không
  tuyên bố artifact đã acquire hoặc phiên bản đó luôn mới nhất.
- Master cũ có errata/status/timestamp lặp: master 08-09 viết mới thành từng
  phần append, một END sentinel; giữ bản 05-09 làm lịch sử, không chỉ dẫn thi hành.
- RPO24h vs item ACK, room journal vs mất disk: DB-D1–D4/EX07/EX29–32,
  API durable attempt/receipt và synchronous protection. Async archive/PITR
  có failure model riêng, không dùng idempotency key giả phục hồi balance.
- Thêm phòng ngừa race: reserve reward capacity trước activity và test quota
  giữa start/finish/expiry; notification <=2s chỉ yêu cầu khi đường mạng khỏe.
- Các đề xuất này là giải quyết của coordinator, không phải chữ ký critic.

coordinator-static-check.json: PASS_STATIC_ONLY, 13 source files, 32 bảng/32
heading WP, 33 dependency edges, 36 EX, 4 DB profiles, 13 R references và 7
Markdown links. Không có lỗi UTF-8/link/duplicate marker; số học ví dụ khớp.
git diff --check -- hh-3d/hh-3d-2: exit 0. Đây là kiểm tài liệu, không runtime,
không headless/gameplay/benchmark/human test. Sáu canonical files đổi so v2
được liệt kê trong report; trạng thái 32 PLANNED được giữ nguyên.

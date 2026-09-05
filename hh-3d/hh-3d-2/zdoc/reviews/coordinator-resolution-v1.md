# Reconcile hai critic — revision v2

2026-09-05. Hai critic v1 đều REVISE trên plan hash
`3477424499f1922b003cf07638503c98a84fb1acd68cc107b5e15706f9c9934a`.
Shell hash của critic bị từ chối; coordinator đã verify host 12 file nhưng
không coi đó là independent verification. V2 cho phép read-only shell hash
trong Cursor invocation, không cấp quyền sửa source.

| Finding | Cách xử lý trong canonical v2 |
|---|---|
| A1 test IDs gộp | Q01-B/F/C/W, Q03-A/R/H, Q04-L/N/C/W1/W2; roadmap Verify trỏ IDs |
| A2 cap32 mềm/cứng | 32 là gate mặc định; cap thấp hơn cần owner đổi scope, sửa contract và đo lại |
| A3 device gate | Early Windows+1 Android; final đủ 3 SKU/thermal; thiếu máy ghi gap đúng gate |
| A4 onboarding không BUILD | P0 skeleton, P2 full Solo/tut skip, P3 Solo no-login, P6 human recruitment |
| A5 cold/thermal/fallback | Warmup trong budget cold; first action sau playable; thermal thresholds final; D02 áp P5 fail |
| A6 fixture WAN | DEV_ONLY loopback-only; P6 cấm fixture auth, credential gap không mở WAN |
| A7 OS/transport | Linux room target, pin ở P0, khóa transport P3, đo đúng môi trường P6; UDP-block fail-closed |
| A8 style/font | Style guide và font/license tạo P2-02, final update P5 |
| B1 Solo house | Namespace/save riêng, không import/visit Solo, chuyển Online UI giải thích |
| B2 reservations | Reconnect30s/actor10s, active leave release, party all-or-none reserve15s, network join không giả atomic |
| B3 room reward | Pending durable journal/retry; API commit+readback rồi receipt; crash before/after test |
| B4 deletion/restore | Tombstones độc lập rollback snapshot, replay trước traffic; linking/ledger/chat/solo scope rõ |
| B5 tooling gate | P1-02 dispatch song song P1-01 sau bootstrap; P1-03 không đợi full tool; P2 mới cần tool |
| B6 clocks | Held last + ordered/dedup edges, server time cooldown, late-window schema, Q04 tolerance riêng |
| B7 thermal | Ngưỡng warm/stall áp cả late thermal route, không observe-only final |
| B8 hidden/known/block | Invisible rời Public, private giải thích; known actor ACK+epoch+2s; revoke interaction/priority |
| B9 pin/transport | Đọc trang khác khóa artifacts; P0 kiểm fullhash/checksum; P1 chỉ capability, P3 khóa production transport |
| B10 protocol/save/hash | N-only drain default, N/N-1 gated; Solo schema/migration; re-review v2 independently hash |

Coordinator bổ sung phân biệt avatar↔avatar với mua ở shop public khi chủ
offline; không lấy mutual visibility làm điều kiện phải có chủ shop Online.
Các sửa đổi là thiết kế, không code, không benchmark mới hay runtime acceptance.

# Kế hoạch đề xuất — Superagent 2D Web, Classic-first

`DOCUMENT_TYPE=WEB_ARCHITECTURE_ADVISORY`
`AUTHORITY=0`
`SOURCE_PLAN=8-9-hh3d-3/zdoc/18-9-superagent-2d-y8-plan.txt`
`SOURCE_CURRENT_VALID_WP=SA-02`
`DATE=2026-10-14`
`STATUS=PROPOSED_NO_IMPLEMENTATION`

## 1. Quyết định công nghệ

Chọn **Phaser 4.2.1 + TypeScript + Vite** làm đường Web-first. Phaser phù hợp hơn HTML/CSS/JS thuần vì đã có scene, camera, loader, animation, input, scale và hai hệ physics cho game 2D; Vite cung cấp dev server, type-aware build và static output. Pin đúng phiên bản trong `package-lock.json` hoặc lockfile tương đương; không dùng `latest` trong CI.

World không nên được dựng bằng các `<div>` CSS. Canvas/WebGL xử lý sprite, camera và gameplay view; HTML/CSS xử lý menu, HUD, settings, pause panel và nút cảm ứng. Cách chia này giữ được responsive layout mà không biến physics thành một bài toán layout DOM.

Phaser v4.2.1 là bản phát hành chính thức mới nhất được kiểm tra trong nghiên cứu ngày 14-10-2026. Nếu vertical slice phát hiện plugin hoặc công cụ nội bộ chưa tương thích, thử nghiệm riêng với Phaser 3.90; không tự động hạ phiên bản trong source chính.

## 2. Kiến trúc runtime

```text
src/
  sim/                 # pure TypeScript, không import Phaser/DOM
    world.ts           # state trận, tick 60 Hz
    input-frame.ts     # pressed/held/released + device-independent actions
    combat.ts          # hitbox, damage, knockdown, projectile, throw
    physics.ts         # collider contract và impulse policy
    rng.ts              # stream seed: spawn, spread/crit, AI
    replay.ts           # trace, snapshot, quantized hash
  client/
    phaser/             # Scene, camera, sprite/animation, asset binding
    render-snapshot.ts  # chỉ đọc state đã commit của sim
  input/
    keyboard.ts         # WASD/J/K/L/ và arrows/Numpad 1–4
    pointer-touch.ts    # Pointer Events, multi-touch, virtual controls
    gamepad.ts          # poll navigator.getGamepads khi có controller
  ui/                   # DOM/CSS menu, HUD, pause, settings
  content/              # data JSON, atlas metadata, original asset manifest
  platform/             # audio unlock, visibility, resize, fullscreen hints
  main.ts
public/
  index.html
  icons/                # chỉ thêm khi mở PWA

tests/
  sim/                  # chạy được trên Node, không cần browser
  browser/              # smoke input, resize, audio gate, pause/resume
  traces/               # input + seed + expected snapshot/hash
```

`src/sim` là nguồn sự thật. Phaser Scene chỉ chuyển input thành `InputFrame`, gọi tick và vẽ snapshot/event sau khi tick đã commit. FX, camera shake và SFX không ghi ngược vào state hoặc replay hash.

Mỗi tick dùng thứ tự cố định:

1. Lấy `InputFrame` của tick hiện tại.
2. Cập nhật state fighter (đi, sprint, jump, ladder, crouch, roll, dive).
3. Xử lý cận chiến, đạn, ném, pickup và damage.
4. Xử lý platform, pit, crate, hazard và impulse.
5. Cập nhật bot qua cùng schema input như người chơi.
6. Áp dụng luật mode, thắng/thua và pause transition.
7. Ghi snapshot lượng tử hóa, event row (`event_id`, `tick`) và hash.

Render dùng accumulator độc lập với simulation:

```text
accumulator += min(frame_delta, 250ms)
while accumulator >= 1/60s:
    sim.step(input_for_tick)
    accumulator -= 1/60s
render(sim.previous_snapshot, sim.snapshot, accumulator / (1/60s))
```

`requestAnimationFrame` chỉ điều khiển render. Không lấy số frame callback làm số đo parity. Khi tab bị ẩn, dừng hoặc giới hạn simulation theo policy đã ghi; khi quay lại phải resume từ tick rõ ràng, không chạy bù vô hạn.

## 3. Physics và determinism

Vertical slice bắt đầu bằng Arcade Physics cho fighter, sàn tĩnh, one-way platform và collider hình chữ nhật. Arcade có giới hạn shape nhưng nhẹ, dễ đo và hợp phần platform shooter đầu tiên.

Trước khi thêm thùng nổ, vật treo, kính và mảnh vỡ, chạy một spike riêng với Matter. Phaser không cho Arcade body va chạm trực tiếp với Matter body; một bản Classic phải chọn một contract thống nhất cho các body cần tương tác. Nếu Matter không đạt replay/hash trong epsilon đã ghi, giữ object interaction ở dạng impulse/state có giới hạn và ghi rõ GAP; không tuyên bố rigid-body parity chỉ vì demo nhìn giống.

Không viết lại một rigid-body engine lớn bằng UI code. Mọi số chỉnh nằm trong `content/*.json`, có mã dòng ledger. RNG tách stream và luôn nhận seed từ trace. Replay phải kiểm tra cùng build + seed + trace cho ra cùng hash; cross-device exact equality không được giả định.

## 4. Input, audio và mobile

- Chuẩn hóa mọi thiết bị về action (`left`, `right`, `jump`, `crouch`, `melee`, `shoot`, `throw`, `power`, `pause`), không để sim biết đó là phím hay ngón tay.
- Keyboard giữ keymap owner: P1 WASD + J/K/L/; P2 arrows + Numpad 1–4. Numpad không có trên nhiều laptop nên settings phải cho remap ở giai đoạn phù hợp của plan.
- Touch dùng Pointer Events, map `pointerId` cho từng ngón, xử lý `pointercancel` và đặt `touch-action: none` trên vùng control. Có nút landscape/rotate hint; không phụ thuộc `ScreenOrientation.lock`.
- Gamepad poll ở game loop, nhưng không để gamepad là điều kiện khởi động.
- Màn “Bấm để chơi” phải gọi resume AudioContext và lấy keyboard focus; không tự phát nhạc trước user gesture.
- Pause khi `visibilitychange` hoặc khi mất focus. Fullscreen chỉ là nút tùy chọn vì browser có thể từ chối request.

## 5. Lộ trình triển khai đề xuất

Các mục dưới đây là backlog của nhánh Web, không phải checkbox của plan gốc.

### WEB-01 — bootstrap và contract

Tạo Vite + TypeScript, pin Phaser, lint/typecheck, static dev server và một canvas responsive. DoD: `npm ci`, `npm run typecheck`, `npm run build` sạch; có manifest source hash; không commit `node_modules`/`dist`.

### WEB-02 — simulation phòng thử

Viết `SimulationWorld` thuần TypeScript: hai fighter hộp chữ nhật, sàn, hố, ladder placeholder, tick 60, InputFrame và seed. DoD: test Node chạy cùng trace hai lần cho cùng hash; pause không tăng tick simulation; render cadence không ảnh hưởng hash.

### WEB-03 — Classic vertical slice

Một map arena nguyên bản có tầng, ladder, one-way platform, pit, cover, crate; hai fighter; đi/chạy/nhảy/rơi/crouch/ladder/roll cơ bản; đấm, bắn, ném, pickup; 1P-vs-bot và 2P local; menu → VS → kết quả → replay. DoD: kịch bản input thật, snapshot sau mọi transition, không dùng fixture/teleport làm bằng chứng duy nhất.

### WEB-04 — object/hazard spike

Đo Arcade trước; Matter spike riêng cho thùng nổ, vật treo, kính, lửa và impulse. DoD: chọn một physics contract, ghi epsilon và replay evidence; nếu chưa đạt thì giữ GAP và không mở rộng content.

### WEB-05 — touch, responsive và presentation

Thêm touch overlay đa chạm, HUD hai người, pause/settings, landscape hint, original pixel fighter/props/map và audio cue. DoD: Chrome/Edge/Firefox desktop, Safari macOS/iOS, Chrome Android; console không có lỗi; audio chỉ phát sau gesture; không cắt HUD ở 960×540, 1280×720 và viewport điện thoại.

### WEB-06 — parity review Classic

Ánh xạ R01–R15 của plan gốc sang test của Web. Tầng A phải đo bằng cùng rig; tầng B phải qua input thật và owner side-by-side; tầng C chỉ ghi APPROX có nguồn + owner OK. DoD: không còn dòng Web `UNVERIFIED` chặn Classic; GAP gameplay phải có chủ sở hữu và bước sửa.

### WEB-07 — static release candidate

`vite build` ra bundle static, nén Brotli/gzip ở CDN, HTTPS, versioned assets. PWA manifest/service worker chỉ thêm sau khi cache invalidation và offline test có bằng chứng. Không đưa WebSocket server vào static host.

### WEB-08 — hậu Classic, chỉ khi owner mở

Online dùng server authoritative lâu dài qua WebSocket trước; WebRTC/WebTransport chỉ là spike có browser matrix. PixiJS custom renderer, PlayCanvas/Three.js 2.5D, Hero/MUGEN và chỉnh trang phục giữ ngoài MVP.

## 6. Ma trận nghiệm thu Web

| Nhóm | Kiểm tra bắt buộc | Bằng chứng cần giữ |
|---|---|---|
| Simulation | 60 tick, seed + trace + snapshot/hash, pause không chạy simulation | log test Node + trace JSON |
| Input | pressed/held/released, hai người cùng lúc, touch multi-pointer, gamepad tùy chọn | input trace + browser smoke |
| Gameplay | movement, ladder, pit, melee, shoot, throw, pickup, hazard, bot, VS/result/restart | replay + transition snapshots |
| Browser | Chrome/Edge/Firefox desktop; Safari macOS/iOS; Chrome Android | matrix có browser/version/device |
| Performance | p95/p99 theo Q2 của plan gốc; tải lần đầu + memory theo Q5 | profiling raw + source hash |
| Presentation | authored assets, HUD, SFX/audio unlock, responsive/landscape hint | clip runtime và asset manifest |
| Release | static HTTPS, no console error/warning, actual exit/build hash | build manifest + deploy receipt |

Một banner PASS, ảnh tĩnh hoặc file asset tồn tại không thay cho kịch bản input, postcondition và actual exit. Không tick SA-04, SA-11, SA-12 hay SA-13 từ tài liệu này.

## 7. Hosting và nâng cấp

Giai đoạn đầu dùng static HTTPS (GitHub Pages, Cloudflare Pages, Netlify, Vercel hoặc CDN tương đương) cho single-player/local 2P. PWA cache dùng service worker và cache version; IndexedDB lưu settings/replay nhỏ, tránh ghi snapshot thường xuyên vào synchronous localStorage.

Khi mở online, frontend static vẫn tách khỏi room service có state lâu dài. WebSocket là đường đầu tiên để server-authoritative; server phải có room lease, tick/sequence, reconnect và chống gian lận. Không giả định serverless function ngắn hạn là authoritative game server.

Không bật SharedArrayBuffer/threads chỉ để tối ưu sớm. Nếu cần, phải kiểm tra HTTPS, COOP/COEP/cross-origin isolation và third-party asset compatibility trong một gate riêng.

## 8. Rủi ro cần ghi trước khi code

1. Phaser physics tiện nhưng không tự cung cấp determinism/replay contract; `src/sim` phải độc lập.
2. Phaser Arcade và Matter không trộn collision; chọn contract sau WEB-04.
3. WebGPU không phải baseline; WebGL2 trước, Canvas fallback nếu renderer cho phép.
4. Mobile Safari, audio autoplay, orientation/fullscreen và tab visibility có hành vi riêng; test trên máy thật.
5. Build Web khác bản Godot hiện hành không được dùng để suy ra parity; mọi claim quay về ledger và owner side-by-side.
6. Online là dự án sau Classic, không thêm dependency backend vào vertical slice.

## 9. Nguồn chính thức được dùng

Xem [web-stack-research.md](web-stack-research.md) và [source-register.tsv](source-register.tsv). Nguồn được kiểm tra ngày 2026-10-14; tài liệu browser/engine có thể thay đổi, nên phải re-check trước khi pin dependency hoặc phát hành.

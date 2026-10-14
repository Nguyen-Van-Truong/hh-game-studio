# SUPERAGENT 2D WEB — PLAN RIÊNG, CLASSIC-FIRST

`DOCUMENT_TYPE=WEB_PRODUCT_PLAN`
`AUTHORITY=0`
`SCOPE=8-9-hh3d-3/14-10superagent-2d-web`
`SOURCE_PLAN=8-9-hh3d-3/zdoc/18-9-superagent-2d-y8-plan.txt`
`SOURCE_CURRENT_VALID_WP=SA-02`
`DATE=2026-10-14`
`STATUS=WEB-01_WEB-02_IMPLEMENTED_VERTICAL_SLICE_RUNNING`

## Mục tiêu

Tạo một bản Web độc lập, chơi được ngay trong browser, giữ nhịp của arena platform shooter Classic trước khi thêm online, Hero mode, chỉnh trang phục hoặc 2.5D/3D. Cơ chế có thể tham khảo hành vi phổ biến của thể loại và bản Y8 theo reference ledger của plan gốc; tên, code, art, âm thanh, UI và layout map cụ thể đều phải nguyên bản.

Bản đầu là **Superagent // Neon Relay**: một Relay Yard nguyên bản với hai fighter, platform, ladder, pit/hazard, crate, shard pickup, đấm, bắn, ném grenade, bot, HUD, pause và restart. Đây là vertical slice quan sát được, chưa phải claim Classic parity hay release candidate.

## Quyết định stack

- Phaser 4.2.1, pin exact trong `package-lock.json`.
- TypeScript strict + Vite 8; `src/sim` giữ simulation độc lập khỏi Phaser/DOM.
- Phaser Canvas/WebGL cho world; DOM/CSS cho start gate, HUD shell và touch overlay.
- Web Audio tổng hợp SFX sau user gesture; VFX procedural/pool trong event boundary.
- Fixed-step 60 Hz, render bằng `requestAnimationFrame`, seed/replay/hash là gate kế tiếp.

## Hiện trạng đã làm

### WEB-01 — bootstrap

Đã có `package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/style.css`. Lệnh kiểm tra:

```text
npm ci
npm run typecheck
npm run build
```

Build hiện tạo bundle static `dist/`. Phaser làm bundle lớn hơn ngưỡng cảnh báo mặc định, nhưng output hiện khoảng 365 kB gzip; phải đo Q5 trên máy thật trước khi tối ưu/chia chunk.

### WEB-02 — vertical slice

Đã có `src/main.ts` với:

- Simulation tick 60 Hz tách khỏi render cadence.
- P1 WASD + J/K/L/; P2 arrows + Numpad 1–4; touch buttons map vào action P1.
- Di chuyển, nhảy, ladder, crouch/slow, đấm, bắn, grenade, pickup shard, bot, damage/knockback, pit reset, crate break.
- HUD HP/ammo/relay, pause P, restart R, round-over state.
- Neon Relay Yard có background depth layers, original fighter silhouettes, ladder/platform/cover/crate, shard identity, muzzle/hit/landing/explosion particles và camera shake.
- Web Audio SFX tổng hợp: deploy, jump, shot, hit, pickup, explosion; audio chỉ unlock sau `CLICK TO DEPLOY`.

Runtime smoke ngày 2026-10-14 đã thấy trong browser: start gate, match live, P1 bắn trúng P2, damage text, grenade VFX, round-over banner và restart path.

## Chuẩn hình/tiếng và pipeline AI

Style hiện tại là **Neon Relay Yard**: nền xanh đậm ít tương phản, kiến trúc mid-layer, gameplay plane xanh slate, fighter cyan/amber đối lập với foe rose, hazard magenta-red, pickup mint. Fighter có outline, accent và silhouette khác nhau; không chỉ phân biệt bằng màu.

AI chỉ được dùng cho moodboard/concept/reference ánh sáng hoặc bố cục. Nếu dùng output AI sau này:

1. Ghi prompt, model, seed, ngày, hash và nguồn vào provenance.
2. Không prompt bắt chước Superfighters, nhân vật/thương hiệu có chủ hoặc artist cụ thể.
3. Redraw/author lại layer, pose, pivot, anchor và atlas trước khi đưa vào runtime.
4. Kiểm alpha, silhouette, frame consistency, watermark/logo và license.
5. Ảnh AI/concept không được coi là bằng chứng art runtime; clip thật và manifest asset mới là bằng chứng.

VFX phải gắn `event_id/tick`, có anticipation → contact → recovery, cap số hạt/voice trên mobile, có reduced-motion toggle về sau. SFX có visual fallback khi mute; pause/mute không làm thay đổi simulation hash.

## Các gate tiếp theo

### WEB-03 — deterministic contract

Tách `src/sim` thành module thuần TypeScript, thêm trace JSON, seed, quantized snapshot/hash và test chạy hai lần. Pause không tăng simulation tick; render 60/120/144 Hz không đổi kết quả.

### WEB-04 — gameplay expansion

Thêm inventory/weapon identity, one-way drop, healing, bullet-time/power item theo ledger. Chạy physics spike cho crates, glass, fire và impulse; Arcade/Matter không trộn body. Không claim rigid-body parity nếu replay epsilon chưa đạt.

### WEB-05 — touch/presentation quality

Kiểm Chrome/Edge/Firefox desktop, Safari macOS/iOS và Chrome Android. Thêm multi-touch pointer lifecycle, safe-area/landscape hint, high-contrast/reduced-motion, authored fighter atlas và audio clip review.

### WEB-06 — Classic review

Đối chiếu R01–R15 của plan gốc; tầng A đo cùng rig, tầng B chơi song song bằng input thật, tầng C ghi APPROX có nguồn và owner OK. Chưa tick SA-04/SA-11/SA-12/SA-13 từ plan gốc.

### WEB-07 — publish

Static HTTPS, versioned assets, PWA manifest/service worker sau khi có cache invalidation test. Online authoritative WebSocket chỉ mở sau Classic; không nhét backend vào MVP.

## Verify hiện tại

- `npm ci`: PASS, không phát hiện lỗ hổng trong dependency audit tại thời điểm chạy.
- `npm run typecheck`: PASS.
- `npm run build`: PASS; Vite chỉ báo bundle lớn hơn ngưỡng mặc định, đã ghi nhận để xử lý ở WEB-07/Q5.
- Browser smoke trên `http://127.0.0.1:5175/`: PASS cho start, render, input, hit, VFX/SFX path, round-over và restart.
- Chưa có parity measurement Y8, critic signature, owner approval hoặc release claim.

## Không được làm trong plan này

Không rip asset/code/screenshot/audio, không đưa tên Superfighters vào metadata phát hành, không sửa plan gốc, không tick checkbox gốc, không mở SA-14/online trước Classic, và không xem ảnh AI hoặc một banner PASS là nghiệm thu gameplay.

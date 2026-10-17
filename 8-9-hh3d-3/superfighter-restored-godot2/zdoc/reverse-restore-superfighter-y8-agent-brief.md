# Handoff: reverse/restore trải nghiệm arena shooter kiểu Y8

Ngày lập: 2026-10-17
Phạm vi thư mục: `8-9-hh3d-3/superfighter-restored-godot2/`
Kế hoạch: [`reverse-restore-superfighter-y8-plan.txt`](./reverse-restore-superfighter-y8-plan.txt)

## Mục tiêu

Agent kế tiếp xây dựng một game Godot 2D arena platform shooter có các nhịp chức năng quan sát được từ bản Y8: hai người cùng bàn phím, di chuyển trên sàn và platform, thang, rơi qua sàn, pickup, vũ khí, va chạm, hazard, pit, vòng đấu, pause, restart và kết quả trận. Mã nguồn, cấu trúc dữ liệu, art, audio, tên hiển thị và layout cụ thể phải do project này tự tạo.

Thư mục này là một project phục hồi độc lập. Tài liệu này là handoff cục bộ, không thay thế các plan sản phẩm khác trong `8-9-hh3d-3/zdoc/`, không mở hoặc tick WP của plan cha, và không tạo claim owner acceptance.

## Quyết định công nghệ

- Engine: Godot stock 4.7.1-stable theo route Vault Fighters của repo.
- Ngôn ngữ: typed GDScript.
- Physics: Godot 2D qua adapter riêng; gameplay chạy fixed 60 Hz.
- Determinism: input trace có `pressed/held/released`, seed, tick và snapshot/hash.
- Chỉ quan sát hành vi công khai của bản Y8 hoặc nguồn công khai trong phiên được ghi rõ. SWF/FFDec content nếu có là quarantine-only; không tải, trace, reverse-engineer, copy, bundle, capture hoặc dùng làm runtime/evidence.
- File ActionScript decompile hoặc SWF cũ chỉ là historical lead/quarantine; không dùng làm `OBSERVED`, `MATCHED`, evidence, source closure hay runtime, và không coi là source build được.
- Haxe/OpenFL, Apache Royale, C#/MonoGame không nằm trong stack của project này.

## Phân lớp bắt buộc

1. `game/core/`: state, rules, input frame, replay, seed, snapshot.
2. `game/world/`: map topology, platform, ladder, pit, hazard, pickup spawn.
3. `game/fighter/`: state fighter, intent, hitbox/hurtbox, physics adapter.
4. `game/combat/`: weapon, projectile, damage, knockback, fire và round rules.
5. `game/presentation/`: scene, animation, camera, HUD, particles, audio. Presentation không ghi vào gameplay hash.
6. `data/`: tuning/map/weapon dưới schema có version và hash.
7. `tests/` và `evidence/`: test headless, replay, logs, source manifest và stills.

## Luật reference và clean-room

- Ghi observation hành vi công khai vào ledger với URL hoặc nguồn, timestamp, scenario, input và kết quả. Không lưu screenshot/video của bản Y8 vào product hoặc evidence. Không biến suy đoán thành fact.
- Không bundle SWF, bytecode, HTML5 package, decompiled source, sprite/audio rip hoặc title card vào bản phát hành.
- Asset reference chỉ được quarantine ngoài product root và ngoài runtime/evidence. Project dùng art/audio nguyên bản hoặc nguồn có giấy phép được ghi trong manifest.
- Folder có chữ `superfighter` là tên kỹ thuật của handoff; title, logo, metadata phát hành dùng `Vault Fighters` trừ khi owner mở brand/legal gate riêng.
- Nếu muốn khôi phục nguyên hình hoặc dùng asset reference, dừng và ghi gap report để owner/legal quyết định; agent không tự mở waiver.

## Invariants kế thừa

Semantic command có schema/validate, unique `command_id` và dedup; ACK sau postcondition đọc lại; path allowlist và chặn traversal/symlink; một writer/file với lease; checkpoint/rollback; immutable Play snapshot; pause/stop drain; atomic save với schema/hash; fixed 60 Hz input + seed; deterministic physics/combat; typed GDScript; timestamp/run/trace/source hash và repro command.

## Tiêu chuẩn bằng chứng

Mỗi run phải ghi tối thiểu: `run_id`, `command_id`, timestamp, seed, map, mode, input trace, source hash, engine path/version, process exit thực tế và thư mục evidence. Claim gameplay phải có postcondition đọc lại từ runtime. Banner PASS, ảnh tĩnh, fixture teleport hoặc force-kill không đủ làm bằng chứng E2E.

Mỗi tính năng đi qua ba trạng thái: `UNVERIFIED` → `IMPLEMENTED` → `OBSERVED/MATCHED`. `MATCHED` chỉ dùng khi có observation hoặc đo cùng cách với reference và có tolerance. Nếu không đo được, ghi `APPROX` và nêu giới hạn.

## Cách agent tiếp nhận việc

1. Đọc file này rồi đọc plan `.txt` cùng thư mục.
2. Kiểm tra `git status`, baseline hash, process/lock và source closure trước khi sửa.
3. Chỉ làm WP đầu tiên chưa hoàn tất; không nhảy cóc và không tự tick checkbox.
4. Một writer cho mỗi file; mutation source phải atomic và có checkpoint trước thay đổi phá huỷ.
5. Mỗi WP phải chạy verify riêng, lưu raw output và actual exit; source đổi sau evidence thì phải chạy lại.
6. Không chạy hai Godot worker trên cùng project path.
7. Kết thúc WP bằng handoff gồm: thay đổi, test, evidence path, source hash, gap và next step.

## Stop conditions

Dừng WP và ghi `GAP` nếu gặp một trong các tình huống: thiếu postcondition, warning/error chưa giải thích, source hash không khớp evidence, process không có exit thực, asset không rõ provenance, path vượt product root, reference bị đưa vào runtime release, hoặc yêu cầu làm giống nguyên layout/title/asset đến mức cần review pháp lý.





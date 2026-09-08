Tôi sẽ đọc các file zdoc trong repo, kiểm tra research JSON trong TEMP nếu có, rồi đối chiếu tối đa 3–5 tài liệu official Godot/Blender.Đã thấy đủ 3 file zdoc và JSON research. Tiếp theo đọc nội dung chúng và mở tối đa 5 trang official.Đang mở đúng 5 trang official và đối chiếu kiến trúc/tool hiện có trong repo.# CRITIC — Godot+Blender agent + HH World 3D (một TXT)

ROLE=researcher/critic | MODEL=cursor-grok-4.6-xhigh-fast | DATE=2026-09-08  
SCOPE: `hh-3d/hh-3d-2/zdoc/04-GODOT-TOOLS.md`, `05-QUALITY-GATES.md`, `08-AGENT-WORKFLOW.md`. Coordinator là người viết duy nhất một TXT tự chứa tại sibling `hoan-hao/zdoc/` (không nhiều plan mảnh). Critic không tick, không fork, không chứng minh “mọi AI làm được”.

## Lệch so với 04/05/08

`04` T01–T04 khóa pin Godot, command Godot, lease, UndoRedo, staged save, ACK đọc lại — **đủ hướng Godot**, thiếu catalog máy đọc (`capabilities.describe` / schema_version wire / allowlist verb). T05 chỉ pipeline art; **không** protocol Blender, không writer `.blend`, không job `--background`, không bake IK/constraint. `05` đo gameplay/GPU/ledger, **không** OOM/timeout/Unicode của DCC, không fingerprint GLB, không rollback nửa-publish. `06-ROADMAP` P1-01 = addon Godot; **không WP Blender adapter**. Song song hiện tại là P1-01∥P1-02, chưa “tools baseline ∥ slice chơi”. `08` không có evidence job Blender hay proof từng adapter. Vault Fighters 2D + `docs/godot-agent` (163 action, `capabilities.describe`) là **mẫu hợp đồng**, không phải bằng chứng 3D/mobile. `demos/blender-agent-demo` (`blender --background --python`) là script tự do — **không** adapter đã verify.

Pin PRIMARY (trang live, không suy từ repo): Godot **4.7.2-stable** nút Download Windows 18 Aug 2026; **4.7.1-stable** còn archive 14 Jul 2026. Blender **5.2.1 LTS** 25 Aug 2026; song song **4.5.13 LTS**. Không bịa bản “mới hơn”.

## Thứ tự (bắt buộc ghi trong TXT)

1. **Không fork core / không C++ module** trừ gap report + owner (T01/T02). Stock EditorPlugin + bpy isolated.  
2. **P0 lock** Godot 4.7.2 + Blender 5.2.1 + templates/SHA/`--version` (tách cache VF).  
3. **Tools baseline** (C1–C4, C7, C11) **song song** slice Solo sớm (controller/plaza dummy) trên **lease/file/runtime path khác**; P1-01 Godot mutation không chặn P1-02/P2-01 generator. Semantic mutation P2 chỉ sau adapter Godot PASS.  
4. **Pipeline GLB+contract xương** (C5–C6, C8–C10) trước bulk map VN.  
5. **Q01-B Android thật** trước claim mobile; evidence 2D VF / headless **không** thay GPU 3D.

---

## 10 điều must-have

**C1 — Discovery/schema/capability (không “AI hiểu editor”)**  
Hợp đồng JSON: `schema_version`, `protocol_id`, `capabilities.describe` (version/class/property/method/action + 4 invalid/kind như `docs/godot-agent/CONTRACT_MATRIX.md`). Verb allowlist; reject unknown/`__hh_unknown`.  
VALIDATE: fixture dương + missing/unknown/type/bounds; mismatch schema → 0 mutation.  
EXPECTED: client chỉ thấy verb đã pin; MCP không thêm eval ẩn.

**C2 — Main thread vs process tách**  
Godot: mọi Object/EditorPlugin/UndoRedo trên main thread; worker queue; không stale ObjectID sau reload (T03). Blender (docs threading): **không** thread Python gọi `bpy` (crash); thread chỉ khi main bị block rồi `join` trước `bpy`; Timer sống sau script = unsupported. UI: queue vào luồng chính process UI. Batch: **process `--background` riêng**, 1 writer/file. Không mở `bpy.app.timers` trong lượt này — không claim API timer cụ thể.  
VALIDATE: stress queue Godot; job Blender song song trên **hai file**; cố `bpy` từ thread → FAIL/crash có log, không PASS.  
EXPECTED: 0 mutation chéo process; host PID/exit/leftover.

**C3 — Cấm remote/arbitrary eval**  
Không `exec`/`eval`/`bpy.ops.script`/`script.write` unbounded, không `--python` string từ LLM. Chỉ operator đã schema + path allowlist. Demo `build_gaming_room.py` không được promote thành tool agent.  
VALIDATE: payload script/path traversal/symlink → reject, hash nguồn không đổi.  
EXPECTED: không có verb “run_python”.

**C4 — Idempotent retry ≠ atomic commit**  
Cùng `command_id`+payload → cùng result; khác payload → reject (T03). UndoRedo **không** atomic đa file; `.blend` ghi binary không giả transaction Godot. Staged: journal → temp → fsync → rename; crash giữa chừng = INCOMPLETE + rollback proof, không ACK.  
VALIDATE: kill giữa save scene; kill giữa `bpy.ops.wm.save_as_mainfile`; retry cùng id.  
EXPECTED: không partial `.tscn`/`.blend`; không nhân node/object.

**C5 — Một writer `.blend` vs sở hữu scene Godot**  
Lease path+base_hash+expiry cho từng `.blend`. Godot **không** ghi nguồn DCC; inherited `.tscn` gameplay; reimport chỉ khi GLB staged commit. Không commit `.blend` vào game tree nếu CI thiếu binary pin (docs: `.blend` import gọi Blender; không có trên editor Android/web).  
VALIDATE: hai writer cùng file → conflict; Godot mở `.blend` khi lease Blender cầm → chặn.  
EXPECTED: 1 owner/file; reimport sau commit GLB, không đua.

**C6 — GLB staged + fingerprint ngữ nghĩa**  
Xuất GLB pin (không tin import `.blend` trong CI). Staging dir → validate → copy atomic vào `res://` → sidecar import → catalog. **Không** đòi byte-identical GLB (timestamp/sparse/Draco). Fingerprint: triangle, AABB, material slots, bone names, bind pose, clip names/length, tex hash.  
VALIDATE: đổi 1 bone name / clip / material → fingerprint FAIL; re-export không đổi mesh → fingerprint PASS dù SHA file lệch (ghi delta).  
EXPECTED: importer Godot đọc GLB đã freeze; preset import hash trong manifest.

**C7 — Rollback nửa-publish**  
Thứ tự: freeze nguồn → GLB+fingerprint → Godot import → catalog/license. Fail bất kỳ bước → revert file đã copy, journal `FAILED`, không catalog “có asset”.  
VALIDATE: crash sau copy GLB trước `.import`/catalog; restore khớp base_hash.  
EXPECTED: tree sạch hoặc checkpoint đã chứng minh; không hero nửa-import.

**C8 — Manifest license + an toàn path/script/link**  
Mỗi asset: license, nguồn, hash, author, allow-ship. Chặn auto-run script, linked `.blend` ngoài allowlist, path Unicode/space/junction (T03). Addon/exporter chỉ bản lock.  
VALIDATE: path `../`, junction, `.blend` link ngoài, Python auto; Unicode tên file.  
EXPECTED: reject; credits/release chứa license; 0 secret.

**C9 — Pin Python/addons/exporter + OOM/timeout**  
Lock: Blender blender.org 5.2.1 (không distro/Flatpak — Godot formats), addon glTF built-in (manual 5.2 LTS: enable mặc định), Godot 4.7.2 standard **không .NET**, SHA, `blender --version`. Không CPython hệ thống cho `bpy`. Job: timeout, RAM cap, hủy, log không token.  
VALIDATE: mismatch version fail-closed; job quá hạn/OOM = FAIL có leftover.  
EXPECTED: `tools/engine.lock.json` tái tạo; 0 “latest”.

**C10 — Contract xương/LOD/anim + bake**  
glTF 5.2: mesh→triangle; Principled/Unlit; punctual lights; skinning; keyframe object/pose/shape. **Bỏ** anim physics/lights/materials. Procedural material phải bake (AO qua `glTF Material Output`; normal bake tangent). IK/constraint/driver: bake pose/action trước export; rest T-pose; deformation bones; influences 4 hoặc 8. LOD là mesh/catalog Godot, không suy exporter tạo LOD. Godot: blend shapes cần Armature “Export Deformation Bones Only” = Enabled (docs formats). Bone/clip names = catalog.  
VALIDATE: fixture IK không bake → clip/pose lệch; bake → fingerprint xương+clip khớp; LOD pop đo Q02; look-dev Q03-R.  
EXPECTED: 1 hero contract; bulk sau P2-02.

**C11 — Proof từng adapter, tái sử dụng đã verify**  
Adapter tách: `godot.editor`, `blender.bg`, `import.stage`. Mỗi cái: matrix C1 + 1 mutation có readback. Copy quy trình `hh-godot-agent/1`, **không** copy product VF, không GDExtension/fork vì “agent hai editor”. MCP = vỏ.  
VALIDATE: mỗi adapter PASS độc lập; tuyên bố “plugin làm được 3D mobile” không có Q01-B → INSUFFICIENT.  
EXPECTED: gap rõ verb chưa có; không hứa mọi model AI.

---

## Nguồn / kết quả (truy cập 2026-09-08)

Mở tối đa 5 trang official lượt này:  
[1] https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html — **OK** (docs 4.7; glTF khuyến nghị; `.blend`=gọi Blender≥3.0, tốt ≥3.5; blender.org; không Android/web editor).  
[2] https://docs.blender.org/api/current/info_gotchas_threading.html — **OK** (Python threads + bpy không hỗ trợ).  
[3] https://docs.blender.org/manual/en/latest/addons/import_export/scene_gltf2.html — **FAIL 404**. Retry cùng tài liệu: https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html — **OK** (nhãn Blender 5.2 LTS; bake AO/normal; anim chỉ transform/pose/shape keys).  
[4] https://docs.godotengine.org/en/stable/classes/class_editorplugin.html — **OK** (dump lớn; `get_undo_redo` / post-import; **không** câu “main thread only” trên trang này).  
[5] https://www.blender.org/download/lts/ — **OK** (5.2.1 / 4.5.13, 25 Aug 2026).  

Phiên bản Godot: WebSearch + research `%TEMP%/hh2-0809-godot-blender-research.json` (cùng ngày): https://godotengine.org/download/windows/ = **4.7.2**; archive 4.7.1 còn. Không fetch thêm download page lượt này (giới hạn 5).  

Không mở: Thread-safe APIs Godot, `bpy.app.timers`, CLI Blender (CLI nằm research JSON trước). Không chạy Godot/Blender, không đo Play Together.

WEB_VERIFIED: **partial** | fail_404=[3 old glTF path] | success=[1][2][3 retry][4][5]  
MODEL_REQUESTED: cursor-grok-4.6-xhigh-fast  
VERDICT: TXT coordinator phải nhúng C1–C11 + thứ tự trên; `04/05/08` chưa đủ Blender-agent; 2D VF ≠ 3D mobile.

# Điều phối Cursor và bằng chứng

## W01 — Model và phân vai bắt buộc

Coordinator: quyết định, chia việc, sửa plan, kiểm tra diff/report/evidence.
Worker: implement/test/play/fix trong file lease. Researcher/critic: đọc và
search khi cần, không sửa source của implementer. Tất cả worker/researcher/
critic gọi **Cursor CLI `cursor-grok-4.6-xhigh-fast`**; không Composer/Auto,
model fallback hoặc Task/Explore/subagent không ghim đúng model. Không tự đổi
qua model khác để tiết kiệm hay vượt lỗi quota. CLI thiếu model/auth thì báo
gap cụ thể; không dump token hay account details vào evidence.

Trước dispatch: `agent --help` và `agent --list-models` để xác minh flags/model
(cache kết quả cùng phiên nếu không đổi version). `agent login` đã có từ owner;
không bắt đăng nhập lại khi chưa có lỗi auth thật. Credentials ở tool config.
Read/research ưu tiên `--mode ask --print`; worker triển khai dùng mode thích
hợp với quyền đã có. Không ghi `--force` chung cho mọi việc; chỉ sử dụng theo
scope đã được cho phép, không vượt blocked harmful action hoặc secrets gate.
Không coi `--mode ask` là filesystem sandbox; review phải kiểm tra Git sau.

Không coordinator sửa file đang giao cho worker. Parallel chỉ khi files và
runtime paths độc lập; dependency/merge/critic theo thứ tự. Một worker thực
hiện test script và ghi evidence; critic không chạy cùng official folder làm
ghi đè. Critic có thể tái lập bằng snapshot riêng, gắn run riêng.

## W02 — Task contract bắt buộc

Mỗi prompt phải đủ thông tin, không chỉ “đọc plan rồi làm tiếp”:

```text
ROLE=implementer | researcher | critic
MODEL=cursor-grok-4.6-xhigh-fast; no fallback/subagents/Composer
WORKSPACE=<absolute root>; PRODUCT_ROOT=<absolute hh-3d-2>
WP_ID=<current WP>; AUTHORIZATION=<owner request and allowed scope>
BASE_COMMIT=<git>; SOURCE_MANIFEST=<hash>; PLAN_REVISION=<hash>
READ=<AGENTS, PROGRESS, current WP and exact contracts>
GOAL=<one concrete player/tool behavior>
ALLOWED_FILES=<exact files>; FORBIDDEN=<all outside lease/other products>
LEASE=<owner, expiry, base hashes, reconcile rule>
INPUTS=<schema/assets/seed/config>; DELIVERABLES=<source + evidence>
VERIFY=<actual commands + expected postconditions + required real-input route>
QUALITY=<Q IDs, device matrix, current thresholds; no invented results>
STOP=<scope breach, conflicting writer, secrets/publish/legal/major-goal gate>
REPORT=<diff/tests/exit/source hash/gaps/model requested; no tick>
```

Đường dẫn/shell args có dấu/space phải quote đúng. Prompt dài lưu UTF-8 file;
đọc string truyền thành một argument, không interpolate thành shell code.
Không paste secrets vào prompt/log. CLI output/exit được host capture; tool
timeout hoặc truncated report không phải candidate đầy đủ.

## W03 — Evidence contract

Mỗi WP/candidate có run_id duy nhất (date/time+sequence), command_id per action,
seed/map/mode, baseline and complete runtime source manifest (code/scenes/
shaders/assets/import settings/protocol/config), artifact/build/protocol hash,
engine lock, actual test invocation, process roles/PIDs/start/exit/leftovers,
timestamps, raw telemetry and parsed outcomes, input trace, screenshots/video,
expected/observed postconditions và known limitations.

`source_hash` là SHA-256 trên manifest đã sort theo path với từng file hash,
không chỉ git HEAD khi source dirty. Official package frozen trước run;
thay source/asset/config → new candidate/run ID, critic lại đúng hash.
Không hash evidence output như runtime source; không bỏ shader/catalog nhập
ngoài closure để package có vẻ sạch. Packer kiểm tra missing/mismatch/stale,
run config/hash, parsed exits, explained warning policy, path roots và schema.

Mọi run có timeout, cancellation và cleanup proof. Exit 0 chưa đủ nếu evidence
thiếu. Số FPS/CCU trong report phải trỏ raw run và loại test; fixture/teleport/
render bot không là sole E2E/network/human proof. Log không chứa token/email/
chat private. Retention media và anonymization có policy, không auto-upload.

## W04 — Review/acceptance

1. Worker đóng lease candidate, báo diff/evidence/gap; không tick.
2. Coordinator kiểm scope, source hash, DoD/Q requirements trước critic.
3. Independent Cursor critic đọc source+tests+evidence, tìm counterexample;
   chỉ rõ file/line/impact/repro, verdict ACCEPT/REVISE/INSUFFICIENT_EVIDENCE.
   2 critics cho các WP rủi ro đã ghi roadmap. Không giả “hai người” khi một
   worker tự chia hai vai trong một report; sessions riêng, không copy verdict.
4. Coordinator reconcile mọi finding. Source sửa → critic lại frozen hash mới;
   một TICK=yes cũ không chuyển được sang build khác.
5. Coordinator cập nhật một hàng roadmap và PROGRESS pointer/current grant;
   checkpoint riêng WP khi thích hợp. Không auto stage `git add .`; scope exact.

Một WP một checkpoint/commit nếu được thực hiện; prefix `H2-Pn-nn: ...`.
Không include unrelated dirty files/cache/.godot/build output/reference assets.
Nếu chưa commit ghi lý do trong handoff. Documentation planning lần này có
thể giữ working tree để owner review; không claim implementation checkpoint.

## W05 — Gap handling và điều phối bền vững

Khi fail: ghi reproduction, expected/actual, scope bị dừng, nguyên nhân biết/
chưa biết, file lease và next experiment. Continue phần độc lập nếu coordinator
dispatch rõ, không nâng acceptance theo phần đang thiếu.
Owner chỉ cần quyết định khi thiếu secret/tiền, ký/public publish, legal/brand,
hoặc đổi mục tiêu lớn. Thực hiện đủ việc chuẩn bị trước khi hỏi. Missing human/
device là evidence gap cần đầu vào thật, không diễn thành approval cho code.

Stop/cancel worker ưu tiên; không tự resume task user đã dừng. Khi chuyển agent,
handoff ghi next WP, exact source/plan hash, active processes/ports/user dirs,
leases, tests đã pass, unresolved failures, ai đang chờ user. Không wake/monitor
hay tạo task tự chạy sau này trừ khi owner yêu cầu automation.

## W06 — Tự kiểm tra tài liệu

Trước handoff plan: kiểm local links, unique WP IDs, dependency IDs tồn tại,
không cycle, PROGRESS pointer khớp WP đầu chưa ACCEPTED, không hai nguồn ticks,
scope root đúng, mọi gate có Verify/DoD và không gán human/engine/runtime PASS.
Review plan là review thiết kế; không có source runtime mới để benchmark.

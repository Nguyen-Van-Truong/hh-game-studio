# HH3D S17 — GT-01 in progress, acceptance pending

The two canonical TXT plans are the only progress authority. GT-01 remains
IN_PROGRESS; GT-02 and HH World implementation have not opened. Owner permission
does not substitute for runtime evidence, critic decisions, legal or human review.

## S17 (10-09-2026, 11:05 Asia/Saigon) — audit độc lập của coordinator thứ hai

Freeze `freeze-s17.json`: tools `a29ef954…2043` (69431 B), game
`cc17beb8…eba3e` (205771 B), aggregate `853d3578…5ab6`. `static-s17.json`
PASS_STATIC_ONLY (0 lỗi, 0 warning); `selfcheck-s17.json` 31/31 mutation test;
`negative-s16-snapshot-under-s17.json` cho thấy S16 fail đúng 9 check S17 mới.
Validator r4 (S8) chạy trên S17 chỉ báo các khác biệt đã biết (owner
authorization, IN_PROGRESS, check Codex S13 đã lỗi thời); mọi closure S6–S8
(LEGAL-VN, catalog shop, SCALE-LOCKS, EX45–EX53, Q01-T, profile số) vẫn PASS.
Snapshot trước sửa: `before-s17/`; diff: `s16-to-s17-*.diff`.

Phát hiện và cách sửa trong S17 (plan chỉ, không đụng `studio/` đang leased):

1. Chưa có verdict critic thiết kế nào ACCEPT từ S6 đến S16. S6/S7 hai critic
   REVISE; S8 bị quota; S9 có request nhưng không có output; S10–S13 không có
   critic; S14–S16 các worker audit Grok bị REJECT vì không nộp report. GT-01
   mở bằng quyền owner, không phải bằng gate critic. S17 ghi header
   `PLAN_DESIGN_CRITICS=NO_ACCEPTED_VERDICT_S6_TO_S16` ở cả hai plan để người
   đọc bảng đầu file không hiểu nhầm; validator từ chối giá trị ACCEPTED.
2. Pin Godot trôi: plan nói ứng viên 4.7.2 nhưng hai ngày evidence GT-01 chạy
   trên 4.7.1 của tooling Vault Fighters, lock ghi `CANDIDATE_GAP`, còn
   `test_gt01.py` lại ép `4.7.1-stable`. Owner đã chọn "Godot stock 4.7.2";
   trang archive official xác nhận 4.7.2-stable tồn tại (18-08-2026). S17 chốt
   `GT01_PIN_DECISION=GODOT_4.7.2_STABLE_OFFICIAL`, tải + xác minh SHA512-SUMS
   từ kênh official (S18), 4.7.1 chỉ DIAGNOSTIC và không vào package candidate.
3. `toolchain.lock.json` và `evidence/gt01-20260909-06/bootstrap-run.json`
   chứa đường dẫn tuyệt đối kèm username máy chủ, không tái tạo được trên máy
   khác và lộ thông tin host. S17: lock chỉ giữ artifact/URL/SHA/version/commit/
   license; vị trí cài ghi ở `studio/.local/toolchain.local.json` (ignored);
   evidence commit dùng đường dẫn tương đối, redact phần tuyệt đối.
4. `run_fixture.py` hiện trả PASS khi hai process exit 0, không đọc dòng
   GT01_TRACE, không kiểm stderr, ghi `leftover=UNVERIFIED_PROCESS_TREE`, mở
   log bằng `wb` (ghi đè). `trace.gd` hiện chỉ press Enter không release nên
   sau khi bỏ Enter toàn cục ở `main.gd` sẽ FAIL (Button phát `pressed` khi
   release). S17 ghi rõ tiêu chí PASS của runner (host exit + đúng một dòng
   GT01_TRACE + stderr sạch/giải thích + --version khớp pin + không process con,
   Job Object/descendants) và bắt parse `--check-only` trước chạy.
5. Worker Grok: 6 batch liên tiếp bị REJECT hoặc chỉ nhận một phần; batch
   focused `20260910T011833Z` đã kết thúc (exit 0) từ 08:21 nhưng chưa được
   coordinator kia review. Đọc read-only: bản `process` khá hơn (bắt OSError,
   timeout kill) nhưng vẫn `wb`, đánh dấu lỗi bằng `"ERROR" in stdout.upper()`
   quá rộng; bản `fixture` có `old` không khớp source (thụt lề sai), dùng
   `get_tree()` trong script `extends SceneTree`, truy cập `fixture.quit_button`
   trên biến kiểu `Object` và kiểm focus sau Enter thay vì trước — không thể
   integrate nguyên bản. S17 thêm kiểm máy bắt buộc cho output worker và luật
   leo thang: hai batch REJECT liên tiếp trên deliverable ≤3 file thì
   coordinator tự viết, critic vẫn độc lập.
6. Toàn bộ `studio/` (lock, runner, fixture, test, evidence) chưa được commit
   dù GT-01 IN_PROGRESS hai ngày; commit `d7962ad`…`4a289be` chỉ có zdoc. S17
   yêu cầu checkpoint commit WIP hoặc ghi lý do trong report hiện hành.

Không sửa: `studio/**` (đang leased cho worker), `AGENTS.md`, validator r4
(bản sửa S13 của coordinator kia còn uncommitted và có check Codex lỗi thời;
nên xóa check đó hoặc chỉ giữ r5 làm validator hiện hành). Không chạy Godot,
không cài binary, không đổi model worker.

Việc tiếp theo cho coordinator GT-01 (theo thứ tự): tải và xác minh 4.7.2 +
templates + SUMS vào `.local`, viết lại lock không đường dẫn tuyệt đối, sửa
`test_gt01.py` theo pin, tự viết `trace.gd`/`run_process` nếu batch tiếp theo
lại REJECT, chạy `--check-only` rồi run thật trên 4.7.2, commit WIP `studio/`,
sau đó mới mint candidate và gọi hai critic Grok trên cùng hash.

## S16 record (kept verbatim below)

S14 recorded owner authorization and official Grok CLI worker policy. S15 made
the release-profile field list agree with its closed schema. S16 specifies the
signed bytes, excludes the signature and its digest from that payload, and defines
the acyclic input manifest → profile → build → release manifest dependency chain.
Signer role must be checked against the independent trust registry. Canonical JSON
uses [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html); the payload/exclusion
rules are this project's design decisions, not requirements imposed by that RFC.
These contracts still require implementation and independent semantic review.

## What has and has not been verified

- `freeze-s16.json` binds the current full bytes of both plans.
- `static-s16.json` and `selfcheck-s16.json` record structural checks and mutation
  tests only. They do not establish runtime, legal, capacity or human acceptance.
- Earlier GT-01 diagnostics used observed Godot 4.7.1, not the unverified final
  toolchain pin. The 20260910 trace did not prove focused Quit-button behavior,
  final quit postcondition, or Windows descendant-process cleanup. Its PASS line
  is insufficient for GT-01 closure; fixes are being delegated and verified.
- Remaining GT-01 evidence includes official pin provenance/compatibility,
  bootstrap safety, actual headed UI, complete process lifecycle, Blender fixture,
  rollback and two independent critic verdicts on the same frozen source.
- No public readiness, hundreds-of-millions capacity or legal signoff is claimed.

Run from the repository root:

```powershell
python 8-9-hh3d-3/zdoc/reviews/20260910-r5/validate_plans.py --freeze
python 8-9-hh3d-3/zdoc/reviews/20260910-r5/test_review_s16.py
```

Historical script names identify their frozen revisions. S14/S15 evidence does
not certify S16. Missing tracked historical files were recovered from `b4195ca`
without overwriting edited files; `history-recovery.json` lists those recoveries.

## Worker delivery and failures

Use official Grok CLI `grok-4.6`, `--reasoning-effort xhigh`, `--no-subagents`.
Installed CLI help does not expose a separate fast flag. No model substitution.
The [official CLI reference](https://docs.x.ai/build/cli/reference) documents
headless model/tool controls; installed `--help` determines available flags.

The five native CLI workers in batch `20260910T004529Z` exited 0 but did not
deliver the required report/evidence files. Some answers claimed nonexistent
changes/tests. Their inputs were S14 despite stale S13 labels in the prompts.
The next batch `20260910T005231Z` delivered code text, but the runner bundle was
invalid and the fixture bundle incomplete. Both were rejected. The profile
review supplied a field-list clarification, not a full plan ACCEPT.
`worker-rejections.json` binds these terminal decisions to raw event digests.
No missing file, fabricated hash or AI claim has been used as acceptance proof.

Current repairs are split into runner, fixture and tests, with distinct source
allowlists and base hashes. The coordinator reviews returned files before
materializing them and runs the resulting tests. Adding workers is useful only
when each produces reviewable work; prior simultaneous starts also encountered
provider 429 request-rate errors. Launches are now staggered.

Batch `20260910T010752Z` was also rejected after both bounded polls: the runner
read the snapshot before creating it and replaced observed exits, the fixture
retained the Enter interception despite claiming otherwise, and tests were not
valid runnable output. `repair-batch-rejected.json` binds each response digest.
No code from that batch was integrated. Batch `20260910T011409Z` narrows the task
to exact patches for menu input and actual subprocess exit capture; both are
still subject to coordinator review and tests. No acceptance is delegated.

`dispatch_batch.py` and `prepare_bundles.py` prepare fresh isolated batches;
`Launch-Batch.ps1` starts hidden supervisors. Never redispatch just to inspect
status. Ignored `active-batch.local.json` stores per-machine paths and sessions.
Raw worker workspaces/transcripts stay in Windows TEMP. A supervisor waits up to
its configured deadline, records actual exit/timeout/error, then emits a
best-effort Windows notice. A notice is NEEDS_REVIEW or WORKER_INCOMPLETE, not
ACCEPT. At most two coordinator polls per batch; no automatic model continuation
is implied by the Windows notification. Ordinary PowerShell waiting invokes no
model, while Grok itself continues to consume its own usage during work.

## Git and retention

The branch `codex/hh3d-s14-bootstrap` starts from `origin/main` (`b4195ca`), outside
rejected local main commit `54d0c7c`. S14 checkpoint `d7962ad` was pushed normally;
the 386 MB Blender ZIP was excluded from every outgoing blob. Local main remains
available for recovery; no force-push or published-history rewrite is needed.

Keep concise reports, manifests and reproducible acceptance evidence in Git.
Ignore `.local/`, transient worker logs and local pointers. Do not blanket-ignore
or recursively delete reviews. Older evidence is historical; remaining unrelated
file moves/deletions are not part of the scoped checkpoint.

# GT06 Formal25 critic package

## Trạng thái

Formal25 đã hoàn tất hai pair trên cùng source closure. Bằng chứng benchmark
đạt các kiểm tra lắp ghép và verifier offline, nhưng GT-06 vẫn **chưa
ACCEPTED**. Đây là thành phần benchmark của gói critic; coordinator còn phải
đóng mapping functional/dependency và final manifest theo dòng 692–695 của
plan trước khi đề nghị nghiệm thu toàn GT06. Coordinator không ký thay critic.
Hai phiên review độc lập phải dùng hai model khác nhau, cùng final manifest/
source/profile/dataset hash; lưu nguyên văn hai báo cáo trước quyết định nghiệm thu.

- Formal ID: `gt06-o4-formal-25`
- Pair 0: `gt06-o4-formal-25.r00.a01`, 35 mẫu, actual child/editor/import exit 0
- Pair 1: `gt06-o4-formal-25.r01.a01`, 35 mẫu, actual child/editor/import exit 0
- Source closure: `727f9039c1cc83239f5ef1daff13de5e92e37b5ba442e64be8341ca058800b58`
- Profile: `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`
- Dataset SHA-256: `3b0da65e10ea4425bd06d4c2ef7a446dde171a1e0b56fd125301ed1b6ea0a15a`
- Summary SHA-256: `9b8e70f91ac4c08cabe592c96387aa3d88ed01038788fc4a90dda19fe88e84a2`
- Campaign capture SHA-256: `fb6c877d06667ddb293d3961bc90aa46ad43b48541a3c26e1d88cf1f84d1c914`

Raw evidence remains under
`8-9-hh3d-3/studio/.local/reviews/gt06-o4-formal-25/` and its supervisor
directory. The F-tier archive and manifest are:

- `studio/.local/reviews/gt06-o4-formal-25-f-tier.zip`
- `studio/.local/reviews/gt06-o4-formal-25-critic-package/raw-manifest.json`
- ZIP SHA-256: `0e4e8e94d5860c1b3ba6cf63b84cb15de31ebd2cd3e724e035b2dbfd174572a2`
- Raw manifest SHA-256: `49f7e497e9282cc77fd194542a76a37c4e5fc682e53caff969b29b828cbd7996`

The exact formal Scheduler task reached Ready with result 0, its instances were
empty, and the exact task was deleted only after terminal closeout. XML,
registration/start/return and deletion receipts remain in the supervisor raw
directory. No old run was resumed, and no old raw verdict was overwritten.

## Independent verification performed

The following read-only checks were run after the campaign ended:

1. `benchmark_assembly.assemble_run` rebuilt both runs from their immutable
   `assembly-manifest.json`; each returned 35 samples and the expected source
   and profile binding.
2. `assemble_dataset` rebuilt the two-run dataset byte-for-byte equal to the
   stored `dataset.json`; `benchmark_profile.summarize_dataset` returned
   `status=PASS`, with no failures or gaps.
3. The campaign verifier replayed source closure, snapshot hashes, campaign
   capture, run captures, actual exits, natural tree exits, Job active count,
   zero/closed state and retained-handle flags. It also rechecked the O7 host
   prerequisite: 49 batches, 1832.842787 active seconds, watchdog verified,
   maximum gap 444.9745 ms, and O7 metrics pass.

Reproducible read-only command:

Chạy trong PowerShell tại repo chính:

```powershell
python -B '8-9-hh3d-3/studio/.local/reviews/gt06-o4-formal-25-critic-package/verify.py' --studio '8-9-hh3d-3/studio'
```

The command does not start Godot, Blender, Docker, a campaign, or a retry. It
needs the original workstation paths and retained O7 control inputs.

## Review boundaries

Formal25 proves the benchmark lane (F13/F14 evidence), not all functional
gameplay requirements. F01–F12 and TQ00 remain separate authority-0 functional
packets and need their own source pins, postconditions, true exits, cleanup and
critic review. In particular, the older S133 functional closure
`1a2b2b392a39afc7dc0052b66a96f751c2b41261b38f6d0bedc9346913f8db16` and helper
freeze `eab399...` must not be relabeled as Formal25. Formal25's fixture HTTP
lane and direct native fixture cycles do not by themselves prove an authored
game, full product gameplay, Blender asset publication, Android export or
human playtest.

Pending artifacts: final functional dependency/requirement map and final
source/review manifest, then `critic-01.json` and `critic-02.json`. Until both reports
explicitly say `TICK=yes` for these exact hashes, GT06 remains unaccepted and
GT07 remains closed.

## Functional binding repair and targeted refresh

The current installed binding had one changed source out of 215:
`godot-addon/linux_executor.py`, adding the O9 measurement-window guard before
Docker create/start. The regression now also acquires that guard between
create and start and verifies no start/ACK, removal of the owned container,
unchanged input/snapshot and preserved guard. The 57 focused executor/binding/
installed tests exited 0. No Docker or engine was started by those tests.

The two installed metadata files were refreshed after verifying exact source
membership and the accepted GT05 input hashes. Their old/new bytes and receipt
are retained under the local critic package's `binding-refresh/` directory.
Current execution-source SHA-256 is
`7bd657381817fe873214272f96e296f93a04d9f1608147399742a91bb36eda1c`;
the 217-file installed closure is
`9a9c9c42fa2be7dedf485b25c99245e92073f7b024909a8f72ec948f08219691`.
All 64 Formal25 pins are unchanged. This refresh does not change the source
identity or verdict of any historical native run.

S138's authenticated repair/replay already exists (S139 coordinator report);
the earlier S133 pending repair label is stale. S65 performance exports also
exist, with the three exporter/schema pins still equal to current bytes.
However, S133 HTTP/reviewer evidence has changed journal/transport/probe
dependencies. A bounded seven-lane functional supplement uses the original
S133 verifier, unchanged thresholds/timeouts and fresh `gt06-f25-*-02` IDs.
The adapter is `20261003-gt06-functional-refresh/run_refresh.py`; raw and frozen
sources are in `studio/.local/reviews/gt06-f25-functional-20261003-02/`.
Read `terminal.json` and lane receipts for its actual result. It is neither a
new formal campaign nor acceptance; never resume engines from partial output.

Preparation attempt 01 passed resource preflight but stopped before any engine:
the launch observer requires its exact 64-file campaign domain, while the first
adapter supplied functional217. Attempt 02 separates these checks: the unchanged
launch observer verifies64 and the frozen functional envelope verifies217.
Attempt01 raw remains unchanged; no functional engine run or formal retry was consumed.
Attempt02 also ended before engines, at 19:30:14 Asia/Saigon: resource
preflight recorded 3,826,409,472 available bytes (3.56 GiB), 71.9545% commit,
and no foreign engines. No lane started; the measurement guard released cleanly.
Keep this terminal record. Next admission requires changed resource conditions;
do not rerun the terminal wrapper or any old native ID. A subsequent adapter
should separate append-only admission attempts from the once-only engine launch,
so deferred resource checks do not require recreating a valid source freeze.
For F06, source audit narrowed the remaining native supplement to authenticated
managed repair and replay against the original S65 fault anchor. No new fault
run is needed; the Linux-validator guard and redactor changes need integration
evidence rather than relabeling S138 as current.

The prerequisite archive (host, chain and original O7 controls) is
`studio/.local/reviews/gt06-f25-prerequisites.zip`, SHA-256
`a22ab8280ff02b37d28f216f259efa7da764a67423cf4d5b3dc2011ca287c9da`.
Both evidence archives were read back entry-by-entry with matching SHA-256/CRC.

## Deferred admission repair (group 03)

The active adapter now uses fresh group `gt06-f25-functional-20261003-03` and
native IDs `gt06-f25-<lane>-03`. Each `--run` invocation records exactly one
admission under `admissions/NNNN/`. Resource/CPU-busy deferral returns 75 without
consuming a native ID or making a group terminal; a later admission may use the
same unchanged source freeze. Only admitted engine work consumes the group.
An actual failed/started/terminal group cannot launch again, and attempted
reentry is rejected before touching a retained ownership marker. No automatic
retry or poll loop was added. Old groups 01/02 remain unchanged.

Five pure lifecycle regressions passed with exit 0, including defer then one
launch, immutable prior receipts, native-failure guard retention and rejection
of repeat launch. A scoped read-only review found no blocking issue; it is not
an acceptance critic. Group03 was prepared with functional217 and helper234
source files, plus the separate 64-file preflight domain and driver snapshot.
Preview at 19:48 recorded 11.03 GiB available, commit 59.77%, no foreign engine.
Execution still requires its own fresh preflight/CPU minute. Determine the
actual outcome from the group admission/terminal and per-lane receipts, never
from this preparation record.

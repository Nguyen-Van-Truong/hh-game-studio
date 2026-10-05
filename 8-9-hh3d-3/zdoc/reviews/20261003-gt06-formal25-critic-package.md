# GT06 Formal25 critic package

## Trạng thái

Formal25 đã hoàn tất hai pair trên cùng source closure. Bằng chứng benchmark
đạt các kiểm tra lắp ghép và verifier offline, nhưng GT-06 vẫn **chưa
ACCEPTED**. Bảy luồng chức năng và F06 repair/replay cũng đã hoàn tất; mapping
functional/dependency và quy trình đóng manifest cuối nằm trong
`20261003-gt06-functional-refresh/README.md` và `requirements.md`.
Chỉ bàn giao nghiệm thu khi kiểm manifest cuối thành công; coordinator không ký thay critic.
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

Current functional map and sealing instructions are in the functional-refresh
directory. The final-review packet's `manifest.json` and `manifest.sha256` bind
that map and the source/public raw. Remaining acceptance artifacts are
`critic-01.json` and `critic-02.json`. Until both reports
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
the launch observer requires its exact imported collector domain, while the first
adapter supplied functional217. Attempt 02 separates these checks: the unchanged
launch observer verifies that domain and the frozen functional envelope verifies217.
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
source files, plus the separate 71-file imported preflight domain and two driver
files (73 total). Formal25 itself freezes 64 files; the collector's imported
membership depends on the driver. Earlier adapter comments calling this domain
64 are shorthand, not the actual frozen inventory or its acceptance condition.
Preview at 19:48 recorded 11.03 GiB available, commit 59.77%, no foreign engine.
Execution still requires its own fresh preflight/CPU minute. Determine the
actual outcome from the group admission/terminal and per-lane receipts, never
from this preparation record.

## Group03 verified terminal result

At 19:55:17 Asia/Saigon the seven functional lanes finished on installed217
`9a9c9c42fa2be7dedf485b25c99245e92073f7b024909a8f72ec948f08219691`.
The captured outer execution session returned exit 0. The existing helper
verified each lane's original host receipts, source copies, native artifact
hashes, named checks or real UI flags before starting the next lane, then
collected the selected public raw. `lanes/verification.json` SHA-256 is
`a6b23ff2a4255c6e7d52e453d5d2ed8b9d99e4208cd80c16dd7feec5dbde6639`.

Lanes: HTTP complete, HTTP Stop, saturated Stop, revoked result, stale capture,
reviewer complete and reviewer Stop. Actual outer/inner helper exits and all
imports are 0; the four completion runtimes also have actual exit 0. The three
intentional Stop runtimes keep `completed=false`, wrapper exit 2 and unknown
natural exit; they are cancellation evidence, not natural-success evidence.
All native Jobs are zero/closed/untainted with no retained handle. A fresh
process snapshot found no Godot/Blender, and the cooperative marker is absent.

F06 continues through `run_managed.py` with fresh repair/replay IDs and the
unchanged S138 verifier. The wrapper holds the same permanent kernel guard as
the benchmark, but creates no measurement marker because this non-benchmark
repair requires the Linux validator. It never removes an existing marker;
the executor's Docker fence remains unchanged. Seven pure guard/lifecycle tests
passed, including both-direction exclusion, preservation of a formal marker,
rejection of reused lanes and refusal to replay an unverified repair.
The packet is `studio/.local/reviews/gt06-f25-managed-20261003-02/`.
A scoped review also required post-run driver verification and deterministic
registration of the lazily imported script-profile module before freezing.
Both were fixed before native launch; group01 remains preparation-only, with no
engine. The managed driver freezes 75 imported studio files and two driver files
(77 total), separately from installed217. Repair was launched at 20:14:22
Asia/Saigon; actual lane receipts remain necessary before F06 is current evidence.

## F06 completed on the current execution source

Both lanes in `gt06-f25-managed-20261003-02` completed and were verified by the
unchanged S138 semantic verifier plus the new wrapper's post-run driver check.
The outer tool session also returned actual exit 0 for each lane. Repair owner
36416/child13740 and editor29968/editor19712 exited 0; both editors have zero,
closed, untainted Jobs and no retained handles. Replay owner31284/import14340/
runtime49180 exited 0; both native stages have natural tree exits and clean Jobs.
No natural-exit classification was invented for the repair editor close records.

The original S65 fault capture remains
`d3469bee92f7decad37d1f937631cff467548c8751f03ca99eac029c7547b7a1`.
Authenticated repair selected config
`4fe3141b9afe6b411b585b203cebae77e851a406c291ac26620eb8cd7c018d90`
and read it back before COMMITTED/public ACK; retry and lookup returned the same
receipt. Repair capture SHA256 is
`e49a4522962e3c9a062079550251ff654682617b4e6e2793f0d2a7bca50aca81`.

Replay binds that config, accepted GLB and original 60 Hz/seed17 trace to its
immutable runtime snapshot. Observed movement is 1.50000023841858 m against
1.5 m expected; fault is absent and every declared semantic postcondition passes.
Replay capture SHA256 is
`4ff63ca53048da5e322507da641052fd2804b194c67503a556a178f98317f167`;
causal report SHA256 is
`93201023b6a2f1b44fbe73b3d9578f0eb867ff598c928a85792d554106c7a0f2`.
The outer causal report establishes managed repair; the nested standalone
observation's `managed_repair_proven=false` remains unchanged and has narrower
scope. Likewise a native runtime capture's `public_ack=false` does not overwrite
the authenticated repair command's observed `public_ack=true`.

The source domains remain separate: native217, functional launch71/driver73,
managed launch75/driver77 and Formal25 benchmark64. A bounded read-only audit
checked the causal hashes, receipt order, validation exits/removal and teardown;
it is not either acceptance critic. The final map is
`20261003-gt06-functional-refresh/requirements.md`.

## Captured regression receipts for the final package

Source-bound subprocess receipts retain protocol 447 tests (4 skips), replay
849 (1 skip), reviewer65, Linux executor24 and admission wrappers13; each named
successful suite has actual exit0. Replay already includes execution binding
and installed-source tests, so totals are not double-counted. Source maps,
invocations and full logs are in `gt06-f25-final-tests-20261003-01/02/03`.

Two proof-harness issues were retained and corrected without changing native
runtime source: group01's parent guard collided with campaign unit tests; group02
isolated child LOCALAPPDATA. Then two wrapper unit tests saw real already-consumed
IDs; their disposable raw namespace was fixed and explicit consumed-ID rejection
added. Group03 reran only wrappers. Protocol and already successful suites were
not repeated. The original failing logs and pre-fix wrapper test bytes remain.

The archive builder rejects missing required members using source freezes,
public lane inventories, repair artifact hashes, runtime snapshots and captured
process-artifact hashes. A missing-inventory-reference injection was rejected
without changing raw. Byte integrity still does not replace source/semantic
review, and neither scoped implementation audit counts as an acceptance critic.

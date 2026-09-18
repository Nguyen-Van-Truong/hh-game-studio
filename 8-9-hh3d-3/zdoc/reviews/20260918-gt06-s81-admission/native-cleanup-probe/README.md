# Completed supplemental real child cleanup smoke

AUTHORITY=0. The coordinator ran the single-use probe once under the sole engine lease after freezing source. It completed `CLEANUP_SMOKE_VERIFIED`; this is supplemental cleanup evidence, not a benchmark PASS or critic verdict. The [independent evidence summary](evidence/summary.md) records actual exits, missing exits, cleanup observations, source bindings and the portable exact-byte packet. The original invocation and scope below are retained for reproducibility; the existing run ID must not be rerun or overwritten.

The fixed, single-use raw root is `studio/.local/reviews/gt06-s81-cleanup-probe-01`; the inner child uses its new `child/` directory and run ID `gt06-s81-cleanup-probe-01.r00.a01`. Existing output is never overwritten or resumed. If an attempt fails, keep it and prepare a newly identified attempt separately.

The driver loads the real campaign and trusted fixture before computing its complete imported source map. It requires an externally supplied expected closure, preserves every runtime source file and the driver bytes, and verifies the same bytes before/after. It calls the original `run_child` with a generated diagnostic context; the original preparation, pinned import, real editor, NativeLog READY verification, process probes, HTTP listener threads, indexed journal and original cleanup code execute unchanged.

Two explicit in-memory diagnostic hooks are recorded in `probe-request.json`: `CampaignProducer.run_batch(0)` raises a fixed CommandError at its first call, after `run_child` verifies READY; a transparent `_finish_child_cleanup` wrapper retains the actual owner/probe/producer/index references and calls the original cleanup exactly once. No command batch or native cycle runs. The driver checks the same original exception and cause survive, then compares the persisted terminal record to direct post-finally observations, including the retained SQLite object's DB/directory fields, listeners, threads, native probe handles and checked editor owner state.

The expected editor natural exit remains **null**, while its observed helper exit is separately 2. The pinned import must have actual exit 0. The outer diagnostic observer returns 0 only after smoke verification; that does not convert the intentionally failed child body to benchmark success. Missing target-exit bytes are never synthesized. All measurement/effect/benchmark acceptance claims remain false.

The outer runner reuses `BenchmarkProcess(campaign_host=True)` and its checked Job/handle/actual-exit verifier. Its host watchdog stops the owned tree at 120 seconds; the existing finite owner profile is recorded unchanged. Checked teardown may add its existing bounded cleanup time after watchdog expiry. Source freezing occurs before that owned interval. On success the outer capture must prove natural observer target exit 0, helper exit 0, Job zero/closed and released wrapper handles. The inner terminal record supplies the independent editor/producer/probe cleanup observations. It does not invent an import-wrapper-handle receipt absent from that older stage's capture.

After source freeze, compute the closure with the same load order (read-only, no engine):

```powershell
@'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('8-9-hh3d-3').resolve()))
from studio.tests.replay import run_benchmark_campaign as campaign
campaign.load_fixture()
print(campaign.closure(campaign.source_files()))
'@ | python -B -
```

Only with the coordinator engine lease, substitute that verified hash:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s81-admission/native-cleanup-probe/run_probe.py --expected-source-closure SHA256
```

Do not call `--owned-child` directly. The parent launches that fixed internal mode under the checked Job. No Task Scheduler task is created or deleted by this driver.

Review `probe-outer-result.json`, `probe-owner/capture.json`, `child/probe-result.json`, `child/child-terminal-cleanup.json`, the original child failure, the injection/READY binding and both import/editor raw logs. A timeout, unexpected body failure, receipt mismatch, source drift, retained/uncertain handle or failed outer ownership check is a failed diagnostic. Preserve it; do not promote it or count partial work toward the ten-run benchmark.

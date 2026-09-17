# S71 bounded measurement/contract review — draft, no acceptance

Read-only source/small-artifact inspection on 2026-09-18, HEAD `58d2bffe2b6fe25493dfaabeead931d6a6862211`. No tests, engines, task actions, source edits or acceptance signature. Paths below are relative to `8-9-hh3d-3/`. This report does not identify the owner of the added objects.

**Finding:** campaign02's failure is correctly derived from its frozen v2 predicate. The actual failing counter is editor ObjectDB count, +476 from warm batch04 to measured batch05. No arithmetic, baseline-index, PID-replacement or batch/ACK discrepancy explains that increase. It is not a completed benchmark, and six snapshots cannot by themselves distinguish an unbounded leak from bounded editor/diagnostic retention or delayed cleanup.

## Contract and predicate

| Authority/implementation | Exact rule or behavior | Assessment |
|---|---|---|
| `zdoc/8-9-godot-blender-agent-studio-plan.txt:1037`–1054 | 10 fresh process runs; 5 warmups excluded then30 measured batches; each1000 commands +100 create/undo/save/reload cycles. No duplicate/lost effects or steadily growing leaks; stable RAM after10 same-workload repetitions ≤10% above warm baseline; raw samples, GC/import phases explicit, OS cache separate. | Preserve these requirements. The prose does **not** itself specify zero tolerance for every one-sample ObjectDB/ResourceCache/OS-handle excursion. |
| `studio/tests/replay/benchmark_profile.py:57`, `:187`, `:241`, `:304`–326 | Frozen `gt06-tools-ux-exact-v2`; baseline exactly batch04; all30 measured RSS points must be≤110%; every applicable non-RSS point must be≤baseline. `repetition_10` reports measured index9 (batch14), but is not the sole RSS gate. Missing applicable counters are GAP. | A deliberately stricter operational rule than “no steadily growing leaks / RAM after10”; not logically equivalent to that prose. No new policy may be inferred from this failed prefix. |
| `studio/tests/replay/run_benchmark_campaign.py:256`–271, `:670`–675 | Warmups bypass growth check; batch04 then becomes baseline. At index≥5, integer `value*100 <= baseline*110` for RSS; other counters `value<=baseline`. | Matches the final v2 summarizer's memory rules, including exact110% boundary. Early abort is sound for that frozen profile because later observations cannot undo an already failing point. |
| `studio/tests/replay/test_benchmark_campaign.py:247`, `:261`, `:274`; `test_benchmark_profile.py:109`, `:123` | Existing tests specify exact RSS boundary, +1 retained-counter rejection, warmup exclusion and final retained-handle failure. | Evidence that the strict predicate is preexisting and intentional, not an accidental online-only mismatch. Tests read, not rerun. |

Keep campaign02 failed/incomplete. Do not reinterpret +476 as an allowed percentage, move the baseline, count warmups as measured, discard the failing sample, or remove the prefix guard while still claiming v2. A justified measurement-definition correction would need its own reviewed source/profile implications and fresh evidence; it cannot retroactively turn this attempt into a valid complete campaign.

## Small-artifact comparison

Evidence root `R = studio/.local/reviews/gt06-s70-campaign-02/run-00-attempt-01/`.

| Counter | Warm baseline `sample-preview-04.json` | Measured `sample-preview-05.json` | Difference |
|---|---:|---:|---:|
| Editor objects | 72,866 | 73,342 | **+476 — trigger** |
| Editor cached resources | 6 | 6 | 0 |
| Editor OS handles | 555 | 555 | 0 |
| Editor RSS/working set bytes | 223,989,760 | 181,624,832 | −18.914% |
| Host OS handles | 194 | 194 | 0 |
| Host RSS/working set bytes | 26,693,632 | 27,267,072 | +2.148% |

Both rows retain host PID48568/start `windows:134341431297699638` and editor PID34644/start `windows:134341431363866855`. Python-host ObjectDB/resources are explicitly `NOT_APPLICABLE_PYTHON_HOST`; no invented zero. The six available ACK object counts are 71,261 /71,497 /71,945 /72,400 /72,866 /73,342. This rising prefix warrants investigation, but five of those observations are warmups and only one is measured.

`R/child-failure.json` records `CAMPAIGN_RETAINED_COUNTER_GROWTH`, batch5, `completed_batches=6`, phase `joint_observation`, `completed=false`, `formal_acceptance=false`. Six captures mean five warmups plus one measured batch, not six measured repetitions or one complete35-batch run.

## Phase/order verification and measurement limits

The source order is ready → host1000 → host report released/`gc.collect()` → start permit → native100 → minimum quiescent interval → native batch → host/editor OS sample → bound ACK → fresh native ObjectDB/ResourceCache sample → next ready. See `run_benchmark_campaign.py:601`–675; `benchmark_native.gd:533`–689; `benchmark_assembly.py:399`–406 and `:488`–533. Assembly uses the **fresh ACK counters**, not the earlier native-batch counters. Different host/native monotonic clocks are bound by the barrier rather than directly compared.

| Observation | Batch04 | Batch05 |
|---|---:|---:|
| Last reload observed process frame | 24,703 | 26,729 |
| Native batch memory frame | 24,717 | 26,743 |
| Recorded settle frames / microseconds | 13 /1,297,584 | 13 /1,296,982 |
| Native batch objects /resources | 72,864 /6 | 73,340 /6 |
| ACK frame | 24,718 | 26,744 |
| ACK objects /resources | 72,866 /6 | 73,342 /6 |
| ACK native-time minus batch native-time | 104,947µs | 104,318µs |

These rows exceed the frozen ≥4 frames and≥1,100,000µs minima and occur after actual save signal/reload readback. The native batch counts themselves already differ by+476. ACK sampling adds the same+2 in both rows, so changing to the older batch counters would not fix this failure.

There are real limits to the “retained” label which must remain explicit:

- `_wait_host_ack()` keeps its local `FileAccess` reference alive after `file.close()` while calling `Performance.get_monitor()` (`benchmark_native.gd:626`–666). It therefore samples at least one transient probe Object, and counts the whole editor ObjectDB, not just objects owned by the workload. The exact source of both extra ACK objects is not established. This consistent phase offset does **not** explain the +476 cross-batch growth.
- The4-frame/1.1-second condition is an elapsed quiescence floor plus semantic-scene stability, not proof that every editor UI/cache/deferred-free population has reached a plateau. No per-class ownership or longer-idle convergence observation is present in these small artifacts. An actual retained leak remains possible; bounded editor/history/log/cache growth is also unexcluded. Do not assert either cause as proven.
- `ProcessProbe.sample()` (`studio/host/replay/process_probe.py:42`–47, `:72`–95) uses Windows working set, correctly reported as RSS. That can fall independently of logical object counts. It does not measure private committed bytes or OS-cache attribution; the falling editor RSS does not disprove object retention. These reviewed sample/profile schemas contain no separate OS-cache/GC-phase record. Import is a separate captured stage and `gc.collect()` is source-visible, but final packaging still needs the plan's explicit phase/cache context rather than calling the raw RSS a leak diagnosis.

## Minimal next work

Preserve the failed attempt. Attribute the ObjectDB population/retention in the owner investigation before another hours-long campaign; specifically distinguish adapter/UndoRedo lifetime, editor/UI/log history, and bounded probe overhead. Keep the exact workload and fixed thresholds. Any diagnostic instrumentation must be labeled diagnostic and must not silently clear histories, caches or receipt tables to manufacture a flat count. After a justified implementation or measurement fix, freeze the affected closure and run fresh evidence under the reviewed contract. Unchanged independent functional dependencies do not need speculative remints. This report neither authorizes a criterion change nor signs GT06 acceptance.

## Source/artifact pins

Campaign source closure `21a17b2a350160efb17950979adada0a2b3e12dbd95e12158833acbe9f233aa0`; profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`; toolchain `28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9`. The five inspected live implementation dependencies below exactly match `R/source-files.json` at inspection time; no whole-tree/raw-tree scan was performed.

| Studio-relative source | SHA256 |
|---|---|
| `tests/replay/benchmark_native.gd` | `da0bb949ebaf3bc3881a1e9ad325d98ac6496fc3a0454b825a28655fdbc37515` |
| `tests/replay/benchmark_profile.py` | `ddbd98583060f791226fca83e275cf01204b37112627383198dcef4ec6f6f233` |
| `tests/replay/run_benchmark_campaign.py` | `09f9d6a24c6281193f21c9aa89c48602ac5d70dfe86882fbaf76e8366c66dd6c` |
| `tests/replay/benchmark_assembly.py` | `16ba15ea1961d78c89d5ea2b8c389e89b960a4df25e6a2783e4cc8a6d0c1111a` |
| `host/replay/process_probe.py` | `53b6b24813e6ba6dc040dcbb87aee529b7f4e8855a64bcd0689b19c240180500` |

| R-relative evidence | SHA256 |
|---|---|
| `source-files.json` | `4ce35b98d4f850ba1fdf8aa9d86058cabc4ac45f72e1ef661626149235da2ebf` |
| `sample-preview-04.json` | `593307e15fb49b3695baea64c36ef6c9eb46b0c4cf87fcb3e005890f84d91e14` |
| `sample-preview-05.json` | `2f5a7039b99f390dd678734fa148509ed79709522c2330ab00f6286b98d6a2da` |
| `joint-04.json` | `d1e21d09a234bdc343d65e5998a300cf21ae59acb2a21be29fbcf2a4a87389a8` |
| `joint-05.json` | `5a8a4c04992e8592297f3bb9833b1b9ce4c072b77dba2b6e0fc4ccd534087754` |
| `batch-capture-04.json` | `a21c640e1445a360684c9faa54998c7219dec1dbdf2839cc35ae221f67a7cbfc` |
| `batch-capture-05.json` | `77f57b7b6f443b0cb1cb249d7c03df520019db2b2fbca97352faf7597ffc9a01` |
| `project/benchmark/out/batch-04.json` | `a237bae644abf6289c03d722a41fb69a7942a73b0e757d28bc50e14361c0ca06` |
| `project/benchmark/out/batch-05.json` | `e5bf4a8983131922188afbe6ce70818ebf1fd5c2489184635c49fb52332e104c` |
| `child-failure.json` | `d7bcb91140e7b854edf107861a5b4e46734e0bdd49c9cdf2616a0f284eefad7a` |

Plan SHA256 when read: `ce7d32af5a55b0c0df8e5ec9bfef93309cd7d6bb42056f09d5b597a505a51cf6`. Status paragraphs can evolve; the cited unchanged benchmark requirements govern this assessment.

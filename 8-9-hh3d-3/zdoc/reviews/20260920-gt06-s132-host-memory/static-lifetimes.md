# S132 bounded host allocation-lifetime review

Date: 2026-09-20, Asia/Saigon. AUTHORITY=0. Supporting static review only;
not a final critic, acceptance verdict, dataset, leak diagnosis, or no-leak proof.

Scope: current HH3D tools source, principally CommandProducer,
benchmark_http_phases, BenchmarkFixtureHost, core transport, VerifiedJournal,
and run_benchmark_campaign. Direct journal/redaction dependencies and the
host_memory.py sampling helper were read to resolve ownership boundaries.
No engine/test/probe was launched, no live metrics/raw run files were read,
and no source or plan was edited. This document is the only authored file.

Baseline observed by this reviewer: HEAD
`9a851db3ca165643bce7257b513045d651456ae0`; scoped
`git status --short -- 8-9-hh3d-3/studio` returned no changes at review start.
The plan top declares GT-06 IN_PROGRESS, S132 host-only diagnostic, and
runtime closure `763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4`.
The closure is a supplied/declared binding, not independently rehashed here.
Only process names/IDs/start times were listed as an initial ownership check;
live measurements and lifecycle verification remain the coordinator's work.

The reviewed code does not retain every successful batch report on the
producer. It does intentionally retain several increasing, capped structures,
including session-secret history, compiled aggregate redaction patterns, and
campaign artifact references. Journal command/offset history grows on disk.
These facts do not bound total process RSS or explain the supplied S131
40,861,696 -> 45,395,968-byte failure. The supplied handle plateau and offline
assembly plateau do not distinguish these remaining live-host allocations.

Paths and line numbers below are relative to `8-9-hh3d-3/` unless absolute.
“Bounded” describes a code-visible cardinality/lifetime, not a measured byte
ceiling or a guarantee that an allocator returns memory to the OS.

| Owner / references | Proven source lifetime or growth | RAM versus disk; qualification |
| --- | --- | --- |
| `CommandProducer._run`, `studio/tests/replay/benchmark_commands.py:300-359` | A new report per batch, 1,000 command rows, 1,000 latency entries, 200 effect entries, and one cancel record. `_status_ns` is replaced at batch start and emptied in `finally`. `_setup_responses` aliases only that report's two setup rows and is replaced next batch; it does not point back to the full report. `next_index` rejects index >=35. | Report is transient RAM returned to caller. Per-command `lookup_attempts` and response timestamps append during the batch; they have time budgets, not a fixed per-report retry-count cap. A failed `CommandError` intentionally retains the partial report, cleanup owner and chained traceback; failed producer is latched and cannot continue successful batches. |
| Resident producer / wrapper classes, `benchmark_commands.py:111-131`, `benchmark_http_phases.py:272-380` | Recorder plus observed journal/host/client/connection/response classes are constructed once per producer. New batch client replaces `self.client`; new HTTP connection is per call. Wrapper closures retain one recorder, not one recorder per command or batch. | Resident fixed graph plus current client. Classes are not reconstructed by `_connect_batch`. A source-only review does not quantify class/allocator memory. |
| `PhaseRecorder`, `benchmark_http_phases.py:154-268` | Event `deque(maxlen=8192)`, active map capped64; completed spans are removed in `finally`, and thread-local stack is popped. One first-lookup-failure snapshot can retain a second bounded event/active copy. `snapshot()` creates another caller-owned copy. | Bounded event cardinality in RAM; counters grow numerically. Entries hold primitive metadata, not sockets or request/response objects. First-failure capture is a possible one-time step, not per-batch append. Successful span cleanup is code evidence, not proof all live spans are finished at a sample. |
| `BenchmarkFixtureHost` / client, `benchmark_transport.py:25-100` | Adds one disconnect mutex and fixed fault state. Client holds only its most recent sanitized failure dictionary, resetting it at each call. Connection closes in `finally`. | No batch-history list added by subclass. Network response objects/body buffers are local to a call; returned decoded objects are retained by report rows where applicable. |
| Listener request threads, `studio/host/core/transport.py:234-302` | Two semaphores cap handlers at8 work +2 control. Tracking uses a WeakSet; no source-owned strong historical thread list. Request thread targets/arguments are created per request. Teardown drains a temporary list, clears it and its last thread reference, retaining ownership on failure. | Request-thread/native allocation churn remains. Weak tracking does not itself prove native resources have returned at the exact sample. A weak set's backing allocation high-water behavior is not a total RSS bound. |
| Host service threads and worker state, `core/transport.py:337-354,372-420,736-754,790-852` | Exactly3 service threads are appended once. Jobs and queue admission cap16 each. Completion/cancel removes jobs and pending entries; worker dequeues each job. Stop records cap16 and are removed after drain. Pending snapshot is replaced after removals; a general simultaneous work+Stop bound is32 entries. Worker may hold its latest local job until the next loop, rather than every historical job. | Bounded active ownership in RAM, with checked close/join code. No observed live-thread or cleanup verdict is supplied by this review. |
| Diagnostics / fixture state, `core/transport.py:203-211,345-370` | Diagnostics cap32 encoded rows. Fixture contains scalar value/revision/effect_count. Tuple snapshots and decoded diagnostic checks are temporary. | Fixed-cardinality RAM; numeric values and encoded text size can change. |
| Sessions, credentials, redactors, `core/transport.py:108-152`; `benchmark_commands.py:147-167` | One mint/rotation per batch. `_issued` intentionally appends bearer history up to64, never erasing earlier secrets. Active sessions cap16; normal batch rotation overwrites the same session ID. Each mint builds a new aggregate output redactor covering all issued secrets and replaces the previous owner reference. | Actual increasing RAM, capped by history policy and producer's35 batches. Normal live current redactor size grows with issued count. Previous sessions may also remain briefly in an active job/handler. Secrets/pattern text must never be emitted in evidence. |
| Global regex cache reached by redactors, `studio/host/core/redaction.py:65-94` | Redactor constructs variant strings and calls `re.compile` on their combined pattern. Read-only inspection of PATH Python311 `C:/Users/truon/AppData/Local/Programs/Python/Python311/Lib/re/__init__.py:225-227,269-303` shows global `_cache`, max512 entries, retaining both pattern key and compiled object until eviction. | Conditional on this interpreter's binding to the run, older compiled cumulative patterns can survive replacement of `_output_redactor`. Before eviction, aggregate retained pattern bytes can grow as the sum of successive history sizes, not only the latest history size. Cache cardinality is capped; actual occupancy/bytes and contribution to S131 are unmeasured. PATH lookup alone is not a live-process binary binding. No cache purge was performed or proposed as an acceptance workaround. |
| Host/journal leases, `core/transport.py:644-649`; `core/journal.py:386-397` | Host lease entries replace by session ID and expired entries are pruned on lease request. Normal rotation preserves one ID. Journal leases replace by `(project,target)`; this fixture uses one project/target. Journal pending set adds on admission and discards on terminal completion. | No per-successful-command accumulation in those normal-path RAM containers. General APIs may see multiple IDs/targets; this row's single-entry observation is workload-specific. |
| VerifiedJournal fingerprint / replay, `studio/host/replay/verified_journal.py:25-33,102-210` | Retains one digest, size, identity and policy tuple. Snapshot hashes journal through <=65,536-byte chunks; no complete journal byte string retained. Reload reuses a matching index, or closes/replaces index then replays line-by-line. | Constant-cardinality fingerprint and bounded read chunks in RAM; temporary decoded receipt per indexed lookup. Authoritative journal bytes intentionally append on disk, capped64MiB and100,000 records by inherited limits. No history truncation/clearing is part of these batches. |
| Disk index / SQLite, `studio/host/replay/disk_journal_index.py:60-100,113-123,194-314`; `verified_journal.py:146-154` | Commands and record offsets are backed by SQL tables, replacing inherited Python maps/lists before load. One connection, configured pager256KiB, statement cache32, mmap0, temp_store1, spill enabled; each cursor closes. Adapter objects weakly reference the index owner. | Record offsets and unique command keys grow on disk. Configured page/statement caches are bounds on those caches, not SQLite's entire allocation footprint or process RSS. `_pending`/`_leases` remain RAM. Close explicitly closes connection and removes owned disposable index; no close-state was independently observed here. |
| Campaign native log, `studio/tests/replay/run_benchmark_campaign.py:104-157` | Appends non-heartbeat markers with total count <256; overwrites last heartbeat. Reads <=1MiB per poll and retains incomplete tail <=65,536 bytes. Marker match lists and decoded read buffers are local. | Capped marker history in measured campaign-host RAM, deliberately absent from direct CommandProducer host-only workload. Callback `CampaignProducer._received` polls it on every response. |
| Campaign child batch references, `run_benchmark_campaign.py:872-873,956-970` | `batches` appends one dict containing index and six file/hash references per batch, up to35. Only sample4's memory subtree becomes `baseline_memory`. Large parsed artifacts and assembled sample are explicitly deleted; final loop variables `cycle`/`timing` still refer to the last one of100 native rows, a bounded one-row alias. | Intended small increasing RAM reference manifest; full command/native artifacts remain on disk. `cycle`/`timing` do not retain their parent lists. Next batch overwrites ready/start/ack/marker locals; those are small bounded latest-artifact references. |
| Campaign parent, `run_benchmark_campaign.py:378-546` | Keeps completed run references up to10 and bounded attempts/identities. At final assembly, `runs` intentionally accumulates assembled runs then dataset. | Separate parent-process RAM, not the resident child host PID sampled by `producer._observe()`. Final whole-dataset allocation must not be attributed to an earlier child-host batch4->5 sample. |
| S132 diagnostic rows, `host_memory.py:108,117-142,158-162` | `rows` deliberately appends one metric dictionary per successful batch, up to7; baseline aliases row4's host observation. Metric locals alias retained rows. This accumulation happens after each released sample, hence appears in subsequent batch starts. | Small intentional diagnostic RAM growth, not command history. The helper's released sample drops the report, but not these prior metric rows, recorder, journal, credentials, global caches, or active host. |

Exact memory-sample placement:

1. `CommandProducer` initial sample occurs after host startup, before first
   credential/lease setup (`benchmark_commands.py:128-131`). Per-batch
   `memory_before` follows credential rotation, discovery and lease acquisition
   (`318-319`). `memory_after` is sampled with all command rows and response
   objects still retained, before finally creates `host_response_mono_us`
   (`335-358`). It is not a report-released sample.
2. In the coupled campaign, report is written and referenced, then deleted and
   `gc.collect()` runs before native work starts (`run_benchmark_campaign.py:909-920`).
   Host joint sample at932 follows native batch read/JSON parse and validation,
   so `native_raw`, the full `native` object and latest `cycle`/`timing` are live.
   It precedes editor sampling, ACK publication/receipt, construction of `joint`,
   rereading `bound`, and sample assembly (`932-964`). Calling that phase
   `post_batch_quiescent` does not mean all host artifact temporaries are gone.
3. `benchmark_assembly.py:567-582` uses the joint host counters for assembled
   memory. `screen_sample` checks index>=5 against sample4 baseline
   (`run_benchmark_campaign.py:261-275,965-967`). It does not replace the original
   RSS gate with CommandProducer's report-live memory_after. Large assembly
   objects are removed only after screening (`968-970`); failure deliberately
   retains the failing frame/artifacts for cleanup/evidence, and stops the run.
4. S132 helper starts each iteration with metrics before `_connect_batch`, runs
   one batch, reads gap/lookup-count scalars, samples report-live, writes the
   report, samples write-held, deletes report, calls GC, obtains original host
   observation, then supplementary released metrics (`host_memory.py:119-129`).
   Recorder cardinalities and the new retained metric row are built afterward
   (`130-137`). The RSS gate uses `current` from128; private commit/block count
   comes from the immediately following separate sample129. These are ordered
   observations, not one atomic snapshot. No native wait/read/parse/ACK or
   assembly occurs in this helper, and response completion is not an explicit
   request-thread join barrier.

One next precise differentiator, only if the coordinator's terminal S132
evidence leaves meaningful released growth unresolved: in one separately
identified, bounded host-only diagnostic after the current run has ended,
measure how much released Python retention is accounted for by cumulative
session-redaction regex cache entries. At the same released boundaries after
batches4,5,6, record only counts and aggregate byte sizes for issued-history
length, current redactor replacements/pattern, and historical compiled patterns
still reachable from `re._cache`; bind the actual interpreter and keep tracing
overhead outside acceptance claims. Never persist bearer values, pattern keys,
replacement strings, or arbitrary object repr. Do not purge the cache, clear
history, trim working set, or change gates. If cache-accounted bytes track a
growth component, that identifies a reachable owner for that component; if
they do not, it leaves native allocator/journal/thread and other owners open.
Either outcome is narrower than attributing total RSS, and neither proves a
leak or absence of one. This is a proposed discriminator, not work launched by
this reviewer.

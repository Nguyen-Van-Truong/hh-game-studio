# S77 Python host retention review

Bounded read-only audit, 2026-09-18, Asia/Saigon. This report is diagnostic, not acceptance. No runtime/source changes, tests or engine launches. Source scope started with `studio/tests/replay/run_benchmark_campaign.py`, `benchmark_commands.py` and `benchmark_job.py`; the coordinator then authorized the narrow `VerifiedJournal`, `LoopbackFixtureHost`, `journal_index.py` and relevant base Journal definitions. Existing S76 artifacts and a structural allocation model were parsed for offline object-graph estimates; no benchmark/application module was imported or executed. Only this report was written for this subtask.

**The material growth is the application journal's exact index, not a retained stdout buffer.** Its current representation grows by approximately4073583Python bytes from batch04 to34, versus this S76 run's1909145byte RSS growth allowance. This is a concrete software-retention risk before another long campaign, although reachable allocation size is not live RSS and does not prove the exact batch at which the gate would fail. Required command deduplication must survive any representation change. Native stdout streams to disk; benchmark markers/descriptors grow more slowly, and large report bodies are released each batch. Nothing here justifies attributing an RSS failure to OS trimming or promising that the unchanged10% bound will pass.

## Which process is measured

`benchmark_commands.py:72–74` constructs the observer for `os.getpid()`. `run_benchmark_campaign.py:599` creates the resident CommandProducer directly in `run_child`. Consequently host RSS contains both the application (`LoopbackFixtureHost`, journal, credentials, transport) and benchmark instrumentation (NativeLog, parsed evidence, process ownership/drain threads). The campaign parent owns a separate Python process (`run_benchmark_campaign.py:452–455`); its final assembly dataset is not included in this child's per-batch RSS.

The joint host observation is at `run_benchmark_campaign.py:637`, after the command report has been persisted/deleted and `gc.collect()` called at`:614–619`, but while the current native batch's raw bytes and decoded100cycle/timing rows are still alive (`:629–637`). That current native-report footprint is present in every comparable batch. The later six-artifact decode/assembly at`:665–669` occurs after the current sample; these objects are explicitly deleted at`:673–675` before the next batch. It can produce allocator high-water effects without being a growing chain of reachable reports. `gc.collect()` is not an RSS guarantee, and this audit did not measure the live allocator or OS working-set decisions.

## Retention inventory

| Owner | Lifetime and bound in reviewed source | Finding |
|---|---|---|
| `BenchmarkProcess._drain` | Reads4096bytes, writes/flushed to `stdout.txt`/`stderr.txt`; only current chunk and integer count survive (`benchmark_job.py:293–307`). Disk log limit8MiB each (`:26–29`). | No in-memory stdout history. Two retained drain threads, not one per batch. |
| `NativeLog.tail` | Incremental offset; at most1MiB newly read per poll, split into complete lines; retained unfinished tail≤65536bytes (`run_benchmark_campaign.py:114–124`). | Bounded tail; temporary split/decode allocations. Complete logs live on disk. |
| `NativeLog.last_heartbeat` | Previous heartbeat overwritten (`:133–134`). | Constant-count reference. |
| `NativeLog.events` | Every non-heartbeat marker retained; total<256guard (`:135–137`). `wait()` returns matching existing dictionary without consuming it (`:140–149`). | Deliberate growth over35batches, bounded by marker cap. Expected normal markers are CADENCE plus READY/START/BATCH/ACK per batch and COMPLETE. Not a command-history-sized leak. |
| Child `batches` | One descriptor dictionary, six file/hash/size references per batch (`:661–664`), used for final manifest. | Deliberate O(batch-count) bookkeeping, max35. Full report bodies are not appended. |
| `baseline_memory` | One `sample['memory']` mapping from batch04 (`:671–672`). | No backreference to whole sample/report in the shown shape. |
| `native`, `native_raw`, `joint`, `editor`, `host`, `receipt`, `bound`, `sample` | Explicitly deleted at`:673–674`. | No growing list of these report bodies. |
| Loop locals `cycle`, `timing`, `ready`, `start`, `ack`, `command_ref`, marker refs | Python loop locals persist until reassigned. | At most the last cycle/timing row and current small mappings, not every previous native batch. Marker aliases point into the already-counted events collection. |
| `CommandProducer._status_ns` | Reset at each batch start and emptied in finally (`benchmark_commands.py:281,319`). Report owns copiedµs series at`:316`. | No cross-batch response timestamp history. |
| Command report | New1000command rows, latency arrays and lookup-attempt data per `_run` (`:273–305`). Returned to caller; not stored on producer. Failure stores partial report in terminal exception (`:308–311`). | Successful batches release it before joint sample. Failure tracebacks can retain a partial report, but no later successful sample follows that latched failure. |
| Current client/credential | Replaced once per batch, rotation preserves session/receipt history (`:128–140`). | One direct client/credential reference on producer. Session authority additionally retains bounded secret/redaction history; dependency findings below. |
| Journal and application host | Created once (`:109–110`) and retained until close (`:322–333`). | Exact latest-command and all-record-offset indexes grow through the run; quantified below. Do not clear required history to lower RSS. |
| `HELD_OWNERS` | Constructor rejects another held owner; appends current owner (`benchmark_job.py:222,250`); checked close removes it (`:471`). | At most one owner on successful lane. Retention on cleanup failure is intentional fail-closed ownership, not repeated batch allocation. |
| Source maps, imported result, fixture bytes | Fixed dictionaries/bytes captured before measured loop. | Static run cost. Binary/source hashing during construction occurs before baseline; completion log hashing at`:375–376` occurs after all samples. |

The command report embeds terminal result dictionaries and snapshots, sometimes by alias (`benchmark_commands.py:177,197–204,232`). That can make one report large; the reviewed code does not keep a historical list of reports. The audited journal implementation leaves receipt bodies on disk and decodes the requested record on access; it does not retain a full receipt-body cache.

## Bounded accounting from existing S76 evidence

Raw root is `studio/.local/reviews/gt06-s76-campaign-01/run-00-attempt-02/`. No recursive tree scan or source execution was used. A Python3.11.9 read-only script parsed its six batch descriptors, native stdout markers and current command/native report, then recursively summed `sys.getsizeof` with identity deduplication. These are offline object-graph estimates, **not live RSS measurements**; independent JSON decoding can share strings differently from execution.

| Parsed structure | Bytes |
|---|---:|
| Native non-heartbeat markers:1CADENCE,7READY,6START,6BATCH,6ACK | 49809 |
| Six batch descriptors with artifact references | 19680 |
| Batch05 native raw JSON | 98338 |
| Batch05 parsed native JSON | 303076 |
| Batch05 parsed command report | 3050372 |

Marker+descriptor growth from5warmups to35batches is real and avoidable in principle, but its current shape suggests hundreds of KiB rather than a retained3MiB report every batch. This is an estimate, not a proof it cannot trigger the strict RSS comparison near a low baseline. Preallocating or moving compact provenance bookkeeping to disk could reduce instrumentation growth, but it should not be presented as an established fix before application retention is identified. Preserve duplicate-marker rejection, exact artifact references, all raw logs and the dataset assembler contract.

The six command reports are1139417,1146839,1143578,1144899,1143690,1151251bytes on disk. Their response-clock lengths are1708,1720,1709,1712,1708,1709. These fluctuations are bounded per batch in observed evidence and the full reports are released before the joint observation. Native stdout is221740bytes on disk after six batches, not a221740byte string retained on `NativeLog`.

Journal disk sizes after each batch are982013,1965558,2949103,3932648,4916197,5902542bytes. This monotonic≈0.984MB-per-batch disk growth is expected durable evidence; it **does not prove equivalent in-memory growth**. The dependency audit below identifies the smaller, nevertheless material exact indexes separately from the on-disk bodies.

Observed command-lane RSS also varies within phases: batch04 memory_before29184000, memory_after28930048, joint19091456; batch05 memory_before27959296, memory_after28835840, joint20480000. The joint figures use the accepted sample phase. Different figures do not identify trimming, allocator retention, a leak, or a sampler defect by themselves. In particular the S73 RSS failure should not be explained away with these S76 measurements.

## Application index growth: identified and quantified

`host/replay/verified_journal.py:65–73` retains exact indexes using `PackedOffsets` and `ProjectCommandIndex`. It streams the durable-history fingerprint in at most65536byte chunks (`:31–61`); it does not cache the history bytes. `host/replay/journal_index.py:16–54` stores two uint64words per journal record. Its `:60–100` keeps a nested ordinary dictionary of project→command-string→Python-int record number, with no eviction. It shares the project string rather than keeping duplicate `(project,command)` tuple keys, so that previously removed duplication is not a new finding.

Base `host/core/journal.py:386–423` updates a command's latest record index but appends an offset for **each** pending record, terminal record and lease record. `_DiskRecords` at`:73–90` rereads/decode receipts on demand. At quiescence `_pending` has drained; one fixture lease key is overwritten. The limits permit100000records (`:38–43`), greater than the49105records required by this35batch workload. Compaction is an explicit method (`:574–610`), not invoked by the audited campaign/transport path, and deliberately retains every command/tombstone key. Even adding compaction would not remove the dominant command-string dictionary without breaking the dedupe obligation.

Every batch has500inspect+200admitted+1cancel commands admitted to the journal. The300invalid-payload commands reject before append (`transport.py:629–635`). Each of the701journalled commands produces pending and terminal rows; one lease acquisition gives **701unique command IDs and1403records per batch**. Exact raw six-batch replay confirms this count. No secret, token, receipt body or session identifier was emitted in the accounting result.

The following byte estimates use the current CPython3.11.9 container representation: a shared project dictionary, command strings, latest-record Python integers, and `array('Q')` words extended in pairs. Existing raw rows reconstruct the first six states; a no-I/O, no-production-import model extends the exact command-ID format and fixed workload to35batches. Modeled04/05 match the raw-derived04/05 estimates. It excludes small fixed wrapper objects and allocator/RSS overhead.

| Batch | Unique command IDs | Record offsets | Command keys | Latest-record ints | Dictionaries | Packed offsets | Total bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 04 | 3505 | 7015 | 322335 | 98140 | 104107 | 112448 | 637030 |
| 05 | 4206 | 8418 | 386802 | 117768 | 104107 | 135080 | 743757 |
| 09 | 7010 | 14030 | 644670 | 196280 | 207867 | 233800 | 1282617 |
| 14 | 10515 | 21045 | 970510 | 294420 | 207867 | 357896 | 1830693 |
| 19 | 14020 | 28060 | 1296350 | 392560 | 415403 | 456360 | 2560673 |
| 24 | 17525 | 35075 | 1622190 | 490700 | 415403 | 581856 | 3110149 |
| 29 | 21030 | 42090 | 1948030 | 588840 | 415403 | 698120 | 3650393 |
| 34 | 24535 | 49105 | 2273870 | 686980 | 961531 | 788232 | 4710613 |

The batch04→34 increase is4073583bytes:1951535key bytes,588840integer bytes,857424dictionary bytes and675784packed-offset bytes. The dictionary crosses its next capacity step around21845keys, reached during batch31, so the growth is not smooth. The absolute retained representation remains within the configured broad resource caps, but it has not plateaued after warmup. At the observed joint baselineRSS19091456, the10% comparison permits at most21000601total bytes, or1909145growth bytes. Index representation growth is2.13×that allowance. Batch19's modeled index delta is1923643bytes, already slightly greater than the allowance; **this is not a prediction that RSS fails at19**, because allocator pools, shared objects, pages and residency are different measurements.

Transport itself has smaller bounded state. `transport.py:63–76` caps pending jobs16, sessions16, credential history64, diagnostic messages32 and concurrent connections8+2. Terminal jobs are removed at`:706–710`, dequeued at`:717`, and the worker resets its local job on each iteration. Session rotation overwrites the same session entry (`:138–151`); `_issued` and the combined redactor retain every issued secret by design (`:109–143`), with35rotations below the64limit. Lease dictionary entries prune expired entries and replace the same session key (`:566–568`). No successful-request list or cumulative terminal-job dictionary was found. Do not weaken redaction history to lower RSS.

## Concrete outcome and next check

No unbounded successful-batch stdout/report retention defect was found. There **is** intrinsic, non-plateauing application index growth material to the unchanged RSS gate. This is a representation/workload mismatch to investigate, not permission to discard correct dedupe history. The three-file-only findings are insufficient without this dependency result, and the completed review should not be summarized as “no host growth.”

The maintainable fix choices preserve the complete `(project_id, command_id)` identity and every tombstone; the authoritative append/fsync journal remains unchanged:

| Option | Benefit | Required proof and risk/scope |
|---|---|---|
| Disk-derived exact index with fixed resident cache | Strongest resident-memory bound; full IDs/record locations stay recoverable on disk. | Secondary state must be reconstructible from authoritative journal bytes, synchronized under its existing lock, and invalidated/rebuilt on changed history. Additional file lifecycle/crash/reopen/path safety and cache sizing need validation. Extra I/O may threaten current lookup/status latency. Candidate implementation belongs in `host/replay` index/VerifiedJournal and its targeted tests; changing accepted base Journal semantics broadens the dependency audit. |
| Packed exact ID storage / common-prefix compression, with compact record numbers | Removes many per-string/per-int/dictionary allocations while preserving arbitrary IDs, not merely this benchmark's known name grammar. A shared byte pool or prefix representation can preserve full key bytes. | Exact project separation, Unicode/byte canonical identity and collision comparison must match current mapping behavior; no truncation, lossy hash-only membership or eviction. It still grows with IDs unless storage/cache is bounded, so smaller measured footprint alone does not prove a plateau or the RSS gate. Keep the replacement mapping's iteration/compaction contract. Lower dependency scope if contained in `journal_index.py`, but all callers and reconstruction paths still need review. |

Hash acceleration in either option must verify full exact keys on collisions; a probabilistic filter cannot be the only dedupe check. Keep the same validation, lock/reload/durability barriers, changed-history checks, crash/reopen/compaction reconstruction and exact error semantics. Preserve existing lookup/status deadlines and measure the latency tradeoff. No baseline prefill, ballast, RSS waiver, workload reduction, altered warmup or tombstone pruning is proposed. No implementation was made while the native source remained frozen.

The useful diagnostic is fixed per-batch scalar cardinalities/retained-byte estimates for the actual application caches, plus instrumentation collection sizes and phase-labelled RSS, on a disposable run. Record counts without serializing secrets or full request histories into diagnostic output. Do not add a count-dependent resampling policy, change baseline04, trim the process working set, inflate warmup memory, erase tombstones/receipts, or weaken the10% gate. A later observed stable plateau is evidence; a theoretical bound alone is not.

## Read-only accounting reproducer

Run this Python3.11.9 program from the repository root (for example feed the code to `python -B -` through a PowerShell single-quoted here-string). It opens only the already-existing6MiB S76 journal, creates ordinary local containers, emits aggregate numbers, and neither imports production modules nor launches engines, listeners or tests. The synthetic continuation reproduces the **representation and identifier/workload cardinality**, not journal execution, performance, durability or RSS. Constant offset/length values in that continuation do not affect the `array('Q')` storage size.

```python
import json, sys
from array import array
from pathlib import Path

root = Path('8-9-hh3d-3/studio/.local/reviews/'
            'gt06-s76-campaign-01/run-00-attempt-02')
ends = [982013, 1965558, 2949103, 3932648, 4916197, 5902542]

def size(projects, words):
    keys = sum(sys.getsizeof(k) for d in projects.values() for k in d)
    values = sum(sys.getsizeof(v) for d in projects.values() for v in d.values())
    dictionaries = sys.getsizeof(projects) + sum(
        sys.getsizeof(k) + sys.getsizeof(d) for k, d in projects.items())
    offsets = sys.getsizeof(words)
    return dict(commands=sum(map(len, projects.values())), records=len(words)//2,
                key_bytes=keys, value_bytes=values, dict_bytes=dictionaries,
                packed_offset_bytes=offsets,
                total=keys + values + dictionaries + offsets)

projects, words, offset = {}, array('Q'), 0
actual = []
with (root/'commands/commands.jsonl').open('rb') as stream:
    for line in stream:
        record = json.loads(line)['record']
        index = len(words)//2
        words.extend(array('Q', (offset, len(line))))
        if record['kind'] == 'command':
            projects.setdefault(record['project_id'], {})[record['command_id']] = index
        offset += len(line)
        if offset in ends:
            actual.append(dict(batch=ends.index(offset), **size(projects, words)))

projects, words, modeled = {}, array('Q'), []
run, project = 'gt06-s76-campaign-01.r00.a02', 'benchmark.commands'
def append_record():
    index = len(words)//2
    words.extend(array('Q', (index*704, 704)))
    return index
def admitted(command):
    projects.setdefault(project, {})[command] = append_record()
    projects[project][command] = append_record()

for batch in range(35):
    append_record()  # One lease.
    counts = dict(inspect=0, admitted=0)
    for group in range(100):
        for kind in ['inspect']*5 + ['admitted']*2:
            admitted(f'{run}.b{batch}.{kind}.{counts[kind]}')
            counts[kind] += 1
        if group == 49:
            admitted(f'{run}.b{batch}.cancel')
    if batch in (4, 5, 9, 14, 19, 24, 29, 34):
        modeled.append(dict(batch=batch, **size(projects, words)))
print(json.dumps(dict(python=sys.version, actual=actual, modeled=modeled), indent=2))
```

## Source hashes

| File | SHA256 |
|---|---|
| `run_benchmark_campaign.py` | `09f9d6a24c6281193f21c9aa89c48602ac5d70dfe86882fbaf76e8366c66dd6c` |
| `benchmark_commands.py` | `522e91341eda6175704b692cd9bc5454951f93a891657e815a9a2111cd3eb438` |
| `benchmark_job.py` | `be424a6f37ae573ac4bf40954b31017025daee2147699c80b05f9a0ab70e1611` |
| `host/replay/verified_journal.py` | `9128749e6a04242106e56a86e959b6de0a67e0f10ffb97965e1bc88390d5a6f2` |
| `host/core/transport.py` | `1ec03356b1cb8c8987e1604bcb164aea6a9934dbe259451c19e12de36398aba0` |
| `host/replay/journal_index.py` | `e7b505a928f3100173007413bb9b3f914931bd2431a5033280a309cc4c4ca5c6` |
| `host/core/journal.py` | `826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6` |

These are scoped source hashes, not a final source closure or acceptance seal.

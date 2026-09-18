# S97 read-only HTTP analysis of the S96 terminal failure

`AUTHORITY=0`; `formal_acceptance=false`; `final_critic=false`.
Run: `gt06-s96-coupled-phases-01`. Read nested AGENTS and the GT-06 plan;
performed bounded JSON/source parsing only, with no engine/test execution,
runtime imports, source/helper edits or threshold changes. Derived values and
every directly used input hash are in `http-analysis-01/analysis.json`.

**No lookup transport failure was recorded in S96.** All eighteen command files
(`00` through `17`) are COMPLETE: 18,000 commands, comprising 9,000 inspect,
5,400 rejected and 3,600 admitted commands. Their 12,631 lookup attempts contain
12,600 COMMITTED, 13 ACCEPTED_PENDING and 18 CANCELED results; none is UNKNOWN,
and every per-attempt `transport_failure` is null. The frozen recorder agrees:
all route failure counters are zero, `first_failure=null`, `spans_dropped=0`,
`identity_missing=0`, and no unfinished spans remain at terminal capture.
The counter is cumulative and independent of ring eviction; a missing snapshot
alone would not have established this result.

Batch 17 completed all 1,000 HTTP commands, with effects 3,400→3,600 and maximum
response gap 418.1515 ms. Across all eighteen command files, the largest gap is
1220.1735 ms (batch 7), and the longest lookup is 1212.973 ms, successfully
COMMITTED for `b7.inspect.0`. Two inspect end-to-end latencies exceeded two
seconds: 2005.6215 ms in batch 7 and 2080.8801 ms in batch 8. Their admission
receipts divide those intervals; an end-to-end duration is not the consecutive
response-gap criterion. No S93-style two-second response gap is shown here.

The separate native terminal record is `BENCHMARK_HOST_ACK_READ`, batch 17,
cycle 100, phase HOST_BARRIER. Only seventeen joint rows completed. Native
failure time is 55.117 ms after barrier issuance, with 29,944.883 ms remaining
before its deadline. The frozen native method uses that READ code for either
failed `FileAccess.open` or a short `get_buffer` result; the record does not
distinguish those branches. The final 423-byte ACK has the matching native batch
hash, but later valid bytes do not prove readability at the failed instant.
This is a native file-read failure, distinct from S93's batch-6 HTTP lookup
UNKNOWN / 2033.1318 ms response gap. Neither failure's cause is repaired or
established by this analysis. Godot ticks and host QPC were not subtracted
across clock domains.

## Timing growth actually retained

The following are descriptive values from the instrumented run, including
warmup rows. Lookup durations use the recorded integer-microsecond endpoints;
p95 uses nearest rank. No instrumentation overhead has been subtracted.

| Batch | Warmup | Journal bytes | HTTP batch seconds | Lookup median / p95 ms | Inspect median ms |
|---:|:---:|---:|---:|---:|---:|
| 0 | yes | 976,405 | 44.904 | 30.402 / 42.919 | 47.567 |
| 4 | yes | 4,888,157 | 69.060 | 43.852 / 62.597 | 74.619 |
| 5 | no | 5,868,894 | 74.951 | 46.379 / 65.313 | 80.846 |
| 10 | no | 10,775,385 | 101.624 | 62.415 / 90.777 | 114.291 |
| 17 | no | 17,660,179 | 138.021 | 86.639 / 128.522 | 163.069 |

Journal size, batch duration and median lookup latency increased at every
recorded batch. The frozen journal code reloads/verifies the journal through
`_snapshot`, so growing verification work is a plausible contributor. This
association is not a controlled causal result: early phase traces were evicted,
and scheduling, other IO and diagnostic overhead are not separately measured.

## What the final phase window can show

The 512-event ring evicted **1,263,154** earlier events. Its retained timestamps
span only 991.5852 ms at the end of batch 17's HTTP work; the last event precedes
the terminal snapshot by 23,857.8478 ms. Six retained exit records have evicted
entry markers, although each exit retains its start timestamp. Consequently,
these are tail-only durations, not run-wide maxima or a phase trace of the
native ACK read:

| Delegated boundary | Retained exits | Tail maximum ms |
|---|---:|---:|
| Journal combined guard acquisition | 24 | 3.5565 |
| Journal snapshot | 24 | 45.0964 |
| Journal reload | 24 | 45.1377 |
| Journal guarded operation through release | 24 | 61.2887 |
| Journal append | 10 | 15.2467 |
| Host terminal finish | 5 | 64.6286 |
| Server dispatch | 13 | 124.8817 |
| Server send/encoding/drain | 13 | 1.1410 |

Five complete tail lookup chains can be joined by port pair and client/server
root IDs. Their dispatch-to-lookup intervals range from 48.5203 to 90.9662 ms;
the lookup bodies take 31.9002–42.3086 ms. Each interval overlaps a host finish
span. For example, client root 570358 / server root 570361 on ports
`(60571, 54868)` has 90.9662 ms dispatch-to-lookup, a 33.9023 ms lookup and an
overlapping 52.1760 ms finish span. This is consistent with contention or
serialized host work. It does **not** identify pure lock wait: dispatch also
performs validation, no host-lock acquisition marker exists, and the finish
overlap does not account for the whole interval. Nested journal spans overlap
and must not be added together.

The next repair decision should follow the native ACK file-open/short-read
evidence owned by the separate ACK investigation. These HTTP records do not
justify transport retries, timeout/threshold changes, moving durability work,
or blaming the native ACK read on journal contention. S93 remains unresolved;
S96 supplies a negative observation for lookup transport failures over this
recorded prefix, not a full-run pass.

## Exact evidence identity

Paths below are relative to the S96 run folder unless marked otherwise.
The reported 51-file source closure is
`564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752`;
the helper closure is
`49305105575402570035bbff7f3f7abdcc5a98653b8cc994932b4ae07f921795`.
Directly inspected frozen code hashes match their manifest entries; this was
not a new whole-repository/source-closure audit.

| File | SHA-256 |
|---|---|
| `http-phases-final.json` | `9f41e7ba63253e24555ad8d9b1b68cdd83e620ec08da5e6ffb4fcbd002e9dac8` |
| `command-17.json` | `3b18de408d917b89cf4232c1f9563cd0223b71be7818825f051c9813f9bb1cc5` |
| `project/benchmark/out/failure.json` | `f2c9bb97110a3e469f6d988d5f639b46366f573c947b114b1f2f68ad3a9d93ca` |
| `project/benchmark/out/batch-17.json` | `ba30ed708117e7f9bb526f49f416a4e52dbf25822dc0ad23b9562d069ad3fa11` |
| `project/benchmark/input/ack-17.json` | `ed082013ff329c80205d253bfe630f125978c5326797aa04e97c711c5e7c95bd` |
| Frozen `phase_observer.py` | `9a79e5767f07674e80fb457b6d8f6326cb3558e9feb1d5d51884ad7784f5be57` |
| Derived `http-analysis-01/analysis.json` | `3d7a6194748f3b71ba0115873779ddf07d935e0d3fdd49408ff0b95c52f2b9b0` |

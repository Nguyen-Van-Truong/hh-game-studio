# S100 copied-history HTTP result

AUTHORITY=0; formal_acceptance=false; eligible_for_dataset=false.

The probe completed 20 groups/200 commands/160 lookup attempts with 40 mock effects
and 20 cancellations confirmed without effect. Maximum host status gap was 446.3703 ms
(group 12); longest lookup was 382.548 ms (group 4). No transport failure occurred and
first_failure is null. This does not establish the cause or repair of S98's 2-second
lookup timeout.

The unchanged source51 closure is `cfc4b55a5407891bfd54d22d9f1ac45a74b6c744898199a0e4690d6230a6c1d6`. It loaded
17,761,123 exact S98 postterminal history bytes, then used a fresh project/producer.
This reconstructs neither the pre-failure batch17 history nor coupled residency.
Initial journal load took 12.6688604 s, outside HTTP response windows. The 20 HTTP group
windows totalled 37.318641 s (first-to-last envelope 37.351543 s).

Within the 780 HTTP snapshot contexts (28.7525402 s total), sequential suboperations
accounted for:

| Snapshot suboperation | Total | Share of snapshot time |
|---|---:|---:|
| Hash update |20.272694 s|70.5075%|
| Read |5.0855682 s|17.6874%|
| Snapshot fsync |0.4030053 s|1.4016%|
| Residual |2.9912727 s|10.4035%|

Read and hash each processed 13,943,550,521 bytes across these snapshots. These are
wall-clock call durations, potentially including descheduling. Shares use only
snapshot time; they are not an HTTP/CPU profile or a cause allocation for S98.
Residual includes other snapshot work and instrumentation. Snapshot fsync excludes
append/parser/SQLite durability work. Nested reload/guard/dispatch totals overlap
and must not be added to this table.

The retained trace covers the largest observed gap: group 12 admitted command 9,
client/server socket pair 53341/61540. A 444.0249 ms commands dispatch contains a
366.8098 ms guard-held span, including a 297.7172 ms append. This locates the large
cost inside append in this observation, without identifying append's internal
I/O/SQLite/fsync/scheduling component or explaining S98's lookup timeout.

The ring retains 8192 events and evicted 9418 earlier events. It reports 0 dropped active
spans, 0 missing identities and 0 unfinished spans at completion. These counters do
not establish a complete lifetime trace. first_failure remains null.

Target 37560 and helper 36872 exited 0; owned tree verification succeeded, no timeout,
stderr/stdout empty. Producer threads/sockets/index/observer handles closed according
to the retained cleanup record. Source, helper and original/copied history checks
remain unchanged. This runner supplies its owned Job/actual-exit evidence; it does
not add the separate retained-handle observer's proof.

The JSON analysis records hashes for every input, operation totals, the retained
span chain and limitations. Reproduce by running `analyze_result.py` against an
unchanged retained run in a fresh analysis location; exclusive outputs prevent
overwriting this analysis. No runtime or engine was launched by analysis.

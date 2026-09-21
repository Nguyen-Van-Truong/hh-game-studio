# S147/S149 derived-metadata audit

**Scope and cut.** Read-only comparison of derived metadata against the immutable
S147 raw packet and the S149-01/S149-02 packets. The initial audit cut caught
S149-02 while its child output had reached batch 6; a terminal receipt arrived
later and is recorded in the terminal update below. No raw file, source file,
plan, gate, or running process was changed.

## S147: derived fields checked against raw

- `terminal-01/derived-command-10-counters.json` matches raw
  `command-10.json`: batch 10, command max gap 742.7797 ms, host handles
  204→205, host RSS 37,777,408→37,265,408 bytes, PID 34156 and the same
  process-start token. Its null `profile_sha256` and
  `source_closure_sha256` are appropriate for a command-only projection;
  those fields are present in raw `joint-10.json` and must not be filled by
  copying from a different row.
- `terminal-01/attribution-01.json` has 11 rows and its handle/editor/
  ObjectDB/resource fields agree with the corresponding raw command and joint
  rows. Its `host_rss_before/after` values are command-lane samples
  (batch 4: 48,664,576→44,666,880; batch 10: 37,777,408→37,265,408).
  The plan text’s 45,051,904→37,789,696 values are the joint-lane host RSS
  samples. Both are valid observations from different points; derived reports
  must label the sampling domain instead of presenting them as a contradiction.
- The terminal manifest has 17 entries, but `attribution-01.json` is marked
  “derived read-only.” The count is therefore 16 raw/supervision entries plus
  one projection, not 17 independent captures. This is a wording/interpretation
  correction only; the raw hashes and manifest need no rewrite.
- S147 remains a failed AUTHORITY=0 prefix: accepted full runs 0, actual host
  exit 1, import exit 0, editor target exit UNKNOWN. Nothing in the derived
  files upgrades it to a pass, no-leak result, or root-cause finding.

## S149 observer metadata

S149-01 smoke provides the reason for the S149-02 scheduling adjustment:

- Child sample: 173 target handles.
- External PSS census: target handles 174 before and after; observer handles
  182 before and after; `binding_verified=true`.
- This is a one-handle census/sample mismatch in a one-batch smoke and is not
  evidence of a workload handle growth. S149-02’s decision text accurately
  describes this as an observer-neutrality concern, but derived summaries should
  identify the source run explicitly as `gt06-s149-handles-smoke-01`.

At the initial live audit cut, S149-02’s raw evidence showed:

- The child PID/start identity is stable at PID 41448 /
  `windows:134345066811188986`.
- Child samples for batches 0–6 are 173 handles; the batch-04 external census
  is also 173 before/after with `binding_verified=true`.
- RSS varied by batch but no terminal gate had been reached in the available
  prefix. `result.json` and `summary.json` were not yet present at that cut.
  The later terminal receipt supersedes this live-state observation; at the
  initial cut it was correct not to infer “completed,” “non-reproduced,”
  cleanup, or a final disposition from stdout, directory presence, or the
  current process list.

The S149-02 owner receipt `owner/process-start.json` contains only the PID.
The checkpoint and PSS census carry the process-start token and the census
reports successful identity binding. A derived report may claim binding from
those records together; it must not describe the standalone owner receipt as a
complete creation-time identity record.

## Naming and closure metadata to preserve

- The supervisor request uses outer run/task ID
  `gt06-s129-s149-host-handles`, while the child workload uses
  `gt06-s149-host-handles-02` (and the smoke uses
  `gt06-s149-handles-smoke-02`). These are distinct identities. Any post-run
  summary should label supervisor ID, child run ID, and packet directory
  separately; collapsing them into one “run_id” would be an incorrect derived
  claim.
- S149-02’s freeze map contains 244 relative source entries. The child
  invocation adds the freeze file as the 245th expected source entry. The
  supervision request also carries 245 entries but uses absolute paths. This
  is the same pinned set only after path normalization; raw map hashes should
  not be compared as if they used the same path domain.
- S149-02 freeze metadata intentionally has `authority=0` and a Python pin but
  no scalar runtime/profile closure fields. The invocation/request carry the
  source map, profile through pinned files, and `formal_acceptance=false` /
  `eligible_for_dataset=false`. Do not backfill a runtime closure or
  acceptance flag from S147 or S149-01. If a closure digest is needed after
  terminal, derive it from the S149-02 frozen map and record it as a new
  derived value with its hash domain.

## Repairable metadata actions after S149-02 terminal

These can be corrected from already captured raw files without another engine
run:

1. Publish a terminal-only derived summary with the separate supervisor and
   child IDs, actual target/helper exits, processed checkpoint labels, and
   cleanup result.
2. Label every handle/RSS value as child command sample, joint sample, or
   external PSS census; retain both S149-01’s 173→174 mismatch and S149-02’s
   173→173 result as separate observations.
3. Normalize relative versus absolute source-map paths before comparing source
   closure membership or hashes.
4. If the raw terminal packet is complete, recalculate only packet file counts
   and derived row hashes. Keep `authority=0`, `formal_acceptance=false`,
   and `eligible_for_dataset=false`; no metadata repair can create GT06
   acceptance.

At the initial audit cut, the safe status was **live, non-terminal host-only
diagnostic; no derived acceptance or non-reproduction claim**. The terminal
receipt is now incorporated below; its authority and acceptance fields remain
false.



## Terminal update: S149-02

S149-02 is now terminal and remains AUTHORITY=0:

- Child run `gt06-s149-host-handles-02` completed batches 0–9 and stopped
  before batch 10 with `CAMPAIGN_RETAINED_COUNTER_GROWTH`. Child actual exit
  is 1; helper/wrapper exit is 1; `capture_verified=false`. The supervision
  launcher also has retained-handle actual exit 1, and its handle-close receipt
  reports native close success.
- The original child sample changed from 173 handles at batch 4 to 174 at
  batch 9. External PSS at checkpoint 04 was 173→173; at checkpoint 09 it was
  174→174 with the same PID/start binding and observer count 160→160. This
  confirms the count change was present in both the child counter and the
  external census; it is not the S149-01 one-handle census mismatch.
- The PSS type counts changed from 23 to 24 Event objects; all other aggregate
  type counts were unchanged. Handle-set comparison shows numeric slot churn
  (an Event at handle 916 and a Semaphore at 1000 appeared while a Semaphore
  at 608 disappeared). Names and object identities are unavailable. This is
  measured descriptor-class evidence that can support one narrow follow-up
  hypothesis, but it does not identify object identity, ownership, leak, or
  root cause.
- Batch 9 command max status gap was 1,518.2795 ms, below the 2,000 ms gate;
  RSS decreased from 37,597,184 to 37,138,432 bytes. The retained-counter gate,
  rather than RSS or status gap, caused the stop.
- Child cleanup is clean (`errors=[]`, journal closed, probe released, no
  live threads, source unchanged), but cleanup success does not turn this
  host-only diagnostic into a formal pass. The final summary remains
  `formal_acceptance=false`, `eligible_for_dataset=false`, and explicitly
  omits native/ACK/idle/assembly coverage.

The safe derived disposition is **S149-02 failed at the original host handle
gate with a reproducible +1 process-count observation and Event-class delta;
descriptor identity/root cause remain unresolved**. No formal retry, source
repair, or GT06 acceptance follows from this packet alone.


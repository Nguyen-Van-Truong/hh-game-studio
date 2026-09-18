# S82 preservation of failed S81 campaign

AUTHORITY=0. FORMAL_ACCEPTANCE=false. This packet preserves the failed
`gt06-s81-campaign-01` launch 1. It is neither a benchmark PASS nor an
independent acceptance critic. GT-06 remains open.

The original campaign and sibling supervisor under `studio/.local/reviews/`
were read without modification. `raw-locator-hashmaps.json` inventories all
325 files, including excluded source and cache, with exact SHA256, size and
mtime. A complete second inventory matched. `preserved-byte-manifest.json`
binds 172 exact copies and lists every excluded file. All 12 supervisor files
are copied. Frozen source trees, caches and bulk project content remain in
the original raw locations. The exception is the 294-byte fixture scene:
its bytes differ from the initial/editor maps and are needed for review.

Verified source checkpoint `b3862a10` and admission HEAD
`d1254bf8fbc18585a19cb41153581ec832280425` match all 51 runtime paths in both
frozen snapshots and the live source at preservation:
`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`.
The profile hash is
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
No runtime modules were imported or executed to perform these checks.

The run failed at batch 15, `joint_observation`, with
`CAMPAIGN_RETAINED_COUNTER_GROWTH`. Captures 0–15 contain 16,000 command rows,
1,600 native cycle rows and 16 unique cancellation receipts. These comprise
5 warmup and 11 measured captures, including the failing sample; there are
zero complete/full PASS runs. All 96 batch artifact references and all 16
sample evidence hashes were checked. ObjectDB grew from the batch-4 baseline
71,128 to 71,130 at batch 15. The retained-counter/status screen found this
single breach; it is not a full latency or benchmark acceptance verdict.

Host target PID 4132 has actual exit 1. Import target PID 34776 has actual
exit 0. Editor target PID 48332 has no process-exit receipt; helper PID 22376
exit 2 is separate. Host/editor/import Jobs report zero and closed, with no
recorded uncertainty; host/editor wrapper handle receipts report closed.
The child-terminal-cleanup record additionally reports closed producer,
journal, probes, sockets and threads. Its null host self-exit is reconciled
with the later parent-owned host process-exit receipt, never synthesized.
The scheduler readback is state 3/result 1/no instances; no recorded target,
editor helper or supervisor PID appears in the later process snapshot.
Neither this absence nor scheduler result substitutes for natural exit.

All 30 fixed attempt slots were checked with `lexists`; no operator Stop
latch was present. Both raw roots were searched by filename as well, and
the supervisor latch was absent. Per-batch cancellation receipts remain
present and are distinct from operator Stop latches.

Gaps remain explicit in `terminal-facts.json` and `verification.json`:
editor natural exit and supervisor actual process-exit are missing; the
import wrapper-handle receipt and host/import helper PID inventory are
absent; no full run passed; the cause of +2 ObjectDB is unproven here.
The fixture scene differs from both initial maps (`51eaa111…`) but its
actual hash (`2e7fa9a1…`) matches every native saved-file receipt. This is
an observed serialization difference, not an unchanged-project claim or
a diagnosis of the ObjectDB increase.

Hash domains are separate:

- Raw/copy hashes: SHA256 of exact file bytes. Raw inventory also binds size
  and mtime_ns. Copies were not normalized or redacted. `.gitattributes`
  disables text conversion for any future staging of this packet.
- Runtime closure: SHA256 of UTF-8 concatenated sorted rows
  `path + NUL + lowercase_file_sha256 + LF`.
- Sample evidence hashes: compact sorted-key JSON of source/profile/run/
  index/processes, six artifact refs and barrier receipt, as recorded in
  `completeness-and-screen.json`. These differ from raw batch-capture hashes.
- Packet hash: SHA256 of the exact `package-manifest.json` bytes. The
  manifest enumerates every file under this packet except itself and
  `package-manifest.sha256`; the sidecar is its lowercase digest plus LF.
  It is a preservation hash, not a signed acceptance manifest.

`observe.py` captures read-only scheduler/process/Git observations.
`preserve.py` performs collection with exclusive output creation.
`verify_preservation.py` is a separate read-only recheck that writes a new
report, performed by the same preserving agent, not an independent critic.
`seal.py` verifies those files and seals the packet. Run these with `python
-B`; the collector/observer/sealer intentionally refuse to overwrite outputs.
Two pre-copy collector attempts were retained as `collector-attempt-01/02`:
one exposed the initial-project byte assumption, the other corrected a
sample-evidence hash-domain assumption. Neither wrote raw files or copied
evidence before stopping. The final collector completed with exit 0.

Selected copies passed a limited sensitive-key/credential-pattern screen;
no credentials or token files were selected. The packet includes no engine
run, test execution, runtime source edit, process control, plan edit or commit.
Full raw re-verification still needs the original excluded files in place.

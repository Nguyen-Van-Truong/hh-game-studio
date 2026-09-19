# S105 coordinator corrections

AUTHORITY=0. Supplemental evidence only; no GT-06 acceptance or runtime repair.

The S104 committed packet had 20 files whose Git blobs differed from their
manifest-verified working bytes because of CRLF normalization. The read-only
`s104-git-byte-audit.json` preserves the old commit, blob identities, working
hashes and comparison for all 193 inventory paths. The new S104 `.gitattributes`
uses `* -text`; only the affected evidence paths are re-staged from the original
working bytes. This does not rewrite Git history or change raw evidence.

The two S103 generated children are retained in `s103-generated-supplement/`.
Each matches its original context's `child_script_sha256`. This supplements the
previous packet; it does not retroactively prove the mutable parent helper used
at launch. The old retained report and manifest remain historical inputs.

`archive/tools-plan-s104-committed.txt` is an exact copy from commit
`1c6cbbf3cb4f07ccb8b5841c1b9686768ce6c96d`, with AUTHORITY=0 and a recorded hash.

## Corrections to interpretation

The S104 reader report's phrase “authored frame” should read **observed engine
process-frame counter**. The markers use `Engine.get_process_frames()`. The
accepted ordering allows that counter to advance during save dispatch; it does
not prove the engine's internal cause. The S103 prefix maximum status gap was
728.622 ms at batch 1; 642.433 ms was batch 5 only. Original report bytes are kept.

S105 collector errors are not engine failures: missing `os`, sample `run_id`
lookup, and an undefined `_write` prevented their intended diagnostic outputs.
The original summaries' generic `GATE_RECORDED` and hardcoded `engine_started`
are not trustworthy completion claims. Use the independently derived S105 result
packet. Run 03 reached six batches, did not reproduce the handle excursion and
captured only baseline batch 4. One snapshot cannot supply a type delta.

## Lessons and next boundary

- Exercise the generated child with actual sample/context shapes in static tests
  before any expensive launch. A syntax check of a different helper is inadequate.
- Bind helper bytes separately from the unchanged runtime closure. Record the
  original gate result before observer work; preserve its error if collection fails.
- Keep exact-file SHA and reserialized semantic SHA in explicitly named domains.
- Derive completion, engine start and target/helper exits from bound raw receipts.
  Unknown natural exit remains unknown after a forced diagnostic boundary.
- PSS after batch 4 can affect the next READY interval. Never subtract observer
  duration or relax the original status gap, retained-counter or RSS gates.
- A further handle comparison must be a single finite, discriminating attempt
  with preflight and two bound captures; no repeated identical prefix campaign.

The S102 native latency failure remains a separate unresolved boundary. S105
does not justify a runtime change or a formal campaign retry.

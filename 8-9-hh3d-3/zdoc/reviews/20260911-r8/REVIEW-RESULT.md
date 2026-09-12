# S20 — GT-01 remains in progress

The tools plan is first. HH World implementation still waits for GT-10.
S19 design hardening is present; no statement that either plan is perfect,
public-ready or proven at hundreds of millions of users is justified.

## Verified change

The Godot version probe previously searched combined output without requiring a
successful process exit. It now runs through the existing owned Job/process group,
requires target and wrapper exit0, no timeout, verified process-tree completion,
empty stderr and a bounded single official version string. This prevents a failed
or noisy `--version` invocation from being mistaken for a valid probe.

- Ten new version admission tests passed, including a valid baseline and actual
  temporary log files written by the mock into the supplied output directory.
- Five pre-existing process tests passed; the existing duplicate-output test still
  fails in setup before the intended branch and is not claimed as adequate coverage.
- Real Godot4.7.2 run `GT01-R8-20260912T071338Z`: host exit0; import, parse and input
  trace exit0; PASS/QUITTING readback and owned process trees empty. See
  [version-runtime.json](version-runtime.json). This is partial runtime only.
- S20 runner now binds caller version/executable/checksum arguments to the
  candidate lock, checks lexical path ancestors before resolve, rechecks source
  and binary hashes after snapshot, and rejects warning/error markers in both
  stdout and stderr. The run above passes these checks; negative stream tests
  are included in the 17-test bootstrap suite.
- The first post-runtime check correctly exposed Godot-generated `.gd.uid`
  files in the snapshot. Those two deterministic fixture files are now tracked;
  `.godot/` remains generated cache and excluded from the manifest. The reminted
  run then passed snapshot stability.
- Window/Blender tests from S18 have not been reminted for the new source closure.

Remaining GT-01 work: recheck source/binaries/lock after the complete runtime,
reproducible bootstrap and verified rollback, remint headed/Blender evidence on
the current source hash, complete TQ01/TX12/TX14 evidence, and obtain two
independent critics for the entire WP. GT-02 is not open.

## Worker adjudication

The previous broad batch had stale S13 instructions despite S19 input files. Its
five workers exited0 with missing mandatory reports. Host-runner claimed commands
and writes that do not occur in the event log. Fixture and the subsequent canary
repeated malformed shell/Python commands. No output was promoted.

The r8 runner/admission and offline-bootstrap JSON bundles were malformed.
The memory bundle parsed after removal of one Markdown fence, but its code used
nonexistent APIs/config substitutions, inherited the full environment, never
saved notes, and failed to clean up its second worker. It was rejected without
execution. The coordinator instead performed a bounded runtime verification of
the installed package directly, with isolated child environment and private data.

The first small version bundle compiled but failed 7/10 tests (path method
precedence, wrong regex and mocks writing to the wrong directory). The repair
bundle targeted an unleased test file. Both are rejected. Under tools-plan8.2,
the coordinator wrote the small correction after these two failed attempts.
Raw attempts stay in TEMP with immutable hashes in the role receipt files.
Two read-only Grok critics reviewed the small-change snapshot. Critic A returned
PASS for the exact runner/test hashes, read both files and left source unchanged.
Critic B read both files but exited1 after provider rejection
`403 SAFETY_CHECK_TYPE_DATA_LEAKAGE`; no verdict was accepted and no bypass was
attempted. See [critic adjudication](critic-adjudication.json). The second critic
is still missing; neither report accepts the complete GT-01 WP.

Plan S20 passes the inherited31/31 mutation tests and static graph/hash checks.
They do not test the completeness of S19/S20 design additions. Current reproducible
check: `python 8-9-hh3d-3/zdoc/reviews/20260911-r8/validate_s20.py`.
The new archive-verification worker owns only two new helper/test paths; extraction
and rollback remain separate pending steps. Its batch/session lives in the local
manifest, and any result must pass the same parse/lease/tests before integration.

## AgentMemory short trial

Tested the actual full server from `@agentmemory/agentmemory@0.9.29`, pinned
iii0.11.2 image, no LLM provider, no embeddings, no hooks or client integration.
Six manually authored project notes; no transcript import or API key inheritance.
See [memory-result.json](memory-result.json) and [raw runtime](memory-runtime.json).

- Six keyword queries placed the expected note first, including accented Vietnamese.
- An absent keyword and a query for an empty control project returned no results.
- Restarting both engine and worker retained identical result IDs and scores.
- Ten warm recall samples: median62.5ms, maximum94ms. Engine container sample
 6.469MiB excludes Node and Docker/VM; it is not total memory usage. Data11,516bytes.
- `rg` found the same keyword notes in about21–23ms including process startup.
  This tiny comparison is not a complete coding-task/cost benchmark. Some BM25
  lower-ranked results were irrelevant because notes share source metadata.
- `token_savings=null`, coding quality not measured. The server was stopped after
  testing; no permanent Codex/Grok config or hook was installed.

The stock Windows Docker demo failed with mismatched relocated ports and an
iii-exec watcher lacking its source/Node project. It also wrote a global
`.agentmemory/engine-state.json`; that exact trial marker was moved to TEMP and
the default test container stopped. Native binary download timed out before an
archive existed (not corruption/checksum evidence). Standalone MCP fallback is
substring search and must not be reported as full BM25 evidence.

Decision: keep the experiment off when idle; use source-linked curated notes
and explicit recall only when useful. There is no evidence yet that AgentMemory
is the cheapest option. Any later pilot must measure successful-task cost and
quality against no-memory, exercise stale/conflicting populated-project memories,
and revalidate source hashes before treating recalled notes as applicable.

## Sources and limits

- [AgentMemory source and install modes](https://github.com/rohitg00/agentmemory)
- [Pinned iii0.11.2 release](https://github.com/iii-hq/iii/releases/tag/iii%2Fv0.11.2)
- Installed package files and actual local runs are the evidence for the behavior
  above; upstream marketing metrics are not project quota/quality measurements.

Neither memory retrieval, static plan tests nor a worker exit0 grants acceptance.

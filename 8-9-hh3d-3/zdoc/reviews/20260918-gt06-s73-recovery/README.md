# S73 recovery — candidate, not acceptance

S71 campaign01 terminated with ADMISSION_UNKNOWN after33 complete batches. The failed inspect request is durable QUEUED thenCOMMITTED under the same ID/digest; the wire receipt was lost at2013.8505ms. Raw does not retain the socket exception subtype. The journal is below all byte/record limits and the lease is still valid. `admission-diagnosis.md` and `failure/` retain exact facts, checksum validation, native-exit limitations, cleanup and all failed samples. Never resume those33 partial batches as a complete process run.

The selected production change is deliberately local: `host/replay/verified_journal.py` uses SHA-512 for its ephemeral in-memory history fingerprint, retaining the existing64KiB full-file read and every file-shape, identity, size, policy, corruption-parser and fsync check. Local append still extends only a previously verified state. No record body is cached in RAM. Persisted record checksums, request digests, wire schema and evidence/source SHA-256 hashes remain unchanged. Accepted Journal and transport source are unchanged.

The bounded synthetic32MiB study supports this choice over buffer-only changes: same-loop SHA512 median56.900ms versus SHA25676.177ms, about25.3% lower in that paired run. This is hashing-path evidence, not a full-workload speedup or proof that all lost receipts are fixed. No deadline, memory/counter limit, workload, sample count or UNKNOWN handling was relaxed. Python exposes the same update/digest/copy API for these secure hashes; [official hashlib documentation](https://docs.python.org/3.11/library/hashlib.html) specifies these operations. The SHA512 fingerprint is private and not a new protocol algorithm.

Alternatives were evaluated before editing. Buffer-only readinto changes gave small improvements; BLAKE2b did not beat SHA256 in this environment. Caching all history would conflict with the plan's RAM invariant, so it was not adopted. A CNG/native wrapper was not needed for this portable change. See `performance/` for complete inputs, results and limitations; the synthetic payloads were temporary, not persistent receipts.

Validation completed:382/382 existing replay unit tests in113.004s, actual child/helper exits0, tree/source unchanged. The standalone HTTP diagnostic against an exact COPY of the failed33MiB journal completed30/30 inspections; terminalp95=282.0598ms, maxgap166.111ms, actualexit0/treeclean. It added exactly60records and retained the original bytes/prefix. These are diagnostics, not a full benchmark.

Five affected service lanes were reminted: complete/Stop and saturated-stop/revoked-result/stale-capture,158checks. All outer targets exited0; three natural runtime targets exited0 and two intentional Stop cases have checked closed/zero Jobs without a natural nativeexit claim. `service-remint/verification.json` binds1,281 rawfiles/43,962,707bytes and selected copied capture/log/source/result artifacts. `focused-validation.json` joins these results. The old task was deleted only after terminal scheduler/cleanup evidence; `s71-task-deleted.json` is a later supplemental receipt, not part of the earlier frozen failure inventory.

`source-git-index.json` verifies49 exact runtime Gitbytes at closure `6f5d4c8a14ef8476c4cff6afb06ab161b17905f8593f9a685cd235593d7ee913`; unchanged profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`. A fresh `gt06-s73-campaign-01` is ready to launch after checkpoint. Preserve S65/S69 game trace/repair artifacts under their original dependencies; do not relabel them as S73. Final10x35 measurement and two independent same-closure critics remain outstanding. The S71 sealing draft is historical preparation: rebind its campaign/source constants explicitly for S73 before final use; do not edit an old signed manifest or use S71raw as S73 samples.

Launch follow-up: source was checkpointed at `cb4d1f6f`, and
`source-git-head.json` confirmed the same49 exact bytes before dispatch.
Campaign launch1 started `2026-09-17T21:11:26Z`; a separate scheduler query
and host/native progress observation confirmed startup. See
`../20260918-gt06-s73-next/launch/README.md` for the time-scoped observation
and updated continuation schedule. This does not establish benchmark PASS.

# GT-01 whole-WP critic B — fill only in an isolated read-only session

`ROLE=independent_read_only_critic_b`
`WP=GT-01`
`TICK=<yes|no>`
`SOURCE_CLOSURE_SHA256=<copy exact 64-hex input or TICK=no>`
`CLOSURE_MANIFEST_SHA256=<copy exact input hash>`
`OFFICIAL_EVIDENCE_SHA256=<copy exact input hash>`
`RUN_ID=<copy exact input>`
`COMMAND_ID=<copy exact input>`

Critic B must use a separate read-only session and independently recompute the
closure/evidence identities. Do not read critic A or rely on its conclusions.

## Independent replay-by-inspection checks (all must be YES)

- [ ] All three hashes and both identifiers match the dispatch manifest; any
      mismatch, placeholder, stale directory or candidate status is `TICK=no`.
- [ ] Closure inventory is complete and deterministic; excluded caches,
      `.godot`, runtime output, secrets and absolute paths are absent.
- [ ] Lock/archive verifier checks official URL, SHA, version, commit, sums,
      size, duplicate rows, unsafe paths, symlinks and hardlinks.
- [ ] Installer recovery handles live-owner lock/CAS, PID reuse, TTL expiry,
      crash recovery, replacement race and durability without deleting the
      last-good package.
- [ ] Fixture and runner enforce lexical root containment, reparse/UNC/ADS/
      hardlink rejection, source/binary hash binding, duplicate-key rejection,
      strict trace phases and postcondition readback.
- [ ] Official evidence has real host exit, correct version, exactly one trace
      PASS, expected pause tick/body invariants, no unexplained warning/error,
      and a clean owned process tree.
- [ ] Unicode/space path, clean-environment, headed/headless serial execution,
      cache isolation and rollback-copy observations are present and bound to
      the frozen source closure.
- [ ] TX12/TX14 assertions are limited to GT-01 candidate/cache and
      quota/network/auth/Stop slices; future GT-02/GT-07/GT-08/GT-10 claims are
      rejected as scope errors.

## Findings and verdict

Use exact repo-relative paths, observed values, and a reproducible check. Do
not run tools or make edits in the critic session.

```json
{"schema":"HH3D-GT01-WP-CRITIC-1","critic":"B","tick":"yes|no","source_closure_sha256":"<64-hex>","closure_manifest_sha256":"<64-hex>","official_evidence_sha256":"<64-hex>","findings":[],"remaining_gates":[],"executed_tests":false,"GT01_ACCEPTED":false}
```

The coordinator must treat missing/invalid JSON, non-boolean `tick`, any
blocking finding, or any identity mismatch as `TICK=no`.


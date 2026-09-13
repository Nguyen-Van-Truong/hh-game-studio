# GT-01 whole-WP critic A — fill only in an isolated read-only session

`ROLE=independent_read_only_critic_a`
`WP=GT-01`
`TICK=<yes|no>`
`SOURCE_CLOSURE_SHA256=<copy exact 64-hex input or TICK=no>`
`CLOSURE_MANIFEST_SHA256=<copy exact input hash>`
`OFFICIAL_EVIDENCE_SHA256=<copy exact input hash>`
`RUN_ID=<copy exact input>`
`COMMAND_ID=<copy exact input>`

## Integrity and independence (all must be YES)

- [ ] The closure hash, manifest hash, evidence hash, run id and command id
      match the coordinator input exactly.
- [ ] Manifest status is frozen/official as required by the plan; no
      `CANDIDATE`, `PARTIAL`, `DIAGNOSTIC`, stale or generated-only artifact is
      used as proof.
- [ ] Every required closure path exists, is regular/non-symlink/non-reparse,
      has the recorded hash/size, and contains no absolute host path, username,
      token or secret.
- [ ] I used a read-only snapshot and did not launch, mutate, install, or
      inspect critic B's response.

## Evidence gates (all must be YES)

- [ ] Official Godot binary version and checksum match the locked 4.7.2 pin;
      archive/sums provenance and license fields are complete.
- [ ] Reproduction works on a path containing spaces/Unicode without relying
      on global PATH; mismatch fails before project open and preserves the
      previous package.
- [ ] Fixture is independent of H2/game code, has typed scene/menu/start/quit
      input contract, valid `.uid` source, and clean Blender fixture metadata.
- [ ] Headless parse/check-only succeeds before the real run; headed and
      headless official runs are serial and use the same frozen closure.
- [ ] Host-captured wait exit is independently observed; exactly one valid
      `GT01_TRACE` PASS row is in the expected phase; stderr is empty or every
      warning/error is explained.
- [ ] Trace proves menu→start→movement→pause (simulation frozen)→resume→quit,
      including authored pause-tick semantics and post-transition state.
- [ ] No owned child process remains after exit. Windows uses verified Job
      Object/descendant identity; Linux uses verified process-group cleanup.
- [ ] Runner admission rejects traversal/UNC/ADS/reparse/hardlink/lock
      provenance violations and refuses ambiguous/stale evidence.
- [ ] GT-01 TX12 slice proves isolated candidate/cache behavior without
      claiming GT-08 ABI or GT-10 full migration/uninstall.
- [ ] GT-01 TX14 slice records quota/network/auth/token/Stop behavior with
      redacted logs and no bypass; it does not claim protocol recovery owned by
      GT-02/GT-07.

## Findings

Record at most four concrete findings, each tied to an exact artifact/path and
reproduction. Do not invent a test or infer acceptance from absence of output.

```json
{"priority":"P1|P2|P3","path":"repo-relative/path","claim":"...","reason":"...","verify":"..."}
```

`REMAINING_GATES=<comma-separated concrete gates>`
`EXECUTED_TESTS=false`
`GT01_ACCEPTED=false`

Return one machine-readable object after the checklist. A `TICK=yes` is valid
only when every blocking checkbox is YES and no finding remains.


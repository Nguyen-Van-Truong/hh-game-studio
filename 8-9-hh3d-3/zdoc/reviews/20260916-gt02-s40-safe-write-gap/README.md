# GT-02 S40 — Windows safe-write gap decision

- `RUN_ID=GT02-S40-20260916-SAFE-WRITE-GAP`
- `SOURCE_CLOSURE=2fb0ec013c4037c844b38f7be221c0aa7a6bd905492fa7c4a53eaa8e474c9d59`
- `DECISION=FAIL_CLOSED_GAP`
- `FORMAL_ACCEPTANCE=0`

S40 records the existing, source-bound safety evidence and closes the
implementation question conservatively. The public `SafeFileAccess` contract
continues to advertise `safe_write=false` and `atomic_replace=false`; every
mutation entry point raises `UNSUPPORTED_SAFE_OPEN_WINDOWS` before native I/O.
No write or publish prototype is claimed.

The Windows read/identity probe uses `CreateFileW` with
`FILE_FLAG_OPEN_REPARSE_POINT`, held ancestor handles, final-path identity,
`FileIdInfo`, `FileStandardInfo`, reparse checks, and link-count checks. Those
checks are useful read evidence, but they do not prove that a same-account
actor cannot create a second hardlink after an exclusive handle is opened. The
existing adversarial test creates that alias and confirms that the mutation
operation remains disabled. The race/swap tests also reject ancestor and final
file substitutions before any write.

Evidence cases already present in the frozen source:

- `test_exclusive_handle_hardlink_counterexample_keeps_mutation_disabled`
- `test_final_file_swap_to_hardlink_between_resolve_and_open_rejects`
- `test_every_mutation_rejects_before_io_even_during_junction_swaps`
- `test_ancestor_swap_between_resolve_and_open_is_rejected`
- `test_parent_handle_blocks_rename_before_final_file_is_open`

The private staging store and S39 AppContainer proof are separate layers. They
prove protected staging and confined endpoint access for their tested fixture;
they do not upgrade the public project-root safe-write capability or remove the
same-account hardlink threat. Therefore GT-02 remains a candidate and GT-03/GT-04
remain gated. No long-suite rerun was needed: S40 changes only the decision
record, and all referenced source bytes remain unchanged from S39-02.

## Reproduction boundary

Run the focused protocol test on the frozen snapshot:

```text
python -B -m unittest studio.tests.protocol.test_safe_open
```

On Windows, the environment-dependent native cases may skip when the required
filesystem primitive is unavailable. A skip is not a safe-write pass.

## Hashes

See `manifest.json`; hashes bind this decision to the S39-02 candidate source
and evidence.

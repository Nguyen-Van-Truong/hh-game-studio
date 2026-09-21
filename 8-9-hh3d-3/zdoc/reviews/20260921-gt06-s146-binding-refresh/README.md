# S146 installed metadata refresh

Authority 0; no engine run or GT06 acceptance. The completed refresh is retained
as executed. Do not execute `refresh_installed_binding.py` again: its old/new
evidence writes are not exclusive and it is not a general upgrade facility.
Use `verify_existing.py` to validate the retained result without reinstalling.

Only `host/replay/verified_journal.py` differs among 215 dependency files. Both
metadata files were replaced individually with flushed temporary siblings and
`os.replace`, while no engine was active. This is not an atomic two-file
transaction: an intervening reader rejects a hash mismatch. The exception path
restores the prior bytes; it was not exercised by the successful refresh.
Backups permit recovery, but no crash-durability or hot-upgrade claim is made.

The original receipt's `source_closure_sha256` is the SHA256 of indented JSON
plus newline, not the canonical `native.closure` format. Keep that receipt
unchanged. `postcheck-01.json` names both canonical 215/217-file domains and
validates actual GT05 inputs through the unchanged admission reader. Synthetic
binding suites previously completed 17+16 tests in fresh interpreters; they do
not replace current native functional or formal benchmark evidence.

S145 proved seven diagnostic batches under the changed 64KiB journal reader.
The comparison with S143/S144 is not causal proof. S141 admission timeout and
S131 RSS failure remain historical unresolved observations. The next formal
campaign must use a fresh identifier, unchanged original gates and all 10x35
batches; every failed/diagnostic prefix remains outside F13/F14.

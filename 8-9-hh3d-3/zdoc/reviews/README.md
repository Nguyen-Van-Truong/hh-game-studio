# HH3D review evidence

This directory contains review evidence, not a third plan or a worker service.
Progress belongs only to the two active TXT plans in the parent directory.

Current report: [20260910-r5](20260910-r5/REVIEW-RESULT.md).

Keep in Git: concise decisions/findings, reproducible validators/tests,
source freeze manifests, source snapshots required to reproduce a finding,
and the final evidence supporting an accepted gate. Older revisions remain
historical and do not certify a new source hash.

Keep outside Git: live worker workspaces, streaming transcripts, CLI caches,
tokens, temporary downloads and per-machine attempt pointers. New worker
attempts live under Windows TEMP; locally generated scratch inside this tree
belongs under a `.local/` directory. Commit a small digest/result summary after
coordinator verification if it explains an acceptance or rejection.

Do not ignore or delete this entire directory. Before retiring evidence,
check active plan/report references, preserve the final acceptance and repro
closure, and verify its recovery location and hashes. Historical evidence
being tracked in Git is not, by itself, a reason to erase its current files.
No automatic recursive cleanup is configured.

Worker `exit 0`, Windows toast, and an AI sentence saying “done” are terminal
signals only. Review actual files, native tool results, source hashes and
tests. Reject unsupported claims even when a worker is fast.

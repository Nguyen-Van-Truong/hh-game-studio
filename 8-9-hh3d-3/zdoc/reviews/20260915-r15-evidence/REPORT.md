# GT-01 evidence binder (r15)

`evidence_binder.py` is a read-only, fail-closed boundary between a frozen
source manifest and one runner output. It recomputes the closure hash from
`required_files`, hashes those files on disk, and does not trust a
runner-supplied `source_closure_sha256`. It requires `OFFICIAL`/`ACCEPTED`
status, complete source bindings, clean checks, host and wrapper exit `0`,
`timed_out=false`, gated process-tree ownership, independently hashed UTF-8
logs without warning/error lines, and exactly one ordered passing GT01 trace.
Candidate/diagnostic reports therefore remain useful for debugging but can
never be upgraded by copying a field.

The current R13 runner output is `CANDIDATE` and has no
`source_closure_sha256`; the binder deliberately returns `GAP` for it. A real
remint must first freeze the complete closure, write a manifest with every
required regular file and digest, then run one official Godot process lane at
a time against that frozen snapshot. The runner must publish source bindings,
host-captured exits/tree records, and log files in the same package. After the
run, invoke:

```text
python evidence_binder.py --source-manifest <frozen-manifest.json> --runner-output <official-evidence.json> --repo-root <frozen-repo> --output <binder-result.json>
```

Only `READY_FOR_CRITIC` permits the two independent read-only critics to
review the package. It is not coordinator acceptance and must not tick GT-01
by itself. If source bytes change, or any log/run/trace is reminted, create a
new run/command identifier and recompute the closure; never patch an old
report in place.

Synthetic mutation coverage is in `test_evidence_binder.py` (valid binding,
candidate status, source/log mutation, nonzero exit, unverified tree,
duplicate trace, warning output, and ignored caller hash).

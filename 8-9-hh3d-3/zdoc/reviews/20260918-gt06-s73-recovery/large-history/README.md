# Prepared HTTP diagnostic — not executed

`large_history_http.py` is a standalone child for the coordinator's bounded `run_fixture.run_process` wrapper. Preparation did not execute the script, compile it, run tests, start HTTP listeners, copy history, or launch engines. Review it before invocation.

It copies the exact 33,224,600-byte S71 journal into a new private temporary project under a **new exclusive output directory**, then loads the current `VerifiedJournal` against that copy. It never opens the original journal for writing or constructs a journal object against it. The original hash and copied history prefix are verified again at completion. The private project and evidence remain available after the run; nothing is deleted.

The host uses a fresh project ID, fresh command IDs, and only `fixture.read`; it never acquires the old write lease. The 47,188 original records remain intact. The new fixture is explicitly `{value:0, revision:rev-0, effect_count:0}`; this diagnostic does not claim recovery of the old project's runtime state. Every inspection uses the unchanged `LoopbackFixtureHost` and `FixtureClient` over actual loopback HTTP, with the normal **2.0-second timeout**. Successful submission must be `ACCEPTED_PENDING/QUEUED`, followed by a matching `COMMITTED/READBACK_CONFIRMED` lookup and hashed snapshot. The last command is looked up again through HTTP and must return the identical terminal result.

A submission `UNKNOWN/CONNECTION_LOST_LOOKUP` remains a failed admission even if a bounded same-ID lookup resolves it. No submission is retried. The report retains original receipts, actual lookup attempts, timing, source hashes before/after, history hashes, cleanup outcome, and p95/max response-gap diagnostics. Reconciliation has a five-second budget from its first lookup, and each call needs room for the unchanged two-second timeout. The whole child has a default 90-second cooperative deadline; the outer runner supplies the hard deadline and actual process/Job cleanup evidence.

The source map is checked against its known S71 SHA-256 and selects the 49 S71 dependency **names**, but their hashes are freshly computed from the current source. Imported studio Python modules are also included, and hashes are checked after import and after shutdown. A concurrent source or driver change fails the diagnostic. A successful 30-command run must append exactly 60 records; the repeated terminal lookup must not append anything. Source hashes are an independent diagnostic manifest, not the campaign closure hash.

From the `8-9-hh3d-3` directory, construct this child argv (absolute paths recommended):

```python
child_argv = [
    sys.executable, '-B',
    str(product_root / 'zdoc/reviews/20260918-gt06-s73-recovery/large-history/large_history_http.py'),
    '--source-root', str(product_root),
    '--journal', str(product_root / 'studio/.local/reviews/gt06-s71-campaign-01/run-00-attempt-01/commands/commands.jsonl'),
    '--source-map', str(product_root / 'studio/.local/reviews/gt06-s71-campaign-01/run-00-attempt-01/source-files.json'),
    '--output', str(product_root / 'studio/.local/reviews/gt06-s73-history-http-01-child'),
    '--run-id', 'gt06-s73-history-http-01',
    '--commands', '30', '--deadline-seconds', '90',
]
```

Coordinator wrapper: load `studio/build/bootstrap/run_fixture.py` with `importlib.util` and call its generic function, **not its Godot CLI**:

```python
result = run_fixture.run_process(
    child_argv,
    cwd=product_root,
    output=product_root / 'studio/.local/reviews/gt06-s73-history-http-01-owner',
    timeout=120,
    label='http-history',
)
```

Use fresh child/owner directories and a fresh run ID on every execution. The child creates its own output exclusively; its parent directory must already exist. The coordinator creates/prepares the owner output as required by `run_process`, persists the returned capture, and checks actual exit, timeout, stderr, and owned-tree cleanup. Child `DIAGNOSTIC_OK` or intended return 0 alone is insufficient.

Run this only after performance work and source edits stop. It is a 30-inspection diagnostic over existing history, with no native cycles, writes, rejections, or full workload mix. It cannot establish a complete campaign result or GT06 acceptance, and it must not replace, resume, or repair S71 evidence.

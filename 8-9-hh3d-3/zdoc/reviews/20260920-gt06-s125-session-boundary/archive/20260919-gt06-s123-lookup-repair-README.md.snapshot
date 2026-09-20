# S123 bounded lookup repair diagnostic

`AUTHORITY=0`, diagnostic-only. This packet uses the committed S123 source
checkpoint `b624f1b4`, the post-import 53-file closure
`739447bd1d812b7e4e76754d7c6659a2ba9c1bc53e9045f1cfc2f2b6379dbf08`, the
unchanged profile
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`, and the
stock native hash
`13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`.

The candidate repair separates the local disconnect-test mutex from host
state, allows the read-only lookup route to validate before taking the host
lock, and uses an expiring pending snapshot only after durable admission. It
does not alter the native benchmark, profile, original gates, timeouts,
baseline, priority or RSS policy. The pending snapshot is published only after durable admission, so duplicate lookup preserves the durable request digest.

The copied helper runs the stock campaign child and measures the existing
host/journal/SQLite timing seams. It stops at the first original gate failure
or after seven original gate rows (batches 0–6). The run is not F13/F14 and
cannot be a GT06 PASS or no-leak/root-cause proof.

Static check (no engine):

```powershell
python -B lookup_repair_boundary.py --check
```

The launcher must be invoked once only with a fresh ID. Preserve raw child,
actual target/helper exits, Job/handle cleanup, source pins and all failed
attempts. Do not merge any prefix rows into the formal dataset.




## S123 terminal result

The fresh bounded run `gt06-s123-lookup-repair-01` used source closure `739447bd1d812b7e4e76754d7c6659a2ba9c1bc53e9045f1cfc2f2b6379dbf08` and the unchanged profile/native hashes. It completed diagnostic batches 0–4, including baseline batch 4, then stopped at original gate `CAMPAIGN_RETAINED_COUNTER_GROWTH` during batch 5. Editor handles were 555 at batch 4 and 560 at batch 5; ObjectDB remained 71130 and resources 6. The batch status gap was 727.273 ms and no HTTP transport failure was recorded. Jobs/handles/probes and producer cleanup were recorded clean; editor target natural exit remained UNKNOWN.

This is a bounded diagnostic boundary, not a PASS, no-leak or root-cause proof, and no rows enter F13/F14. The result shows the S122 lookup compatibility failure is repaired, while the retained editor-counter boundary remains unresolved. Do not launch a formal retry or claim the candidate is accepted without a narrower evidence-backed repair.


## Read-only comparison

The candidate changes only `host/core/transport.py`; the editor/native fixture files and native hash remain byte-identical. Prior diagnostic prefixes on the prior 53-file base closure also show variable editor handle counts (for example S108-03 held 556 through batches 4–6 while S119 held 556 through batches 5–7). Therefore S123's 555→560 transition is a retained-counter boundary in the stock editor workload, not proof that the lookup repair caused a leak. This comparison does not establish no-leak or root cause; it only prevents a blind source rollback or formal retry.

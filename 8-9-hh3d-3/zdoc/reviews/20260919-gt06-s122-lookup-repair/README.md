# S122 bounded lookup repair diagnostic

`AUTHORITY=0`, diagnostic-only. This packet uses the committed S122 source
checkpoint `b624f1b4`, the post-import 53-file closure
`e2e5e834619795ca471efac6a62fa87a5da8291bf481b35bff0b1be0e2e08021`, the
unchanged profile
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`, and the
stock native hash
`13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`.

The candidate repair separates the local disconnect-test mutex from host
state, allows the read-only lookup route to validate before taking the host
lock, and uses an expiring pending snapshot only after durable admission. It
does not alter the native benchmark, profile, original gates, timeouts,
baseline, priority or RSS policy. Duplicate admission remains durable-first.

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

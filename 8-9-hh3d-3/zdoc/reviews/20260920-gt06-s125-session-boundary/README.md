# S125 session-boundary repair

`AUTHORITY=0`; no engine launch and no GT06 acceptance sample. The S125
focused regression first reproduced a real authorization race in the S122
transport candidate: a lease or Stop request waiting behind the host lock did
not re-check a session that had expired or been rotated while it waited. The
request could therefore mutate lease/stop state under an invalid session.

The repair adds a second `sessions.check_current()` immediately inside the
locked dispatch section. The fast read-only lookup path remains outside the
host lock and keeps its existing durable-journal authority and pending snapshot
rules. This does not change benchmark gates, timeouts, baseline, profile,
native fixture or RSS policy.

Evidence captured with actual subprocess exits:

* `before-01/receipt.json`: the four race cases fail on the unpatched source.
* `after-01/receipt.json`: four methods, including the same four race cases,
  pass; exit `0`.
* `protocol-01/receipt.json`: 53 transport/recovery tests pass; exit `0`.
* `python -B -W default -m unittest discover -s
  8-9-hh3d-3/studio/tests/replay -p 'test_benchmark*.py' -v`: 166 pass in
  79.037s; tool session 49044 actual exit `0`. Output was returned through
  the command tool, not captured as a complete portable logfile. Do not
  treat this summary as a sealed regression lane for final acceptance.

An exploratory test exposed unclosed listeners in the new test fixture when
`start=False`; the fixture now closes every host, including unstarted hosts.
The retained before/after runs have no such warning. The new test and
helper are supplemental evidence only. GT06 remains `IN_PROGRESS` with zero
accepted full runs; no diagnostic rows enter F13/F14. A formal campaign still
needs the unchanged 10 fresh pairs × 35 batches gate and full cleanup/source
closure.

The captured stdout/stderr bytes remain immutable, including empty stdout
and the failed unittest progress line's trailing space. `.gitattributes`
preserves these bytes so stored SHA256 values also match Git blobs.

# S124 retained-editor counter decay diagnostic

`AUTHORITY=0`; diagnostic only. This fresh run is narrowly justified by S123's
original `CAMPAIGN_RETAINED_COUNTER_GROWTH` at batch 5 (`555 -> 560`) after the
S122 lookup compatibility fix. It keeps the 53-file source closure, native
fixture, profile, stock workload and every original gate unchanged.

The child writes the original gate failure receipt first. Only after that durable
receipt, and only for the retained editor-counter failure, it samples the same
process at offsets 0, 1, 3 and 5 seconds. PSS inventories are taken at offsets 0
and 5 with the existing bounded adapter; identity and cleanup are checked. A
PSS/observer error never replaces the original gate error. The child stops at
the original failure or the planned seven-batch boundary. This is not F13/F14,
does not create a dataset, and cannot be a GT06 PASS, no-leak proof or root
cause claim. Do not change thresholds, baselines, timeouts, priority or RSS
policy based on this packet.

Static checks:

```powershell
python -B handle_decay.py --check
python -B test_post_failure.py
```

If launched, preserve all raw attempts, process identities, actual exits,
cleanup and Stop records. The candidate's source remains the S122 transport
repair; the observation files are outside the runtime closure.

## Terminal result

`gt06-s124-handle-decay-01` completed the planned seven-batch bounded prefix
with all original gate rows recorded as `PASSED`, then stopped at the diagnostic
boundary. The editor counter series was `565,557,560,559,555,555,555`; the
S123 transition `555 -> 560` did not occur at its former batch-5 position.
ObjectDB/resources stayed `71128/6`, HTTP transport failures were zero, and
the timing summary recorded source pins unchanged. Host target/helper exited
`0/0`; the editor target's natural exit remains an explicit evidence gap under
the bounded teardown contract. No post-failure files were expected because no
original gate failed. The prefix is retained as non-acceptance evidence and
does not establish no leak, object identity, root cause, or a formal GT06 PASS.

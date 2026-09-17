# S73 preparation handoff — not a critic review

The S71/S72 draft was copied into a new S73-only folder. Campaign ID, source
closure, expected commit, source checkpoint map, supervisor paths, recipe schema
and adapter report schema now target `gt06-s73-campaign-01` / `cb4d1f6f`. The
exact profile, 49-file benchmark domain, workload and verification chain remain
unchanged. The adapter was not run, compiled or syntax-checked during this work.

The historical S72 review identified JSON type-sensitive comparison, the exact
top-level profile artifact, and structured handling of RuntimeError-based
ownership failures. Its corrections remain in the copied adapter. That review
and its three isolated checks applied to the previous draft hash only. Neither
the historical review nor this handoff is an independent GT06 acceptance critic.

The new recipe adds the S73 recovery `focused-validation.json`, 382-test
invocation, 30-inspection history diagnostic and five service-remint lanes as an
explicit affected-dependency bridge. It distinguishes benchmark49, remint
review148 and runtime173 dependency maps. It retains natural-exit versus
intentional-Stop semantics and original raw ownership evidence.

S65 fault/repair02/S65 replay and S69 managed replay retain their original source,
trace, configuration and receipt/capture hashes. Older GUI/service source maps
are not silently rewritten as S73: final comparisons must document the changed
journal dependency and the scoped remint bridge.

Preparation used named metadata/source reads and a bounded Git changed-path
comparison. No live campaign validator, tests, engines, broad source/raw hash
audit, production edits, plan edits, staging or commits were performed. The
coordinator owns live startup/status/scheduling and the final seal after the
campaign reaches terminal state.

Remaining work: terminal campaign and supervisor evidence; named `cb4d1f6f` Git
byte verification; actual adapter exit capture; complete per-lane dependency/raw
validation; F01–F15 matrix and final manifest; two new independent critics on
that same final manifest/source hash. This handoff supplies no acceptance verdict.

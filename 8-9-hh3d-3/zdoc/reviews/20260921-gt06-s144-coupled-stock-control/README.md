# S144 coupled stock control (diagnostic only)

Same 7-batch coupled workload as S143, but the child restores the pre-S142
`VerifiedJournal._snapshot` method dynamically from the sealed S141 commit.
No runtime source file is changed; source/profile/native pins remain candidate
closure for provenance. This distinguishes host/editor/native interaction from
the journal candidate. Not F13/F14, not PASS, no root-cause/no-leak claim.

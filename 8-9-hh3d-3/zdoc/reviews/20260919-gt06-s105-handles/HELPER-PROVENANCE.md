# Historical S105 helpers — incomplete diagnostic integration

AUTHORITY=0. These files are retained history, not the next runnable candidate.
Use the S106 helper only after its static integration tests and coordinator review.

The original `manifest.json` is an invalid, stale draft: it has a literal `\\n`
after its closing brace and does not bind the subsequently added runner. Preserve
its bytes; `manifest-v2.json` records the current retained helper file bytes only.
The v2 manifest is not evidence that the mutable parent/helper files had these
bytes at historical launches. Each generated child must separately match its raw
context; the S105 result packet performs that check.

`pss-adapter-selfcheck.json` includes a self-declared exit integer. It is a short
same-process observation, not a captured owned-engine preflight. The historical
`pss-selfcheck-output.json` consists of two JSONL output records from the older
S76 adapter selftest, despite its suffix; it is not an S105 integration result.

The eight fake adapter tests and ten reader tests do not cover the S105 generated
child/context integration. Missing imports, an invalid sample key, and an undefined
writer subsequently caused expensive collector failures. All failed attempts are
kept. `GATE_RECORDED` and `engine_started=true` from the old runner must not be used
as success evidence. The independently derived S105 result packet supersedes their
interpretation without replacing original raw records.

Latest `gt06-s105-handles-03` reached the artificial six-batch boundary with one
baseline PSS capture. It did not capture batch 5, did not reproduce the original
handle excursion, and does not justify a runtime repair, formal PASS or no-leak
claim. PSS after ACK can perturb the next READY/status-gap interval.

The top-level README describes the initial preparation stage only. This notice
and the S105 result packet describe the terminal outcomes. No runtime or profile
bytes were changed for these helper corrections.

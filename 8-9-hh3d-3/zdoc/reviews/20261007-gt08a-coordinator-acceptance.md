# GT-08A coordinator acceptance

STATUS=ACCEPTED
MANIFEST_SHA256=49834d31db4996b18c15d9cada4ef030efb30d95f1e68e934251f9a5baafe675
CRITICS=TICK_YES_x2

GT-08A is accepted under O4.6/O10.9 for the clean Windows/Linux slice. The
final matrix `gt08a-matrix-20261007-05` has 18/18 PASS rows, including actual
Windows import/export and Linux headless/import/export, with actual exits and
owned process cleanup. The source closure is
`4c80f7217e955e1c65cd48561f535246a162e4af0208a969b773a9c37c90fa7a`.

This acceptance does not close GT-08B: a physical Android device remains the
hard gate before GT-10. The raw manifest remains authority 0 and is not
rewritten; the two independent critics above are the acceptance record.

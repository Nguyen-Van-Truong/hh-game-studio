# S26-01 incomplete diagnostic package

This attempt is not acceptance evidence. Both owned test children completed,
but the packaging process exited with an error before producing candidate.json.
The golden-output scrubber used str.splitlines(), which splits Unicode line
separators inside valid JSON strings and misclassified a large result fragment
as a diagnostic line. The redactor correctly rejected the oversized fragment.

The fix uses LF delimiters and regression tests; a fresh run was recorded in
the sibling S26-02 package. Preserve this failed attempt instead of editing its
outputs into an apparent successful run.

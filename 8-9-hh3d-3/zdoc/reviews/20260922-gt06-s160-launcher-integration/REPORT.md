# S160 launcher integration (diagnostic, AUTHORITY=0)

This scope adds a real owner/child integration around the existing S157 launcher
publication and campaign services. `prepare` makes a fresh helper directory;
the freeze contains an exact child script pin, helper inventory and closure,
predecessor/source/binary/workstation pins, and an exact execution file map.
`launch_existing` authenticates before dispatch, reads the child/helper and
target exits independently, preserves Stop before and during cleanup, and
reauthenticates the whole closure after close. Boundary exit 0 is distinct from
failure exit 1 and Stop exit 2. The child path runs the existing campaign driver
under the copied S156 observer adapter and reauthenticates before publishing its
summary.

The terminal validator binds a contiguous prefix of exact length to raw
sample/joint/gate/context bytes, process IDs, and editor target identity. It
never infers a target exit from the helper exit. No formal acceptance or dataset
eligibility is produced.

The first real `--prepare` check (`gt06-s160-diag-prep01`) is preserved as a
failed preflight. The predecessor freeze inventory is HH3D-root relative
(`studio/...`), while the stock campaign reports source files relative to its
`studio` root (`blender-addon/...`). The old authentication path tried the
latter against the former and failed closed before any engine launch. The
launcher now validates both coordinate systems explicitly, canonicalizes only
the root-relative execution comparison, and rejects mixed maps. A fresh
prepare-only retest is required after this repair; that failed ID is never
reused. The failure metadata and the eight-file raw inventory are recorded in
`s160-prepare-preflight.json`; the raw run remains under
`studio/.local/reviews/gt06-s160-diag-prep01`.

After that repair, a fresh prepare-only ID (`gt06-s160-diag-prep02`) completed
with exit 0 and a subsequent `--authenticate` completed with exit 0. Its
freeze is `6ddcc5cc9c156ead8fd1f635baa6f625ae1223bfc4cf52fea78520071e5bc8c1`;
the eight-file inventory and bindings are recorded in
`s160-prepare-retest.json`. This proves launcher preparation and exact
readback only. It did not spawn the campaign, Godot, Blender, or a native
worker, and it cannot authorize a formal retry.

## Verification

```
python -B -m unittest discover -s . -p 'test_*.py' -v
```

Result: 10 tests, exit 0 (`s160-tests.txt`, `s160-tests-exit.txt`). Tests use
temporary files, fake retained owners, and raw JSON receipts only. They do not
start Godot, Blender, a benchmark worker, or any native process.

Source hashes for the reviewed scope are recorded in `manifest.json`.
The run remains diagnostic and has no independent creator attribution: the
S156 PSS adapter is a pinned, replaceable integration component and is not
executed by these tests.

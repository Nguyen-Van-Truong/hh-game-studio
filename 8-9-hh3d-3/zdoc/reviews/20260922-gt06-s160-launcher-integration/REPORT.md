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

## Verification

```
python -B -m unittest discover -s . -p 'test_*.py' -v
```

Result: 8 tests, exit 0 (`s160-tests.txt`, `s160-tests-exit.txt`). Tests use
temporary files, fake retained owners, and raw JSON receipts only. They do not
start Godot, Blender, a benchmark worker, or any native process.

Source hashes for the reviewed scope are recorded in `s160-tests-exit.txt`.
The run remains diagnostic and has no independent creator attribution: the
S156 PSS adapter is a pinned, replaceable integration component and is not
executed by these tests.

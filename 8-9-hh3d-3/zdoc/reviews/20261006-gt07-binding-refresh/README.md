# GT07 M9 installed binding refresh (2026-10-06)

This is a coordinator-owned, one-use refresh for the current GT07 source
generation. It was run with no Godot or Blender process live and no competing
writer. The script requires the exact previous selector/binding hashes, the
pinned GT05 anchor, source count `233`, and exactly these changed source files:

- `godot-addon/editor_owner.py`
- `host/blender/export_job.py`
- `host/blender/publication_owner.py`

It writes old/new metadata bytes, performs each metadata replacement through a
temporary file with `fsync` and `os.replace`, rolls both files back if the
installed reader or postcondition fails, and records a read-only postcheck.
No engine is launched and no acceptance authority is created.

The two metadata files are deliberately validated as one generation by their
hash link. They are replaced one at a time; a crash between replacements can
only leave a generation that the strict reader rejects, and this package makes
no stronger power-loss atomicity claim. A later refresh requires a new reviewed
old-hash/delta package; do not rerun this script or alter the retained raw.

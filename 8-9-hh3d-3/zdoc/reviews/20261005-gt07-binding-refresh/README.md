# GT07 installed binding refresh

Authority is zero. This one-use refresh repairs the installed GT06 execution
selector after GT07 source changes; it is not a GT07 acceptance result and it
does not launch Godot, Blender, Docker, or a worker.

The old generation had 215 source entries. The fresh union of the pinned GT05
manifest and the current installed dependency inventory has 233 entries. The
refresh admits exactly the 31-entry delta pinned in
`refresh_installed_binding.py`, writes each metadata file through a flushed
temporary sibling and `os.replace`, then verifies `installed.load_installed`
in the same fresh interpreter. On any error both metadata files are restored
byte-for-byte. `refresh-started.json` is retained as the one-use latch.

Result: source count 233, verified execution files 235, new binding
`8e7bf80e9c625f0b2106cea1e37cde688d1245896ee0b86b2c11ff2a0a6b4bff`, selector
`3948c161f96771b60e8b00ef41724ed8d65e50286595a7356aacbf05cc244685`, and
source-map hash `5a701d981862fe02520f9755bd0b2443bb3119327e65bb164d0e1880d379878e`.

The first attempt exposed an argument-shape bug and rolled back cleanly. The
script was repaired before the successful one-use execution; no engine ran in
either attempt. Keep the old and new metadata snapshots and receipt together.
Do not remove the latch or execute the script again. The next step is one fresh
M9 play-mutation native run after the usual dry-run; that run remains diagnostic
until the final frozen M1–M9 matrix and two same-hash critics.

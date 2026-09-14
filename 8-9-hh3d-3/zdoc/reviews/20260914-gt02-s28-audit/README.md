# S28 solo coordinator verification

Current frozen candidate: `../20260914-gt02-s28-03/`.

Source closure: `8c6ed94846c4737c1ff6dace8c29a2c26b66f62520cecc17fea32831297906bb`.
Coordinator verification independently rehashed 61 current source files and
nine candidate artifacts, checked real host records and completion markers,
and compared all 2,396 Godot/Node rows with Python expectations. The 144 protocol
tests comprise 140 passes and four explicit platform skips; bootstrap is 56/56.
`verification.json` binds P-01 through P-22 to exact executed test IDs and
states the limits of each proof class. It is not an independent critic verdict.

Reproduce the read-only check from the repository root:

```powershell
python 8-9-hh3d-3/zdoc/reviews/20260914-gt02-s28-audit/verify_evidence.py
```

Two additional coordinator findings were reproduced as failing tests before
the fix. A competing journal could change the fencing epoch between validation
and a fixture effect. `lease_guard` now retains the native journal lock through
that bounded effect. An attributes-only directory handle allowed rename before
the final file was opened; the parent handle now also requests directory data
access. The OS can consequently reject a swap earlier than the old tests
expected. Updated tests require either the observed OS sharing rejection and
original inside bytes, or the precise validator rejection; outside sentinels
must remain unchanged. S28-01 failed on the old test assumptions and remains a
diagnostic package; S28-02 was a fresh full remint after the corrections.

Windows share-mode semantics were checked against
[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
and actual disposable-root tests. This does not enable file mutation: all write
and replacement APIs still fail closed. The broader hardlink/private-namespace
and replacement identity problem is documented in
`../20260914-gt02-s27-windows-write-research.md`.

The owner changed execution to solo. All workers finished before S28; none were
restarted. The two S26 critics rejected an older closure and then implemented
fixes, so their reports cannot accept S28. Formal acceptance remains pending;
no GT-03/04 or later gate has been promoted. This WIP checkpoint preserves all
implementation and evidence without claiming the full tool plan complete.

The tools plan was shortened by moving the complete prior S27 text into
`../20260914-plan-history-s27/`. GT/TQ/TX requirements were preserved. Two
stale sentences in sections 6–7 now point to the current progress table and
solo execution instead of all-PLANNED status and a worker count. Section 9
no longer describes Grok CLI as current routing. The unrelated repository-wide legacy marker
scan exceeded its diagnostic time budget and was stopped by its owned process
handle; it is not reported PASS. The scoped bootstrap lane above did pass.

Before checkpoint, the coordinator found that Git LF normalization could change
raw Windows evidence bytes and seven inherited source files had CRLF bytes
different from HEAD despite a clean normalized Git status. Those seven source
files were restored byte-for-byte to existing HEAD (no tracked source content
change); new ERRORS.md was normalized to LF. The runner now rejects non-LF
text source before freeze. Narrow .gitattributes entries preserve exact bytes
of GT-02 Sxx evidence and the archived plan. S28-03 is the fresh full remint
including the LF regression; the earlier verification is retained separately.

`verify_git_bytes.py index` reconstructed all 61 source files, nine artifacts,
the candidate manifest and the historical plan from staged Git blobs. Every
byte matched the working files and recorded hashes. The evidence verifier ran
in an isolated Python process against that temporary reconstruction and exited
0. This is stored-evidence verification, not another engine/suite execution.
Run with `HEAD` after committing to repeat against the concrete Git commit.

Git whitespace checks initially interpreted the captured CRLF log endings as
trailing whitespace. Scoped attributes now recognize CRLF only in preserved
evidence; the two historical critic Markdown reports also retain their authored
hard line breaks. Source whitespace checks remain enabled. No frozen artifact
was rewritten to make a formatting check pass. See the official
[Git attributes documentation](https://git-scm.com/docs/gitattributes#_checking_whitespace_errors)
and [cr-at-eol semantics](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corewhitespace).

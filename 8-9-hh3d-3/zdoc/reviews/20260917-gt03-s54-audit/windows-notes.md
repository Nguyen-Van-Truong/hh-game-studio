# S54 Windows observations and references

Checked 2026-09-17. These notes explain local handling; they are not runtime
acceptance or proof that one generic workaround fixes every Windows failure.

- Git staging of a nested frozen fixture failed with `Filename too long`.
  Retrying that same curated path list with `git -c core.longpaths=true add`
  succeeded; no global Git or OS setting changed. Git for Windows documents
  this opt-in for its native commands and warns that other applications may
  still have path limits. [Official Git for Windows guidance](https://gitforwindows.org/git-cannot-create-a-file-or-directory-with-a-long-path.html).
- A Blender crash-harness readiness sidecar rename failed with sharing
  violation under retained evidence ancestor handles. The harness now writes,
  flushes and closes the exact new sidecar before publishing a separate ready
  marker. This is a test handoff, not project atomic publication. Microsoft
  documents that access/sharing modes must be compatible and stay effective
  until handles close; delete sharing includes rename access.
  [CreateFileW documentation](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).
- The original recovery deadline failure overlapped native journal tests.
  A quiet recovery-only retry still expired. Measurements therefore do not
  justify attributing the failure entirely to disk contention. Inspection
  consolidation removes repeated native folds inside one observation; all
  phase guards, barriers and the 30-second cap remain. The new scene-CAS run
  reached a durable recovered terminal and completed its functional checks.

Protected live storage, AppData and temporary files remain on disk and are
excluded from checkpoint curation. Portable audits use explicit native exports;
copying an ACL-protected live directory would not recreate its authority.

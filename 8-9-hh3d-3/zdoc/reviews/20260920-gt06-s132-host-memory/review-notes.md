# Independent implementation reviews before dispatch

Three read-only Astra xhigh workers reviewed separate scopes. These are not
final critics and give no GT06 acceptance or TICK signature.

`s132_helper_review` found constructor cleanup-owner loss, cleanup exceptions
suppressing terminal receipts, and serialization conflated with release. The
coordinator recovered cleanup_owner, retained cleanup errors/unknown exits,
guarded missing parent process, added after-write-report-held observation and
counter availability checks. Three targeted failure/boundary tests and a native
memory API self-probe passed before request freeze; hashes are in preflight.json.

`s132_memory_review` confirmed failure arithmetic and both offline owned exits.
It corrected prose: S131 final RSS is below batches0–2, not0–3. Original RSS
precedes the current batch assembly but follows native wait/read/parse. The new
host-only boundary deliberately differs and cannot establish the old cause.

`s132_dependency_review` found cli_job.py in accepted GT03/S55, GT04/S60,
GT05/S64 and GT06 S79/S69 dependency maps. Historical acceptance remains valid
for those historical bytes. Existing signatures do not cover the current source.
The native replay runner still rejects changed GT05 dependency bytes. A reviewed
dependency update and appropriate refreshed functional evidence are required
before current-source final closure; no old manifest or admission guard is edited
by this diagnostic. Exact follow-up mapping is separate from live measurement.

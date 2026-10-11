# HH Studio package runbook

## Intake

1. Keep the trust public key and its out-of-band SHA-256 beside the artifact.
2. Verify the archive and its complete source closure before extraction. A
   missing dependency, template declaration, or addon version is an actionable
   input error: restore the exact pinned artifact/closure and retry.
3. Use the target named by the manifest. The installer never contacts a
   package index and never resolves `latest`.

## Install and recovery

Install and rollback operate only on the package-owned release root; project,
art, source and save files remain consumer-owned. Keep the install journal and
use the same command id when retrying an interrupted operation. A receipt is
usable only after the selector and installed files have been read back.

For a support request, collect a scrubbed support bundle from the install root
and include the artifact, manifest, target, command id, and closure digest. Do
not attach raw environment dumps, private keys, bearer tokens, or complete
process environments.

Android is deferred for this PC package. The compatibility lock in the package
is the source of truth for engine, template, addon, and target versions.

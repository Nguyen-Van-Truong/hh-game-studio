# Linux validator runtime image

The validator uses the same locked Godot binary and Python/coreutils base as
before. Godot now lives at `/tool` in a read-only image layer, avoiding repeated
execution of a 146 MB binary through a Windows bind mount. Project and harness
snapshots remain read-only binds. No sandbox, deadline or resource limit is relaxed.

Before building, verify the base image against `base_image_repo_digest` and the
single binary in `.local/tooling/godot-4.7.2-stable-linux` against
`binary_sha256` in `godot-addon/validator-toolchain.lock.json`. Use only that
single-file directory as the build context, never the repository.

From `8-9-hh3d-3`, build with:

```powershell
docker --context desktop-linux build --pull=false --network=none --iidfile <fresh-receipt-directory>/image-id.txt -f studio/build/validator/Dockerfile studio/.local/tooling/godot-4.7.2-stable-linux
```

Record actual exit, image ID, recipe hash and binary hash. A newly produced
image ID requires an explicit lock/source update and regression run; runtime
never falls back to a tag or pulls an image. Before changing the image pin,
reconcile any old executor owner record using its original pinned executor.

Every execution verifies the image ID and command/mount configuration, then
streams the in-image binary hash under the existing PID-1 timeout before
launching any candidate. The image root is read-only and the binary is owned by
root with mode `0555`. The verification emits no success banner, preserving
the authenticated evidence protocol.

# Prepared validator dependency

`gltf-validator.lock.json` pins the official Khronos npm artifact
`gltf-validator@2.0.0-dev.3.10` (Apache-2.0). Its archive SHA-512 was checked
against registry integrity, then SHA-256 and all nine extracted file hashes
were recorded. Extraction admitted only bounded regular files below `package/`;
no install script ran. The artifact cache is local and is not committed.

Reproduction downloads only the exact lock URL, verifies the lock's SHA-512 and
SHA-256, validates regular-file paths/count/expanded-size bounds, and compares
the complete extracted file map. Preserve `LICENSE` and `NOTICES`. Do not use
`npm install` without a pin or fetch `latest` during fixture runs.

Every fixture invocation must pin
the Node runtime, source/lock and bounded host job; verify all dependency bytes
before launch. Output should use a relative fixture identifier, capped issues,
and no arbitrary resource loader. The API's missing `externalResourceFunction`
means external resources are not validated; it does not prove their absence.
Our own URI/extension admission must reject them before the validator runs.

Use `format: 'glb'`, `writeTimestamp: false`, a finite `maxIssues`, and preserve
all severities. Reject errors, truncated/invalid reports and unexplained warnings.
Khronos success is one check alongside actual bounded PNG decode, skin/animation
semantics and pinned Godot import/readback. Do not copy the upstream example's
filesystem resource callback into the product pipeline.

References: [official project](https://github.com/KhronosGroup/glTF-Validator)
and the exact package README recorded by the lock.

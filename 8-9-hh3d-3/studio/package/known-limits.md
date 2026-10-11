# Known limits

This local package uses an externally pinned test key. Public key rotation,
revocation and expiry belong to the full release channel. Windows power-loss
durability is not claimed until the platform primitive is separately verified.

The install journal has a bounded command history. When it is full, retain the
store for audit and provision a new install root; do not delete the journal to
force an update. The package is PC-only (`Windows`, `Linux`, and
`Linux-headless`); Android remains `DEFERRED_NO_DEVICE`. Only the pinned
Godot/template and `hh_studio` addon versions in `compatibility-lock.json` are
supported. Consumer projects must use a matching addon version; mixed or
manually upgraded addon trees require explicit repair.

Support bundles are diagnostic and scrubbed. They omit private keys, bearer
tokens, environment values, and raw consumer source/save content. A bundle
cannot prove public release acceptance or native Android compatibility.
